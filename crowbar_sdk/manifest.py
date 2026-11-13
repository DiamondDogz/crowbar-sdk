"""crowbar.json: reading, validation, and the launch command Crowbar builds from it.

Crowbar's own implementation follows exactly the same rules (SPEC.md).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

FORMAT = 1
PLATFORMS = ("windows", "linux")
PLACEHOLDERS = {"game", "data", "titleId", "runtime", "file", "dir"}
FEATURE_FLAGS = ("trophies", "trophyCard", "pause")
FEATURE_ARGS = {
    "dlc": "{file}",
    "updatePkg": "{file}",
    "updateFolder": "{dir}",
    "noDialogs": None,
}
KNOWN_KEYS = {"$schema", "crowbar", "name", "game", "titleIds", "requiredVersion", "launch", "data", "settings", "backup", "features", "options", "trophyFile", "trophyFormat", "language"}
TROPHY_FORMATS = ("sdk", "ps4rt-unlocks", "trg-progress")
BUTTON_STYLES = ("playstation", "xbox")


@dataclass
class Finding:
    level: str  # "error" | "warning" | "info"
    code: str
    message: str
    fix: str = ""
    file: str = ""
    line: int = 0

    def as_dict(self) -> dict:
        d = {"level": self.level, "code": self.code, "message": self.message}
        if self.fix:
            d["fix"] = self.fix
        if self.file:
            d["file"] = self.file
        if self.line:
            d["line"] = self.line
        return d


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, level, code, message, fix="", file="", line=0):
        self.findings.append(Finding(level, code, message, fix, file, line))

    @property
    def errors(self):
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self):
        return [f for f in self.findings if f.level == "warning"]


def load(root: Path) -> tuple[dict | None, str]:
    """(manifest, problem). problem is '' when the file parsed."""
    p = root / "crowbar.json"
    if not p.is_file():
        return None, "missing"
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except ValueError as e:
        return None, f"not valid JSON: {e}"
    if not isinstance(data, dict):
        return None, "must be a JSON object"
    return data, ""


def _placeholders(s: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", s))


def _str_list(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def validate(m: dict, root: Path, report: Report) -> None:
    """Adds findings for everything wrong in manifest `m` of runtime `root`."""
    F = "crowbar.json"
    fmt = m.get("crowbar")
    if fmt is None:
        report.add("error", "format.missing", '"crowbar" (the format version) is missing.', 'Add "crowbar": 1.', F)
    elif not isinstance(fmt, int) or fmt < 1:
        report.add("error", "format.invalid", '"crowbar" must be a whole number, 1 for this format.', 'Set "crowbar": 1.', F)
    elif fmt > FORMAT:
        report.add("warning", "format.newer", f"Format {fmt} is newer than this checker ({FORMAT}).", "Update crowbar-sdk.", F)

    for key in m:
        if key not in KNOWN_KEYS:
            report.add("warning", "key.unknown", f'Unknown key "{key}": Crowbar ignores it.', "Remove it, or check its spelling against SPEC.md.", F)

    for key in ("name", "game"):
        v = m.get(key)
        if not isinstance(v, str) or not v.strip():
            report.add("error", f"{key}.missing", f'"{key}" is missing or empty.', f'Add "{key}": "…" (see SPEC.md).', F)
    if isinstance(m.get("game"), str) and m["game"] and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", m["game"]):
        report.add("error", "game.invalid", f'"game" must be the catalog id, lower case with dashes (got "{m["game"]}").', 'For example "sakura-wars". Pick a new one if the game is not in the catalog yet.', F)

    tids = m.get("titleIds")
    if not _str_list(tids) or not tids:
        report.add("error", "titleIds.missing", '"titleIds" must list the CUSA ids this runtime runs.', 'Add "titleIds": ["CUSA12345"].', F)
    else:
        for t in tids:
            if not re.fullmatch(r"(CUSA|PLJS|PLJM|PCJS|PCAS|PLAS)\d{5}", t):
                report.add("error", "titleIds.invalid", f'"{t}" is not a PS4 title id.', "Use the CUSA id from the game's param.sfo, e.g. CUSA16429.", F)

    rv = m.get("requiredVersion")
    if rv is not None and not (isinstance(rv, str) and re.fullmatch(r"\d{2}\.\d{2}", rv)):
        report.add("error", "requiredVersion.invalid", '"requiredVersion" must look like "01.01".', "Use the APP_VER of the game version you support, or remove the key.", F)

    launch = m.get("launch")
    if not isinstance(launch, dict) or not launch:
        report.add("error", "launch.missing", '"launch" must give the command for at least one system.', 'Add "launch": {"linux": ["bin/ps4rt", "--game", "{game}"]}.', F)
    else:
        for plat, cmd in launch.items():
            if plat not in PLATFORMS:
                report.add("error", "launch.platform", f'"launch.{plat}": unknown system.', 'Use "windows" or "linux".', F)
                continue
            if not _str_list(cmd) or not cmd:
                report.add("error", "launch.invalid", f'"launch.{plat}" must be a non-empty list of strings.', 'Write one argument per string: ["python3", "scripts/run.py", "--game", "{game}"].', F)
                continue
            for arg in cmd:
                bad = _placeholders(arg) - {"game", "data", "titleId", "runtime"}
                if bad:
                    report.add("error", "launch.placeholder", f'"launch.{plat}" uses unknown placeholder(s) {sorted(bad)}.', "Allowed: {game} {data} {titleId} {runtime}.", F)
            prog = cmd[0]
            if "/" in prog or "\\" in prog:
                if not (root / prog).exists():
                    report.add("error", "launch.program", f'"launch.{plat}": program "{prog}" not found in the runtime.', "Paths are relative to the folder that holds crowbar.json.", F)
            elif plat == "windows" and prog.lower().startswith("python"):
                report.add("warning", "launch.python", '"launch.windows" relies on a Python installed on the player\'s PC.', 'Ship one in the release and point to it, e.g. "python/python.exe".', F)
            for arg in cmd[1:]:
                if re.search(r"\.(py|exe|sh)$", arg) and not _placeholders(arg) and ("/" in arg or "\\" in arg) and not (root / arg).exists():
                    report.add("error", "launch.script", f'"launch.{plat}": "{arg}" not found in the runtime.', "Fix the path, relative to crowbar.json.", F)
            if not any("{game}" in a for a in cmd):
                report.add("warning", "launch.game", f'"launch.{plat}" never passes {{game}}.', "Fine if the runtime reads PS4RT_GAME_DIR; otherwise add the argument it expects, e.g. \"--game\", \"{game}\".", F)
            if m.get("data") and not any("{data}" in a for a in cmd):
                report.add("info", "launch.data", f'"launch.{plat}" never passes {{data}}: the runtime should read PS4RT_DATA_DIR.', "", F)

    for key in ("data", "settings"):
        v = m.get(key)
        if v is not None:
            if not isinstance(v, str) or not v:
                report.add("error", f"{key}.invalid", f'"{key}" must be a path string.', "", F)
            elif os.path.isabs(v) or ".." in Path(v).parts:
                report.add("error", f"{key}.outside", f'"{key}" must stay inside the runtime folder.', "Use a relative path without '..'.", F)
            elif _placeholders(v) - {"data", "titleId"}:
                report.add("error", f"{key}.placeholder", f'"{key}" may only use {{data}} and {{titleId}}.', "", F)
    b = m.get("backup")
    if b is not None and not _str_list(b):
        report.add("error", "backup.invalid", '"backup" must be a list of paths.', "", F)

    check_options(m, report)
    tf, fmt = m.get("trophyFile"), m.get("trophyFormat")
    if tf is not None:
        if not isinstance(tf, str) or not tf:
            report.add("error", "trophyFile.invalid", '"trophyFile" must be a path string.', "", F)
        elif os.path.isabs(tf) or ".." in Path(tf).parts:
            report.add("error", "trophyFile.outside", '"trophyFile" must stay inside the runtime folder.', 'Use a relative path, for example "{data}/user/trophies.json".', F)
        elif _placeholders(tf) - {"data", "titleId"}:
            report.add("error", "trophyFile.placeholder", '"trophyFile" may only use {data} and {titleId}.', "", F)
        elif "*" in str(Path(tf).parent.parent):
            report.add("error", "trophyFile.glob", '"trophyFile": a * is allowed in the file name and its folder only.', 'For example "{data}/user/achievements/*/NPWR*.dat".', F)
    if fmt is not None and fmt not in TROPHY_FORMATS:
        report.add("error", "trophyFormat.invalid", f'"trophyFormat" must be one of {", ".join(TROPHY_FORMATS)}.', "", F)
    if fmt not in (None, "sdk") and tf is None:
        report.add("error", "trophyFormat.file", '"trophyFormat" other than "sdk" needs "trophyFile".', "Say where the runtime writes that file.", F)
    lang = m.get("language")
    if lang is not None:
        if not isinstance(lang, dict) or not isinstance(lang.get("env"), str) or not re.match(r"^[A-Z][A-Z0-9_]*$", lang.get("env", "")):
            report.add("error", "language.env", '"language.env" must be the name of the variable the runtime reads (upper case).', 'For example {"env": "DCP_LANGUAGE", "values": {"1": "english"}}.', F)
        elif not isinstance(lang.get("values", {}), dict) or not all(str(k).isdigit() and isinstance(v, str) for k, v in lang.get("values", {}).items()):
            report.add("error", "language.values", '"language.values" maps a PS4 language number ("1", "2"...) to the value the runtime expects.', "", F)

    feats = m.get("features", {})
    if not isinstance(feats, dict):
        report.add("error", "features.invalid", '"features" must be an object.', "", F)
        feats = {}
    for k, v in feats.items():
        if k in FEATURE_FLAGS:
            if not isinstance(v, bool):
                report.add("error", "features.flag", f'"features.{k}" must be true or false.', "", F)
        elif k in FEATURE_ARGS:
            need = FEATURE_ARGS[k]
            if not _str_list(v) or not v:
                report.add("error", "features.args", f'"features.{k}" must be the list of arguments to add.', f'For example ["--{k}", "{need or ""}"].', F)
            elif need and not any(need in a for a in v):
                report.add("error", "features.placeholder", f'"features.{k}" must contain {need}.', f"Crowbar puts the {'file' if need == '{file}' else 'folder'} path there.", F)
        else:
            report.add("warning", "features.unknown", f'Unknown feature "{k}": Crowbar ignores it.', "See SPEC.md for the list.", F)


def data_dir(m: dict, title_id: str) -> str:
    return (m.get("data") or "user").replace("{titleId}", title_id)


def command(m: dict, platform: str, root: Path, game: Path, title_id: str,
            dlc: list[Path] | None = None, update: Path | None = None) -> list[str]:
    """The command Crowbar runs (program first), with every placeholder filled."""
    data = root / data_dir(m, title_id)
    values = {"game": str(game), "data": str(data), "titleId": title_id, "runtime": str(root)}

    def fill(arg, extra=None):
        v = dict(values, **(extra or {}))
        return re.sub(r"\{(\w+)\}", lambda mo: v.get(mo.group(1), mo.group(0)), arg)

    cmd = [fill(a) for a in m["launch"][platform]]
    if "/" in cmd[0] or "\\" in cmd[0]:
        cmd[0] = str(root / cmd[0]) if not os.path.isabs(cmd[0]) else cmd[0]
    feats = m.get("features", {})
    for pkg in dlc or []:
        if "dlc" in feats:
            cmd += [fill(a, {"file": str(pkg)}) for a in feats["dlc"]]
    if update is not None:
        key = "updatePkg" if update.is_file() else "updateFolder"
        if key in feats:
            cmd += [fill(a, {"file": str(update), "dir": str(update)}) for a in feats[key]]
    if "noDialogs" in feats:
        cmd += list(feats["noDialogs"])
    return cmd


def environment(m: dict, root: Path, game: Path, title_id: str, crowbar_version: str,
                card_dir: Path | None = None, language: int | None = None, lang_code: str | None = None,
                button_style: str = "playstation") -> dict[str, str]:
    """The variables Crowbar adds to the environment (SPEC.md, Launch)."""
    data = root / data_dir(m, title_id)
    env = {
        "CROWBAR": crowbar_version,
        "PS4RT_GAME_DIR": str(game),
        "PS4RT_DATA_DIR": str(data),
        "PS4RT_TROPHY_FILE": str(data / "user" / "trophies.json"),
        "PS4RT_BUTTON_STYLE": button_style if button_style in BUTTON_STYLES else "playstation",
    }
    if m.get("settings"):
        env["PS4RT_CONFIG"] = str(root / m["settings"].replace("{data}", data_dir(m, title_id)).replace("{titleId}", title_id))
    if card_dir is not None and m.get("features", {}).get("trophyCard"):
        env["PS4RT_TROPHY_CARD_DIR"] = str(card_dir)
    if language is not None:
        env["PS4RT_LANGUAGE"] = str(language)
        lang = m.get("language")
        if isinstance(lang, dict) and lang.get("env"):
            value = (lang.get("values") or {}).get(str(language))
            if value is not None:
                env[lang["env"]] = value
    if lang_code:
        env["PS4RT_TROPHY_LANG"] = lang_code
    return env


OPTION_KEY = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _text(v) -> bool:
    """A label: a string, or an object of language code to string with at least "en"."""
    if isinstance(v, str):
        return bool(v.strip())
    return isinstance(v, dict) and bool(v) and all(isinstance(k, str) and isinstance(t, str) and t.strip() for k, t in v.items()) and "en" in v


def check_options(m: dict, report: Report) -> None:
    """`options`: the settings Crowbar shows for this runtime (keys and values of its .ini)."""
    F = "crowbar.json"
    opts = m.get("options")
    if opts is None:
        return
    if not isinstance(opts, list):
        report.add("error", "options.invalid", '"options" must be a list.', "See SPEC.md, settings screen.", F)
        return
    if not m.get("settings"):
        report.add("error", "options.settings", '"options" needs "settings": Crowbar writes the chosen values to that .ini.', 'Add "settings", e.g. "{data}/ps4rt.ini".', F)
    seen = set()
    for i, o in enumerate(opts):
        where = f'"options[{i}]"'
        if not isinstance(o, dict):
            report.add("error", "options.item", f"{where} must be an object.", "", F)
            continue
        key = o.get("key")
        if not isinstance(key, str) or not OPTION_KEY.match(key):
            report.add("error", "options.key", f"{where}: \"key\" must be the .ini key (letters, digits, _ . -).", "", F)
        elif key in seen:
            report.add("error", "options.duplicate", f'Option "{key}" is declared twice.', "", F)
        else:
            seen.add(key)
        if not _text(o.get("label")):
            report.add("error", "options.label", f'{where}: "label" must be a text, or {{"en": ..., "fr": ...}} with at least "en".', "", F)
        if "hint" in o and not _text(o["hint"]):
            report.add("error", "options.hint", f'{where}: "hint" must be a text, or {{"en": ...}}.', "", F)
        values = o.get("values")
        ok = isinstance(values, list) and len(values) >= 2 and all(isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and _text(v[1]) for v in values)
        if not ok:
            report.add("error", "options.values", f'{where}: "values" must list at least two ["value", "label"] pairs, values as strings.', 'For example [["1920x1080", "1080p"], ["3840x2160", "4K"]].', F)
            continue
        vals = [v[0] for v in values]
        if len(set(vals)) != len(vals):
            report.add("error", "options.values-duplicate", f"{where}: a value appears twice.", "", F)
        d = o.get("default")
        if not isinstance(d, str) or d not in vals:
            report.add("error", "options.default", f'{where}: "default" must be one of its values, as a string.', "Use the value the runtime uses when the key is missing.", F)

