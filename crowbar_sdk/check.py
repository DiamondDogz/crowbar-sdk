"""crowbar-check: tells whether a PS4RT runtime is Crowbar compatible, and what to change.

    crowbar-check RUNTIME            human-readable report
    crowbar-check RUNTIME --json     machine-readable report (for AI agents and CI)
    crowbar-check RUNTIME --handout  a step-by-step plan for THIS runtime, in Markdown
    crowbar-check RUNTIME --write-proposal   also writes crowbar.json.proposed

RUNTIME is a folder (your source tree or an unpacked release) or a release archive
(.zip, .tar.gz). Exit code: 0 when there is no error, 1 otherwise, 2 on bad usage.
Nothing is sent anywhere: the check is fully offline.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

from . import __version__, manifest
from .manifest import Report

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "target", "build", "dist-cache", "third_party", "vendor", "external"}
SOURCE_EXT = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".py", ".rs"}
BUILD_FILES = ("CMakeLists.txt", "Makefile", "makefile", "meson.build", "build.sh", "build-headless.sh", "build-windows.ps1", "build-windows.cmd")

# Files that belong to the game or the console: a runtime must never ship them.
GAME_FILES = {"eboot.bin": "the game's executable", "param.sfo": "game metadata", "npbind.dat": "game NP binding",
              "nptitle.dat": "game NP title", "trophy00.trp": "the game's trophy set", "pic0.png": None, "pic1.png": None,
              "icon0.png": None}
GAME_EXT = {".pkg": "a PS4 package", ".sprx": "a PS4 system or game module", ".prx": "a PS4 module", ".self": "a signed PS4 executable", ".rif": "a PS4 licence"}
GAME_DIRS = {"sce_sys": "the game's system folder", "sce_module": "the game's module folder"}
KEY_NAME = re.compile(r"(^|[._-])(keys?|rif|idps|psid|klicensee|passcode)([._-]|$)", re.I)

# Games the catalog already knows, so a proposal can name them.
KNOWN_GAMES = {"CUSA16429": "sakura-wars", "CUSA06810": "valkyria-revolution",
               "CUSA03219": "star-ocean-5", "CUSA03246": "star-ocean-5", "CUSA01722": "star-ocean-5", "CUSA03567": "star-ocean-5"}


def open_runtime(path: Path) -> tuple[Path, tempfile.TemporaryDirectory | None]:
    """A folder to check: `path` itself, or an archive unpacked to a temporary folder."""
    if path.is_dir():
        return path, None
    name = path.name.lower()
    tmp = tempfile.TemporaryDirectory(prefix="crowbar-check-")
    dest = Path(tmp.name)
    if name.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                target = (dest / info.filename).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise ValueError(f"archive entry escapes the folder: {info.filename}")
            z.extractall(dest)
    elif name.endswith((".tar.gz", ".tgz", ".tar.xz", ".tar")):
        with tarfile.open(path) as t:
            for m in t.getmembers():
                target = (dest / m.name).resolve()
                if not str(target).startswith(str(dest.resolve())) or m.issym() or m.islnk():
                    raise ValueError(f"unsafe archive entry: {m.name}")
            try:
                t.extractall(dest, filter="data")
            except TypeError:  # Python without extraction filters
                t.extractall(dest)
    else:
        tmp.cleanup()
        raise ValueError(f"{path} is neither a folder nor a .zip / .tar.gz archive")
    entries = [p for p in dest.iterdir()]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0], tmp
    return dest, tmp


def walk(root: Path):
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            children = sorted(d.iterdir())
        except OSError:
            continue
        for c in children:
            if c.is_dir():
                if c.name in SKIP_DIRS or c.is_symlink():
                    continue
                yield c
                stack.append(c)
            else:
                yield c


def rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


# ---------- what kind of runtime is this ----------

def detect_layout(root: Path) -> dict:
    """The legacy layouts Crowbar recognises without crowbar.json."""
    s = root / "scripts"
    if (s / "ps4rt_launch.py").is_file() or (s.is_dir() and any(p.name.endswith("_launch.py") for p in s.iterdir())):
        script = s / "ps4rt_launch.py"
        if not script.is_file():
            script = sorted(p for p in s.iterdir() if p.name.endswith("_launch.py"))[0]
        return {"kind": "ps4rt-launch", "script": rel(root, script)}
    if (root / "run.py").is_file():
        return {"kind": "ps4rt-run", "script": "run.py"}
    b = root / "bin"
    if b.is_dir():
        native = sorted(p for p in b.iterdir() if p.name.endswith("Launcher.exe"))
        if native:
            return {"kind": "native-play", "script": rel(root, native[0])}
    return {"kind": "unknown", "script": ""}


def title_ids(root: Path, layout: dict) -> list[str]:
    found: list[str] = []
    candidates = [root / layout["script"]] if layout.get("script") else []
    candidates += [root / "README.md", root / "README.linux.md"]
    for p in candidates:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for t in re.findall(r"\bCUSA\d{5}\b", text):
            if t not in found:
                found.append(t)
    return found


def propose(root: Path, layout: dict, sources: dict) -> dict:
    """A crowbar.json to start from, guessed from the layout. Always to be reviewed."""
    tids = title_ids(root, layout) or ["CUSA00000"]
    game = KNOWN_GAMES.get(tids[0], "TODO-game-id")
    script_text = ""
    if layout.get("script") and layout["kind"] != "native-play":
        script_text = (root / layout["script"]).read_text(encoding="utf-8", errors="replace")
    py_win = "python/python.exe"
    m: dict = {"crowbar": 1, "name": root.name, "game": game, "titleIds": tids[:4]}
    feats: dict = {}
    if layout["kind"] == "ps4rt-launch":
        base = [layout["script"], "--game", "{game}"]
        m["data"] = "out/{titleId}"
        if "--data-dir" in script_text:
            base += ["--data-dir", "{data}"]
        m["launch"] = {"linux": ["python3"] + base}
        if (root / py_win).exists() or (root / "python").is_dir():
            m["launch"]["windows"] = [py_win] + base
        if "--dlc-pkg" in script_text:
            feats["dlc"] = ["--dlc-pkg", "{file}"]
        if "--update-pkg" in script_text:
            feats["updatePkg"] = ["--update-pkg", "{file}"]
        if "--update-extracted" in script_text:
            feats["updateFolder"] = ["--update-extracted", "{dir}"]
        if "--no-dialogs" in script_text:
            feats["noDialogs"] = ["--no-dialogs"]
    elif layout["kind"] == "ps4rt-run":
        m["data"] = "."
        m["launch"] = {"linux": ["python3", "run.py"], "windows": [py_win, "run.py"]}
        m["settings"] = "ps4rt.ini"
        m["backup"] = ["user", "ps4rt.ini", "mods", "mods.json", "patches", "patches.json"]
    elif layout["kind"] == "native-play":
        m["data"] = "out"
        m["launch"] = {"windows": [layout["script"], "--play"]}
    else:
        exe = "bin/ps4rt"
        m["launch"] = {"linux": [exe, "--game", "{game}"], "windows": [exe + ".exe", "--game", "{game}"]}
    if sources.get("wired") or sources.get("handler"):
        feats["trophies"] = True
    if sources.get("card"):
        feats["trophyCard"] = True
    m["features"] = feats
    return m


# ---------- the trophy handler in the sources ----------

def _body(text: str, start: int) -> str:
    i = text.find("{", start)
    if i < 0:
        return ""
    depth = 0
    for j in range(i, min(len(text), i + 20000)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    return text[i:i + 2000]


def scan_sources(root: Path) -> dict:
    """Finds the sceNpTrophyUnlockTrophy handler and whether it records unlocks."""
    files = [p for p in walk(root) if p.is_file() and p.suffix in SOURCE_EXT and p.stat().st_size < 4_000_000]
    texts: dict[Path, str] = {}
    for p in files:
        try:
            texts[p] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    out = {"sources": bool(texts), "handler": "", "file": "", "line": 0, "param": "id", "wired": False,
           "card": any("PS4RT_TROPHY_CARD_DIR" in t for t in texts.values()), "build": []}
    noted = re.compile(r"crowbar_unlock|crowbar\.unlock|PS4RT_TROPHY_FILE")
    for p, t in texts.items():
        mo = re.search(r'"sceNpTrophyUnlockTrophy"\s*,\s*([A-Za-z_]\w*)', t)
        if not mo:
            continue
        name = mo.group(1)
        # its definition, in this file or another
        for q, u in [(p, t)] + [(k, v) for k, v in texts.items() if k != p]:
            d = re.search(r"\b" + re.escape(name) + r"\s*\(([^;{)]*)\)\s*\{", u)
            if not d:
                continue
            body = _body(u, d.start())
            params = [x.strip() for x in d.group(1).split(",") if x.strip()]
            names = [re.split(r"[\s*]+", x)[-1] for x in params]
            pick = next((n for n in names if re.fullmatch(r"(trophy_?)?id|trophyId|tid", n, re.I)), names[2] if len(names) > 2 else "id")
            wired = bool(noted.search(body))
            if not wired:
                for callee in set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", body)) - {name}:
                    for v in texts.values():
                        cd = re.search(r"\b" + re.escape(callee) + r"\s*\([^;{)]*\)\s*\{", v)
                        if cd and noted.search(_body(v, cd.start())):
                            wired = True
                            break
                    if wired:
                        break
            out.update(handler=name, file=rel(root, q), line=u.count("\n", 0, d.start()) + 1, param=pick, wired=wired)
            break
        if out["handler"]:
            break
    out["glob"] = None
    if out["file"]:
        handler = Path(out["file"])
        for p in walk(root):
            if not (p.is_file() and p.name in BUILD_FILES) or len(p.relative_to(root).parts) > 4:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if handler.name in text:
                out["build"].append(rel(root, p))
            # a wildcard that already compiles every matching file in the handler's folder
            for pat in re.findall(r"([\w./${}-]*\*[\w*.-]*\.c(?:pp)?)\b", text):
                folder, _, name_pat = pat.rpartition("/")
                if Path(folder).name == handler.parent.name and fnmatch.fnmatch(handler.name, name_pat) and out["glob"] is None:
                    out["glob"] = {"file": rel(root, p), "pattern": pat, "name": name_pat.replace("*", "_crowbar", 1).replace("*", "")}
    return out


# ---------- the checks ----------

GAME_MAGIC = {b"\x7fCNT", b"\x4f\x15\x3d\x1d", b"\x7fELF"}  # PKG, SELF, ELF (an unsigned module)


def _magic(p: Path) -> bytes:
    try:
        with open(p, "rb") as f:
            return f.read(4)
    except OSError:
        return b""


def check_forbidden(root: Path, report: Report) -> None:
    for p in walk(root):
        name = p.name.lower()
        r = rel(root, p)
        if p.is_dir():
            if name in GAME_DIRS:
                report.add("error", "release.game-folder", f"{r}/ looks like {GAME_DIRS[name]}.", "Remove it: Crowbar reads the game from the player's own dump.", r)
            continue
        if name in GAME_FILES and GAME_FILES[name] and "test" not in r.lower():
            report.add("error", "release.game-file", f"{r} is {GAME_FILES[name]}.", "Remove it from the runtime and from the release.", r)
        elif p.suffix.lower() in GAME_EXT and _magic(p) in GAME_MAGIC:
            report.add("error", "release.game-file", f"{r} is {GAME_EXT[p.suffix.lower()]}.", "Remove it: a runtime never ships game or console files.", r)
        elif KEY_NAME.search(p.stem) and p.suffix.lower() in {".txt", ".bin", ".dat", ".key", ".json", ".ini", ""}:
            report.add("warning", "release.keys", f"{r}: the name suggests keys or licences.", "Make sure it holds no console or game key; rename it if it is harmless.", r)


def check_trophy_files(root: Path, report: Report) -> None:
    for p in walk(root):
        if p.is_file() and p.name == "trophies.json" and p.parent.name == "user":
            r = rel(root, p)
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                report.add("error", "trophyfile.json", f"{r} is not valid JSON ({e}).", "Write it through a temporary file and a rename (the SDK does).", r)
                continue
            un = data.get("unlocked") if isinstance(data, dict) else None
            if not isinstance(un, dict):
                report.add("error", "trophyfile.shape", f'{r} has no "unlocked" object.', 'Expected {"unlocked": {"001": "2026-11-07T10:42:13Z"}}.', r)
                continue
            for k, v in un.items():
                if not re.fullmatch(r"\d{1,4}", str(k).strip()) or int(k) > 127:
                    report.add("error", "trophyfile.key", f'{r}: key "{k}" is not a trophy number 0..127.', "Use the id the game passed to sceNpTrophyUnlockTrophy.", r)
                elif len(str(k)) != 3:
                    report.add("warning", "trophyfile.padding", f'{r}: key "{k}" is accepted, but write it with 3 digits ("{int(k):03d}").', "", r)
                if not isinstance(v, str) or (v and not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|[+-]\d\d:\d\d)", v)):
                    report.add("warning", "trophyfile.date", f'{r}: trophy {k} has the date "{v}".', "Use ISO 8601 in UTC, e.g. 2026-11-07T10:42:13Z.", r)


def run(path: Path, write_proposal: bool = False) -> dict:
    root, tmp = open_runtime(path)
    try:
        report = Report()
        layout = detect_layout(root)
        sources = scan_sources(root)
        m, problem = manifest.load(root)
        proposal = None
        if m is None:
            proposal = propose(root, layout, sources)
            if problem == "missing":
                where = f" Crowbar still recognises this {layout['kind']} layout, but guesses its options." if layout["kind"] != "unknown" else ""
                report.add("error", "manifest.missing", "No crowbar.json at the root of the runtime." + where,
                           "Create crowbar.json; start from the proposal in this report and check every value.", "crowbar.json")
            else:
                report.add("error", "manifest.invalid", f"crowbar.json is {problem}.", "Fix the JSON syntax.", "crowbar.json")
            if write_proposal and tmp is None:
                (root / "crowbar.json.proposed").write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        else:
            manifest.validate(m, root, report)
        feats = (m or proposal or {}).get("features", {})
        if sources["handler"]:
            if sources["wired"]:
                report.add("info", "trophies.wired", f"{sources['handler']} records unlocks.", "", sources["file"], sources["line"])
                if m is not None and not feats.get("trophies"):
                    report.add("warning", "trophies.undeclared", "The runtime records trophies but crowbar.json does not say so.", 'Add "trophies": true under "features".', "crowbar.json")
            else:
                level = "error" if feats.get("trophies") else "warning"
                report.add(level, "trophies.not-wired", f"{sources['handler']} (the sceNpTrophyUnlockTrophy handler) does not record unlocks.",
                           f"Call crowbar_unlock({sources['param']}) at the start of {sources['handler']} (sdk/c/crowbar.h).", sources["file"], sources["line"])
        elif sources["sources"]:
            report.add("info", "trophies.no-handler", "No sceNpTrophyUnlockTrophy handler found in the sources.", "If the runtime handles trophies elsewhere, call crowbar_unlock(id) there.")
        elif feats.get("trophies"):
            report.add("info", "trophies.binary", "No sources here (a release?): trophy recording cannot be checked statically.", "Run crowbar-fake with a dump to see unlocks arrive.")
        check_forbidden(root, report)
        check_trophy_files(root, report)
        return {
            "ok": not report.errors,
            "checker": __version__,
            "root": str(path),
            "layout": layout,
            "manifest": m is not None,
            "manifestData": m,
            "trophies": {k: sources.get(k) for k in ("handler", "file", "line", "param", "wired", "build", "glob")},
            "errors": [f.as_dict() for f in report.errors],
            "warnings": [f.as_dict() for f in report.warnings],
            "info": [f.as_dict() for f in report.findings if f.level == "info"],
            "proposal": proposal,
        }
    finally:
        if tmp is not None:
            tmp.cleanup()


# ---------- outputs ----------

def human(r: dict) -> str:
    lines = [f"crowbar-check {r['checker']} · {r['root']}", f"Layout: {r['layout']['kind']}" + (f" ({r['layout']['script']})" if r['layout']['script'] else "")]
    t = r["trophies"]
    if t["handler"]:
        lines.append(f"Trophy handler: {t['handler']} in {t['file']}:{t['line']} · " + ("records unlocks" if t["wired"] else "does NOT record unlocks"))
    lines.append("")
    for kind, mark in (("errors", "✗"), ("warnings", "!"), ("info", "·")):
        for f in r[kind]:
            where = f" [{f['file']}{':' + str(f['line']) if f.get('line') else ''}]" if f.get("file") else ""
            lines.append(f"{mark} {f['message']}{where}")
            if f.get("fix"):
                lines.append(f"    → {f['fix']}")
    if r["proposal"]:
        lines += ["", "Proposed crowbar.json (review every value):", json.dumps(r["proposal"], indent=2, ensure_ascii=False)]
    lines += ["", "OK: Crowbar compatible." if r["ok"] else f"{len(r['errors'])} error(s), {len(r['warnings'])} warning(s)."]
    return "\n".join(lines)


def handout(r: dict) -> str:
    t = r["trophies"]
    steps: list[str] = []
    codes = {f["code"] for f in r["errors"] + r["warnings"]}
    if "manifest.missing" in codes or "manifest.invalid" in codes:
        steps.append("Create `crowbar.json` at the root of the runtime (the folder players unpack). Start from this proposal, "
                     "then check every value against SPEC.md, especially `game`, `titleIds` and the `launch` commands:\n\n```json\n"
                     + json.dumps(r["proposal"], indent=2, ensure_ascii=False) + "\n```")
    elif r["errors"]:
        fixes = "\n".join(f"   - `{f['code']}`: {f['message']} {f.get('fix', '')}".rstrip() for f in r["errors"] if not f["code"].startswith(("trophies.", "release.")))
        if fixes:
            steps.append("Fix `crowbar.json`:\n" + fixes)
    if "trophies.not-wired" in codes:
        folder = str(Path(t["file"]).parent.as_posix())
        g = t.get("glob")
        if g:
            steps.append(f"Copy `sdk/c/crowbar.h` from crowbar-sdk to `{folder}/crowbar.h`, and `sdk/c/crowbar.c` to "
                         f"`{folder}/{g['name']}`. `{g['file']}` already compiles `{g['pattern']}`, so no build change is needed.")
        else:
            build = f" Add `crowbar.c` next to `{Path(t['file']).name}` in {', '.join('`' + b + '`' for b in t['build'])}." if t["build"] else \
                f" Add `crowbar.c` to the build wherever `{Path(t['file']).name}` is compiled."
            steps.append(f"Copy `sdk/c/crowbar.h` and `sdk/c/crowbar.c` from crowbar-sdk into `{folder}/`.{build}")
        steps.append(f"In `{t['file']}`, add `#include \"crowbar.h\"` near the other includes, then make "
                     f"`crowbar_unlock({t['param']});` the first statement of `{t['handler']}` (line {t['line']}). "
                     "Change nothing else in that function: the game must get the same answer as before.")
        steps.append('In `crowbar.json`, set `"trophies": true` under `"features"`.')
    elif not t["handler"] and not t["wired"]:
        steps.append("Find where the runtime answers `sceNpTrophyUnlockTrophy` (usually a table of HLE exports) and call "
                     "`crowbar_unlock(id)` there with the trophy id the game passes. If the runtime has no such handler yet, stop and ask the developer.")
    if any(f["code"].startswith("release.") for f in r["errors"]):
        steps.append("Remove from the runtime and its release every file listed under `release.*` in `crowbar-check --json`. "
                     "Ask the developer before deleting anything that is not obviously a game file.")
    steps.append("Run `crowbar-check . --json` and repeat the fixes until `\"ok\": true` and `errors` is empty.")
    steps.append("If a game dump is available, run `crowbar-fake . --game <dump>`, unlock one trophy in game, and check it appears.")
    steps.append("Show the developer the full diff. Do not commit, push, tag or publish: the developer does that.")
    head = [f"# Crowbar handout for `{Path(r['root']).name}`", "",
            f"- Layout: **{r['layout']['kind']}**" + (f" (`{r['layout']['script']}`)" if r['layout']['script'] else ""),
            f"- crowbar.json: **{'present' if r['manifest'] else 'missing'}**"]
    if t["handler"]:
        head.append(f"- Trophy handler: `{t['handler']}` in `{t['file']}:{t['line']}` · " + ("already records unlocks" if t["wired"] else "**does not record unlocks yet**"))
    head.append(f"- Current status: {len(r['errors'])} error(s), {len(r['warnings'])} warning(s)")
    if r["ok"] and len(steps) <= 3:
        head += ["", "This runtime is already Crowbar compatible. Nothing to change."]
        return "\n".join(head) + "\n"
    body = ["", "## Steps", ""] + [f"{i}. {s}" for i, s in enumerate(steps, 1)]
    rules = ["", "## Do not", "",
             "- Touch the game, its files, keys, or the emulation logic. Crowbar only needs the unlock call and crowbar.json.",
             "- Add game files, keys, firmware or third-party binaries to the runtime or its release.",
             "- Invent trophy names or lists: Crowbar reads them from the player's dump.",
             "- Publish anything. The developer reviews the diff and releases.", ""]
    return "\n".join(head + body + rules)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="crowbar-check", description="Check that a PS4RT runtime is Crowbar compatible.")
    ap.add_argument("runtime", nargs="?", default=".", help="runtime folder or release archive (default: current folder)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--json", action="store_true", help="machine-readable report")
    g.add_argument("--handout", action="store_true", help="step-by-step plan for this runtime (Markdown)")
    ap.add_argument("--write-proposal", action="store_true", help="write crowbar.json.proposed when crowbar.json is missing")
    ap.add_argument("--version", action="version", version=f"crowbar-check {__version__}")
    a = ap.parse_args(argv)
    path = Path(a.runtime)
    if not path.exists():
        print(f"crowbar-check: {path} not found", file=sys.stderr)
        return 2
    try:
        r = run(path, a.write_proposal)
    except (ValueError, OSError, tarfile.TarError, zipfile.BadZipFile) as e:
        print(f"crowbar-check: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    elif a.handout:
        print(handout(r))
    else:
        print(human(r))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
