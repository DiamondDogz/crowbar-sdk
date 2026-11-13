"""crowbar.py - make a PS4RT launch script "Crowbar compatible".

Part of crowbar-sdk, MIT licence: https://github.com/DiamondDogz/crowbar-sdk
Copy this file next to your launch script. Standard library only, never touches the network.

    import crowbar
    crowbar.unlock(14)          # the number the game passed to sceNpTrophyUnlockTrophy
    if crowbar.version():       # started by Crowbar?
        ...
"""
from __future__ import annotations

import datetime
import json
import os
import re
import threading

SDK_VERSION = "1.5.0"
MAX_TROPHIES = 128

_lock = threading.Lock()


def trophy_file() -> str:
    """$PS4RT_TROPHY_FILE, else $PS4RT_DATA_DIR/user/trophies.json, else user/trophies.json."""
    path = os.environ.get("PS4RT_TROPHY_FILE")
    if path:
        return path
    data = os.environ.get("PS4RT_DATA_DIR")
    if data:
        return os.path.join(data, "user", "trophies.json")
    return os.path.join("user", "trophies.json")


def version() -> str | None:
    """Crowbar's version when Crowbar started this runtime, else None."""
    return os.environ.get("CROWBAR") or None


def read(path: str | None = None) -> dict[int, str]:
    """Trophies already recorded: number -> ISO 8601 date."""
    path = path or trophy_file()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    out: dict[int, str] = {}
    for key, when in (data.get("unlocked") or {}).items():
        if re.fullmatch(r"\s*\d{1,4}\s*", str(key)):
            out[int(key)] = when if isinstance(when, str) else ""
    return out


def unlock(trophy_id: int, path: str | None = None) -> bool:
    """Records a trophy. Returns True when it was added, False when it was already there.
    Raises ValueError for an id outside 0..127."""
    if not 0 <= int(trophy_id) < MAX_TROPHIES:
        raise ValueError(f"trophy id {trophy_id} outside 0..{MAX_TROPHIES - 1}")
    path = path or trophy_file()
    with _lock:
        known = read(path)
        if trophy_id in known:
            return False
        known[int(trophy_id)] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = {"unlocked": {f"{k:03d}": known[k] for k in sorted(known)}}
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(body, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
        return True


# ---- Pause from the Guide ("pause": true, SPEC section 4) ----

_last = {"seq": 0, "kind": None}


def poll() -> str | None:
    """A new request from Crowbar: "pause", "resume", "unlock" (test profile: see request_trophy()),
    "quit" (save, answer(), exit with code 0 within 2 s), or None. Call about ten times a second."""
    d = os.environ.get("PS4RT_CONTROL_DIR")
    if not d:
        return None
    if not _last.get("ready"):
        # "0 ready": tells Crowbar this runtime answers pause requests.
        try:
            with open(os.path.join(d, "state.tmp"), "w", encoding="utf-8") as f:
                f.write("0 ready\n")
            os.replace(os.path.join(d, "state.tmp"), os.path.join(d, "state"))
            _last["ready"] = True
        except OSError:
            pass
    try:
        with open(os.path.join(d, "request"), encoding="utf-8") as f:
            parts = f.read().split()
        seq, word = int(parts[0]), parts[1]
        trophy = int(parts[2]) if word == "unlock" and len(parts) > 2 else -1
    except (OSError, ValueError, IndexError):
        return None
    if seq <= _last["seq"] or word not in ("pause", "resume", "unlock", "quit"):
        return None
    if word == "unlock" and not 0 <= trophy < 128:
        return None
    _last["seq"], _last["kind"], _last["trophy"] = seq, word, trophy
    return word


def request_trophy() -> int:
    """The trophy number of the last "unlock" request (SDK 1.3), or -1."""
    return _last.get("trophy", -1)


def answer(ok: bool = True) -> None:
    """Reply to the last request: for "pause", True once paused or False when it cannot pause now."""
    d = os.environ.get("PS4RT_CONTROL_DIR")
    if not d or not _last["kind"]:
        return
    word = {"pause": "paused" if ok else "refused", "unlock": "unlocked" if ok else "refused", "quit": "quitting"}.get(_last["kind"], "running")
    path = os.path.join(d, "state")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(f"{_last['seq']} {word}\n")
    os.replace(path + ".tmp", path)


def set_presence(status: str | None = None, online: bool = False) -> bool:
    """SDK 1.5: what the player is doing ("Chapter 3, Imperial Theater", at most 80 characters),
    shown to their friends and on Discord, and whether an online session is running (Crowbar then
    does not pause the game). Call it when either changes. False when not started by Crowbar."""
    d = os.environ.get("PS4RT_CONTROL_DIR")
    if not d:
        return False
    text = " ".join((status or "").split())[:80]
    path = os.path.join(d, "presence")
    try:
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            f.write(f"status={text}\nonline={1 if online else 0}\n")
        os.replace(path + ".tmp", path)
    except OSError:
        return False
    return True


def capture_dir() -> str | None:
    """SDK 1.5: the folder where Crowbar wants this game's screenshots and clips ($PS4RT_CAPTURE_DIR),
    or None. Write each file whole (a temporary name, then renamed): .png, .jpg, .webp, .mp4, .webm."""
    return os.environ.get("PS4RT_CAPTURE_DIR") or None
