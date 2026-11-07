# crowbar-sdk

**Make your PS4RT runtime Crowbar compatible: trophies, profile, downloads and updates, without writing any UI.**

[Crowbar](https://github.com/DiamondDogz/crowbar) is an XMB-style launcher for PS4RT runtimes on Windows and Linux. This repository holds the public format it reads and small tools to adopt it. Crowbar itself stays closed; everything here is MIT.

*[Français](README.fr.md)*

## What your players get

- **Trophies:** list, icons and descriptions in their language, hidden trophies, read from their own dump. You provide nothing but the unlock.
- **A card and a notification** when a trophy pops, live during the game.
- **A profile:** level, totals, per-game progress.
- **Downloads and updates** from the catalog, each file checked against its SHA-256.
- **DLC and game updates** read from their `.pkg` files; you only receive the ones to install.
- **Backups** of your data folder, and **useful bug reports**: launch log and system info, copied in one click.
- Windows and Linux, controller first.

## What you do

A few minutes of changes with an AI assistant (a bit more by hand), then a rebuild and one trophy in game to check it works.

1. Call `crowbar_unlock(id)` where your runtime handles `sceNpTrophyUnlockTrophy`.
2. Ship a `crowbar.json` at the root of your release: name, CUSA ids, launch command.
3. Run `crowbar-check` until it is clean.
4. Fill in the **Add a runtime** form of [crowbar-catalog](https://github.com/DiamondDogz/crowbar-catalog/issues/new/choose).

## Using an AI assistant?

Paste this to it (Claude, Grok, DeepSeek, Gemini, Copilot…):

> Make this runtime Crowbar compatible. Read https://github.com/DiamondDogz/crowbar-sdk/blob/main/AGENTS.md, run `crowbar-check . --handout` and follow it. Stop when `crowbar-check . --json` reports no error, then show me the diff.

[AGENTS.md](AGENTS.md) is written for them; `crowbar-check --handout` gives them a plan for your runtime specifically, with files and line numbers. They never publish anything: you review the diff and release.

## Testing in Crowbar

Crowbar has a hidden developer mode. Enter the Konami code anywhere in Crowbar, with a controller or the keyboard: **↑ ↑ ↓ ↓ ← → ← → B A** (on a keyboard, B and A or Esc and Enter). **Settings › Developer** then lets you:

- point Crowbar at your local runtime folder (it replaces the installed runtime for the games your `crowbar.json` declares);
- see whether your `crowbar.json` is valid and what it declares;
- watch launches and trophies arrive live;
- simulate a trophy notification;
- copy a catalog entry prefilled from the game's `param.sfo`.

The same code hides it again.

## What is inside

| Path | For |
| --- | --- |
| [`SPEC.md`](SPEC.md) | The format: `crowbar.json`, the trophy file, environment variables, the catalog entry |
| [`sdk/c/`](sdk/c) | `crowbar.h` + `crowbar.c`: `crowbar_unlock(id)` in plain C99, also builds as C++; Windows and Linux |
| [`sdk/python/crowbar.py`](sdk/python/crowbar.py) | The same for Python launch scripts |
| `crowbar-check` | Checks a runtime folder or release archive; `--json` for agents and CI, `--handout` for a step-by-step plan |
| `crowbar-fake` | Runs your runtime exactly as Crowbar would and prints each trophy it records, without installing Crowbar |
| [`schema/crowbar.schema.json`](schema/crowbar.schema.json) | JSON Schema for editors |
| [`templates/`](templates) | Example `crowbar.json` files and a release workflow that publishes your archive with its `.sha256` |

```sh
pip install git+https://github.com/DiamondDogz/crowbar-sdk
crowbar-check path/to/runtime --handout
crowbar-fake path/to/runtime --game path/to/dump
```

Python 3.9+, no dependency, nothing ever sent over the network.

## What the SDK does not do

- It contains no Crowbar code and does not tie you to Crowbar: any launcher can read this format.
- It touches no game data and decrypts nothing. Your runtime ships nothing more than before.
- Releases must never contain game files, keys or firmware. `crowbar-check` and the catalog look for them.

## Licence

MIT. See [LICENSE](LICENSE).
