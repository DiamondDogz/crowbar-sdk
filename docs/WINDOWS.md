# Porting a PS4RT runtime to Windows

What cost us time on Gundam Code Fairy, Sakura Wars and Valkyria Revolution, in the order it bites. Check each point before the first build; most of them compile fine and fail only in the game.

## 1. The game's code calls you with the System V ABI

The PS4 uses the System V calling convention. On Linux it is the default, so nothing shows. On Windows (MinGW, clang, MSVC) the default is the Microsoft one: arguments arrive in other registers.

- **Every function the game's own code calls** must be `__attribute__((sysv_abi))`: imported symbols (`sceXxx`), and also anything the loader **patches a call to** (a `memcpy` routed to a buffer-cache helper, a texture-upload hook). shadPS4 code uses `PS4_SYSV_ABI`.
- **Every pointer to a game function** you call back must have the same attribute in its type: `using Loop = int (PS4_SYSV_ABI *)(…)`.
- Symptom when one is missing: a fault reading a tiny address (`read access to 0000000000000001`) in your function, right after the game starts.

Sakura Wars 1.2 added three such hooks (`ps4rtgpu_new_buffer_copy`, `ps4rtgpu_tile_surface_region(_2d)`); rc.3 crashed on them.

## 2. POSIX calls that do not exist or behave differently

| Linux | Windows |
| --- | --- |
| `flock` | `LockFileEx` on `_get_osfhandle(fd)` |
| `mkstemp` + `rename` + `fsync(dir)` | `_wopen(… _O_CREAT \| _O_TRUNC)`, `_commit`, `MoveFileExW(MOVEFILE_REPLACE_EXISTING)`, `FlushFileBuffers` on the folder (`FILE_FLAG_BACKUP_SEMANTICS`) |
| `open(O_CLOEXEC \| O_NOFOLLOW)` | `_wopen(_O_BINARY)` |
| `setenv` | `_putenv_s` |
| `localtime_r`, `gmtime_r` | `localtime_s(&tm, &t)`, `gmtime_s(&tm, &t)` (arguments swapped) |
| `SIGSEGV` handler | vectored exception handler |
| paths in `char*` | `std::filesystem::path` / wide APIs (`_wopen`, `CreateFileW`): player names have accents |

The trophy state of the GBO and Sakura Windows ports (`gpu/shim/ps4rt_achievements.cpp`, `#ifdef _WIN32`) is a working example of the first two lines.

## 3. Fonts

Japanese, Korean and Chinese trophy texts need a CJK font. On Windows use the system's: `C:\Windows\Fonts\YuGothM.ttc`, `malgun.ttf`, `msjh.ttc`.

## 4. The window

- In borderless fullscreen, do **not** make the game window "always on top" (`SDL_WINDOW_ALWAYS_ON_TOP`, `HWND_TOPMOST`): Crowbar's Guide menu and trophy banner must be able to show over it. Crowbar copes with it, but every topmost window fights for the front.
- Prefer borderless to exclusive fullscreen: nothing can be drawn over exclusive fullscreen.

## 5. Building on GitHub

- GitHub's Windows images now ship their own `C:\msys64`. A build script that puts it first on `PATH` mixes two MSYS2 runtimes, and commands die with exit code **127** and no message. With `msys2/setup-msys2`, set `MSYS2_ROOT` to a folder that does not exist (or remove `C:\msys64` from `PATH`).
- `templates/release-windows.yml` does it.

## 6. Crowbar's files

Read `PS4RT_CONTROL_DIR` (pause, quit, unlock), write the trophy file or declare yours (`trophyFile`, `trophyFormat`), keep your own trophy state in `PS4RT_ACHIEVEMENTS_DIR` when it is set. See SPEC.md.
