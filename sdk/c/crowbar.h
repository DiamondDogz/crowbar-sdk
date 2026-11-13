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

#define CROWBAR_SDK_VERSION "1.3.0"
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
int crowbar_poll(void);
void crowbar_answer(int ok);
int crowbar_request_trophy(void);

#ifdef __cplusplus
}
#endif

#endif /* CROWBAR_H */
