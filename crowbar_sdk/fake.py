"""crowbar-fake: starts a runtime exactly as Crowbar would, and shows the trophies it records.

    crowbar-fake RUNTIME --game DUMP          launch the game, print unlocks as they happen
    crowbar-fake RUNTIME --game DUMP --print  only print the command and the environment
    crowbar-fake RUNTIME --simulate 14        write trophy 14 where Crowbar reads it (no game needed)

No Crowbar install needed. Trophy names and icons are not shown: Crowbar reads them from
the player's dump, which this tool does not decrypt. Numbers are enough to test a runtime.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import __version__, check, manifest

PS4_LANG_CODES = {0: "ja", 1: "en", 2: "fr", 3: "es", 4: "de", 5: "it", 6: "nl", 7: "pt", 8: "ru", 9: "ko", 10: "zh-Hant", 11: "zh-Hans"}


def platform() -> str:
    return "windows" if os.name == "nt" else "linux"


def load_or_propose(root: Path) -> tuple[dict, bool]:
    m, problem = manifest.load(root)
    if m is not None:
        return m, False
    layout = check.detect_layout(root)
    return check.propose(root, layout, check.scan_sources(root)), True


def read_unlocks(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        un = data.get("unlocked", {})
        return {f"{int(k):03d}": str(v) for k, v in un.items() if str(k).strip().isdigit()}
    except (OSError, ValueError, AttributeError):
        return {}


def placeholder_card(dest: Path, count: int = 128) -> Path:
    """A trophy card folder in the right format, with placeholder texts and no icons."""
    dest.mkdir(parents=True, exist_ok=True)
    lines = [f"{i:03d}\t{'P' if i == 0 else 'B'}\tTrophy {i:03d}\tPlaceholder from crowbar-fake" for i in range(count)]
    (dest / "index.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="crowbar-fake", description="Run a PS4RT runtime the way Crowbar does.")
    ap.add_argument("runtime", nargs="?", default=".")
    ap.add_argument("--game", help="the extracted game dump (the folder that holds eboot.bin)")
    ap.add_argument("--title", help="CUSA id (default: the first of titleIds)")
    ap.add_argument("--lang", type=int, default=1, help="PS4 language number (default 1, English)")
    ap.add_argument("--print", dest="dry", action="store_true", help="print the command and environment, do not run")
    ap.add_argument("--simulate", type=int, metavar="ID", help="write this trophy where Crowbar reads it, then check the file")
    ap.add_argument("--version", action="version", version=f"crowbar-fake {__version__}")
    a = ap.parse_args(argv)

    root = Path(a.runtime).resolve()
    m, guessed = load_or_propose(root)
    if guessed:
        print("! No crowbar.json: using the layout crowbar-check proposes. Run crowbar-check for details.", file=sys.stderr)
    title = a.title or (m.get("titleIds") or ["CUSA00000"])[0]
    game = Path(a.game).resolve() if a.game else Path("<game dump>")
    card = placeholder_card(root / manifest.data_dir(m, title) / "user" / "crowbar-fake-card") if m.get("features", {}).get("trophyCard") and not a.dry else None
    env_add = manifest.environment(m, root, game, title, f"fake-{__version__}", card, a.lang, PS4_LANG_CODES.get(a.lang))
    trophy_file = Path(env_add["PS4RT_TROPHY_FILE"])

    if a.simulate is not None:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sdk" / "python"))
        try:
            import crowbar  # the drop-in helper shipped with the SDK
        except ImportError:
            from . import _crowbar as crowbar  # installed package
        added = crowbar.unlock(a.simulate, str(trophy_file))
        r = check.Report()
        check.check_trophy_files(trophy_file.parent.parent if trophy_file.parent.name == "user" else root, r)
        bad = [f for f in r.findings if f.level == "error"]
        state = "written" if added else "already there"
        print(f"{'✓' if not bad else '✗'} trophy {a.simulate:03d} {state} in {trophy_file}")
        for f in bad:
            print(f"  ✗ {f.message}")
        return 1 if bad else 0

    plat = platform()
    if plat not in m.get("launch", {}):
        print(f"✗ crowbar.json has no launch command for {plat}.", file=sys.stderr)
        return 1
    cmd = manifest.command(m, plat, root, game, title)
    if a.dry:
        print("Command:\n  " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        print("Environment added by Crowbar:")
        for k, v in env_add.items():
            print(f"  {k}={v}")
        print(f"Working folder: {root}")
        return 0
    if not a.game:
        print("✗ --game is required to run (or use --print / --simulate).", file=sys.stderr)
        return 2

    before = read_unlocks(trophy_file)
    print(f"crowbar-fake {__version__} · {m.get('name', root.name)} · {title} · {len(before)} trophies already recorded")
    print(f"Watching {trophy_file}\n")
    stop = threading.Event()
    seen = dict(before)
    new: list[str] = []

    def watch():
        while not stop.is_set():
            now = read_unlocks(trophy_file)
            for k in sorted(set(now) - set(seen)):
                seen[k] = now[k]
                new.append(k)
                print(f"\n★ trophy {k} recorded · {now[k] or 'no date'}\n", flush=True)
            stop.wait(0.5)

    t = threading.Thread(target=watch, daemon=True)
    t.start()
    started = time.time()
    try:
        proc = subprocess.Popen(cmd, cwd=root, env={**os.environ, **env_add})
        code = proc.wait()
    except FileNotFoundError as e:
        print(f"✗ could not start {cmd[0]}: {e}", file=sys.stderr)
        code = 127
    except KeyboardInterrupt:
        proc.terminate()
        code = 130
    time.sleep(0.7)
    stop.set()
    t.join()
    minutes = (time.time() - started) / 60
    print(f"\nGame ended · code {code} · {minutes:.1f} min · {len(new)} new trophy(ies): {', '.join(new) or 'none'}")
    r = check.Report()
    check.check_trophy_files(trophy_file.parent.parent, r)
    for f in r.findings:
        print(f"{'✗' if f.level == 'error' else '!'} {f.message}")
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
