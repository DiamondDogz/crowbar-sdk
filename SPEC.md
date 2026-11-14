# Crowbar compatible · specification v1

A PS4RT runtime becomes **Crowbar compatible** by shipping one `crowbar.json` file and writing one trophy file. It needs no Crowbar code. Crowbar stays closed source; this format is public (MIT) and any launcher may implement it.

| The runtime does | Crowbar does in return |
| --- | --- |
| Runs the game from the folder it is given | Finds the dump, downloads and updates the runtime, checks its SHA-256 |
| Writes each unlocked trophy to a JSON file | Trophy list, in-game card, notifications, profile, level, backup of unlocks |
| Shows the trophy card Crowbar prepares (optional) | Prepares translated texts and icons for every trophy |
| Accepts DLC and an update as arguments (optional) | Reads the player's `.pkg` files, passes only what is missing |
| Keeps its settings in a known file (optional) | Graphics settings screen, backups of the data folder |

**Not in this format:** the trophy list. Crowbar reads it from the player's own dump (`sce_sys/trophy/trophy00.trp`, decrypted with the game's NP id from `sce_sys/npbind.dat`). A runtime never has to provide it, and never ships anything from the game.

Runtimes without `crowbar.json` keep working: Crowbar still recognises `scripts/ps4rt_launch.py`, `run.py` and `bin/<Game> Launcher.exe --play`, and guesses their options as it does today.

## 1. crowbar.json

At the root of the runtime, the folder players unpack from your release.

```json
{
  "crowbar": 1,
  "name": "Kagekidan",
  "game": "sakura-wars",
  "titleIds": ["CUSA16429"],
  "requiredVersion": "01.01",
  "launch": {
    "windows": ["python/python.exe", "scripts/ps4rt_launch.py", "--game", "{game}", "--data-dir", "{data}"],
    "linux":   ["python3", "scripts/ps4rt_launch.py", "--game", "{game}", "--data-dir", "{data}"]
  },
  "data": "out/{titleId}",
  "settings": "{data}/ps4rt.ini",
  "backup": ["out"],
  "features": {
    "trophies": true,
    "trophyCard": true,
    "dlc": ["--dlc-pkg", "{file}"],
    "updatePkg": ["--update-pkg", "{file}"],
    "updateFolder": ["--update-extracted", "{dir}"],
    "noDialogs": ["--no-dialogs"],
    "pause": true
  }
}
```

| Key | Required | Meaning |
| --- | --- | --- |
| `crowbar` | yes | Format version: `1` |
| `name` | yes | Runtime name shown in Crowbar |
| `game` | yes | The game's id in the [catalog](https://github.com/DiamondDogz/crowbar-catalog) (`sakura-wars`); lower case and dashes; pick a new one for a new game |
| `titleIds` | yes | The CUSA ids this runtime runs |
| `requiredVersion` | no | Game version expected (`APP_VER`, e.g. `01.01`) |
| `launch` | yes | Command per system (`windows`, `linux`): program first, one argument per string |
| `data` | no | Player data folder (saves, trophies, settings), relative to the root. Default `user` |
| `settings` | no | The `.ini` Crowbar manages from its graphics settings screen. Without it, Crowbar writes no settings file |
| `backup` | no | What Crowbar's backups take. Default: `data` up to its first placeholder (`out/{titleId}` → `out`) |
| `features` | no | What the runtime can do, with the arguments to add (§4) |
| `options` | no | The settings Crowbar's settings screen shows for this runtime: keys and values of the `settings` file (below) |
| `trophyFile` | no | Where the runtime writes its unlocks, when not `{data}/user/trophies.json` (§2). SDK 1.4 |
| `trophyFormat` | no | `sdk` (default), `ps4rt-unlocks` or `trg-progress` (§2). SDK 1.4 |
| `language` | no | The variable that sets the game language, and its value for each PS4 language number (§3). SDK 1.4 |
| `minCrowbar` | no | The oldest Crowbar version the runtime needs (`"0.3.0"`). An older Crowbar does not launch it and asks the player to update. SDK 1.5 |
| `mods` | no | `{"dir": "{data}/mods", "help": "…"}`: the folder the runtime reads mods from, and an optional short text on installing one. Crowbar shows it in the game's Add-ons, opens it for the player and never changes what is inside. SDK 1.5 |

**Paths** are relative to the folder that holds `crowbar.json`, use `/`, and never leave it (`..` and absolute paths are refused). A program with a `/` is a file in the runtime; a bare name (`python3`) is looked up in the PATH. Crowbar always starts the command **from the runtime root** (working directory).

**Placeholders** in `launch`: `{game}` (the dump folder), `{data}` (the data folder, absolute), `{titleId}`, `{runtime}` (the root, absolute). In `features`: `{file}` (a `.pkg`) and `{dir}` (an extracted update). In `data` and `settings`: `{titleId}`, and `{data}` in `settings`.

**Unknown keys** are ignored, so a newer runtime still runs on an older Crowbar.

### Settings screen (optional, `options`)

With `settings`, Crowbar has a settings screen for the game. `options` says what it shows, so it always matches **this version** of the runtime: when an update adds a resolution or a new setting, the player sees it as soon as the update is installed, without a new Crowbar.

```json
"settings": "{data}/ps4rt.ini",
"options": [
  {
    "key": "output_res",
    "label": { "en": "Output resolution", "fr": "Résolution de sortie" },
    "hint": { "en": "Size of the image sent to the screen" },
    "values": [["1920x1080", "1080p"], ["2560x1440", "1440p"], ["3840x2160", "4K"]],
    "default": "1920x1080"
  },
  {
    "key": "vsync",
    "label": "Vertical sync",
    "values": [["0", { "en": "Off", "fr": "Désactivée" }], ["1", { "en": "On", "fr": "Activée" }]],
    "default": "1"
  }
]
```

| Field | Meaning |
| --- | --- |
| `key` | The key in the `.ini` (`key=value` lines). Letters, digits, `_`, `.`, `-` |
| `label` | What the player reads. A text (English), or `{"en": ..., "fr": ..., "ja": ...}` with at least `en` |
| `hint` | Optional line under the label, same form |
| `values` | At least two `[value, label]` pairs, in the order shown. The value is written to the `.ini` as is |
| `default` | The value the runtime uses when the key is missing. Must be one of `values` |

Crowbar writes only the keys the player changed and keeps every other line of the file. Declare what a player should change, read from the code that parses the `.ini`; leave internal or debug keys out. Without `options`, Crowbar falls back to the list in the [catalog](https://github.com/DiamondDogz/crowbar-catalog) entry (`"options": {"windows": [...], "linux": [...]}`, same items, kept by the catalog maintainers for runtimes that do not declare theirs), then to its own built-in list.

## 2. Trophies

The only thing a runtime must write. Each time the game calls `sceNpTrophyUnlockTrophy`, add the trophy's number and the date:

```json
{
  "unlocked": {
    "001": "2026-11-07T10:42:13Z",
    "014": "2026-11-07T11:05:40Z"
  }
}
```

- **Where:** the path in `PS4RT_TROPHY_FILE`. Without it: `$PS4RT_DATA_DIR/user/trophies.json`, else `user/trophies.json`. For a `crowbar.json` runtime, Crowbar sets it to `{data}/user/trophies.json`.
- **Keys:** the number the game passed (0 = platinum, then 1, 2…), 0 to 127. Write three digits (`"001"`); `"1"` is accepted.
- **Dates:** ISO 8601, UTC. An empty date is accepted; the trophy then shows without one.
- **Never remove** a trophy, and keep its first date.
- **Write safely:** write a temporary file next to it, then rename it over the old one.
- **Platinum:** if the game does not unlock it, do not compute it. Crowbar does not either.

The SDK does all of this: `crowbar_unlock(id)` in C (`sdk/c/`), `crowbar.unlock(id)` in Python (`sdk/python/`).

**A runtime that already keeps its unlocks in another format** does not need a second file (SDK 1.4): it says where and how in `crowbar.json`, and Crowbar reads it as it is.

```json
"trophyFile": "{data}/user/achievements/*/NPWR*.dat",
"trophyFormat": "ps4rt-unlocks"
```

| `trophyFormat` | Content |
| --- | --- |
| `sdk` | The JSON above (default) |
| `ps4rt-unlocks` | A first line `PS4RT-UNLOCKS<tab>1`, then one line `<id><tab><unix seconds>` per trophy (the ports of HekamiAeon) |
| `trg-progress` | Lines `unlocked <id> <unix seconds>`; other lines are ignored (the TRG ports) |

A `*` may stand in the file name and in its folder (`achievements/*/NPWR*.dat`): Crowbar takes the first match, user `1` first, and looks again at each reading, since the file often appears with the first trophy.

Crowbar reads the file **every 2 seconds during the game** (live notification), and again when the game ends. It copies new unlocks into its own database, so they survive a reinstall or a new runtime version. It also notes whether mods or patches were active (`mods.json`, `patches.json`), for a future "no mods" mode; the runtime does nothing for that.

With Friends turned on, Crowbar tells the player's online friends about each new unlock (trophy name and grade, read from the player's own dump), and friends can compare trophies (numbers and dates only). The runtime does nothing for that, and nothing else is sent.

### In-game trophy card (optional, `"trophyCard": true`)

If the runtime draws its own card when a trophy pops, Crowbar prepares texts and icons in the player's language and passes the folder in `PS4RT_TROPHY_CARD_DIR`:

```text
index.tsv   one line per trophy: 3-digit number, grade, name, description (tab separated)
000.png     icon of trophy 0
001.png     …
```

```text
000	P	The grand finale	Earn every trophy
001	B	Opening night	Finish chapter 1
```

Grades are `P`, `G`, `S`, `B`; texts are on one line. This is the format the Kagekidan and Ravn launchers already read.

A runtime **without** its own card needs nothing: Crowbar shows its own trophy banner over the game (top right, borderless window), with the name and icon read from the dump. Players can set that banner to Automatic (only when the runtime has no card), Always or Never.

## 3. Environment

Crowbar adds these variables. Read the ones you need, ignore the rest.

| Variable | Value | Passed to |
| --- | --- | --- |
| `CROWBAR` | Crowbar's version (`0.2.5`): you were started by Crowbar | every runtime |
| `PS4RT_GAME_DIR` | The dump folder | `crowbar.json` and `run.py` runtimes |
| `PS4RT_DATA_DIR` | The `data` folder | `crowbar.json` and `run.py` runtimes |
| `PS4RT_TROPHY_FILE` | The trophy file (§2) | `crowbar.json`, `run.py` and native launchers |
| `PS4RT_CONFIG` | The settings file Crowbar wrote | when `settings` is set |
| `PS4RT_TROPHY_CARD_DIR` | Card texts and icons (§2) | when `trophyCard` is true |
| `PS4RT_LANGUAGE` | Game language, PS4 number (1 English, 2 French, 3 Spanish, 4 German…) | when the player picked one |
| `PS4RT_TROPHY_LANG` | Same, as a short code (`en`, `fr`…) | when the player picked one |
| `PS4RT_CONTROL_DIR` | The folder of pause, unlock and quit requests (§4) | every runtime |
| `PS4RT_BUTTON_STYLE` | `playstation` or `xbox`: the button prompts the player wants in games (SDK 1.4) | every runtime |
| *`language.env`* | The value from `language.values` for the chosen language (SDK 1.4), beside `PS4RT_LANGUAGE` | `crowbar.json` runtimes that declare `language` |
| `PS4RT_CAPTURE_DIR` | Where to save screenshots and clips (§4); Crowbar shows them in the game's Captures (SDK 1.5) | every runtime |
| `PS4RT_ACHIEVEMENTS_DIR` | A separate folder for the runtime's own trophy state, test profile only (§4) | every runtime, test profile only |

## 4. Features: DLC, updates, dialogs

- **`dlc`**: Crowbar reads the player's DLC `.pkg` files and passes only those not installed yet, the arguments repeated once per file. A DLC counts as installed when `{data}/player-content/dlc/<label>` exists, the label being the last 16 characters of its Content ID (`NEWSAKURADLC0001`).
- **`updatePkg`** / **`updateFolder`**: a game update, only when the player asks for it, since it changes the game folder.
- **`noDialogs`**: added on every launch. Crowbar shows errors itself; the runtime must not open blocking windows.
- **`trophies`**, **`trophyCard`**: `true` when the runtime records unlocks / reads the card folder.
- **`pause`**: `true` when the game can be paused from Crowbar's Guide menu (below).

### Pause from the Guide (optional, `"pause": true`)

When the player presses Guide during a game, Crowbar asks the runtime to pause. **The game decides:** if it can pause now, its loop and sound stop and the Guide menu opens over it; if it cannot (a cutscene, a loading screen, a network exchange…), it refuses and the Guide does not open, as on a console. A runtime without `pause` keeps running under the menu.

The exchange goes through two small text files in `PS4RT_CONTROL_DIR`, each written whole (a temporary file, then renamed):

| File | Written by | Content |
| --- | --- | --- |
| `request` | Crowbar | `<n> pause`, `<n> resume`, `<n> quit`, `<n> unlock <id>` or `<n> capture <id>` (below), `n` growing with each request |
| `state` | the runtime | `0 ready` as soon as it starts, then `<n> paused`, `<n> refused`, `<n> running`, `<n> quitting`, `<n> unlocked` or `<n> capturing`, `n` copied from the request it answers |

- `0 ready` is what tells Crowbar to ask: without a `state` file, Guide opens at once, game running. This works for every launch format (`crowbar.json`, `ps4rt_launch.py`, `run.py`, native launchers); `features.pause` only documents it.
- Check `request` about ten times a second from the game loop (it is a tiny file; only a new `n` matters).
- `pause`: answer within **300 ms**. `paused` once the game is stopped, `refused` when it cannot stop now. Without an answer in time, Crowbar opens the menu anyway, game running.
- `resume`: start again, then answer `running`. Crowbar does not wait for it.
- **The controller belongs to Crowbar while paused.** The game must ignore it (Crowbar's menu uses it), and after `resume` it keeps ignoring every button still held until it is released: the press that resumed the game is not the game's. Crowbar also waits for the buttons to be released before sending `resume`, but other programs can read the controller too, so the runtime filters it itself.
- When Crowbar or the game closes, the game is never left paused: Crowbar sends `resume` first.

The SDK does it in two calls (its first `crowbar_poll()` writes `0 ready`): `crowbar_poll()` returns `CROWBAR_PAUSE`, `CROWBAR_RESUME` or `CROWBAR_NONE`, and `crowbar_answer(1 or 0)` replies (C); `crowbar.poll()` and `crowbar.answer(True or False)` in Python.

### Quit from Crowbar (optional, SDK 1.4)

When the player quits the game from Crowbar's Guide, Crowbar first asks the runtime, in the same files: `<n> quit`. The runtime saves what must be saved (settings, trophy state; never the game's own save, which only the game writes), answers `<n> quitting`, and exits **with code 0 within 2 seconds**. After 2 seconds, or without an answer, Crowbar closes the process and its children itself; a game closed that way is never reported as a crash.

The SDK: `crowbar_poll()` returns `CROWBAR_QUIT`, then `crowbar_answer(1)` (C); `crowbar.poll()` returns `"quit"` (Python).

### Screenshot on a trophy (optional, SDK 1.6)

With the player's **Screenshot on every trophy** setting on, Crowbar asks the running game for a picture the moment a trophy unlocks: `<n> capture <id>`. The runtime answers `<n> capturing` at once, then saves its **next presented game frame**, without its own overlay or menus, as `trophy-<id>-<n>.png` in `PS4RT_CAPTURE_DIR` (written whole: a temporary name, then renamed). Crowbar waits 0.8 s for the answer; without it, it takes the screen itself on Windows (overlays included), and nothing on Linux. The picture then shows in Crowbar's Trophies, on that trophy, and in the game's Captures.

The SDK: `crowbar_poll()` returns `CROWBAR_CAPTURE`, `crowbar_request_trophy()` gives the id and `crowbar_capture_name()` the file name to write, then `crowbar_answer(1)` (C); `crowbar.poll()` returns `"capture"`, `crowbar.capture_path()` the full path (Python).

### Unlock on request: Crowbar's trophy test profile (optional, SDK 1.3)

To check the whole trophy chain without playing, a developer turns on Crowbar's **test profile** (developer mode): Crowbar then keeps a separate trophy list, and asks the running game to unlock a trophy through the same files:

- `request`: `<n> unlock <id>`, a trophy not yet earned in the test profile (never the platinum).
- The runtime unlocks it **through its own path**, as if the game had called `sceNpTrophyUnlockTrophy` (its trophy file, its own state and its own card if it has one), then answers `<n> unlocked`, or `<n> refused` when it cannot now (before the game registered its trophies, for example). Crowbar waits 1.5 s, then falls back to a test of its own side only.
- In the test profile, Crowbar points `PS4RT_TROPHY_FILE` to a separate file, and `PS4RT_ACHIEVEMENTS_DIR` to a separate folder: a runtime that keeps more trophy state of its own (what the game reads back) keeps it there, so the player's real trophies are never touched. Resetting the test profile deletes both.

The SDK: `crowbar_poll()` returns `CROWBAR_UNLOCK`, `crowbar_request_trophy()` gives the number, `crowbar_answer(1 or 0)` replies (C); `crowbar.poll()` returns `"unlock"` and `crowbar.request_trophy()` the number (Python).

### Presence and online play (optional, SDK 1.5)

The runtime can tell Crowbar what the player is doing, in a third file of `PS4RT_CONTROL_DIR`, written whole (a temporary file, then renamed) whenever it changes:

```
status=Chapter 3, Imperial Theater
online=0
```

- `status`: at most 80 characters, UTF-8, one line. Crowbar shows it to the player's friends ("Sakura Wars · Chapter 3, Imperial Theater") and as the second line of the Discord activity. Empty for nothing. Write it when the scene changes, not every frame; Crowbar reads it every few seconds.
- `online=1` while an online session runs (Dragon's Crown Pro's online play, for example): Crowbar then **never pauses the game**, neither by asking it (no `pause` request) nor by suspending the process; the Guide opens with the game running. Write `online=0` when the session ends.

The SDK: `crowbar_set_presence(status, online)` (C), `crowbar.set_presence(status, online)` (Python).

### Captures (optional, SDK 1.5)

`PS4RT_CAPTURE_DIR` is a folder per game that Crowbar keeps. A runtime that takes screenshots or clips (a capture key, a photo mode) saves them there, each file written whole under a temporary name and then renamed, as `.png`, `.jpg`, `.webp`, `.mp4` or `.webm`. A **Captures** button then appears on the game in Crowbar, with the captures newest first. Without the variable (started outside Crowbar), keep your usual folder.

The SDK: `crowbar_capture_dir()` (C), `crowbar.capture_dir()` (Python); both return nothing outside Crowbar.

When the game ends, its exit code and output go to Crowbar's launch log. A non-zero code within 30 seconds opens that log with a **Copy report** button.

## 5. The catalog entry

For Crowbar to offer your runtime for download, add an entry to `catalog.json` in [crowbar-catalog](https://github.com/DiamondDogz/crowbar-catalog), under the game. Releases are read every hour from your GitHub releases, with their SHA-256.

```json
{
  "platform": "linux",
  "repo": "HekamiAeon/valkyria-revolution-ps4rt",
  "asset": "valkyria-revolution-linux-x86_64-*.tar.gz",
  "checksum": "{asset}.sha256",
  "maintainer": "HekamiAeon",
  "launch": "crowbar-json",
  "trophies": true
}
```

| Key | Meaning |
| --- | --- |
| `platform` | `windows` or `linux` |
| `repo` | GitHub repository whose releases hold the runtime |
| `asset` | File to download; `*` for the part that changes |
| `tagPrefix` | Optional: only tags starting with this (`windows-`) |
| `checksum` | Optional: a `.sha256` file published next to it; otherwise GitHub's own digest |
| `maintainer` | Author shown in Crowbar |
| `launch` | `crowbar-json` for a runtime with `crowbar.json` (older: `ps4rt-launch`, `ps4rt-run`, `native-play`) |
| `trophies` | `true` if the runtime records unlocks |

Entries hold **metadata only**: icons and artwork are always read from each player's dump.

**To submit:** open the "Add a runtime" form in crowbar-catalog's issues. A GitHub Action downloads your latest release, checks its SHA-256, runs `crowbar-check` on it, and opens the pull request. A maintainer reviews and merges.

## 6. Versions

`crowbar` only changes if an existing runtime could break; adding an optional key does not change it. Crowbar ignores unknown keys; a runtime ignores variables it does not read. A `crowbar.json` newer than Crowbar is refused with a message asking the player to update Crowbar.

## Rules

A Crowbar compatible runtime and its release never contain game files (eboot, modules, `sce_sys`, `.pkg`), console or game keys, firmware, or third-party binaries you may not redistribute. `crowbar-check` and the catalog's Action look for them.
