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
    "noDialogs": ["--no-dialogs"]
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

Crowbar reads the file **every 2 seconds during the game** (live notification), and again when the game ends. It copies new unlocks into its own database, so they survive a reinstall or a new runtime version. It also notes whether mods or patches were active (`mods.json`, `patches.json`), for a future "no mods" mode; the runtime does nothing for that.

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

## 4. Features: DLC, updates, dialogs

- **`dlc`**: Crowbar reads the player's DLC `.pkg` files and passes only those not installed yet, the arguments repeated once per file. A DLC counts as installed when `{data}/player-content/dlc/<label>` exists, the label being the last 16 characters of its Content ID (`NEWSAKURADLC0001`).
- **`updatePkg`** / **`updateFolder`**: a game update, only when the player asks for it, since it changes the game folder.
- **`noDialogs`**: added on every launch. Crowbar shows errors itself; the runtime must not open blocking windows.
- **`trophies`**, **`trophyCard`**: `true` when the runtime records unlocks / reads the card folder.

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
