# Vision

Today each PS4RT runtime is its own project: its loader, its system services, its graphics, its
trophy code, its pause, its quit. Most of that is the same from one game to the next. The goal is
that a new port only brings what is really specific to its game, and gets everything else, tested,
from shared pieces.

## One contract, several pieces

```
Crowbar (closed)              the console: interface, trophies, friends, Guide
   │  files and environment variables, described in SPEC.md (this SDK, MIT)
   ▼
Game runtime                  crowbar.json, the game's patches, a few stubs of its own
   ├─ shared HLE core         loader, system services, virtual file system, Crowbar module (GPL)
   └─ shared Vulkan backend   GNM to Vulkan, shaders, derived from shadPS4 (GPL)
```

- **The contract stays this SDK.** Crowbar and a runtime only ever talk through files and
  environment variables (SPEC.md). Nothing links them: a runtime built on the shared pieces, or on
  none, is treated the same way.
- **The player's dump stays the player's.** No piece ships game files, keys or firmware; the
  runtime reads the dump where the player keeps it and never writes into it.
- **Licences follow the code.** This SDK is MIT. Code derived from shadPS4 keeps its GPL licence,
  as the runtimes do today. Crowbar is closed and talks to games only through public interfaces.

## What comes first

These need no shared core and help every runtime now:

| Piece | What it does | Status |
| --- | --- | --- |
| `crowbar-check --runtime-test` | Starts a runtime with a dump and checks every answer against SPEC.md: `0 ready`, pause within 300 ms, resume, unlock on request, screenshot, quit with code 0 within 2 s | SDK 1.7 |
| Feature badges | Crowbar shows what a runtime supports (pause, live trophies, captures, presence, mods) on its page, before download | planned |
| Compatibility report | Exported from Crowbar's developer mode: which parts of the spec were seen working, to attach to a catalog pull request | planned |

Then, in order: the shared pieces (`crowbar-core-hle`, `crowbar-gfx-vulkan`) with the runtime
authors who want them, a runtime template that starts a new port from a dump, declarative patches
(a game's options as files, shown in Crowbar's settings), save import from shadPS4, and a shared
list of PS4 functions with what each runtime implements.

Nothing here is required. A runtime that follows SPEC.md, whatever it is built on, works in
Crowbar. Ideas and help are welcome in the issues.
