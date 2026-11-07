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

SDK_VERSION = "1.0.0"
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
