"""crowbar-check --runtime-test: starts the runtime the way Crowbar does and checks its answers.

    crowbar-check RUNTIME --runtime-test --game DUMP [--trophy 1] [--ready-timeout 90] [--json]

Steps, in this order, each with the limit from SPEC.md section 4:

1. start      the runtime writes `0 ready` in PS4RT_CONTROL_DIR (no blocking dialog)
2. pause      `<n> paused` or `<n> refused` within 300 ms
3. resume     `<n> running`, and the process keeps running
4. unlock     `<n> unlocked` within 1.5 s, and the trophy is in the trophy file (test profile)
5. capture    `<n> capturing` within 0.8 s, then `trophy-<id>-<n>.png` (optional, SDK 1.6)
6. quit       `<n> quitting`, then exit code 0 within 2 s

Everything the runtime writes goes to temporary folders, as in Crowbar's test profile: the
player's real trophies and captures are never touched. The game's own save is the game's: this
test does not open a save, but the runtime runs normally, so use a dump you can play.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import __version__, manifest

PAUSE_MS, UNLOCK_MS, CAPTURE_MS, QUIT_MS = 300, 1500, 800, 2000


@dataclass
class Step:
    name: str
    status: str  # "ok", "warning", "error", "skipped"
    message: str
    ms: int | None = None


@dataclass
class Result:
    runtime: str
    title: str
    steps: list[Step] = field(default_factory=list)
    exit_code: int | None = None

    @property
    def ok(self) -> bool:
        return not any(s.status == "error" for s in self.steps)

    def add(self, name, status, message, ms=None):
        self.steps.append(Step(name, status, message, None if ms is None else int(ms)))

    def as_dict(self) -> dict:
        return {"tool": f"crowbar-check {__version__}", "runtime": self.runtime, "title": self.title, "ok": self.ok,
                "exitCode": self.exit_code, "steps": [asdict(s) for s in self.steps]}


class Exchange:
    """Crowbar's side of the request / state files."""

    def __init__(self, folder: Path):
        self.dir = folder
        self.n = 0

    def state(self) -> tuple[int, str] | None:
        try:
            parts = (self.dir / "state").read_text(encoding="utf-8").split()
            return int(parts[0]), parts[1]
        except (OSError, ValueError, IndexError):
            return None

    def ask(self, words: str, limit_ms: int, proc: subprocess.Popen | None = None) -> tuple[str | None, float]:
        """Writes `<n> words` whole and waits for `<n> <answer>`. Returns (answer or None, elapsed ms)."""
        self.n += 1
        tmp = self.dir / "request.tmp"
        tmp.write_text(f"{self.n} {words}\n", encoding="utf-8")
        start = time.perf_counter()
        os.replace(tmp, self.dir / "request")
        while True:
            elapsed = (time.perf_counter() - start) * 1000
            st = self.state()
            if st and st[0] == self.n:
                return st[1], elapsed
            if elapsed > limit_ms or (proc is not None and proc.poll() is not None):
                return None, elapsed
            time.sleep(0.002)


def _sdk_unlocks(path: Path) -> set[int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {int(k) for k in data.get("unlocked", {}) if str(k).strip().isdigit()}
    except (OSError, ValueError, AttributeError):
        return set()


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def run(root: Path, game: Path, title: str | None = None, trophy: int = 1, ready_timeout: float = 90.0,
        platform: str | None = None, keep: bool = False, echo=None) -> Result:
    m, problem = manifest.load(root)
    if m is None:
        r = Result(str(root), title or "")
        r.add("start", "error", f"No usable crowbar.json: {problem}. Run crowbar-check first.")
        return r
    plat = platform or ("windows" if os.name == "nt" else "linux")
    title = title or (m.get("titleIds") or ["CUSA00000"])[0]
    r = Result(str(root), title)
    if plat not in m.get("launch", {}):
        r.add("start", "error", f"crowbar.json has no launch command for {plat}.")
        return r
    say = echo or (lambda s: None)

    work = Path(tempfile.mkdtemp(prefix="crowbar-runtime-test-"))
    control, captures, achievements = work / "control", work / "captures", work / "achievements"
    for d in (control, captures, achievements):
        d.mkdir()
    trophy_file = work / "trophies.json"
    env_add = manifest.environment(m, root, game, title, f"runtime-test-{__version__}", control_dir=control, capture_dir=captures)
    env_add["PS4RT_TROPHY_FILE"] = str(trophy_file)
    env_add["PS4RT_ACHIEVEMENTS_DIR"] = str(achievements)
    cmd = manifest.command(m, plat, root, game, title)
    log = open(work / "runtime.log", "wb")
    ex = Exchange(control)
    say(f"Starting {Path(cmd[0]).name} ({title}), waiting up to {ready_timeout:.0f} s for `0 ready`…")
    try:
        proc = subprocess.Popen(cmd, cwd=root, env={**os.environ, **env_add}, stdout=log, stderr=subprocess.STDOUT)
    except OSError as e:
        r.add("start", "error", f"Could not start {cmd[0]}: {e}")
        log.close()
        return r
    try:
        # 1. start
        t0 = time.perf_counter()
        while True:
            st = ex.state()
            if st and st[0] == 0 and st[1] == "ready":
                r.add("start", "ok", "The runtime wrote `0 ready`.", (time.perf_counter() - t0) * 1000)
                break
            if proc.poll() is not None:
                r.add("start", "error", f"The runtime exited (code {proc.returncode}) before writing `0 ready`. Output: {work / 'runtime.log'}")
                return r
            if time.perf_counter() - t0 > ready_timeout:
                r.add("start", "error", f"No `0 ready` in {ready_timeout:.0f} s: the runtime does not poll PS4RT_CONTROL_DIR "
                      "(crowbar_poll() / crowbar.poll()), or a dialog is waiting (add features.noDialogs).")
                return r
            time.sleep(0.05)
        time.sleep(1.0)  # let the game loop run a little

        # 2. pause (a refusal is allowed: the game decides; retry a few times so a loading screen passes)
        word, ms = None, 0.0
        for attempt in range(4):
            word, ms = ex.ask("pause", PAUSE_MS * 4, proc)
            if word != "refused":
                break
            time.sleep(2.0)
        if word is None:
            r.add("pause", "error", f"No answer to `pause` (limit {PAUSE_MS} ms).", ms)
        elif word not in ("paused", "refused"):
            r.add("pause", "error", f"Answered `{word}` to `pause`; expected `paused` or `refused`.", ms)
        elif ms > PAUSE_MS:
            r.add("pause", "error", f"Answered `{word}` in {ms:.0f} ms; the limit is {PAUSE_MS} ms (poll about ten times a second).", ms)
        elif word == "refused":
            r.add("pause", "warning", "Refused every `pause` (4 tries, 2 s apart). Allowed, but check the game can pause in normal play.", ms)
        else:
            r.add("pause", "ok", f"Paused in {ms:.0f} ms.", ms)

        # 3. resume
        word, ms = ex.ask("resume", 2000, proc)
        time.sleep(0.5)
        if proc.poll() is not None:
            r.add("resume", "error", f"The runtime exited (code {proc.returncode}) after `resume`.")
            return r
        if word == "running":
            r.add("resume", "ok", f"Running again in {ms:.0f} ms.", ms)
        else:
            r.add("resume", "warning", "No `running` answer to `resume` within 2 s (Crowbar does not wait for it, but the SDK writes it).", ms)

        # 4. unlock (test profile)
        word, ms = ex.ask(f"unlock {trophy}", UNLOCK_MS, proc)
        if word == "unlocked":
            if m.get("trophyFile"):
                r.add("unlock", "ok", f"Trophy {trophy:03d} unlocked in {ms:.0f} ms (trophyFile {m['trophyFile']}: not read by this test).", ms)
            elif trophy in _sdk_unlocks(trophy_file):
                r.add("unlock", "ok", f"Trophy {trophy:03d} unlocked in {ms:.0f} ms and written to PS4RT_TROPHY_FILE.", ms)
            else:
                r.add("unlock", "error", f"Answered `unlocked`, but trophy {trophy:03d} is not in PS4RT_TROPHY_FILE ({trophy_file}).", ms)
        elif word == "refused":
            r.add("unlock", "warning", "Refused `unlock` (allowed before the game registers its trophies: retry later in the game).", ms)
        elif word is None:
            r.add("unlock", "warning", f"No answer to `unlock` within {UNLOCK_MS} ms: the test profile is not supported (optional, SDK 1.3).", ms)
        else:
            r.add("unlock", "error", f"Answered `{word}` to `unlock`; expected `unlocked` or `refused`.", ms)

        # 5. capture (optional)
        word, ms = ex.ask(f"capture {trophy}", CAPTURE_MS, proc)
        if word == "capturing":
            shot = captures / f"trophy-{trophy}-{ex.n}.png"
            deadline = time.perf_counter() + 5
            while not shot.exists() and time.perf_counter() < deadline and proc.poll() is None:
                time.sleep(0.05)
            if shot.exists() and shot.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n":
                r.add("capture", "ok", f"Screenshot {shot.name} saved.", ms)
            elif shot.exists():
                r.add("capture", "error", f"{shot.name} is not a PNG file.", ms)
            else:
                r.add("capture", "error", f"Answered `capturing` but {shot.name} did not appear in PS4RT_CAPTURE_DIR within 5 s.", ms)
        elif word is None:
            r.add("capture", "skipped", "No answer to `capture`: screenshot on a trophy is not supported (optional, SDK 1.6).", ms)
        elif word == "refused":
            r.add("capture", "warning", "Refused `capture`.", ms)
        else:
            r.add("capture", "error", f"Answered `{word}` to `capture`; expected `capturing`.", ms)

        # 6. quit
        start = time.perf_counter()
        word, ms = ex.ask("quit", QUIT_MS, proc)
        try:
            code = proc.wait(max(0.0, QUIT_MS / 1000 - (time.perf_counter() - start)))
        except subprocess.TimeoutExpired:
            code = None
        total = (time.perf_counter() - start) * 1000
        if code is None:
            r.add("quit", "error" if word else "warning",
                  ("Answered `quitting` but" if word else "No `quitting` answer, and the runtime") + f" was still running after {QUIT_MS} ms; Crowbar would close it.", total)
        elif code != 0:
            r.add("quit", "error", f"Exited with code {code}; expected 0 (Crowbar reports a non-zero code as a crash).", total)
        elif word != "quitting":
            r.add("quit", "warning", f"Exited with code 0 in {total:.0f} ms, without answering `quitting`.", total)
        else:
            r.add("quit", "ok", f"Answered `quitting` and exited with code 0 in {total:.0f} ms.", total)
        r.exit_code = code
        return r
    finally:
        _stop(proc)
        if r.exit_code is None and proc.returncode is not None:
            r.exit_code = proc.returncode
        log.close()
        if not keep and r.ok:
            shutil.rmtree(work, ignore_errors=True)
        elif not r.ok:
            r.add("log", "skipped", f"Runtime output and files kept in {work}")


ICON = {"ok": "✓", "warning": "!", "error": "✗", "skipped": "·"}


def human(r: Result) -> str:
    lines = [f"crowbar-check {__version__} · runtime test · {Path(r.runtime).name} · {r.title}", ""]
    for s in r.steps:
        lines.append(f"{ICON[s.status]} {s.name:<8} {s.message}")
    lines += ["", "Runtime test passed." if r.ok else "Runtime test failed: fix the ✗ lines (SPEC.md, section 4)."]
    return "\n".join(lines)


def main(a) -> int:
    root = Path(a.runtime).resolve()
    if not root.is_dir():
        print(f"crowbar-check: --runtime-test needs the runtime folder, not {a.runtime}")
        return 2
    if not a.game:
        print("crowbar-check: --runtime-test needs --game <the extracted dump that holds eboot.bin>.")
        return 2
    echo = None if a.json else (lambda s: print(s, flush=True))
    r = run(root, Path(a.game).resolve(), a.title, a.trophy, a.ready_timeout, keep=a.keep, echo=echo)
    print(json.dumps(r.as_dict(), indent=2, ensure_ascii=False) if a.json else human(r))
    return 0 if r.ok else 1
