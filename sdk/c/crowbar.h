/*
 * crowbar.h - make a PS4RT runtime "Crowbar compatible".
 * Part of crowbar-sdk, MIT licence: https://github.com/DiamondDogz/crowbar-sdk
 *
 * Copy crowbar.h and crowbar.c into your sources, then call crowbar_unlock(id)
 * from your sceNpTrophyUnlockTrophy handler. That is all Crowbar needs for trophies:
 * it reads the trophy list (names, icons, grades) from the player's own dump.
 *
 * Plain C99, no dependencies, works from C++ too. Never touches the network.
 */
#ifndef CROWBAR_H
#define CROWBAR_H

#ifdef __cplusplus
extern "C" {
#endif

#define CROWBAR_SDK_VERSION "1.6.0"
#define CROWBAR_MAX_TROPHIES 128 /* a PS4 trophy set holds ids 0..127 */

/*
 * Records trophy `id` (the number the game passes to sceNpTrophyUnlockTrophy) in the
 * trophy file Crowbar reads. Safe to call several times: the first date is kept.
 * Returns 1 when the trophy was added, 0 when it was already there, -1 on error
 * (bad id, unwritable file). Never blocks the game for long and never aborts.
 */
int crowbar_unlock(int id);

/* The trophy file in use: $PS4RT_TROPHY_FILE, else $PS4RT_DATA_DIR/user/trophies.json,
 * else user/trophies.json (relative to the working directory). */
const char *crowbar_trophy_file(void);

/* Crowbar's version when the runtime was started by Crowbar ($CROWBAR), else NULL. */
const char *crowbar_version(void);

/*
 * Pause from Crowbar's Guide menu ("pause": true in crowbar.json, SPEC section 4).
 * Call crowbar_poll() about ten times a second from the game loop: it returns a new
 * request, or CROWBAR_NONE (also when the game was not started by Crowbar).
 * Then reply with crowbar_answer(): for CROWBAR_PAUSE, 1 once the game is paused or
 * 0 when it cannot pause now (within 300 ms); for CROWBAR_RESUME, 1 once it runs again.
 */
#define CROWBAR_NONE 0
#define CROWBAR_PAUSE 1
#define CROWBAR_RESUME 2
/* SDK 1.3, Crowbar's trophy test profile: unlock trophy crowbar_request_trophy() as if the game
 * had (through your own unlock path), then crowbar_answer(1), or 0 when it cannot now. */
#define CROWBAR_UNLOCK 3
/* SDK 1.4: the player quit from Crowbar. Save what must be saved, crowbar_answer(1), then exit
 * with code 0 within 2 seconds; Crowbar closes the process itself after that. */
#define CROWBAR_QUIT 4
/* SDK 1.6: a trophy just unlocked and the player wants a screenshot of it. crowbar_answer(1), then
 * save the next presented game frame (without overlays) as crowbar_capture_name() in
 * crowbar_capture_dir(), written whole (a temporary name, then renamed). */
#define CROWBAR_CAPTURE 5
int crowbar_poll(void);
void crowbar_answer(int ok);
int crowbar_request_trophy(void);
/* SDK 1.6: "trophy-<id>-<n>.png" for the last CROWBAR_CAPTURE request, or NULL. */
const char *crowbar_capture_name(void);

/*
 * SDK 1.5: what the player is doing, shown to their friends and on Discord ("Chapter 3, Imperial
 * Theater", at most 80 characters, UTF-8; NULL or "" for nothing), and whether an online session is
 * running (online = 1: Crowbar does not pause the game, other players keep playing). Call it when
 * either changes, not every frame. Returns 0, or -1 when not started by Crowbar or on error.
 */
int crowbar_set_presence(const char *status, int online);

/* SDK 1.5: the folder where Crowbar wants this game's screenshots and clips ($PS4RT_CAPTURE_DIR),
 * shown in Crowbar's Captures; NULL when not started by Crowbar. Write each file whole
 * (a temporary name, then renamed) as .png, .jpg, .webp, .mp4 or .webm. */
const char *crowbar_capture_dir(void);

#ifdef __cplusplus
}
#endif

#endif /* CROWBAR_H */
