# AGENTS.md · making a PS4RT runtime Crowbar compatible

You are an AI assistant helping a developer make their PS4RT runtime work with [Crowbar](https://github.com/DiamondDogz/crowbar), a launcher that adds trophies, a profile, downloads and updates. This file is your procedure. Follow it in order. The format itself is in [SPEC.md](SPEC.md); read it when a step points to it.

The change is small on purpose: **one `crowbar.json` file** and **one function call** where the runtime handles trophies. Most runtimes need under 20 changed lines.

## 0. Get the tools

```sh
pip install git+https://github.com/DiamondDogz/crowbar-sdk
```

This gives `crowbar-check` and `crowbar-fake`. Without pip: clone this repository and run `python -m crowbar_sdk.check` / `python -m crowbar_sdk.fake` from it. Python 3.9 or newer, no dependency, nothing sent over the network.

## 1. Ask the checker for a plan

From the runtime's root (the folder players unpack, or the source tree that produces it):

```sh
crowbar-check . --handout
```

It detects the layout, finds the `sceNpTrophyUnlockTrophy` handler in the sources, and prints numbered steps **for this runtime**: which files to copy where, which line to edit, a proposed `crowbar.json`. Follow that handout. The rest of this file explains the steps and the limits.

## 2. crowbar.json

Create it at the root of what players unpack. Start from the handout's proposal (or `crowbar-check . --write-proposal`, which writes `crowbar.json.proposed`), then check every value against the runtime itself:

- `game`: the catalog id. Known: `sakura-wars`, `valkyria-revolution`, `star-ocean-5`. For another game, use lower case and dashes, and tell the developer it is new.
- `titleIds`: the CUSA ids the runtime really accepts. Read them from the code, not from guesses.
- `launch`: run the exact command the runtime's own launcher or README uses. One argument per string, `{game}` where the dump folder goes. A Windows release usually ships its Python (`python/python.exe`); Linux uses `python3`.
- `data`: where the runtime keeps saves and settings. Only add `settings` if Crowbar should manage that `.ini`.
- `features`: declare only what the runtime really supports. Check each flag in its argument parser before adding `dlc`, `updatePkg`, `updateFolder` or `noDialogs`.
- `options` (with `settings`): the settings Crowbar shows for this runtime. Read the code that parses the `.ini`: each key, the values it accepts, the default when the key is missing. Declare what a player should change (resolution, display mode, upscaler, frame rate…), with English labels and French if you can. Never invent a key or a value the code does not accept. When the runtime gains an option later, adding it here is all it takes: Crowbar follows. Format: SPEC.md, settings screen.

If the source tree is not what players unpack (a build step produces the release), `crowbar.json` must end up at the root of the **release archive**: add it to the packaging script, and say so to the developer.

## 3. Trophies

Find the function the runtime registers for `sceNpTrophyUnlockTrophy` (often in a table such as `{"sceNpTrophyUnlockTrophy", trophy_unlock}`). The handout gives its file and line.

**C or C++ runtime:** copy `sdk/c/crowbar.h` and `sdk/c/crowbar.c` next to that file (the handout may give `crowbar.c` another name so an existing wildcard in the build compiles it), add `#include "crowbar.h"`, and make this the first statement of the handler:

```c
crowbar_unlock(id);   /* id = the trophy number the game passed */
```

Add `crowbar.c` to the build unless a wildcard already picks it up. Do not change what the handler returns to the game.

**Python launcher that sees unlocks** (rare): copy `sdk/python/crowbar.py` next to the script and call `crowbar.unlock(trophy_id)`.

**Already recording** (the handler writes `PS4RT_TROPHY_FILE` itself, like the Kagekidan and Ravn runtimes): change nothing. Just set `"trophies": true` in `crowbar.json`.

Never write a trophy list, names or icons: Crowbar reads them from the player's dump.

## 4. Check until clean

```sh
crowbar-check . --json
```

Repeat fixes until `"ok": true` and `errors` is empty. Each error has a `code`, a `message`, a `fix`, and often a `file` and `line`. Warnings are worth reading; info lines need no action.

Then, if the developer has a dump and a build:

```sh
crowbar-fake . --game /path/to/dump      # runs the game as Crowbar would, prints each trophy recorded
crowbar-fake . --game /path/to/dump --print   # only shows the command and environment
crowbar-fake . --simulate 14             # writes trophy 14 where Crowbar reads it, no game needed
```

You cannot play the game; ask the developer to unlock one trophy and paste what `crowbar-fake` printed.

If the developer uses Crowbar itself to test: the Konami code (↑ ↑ ↓ ↓ ← → ← → B A) unlocks **Settings › Developer**, where they can point Crowbar at the local runtime folder and watch trophies arrive live.

## 5. Hand over

Show the developer the full diff and a short summary: files added, lines changed, what `crowbar-check` says. Mention anything you guessed. Then stop.

## Never

- Commit, push, tag, publish a release or open a pull request unless the developer explicitly asks for that specific action.
- Touch the game, the emulation logic, or anything unrelated to the steps above.
- Add game files (eboot, modules, `sce_sys`, `.pkg`), keys, firmware, or third-party binaries to the runtime or its release.
- Remove or rename files the developer did not ask you to, including files `crowbar-check` flags: list them and let the developer decide.
- Invent trophy names, title ids, or command-line options the runtime does not have.

## Submitting to the catalog (only when the developer asks)

When the release containing `crowbar.json` is published on GitHub, the developer (or you, on request) opens the **Add a runtime** form at https://github.com/DiamondDogz/crowbar-catalog/issues/new/choose. An Action re-checks the release and opens the pull request; a maintainer merges it. Nothing reaches players before that review.
