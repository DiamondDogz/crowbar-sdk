/*
 * crowbar.c - see crowbar.h. MIT licence, crowbar-sdk.
 *
 * Writes {"unlocked":{"001":"2026-11-07T10:42:13Z", ...}} as described in SPEC.md.
 * The file is rewritten through a temporary file and a rename, so a crash never
 * leaves half a JSON behind.
 */
#if !defined(_WIN32) && !defined(_POSIX_C_SOURCE)
#define _POSIX_C_SOURCE 200809L /* gmtime_r */
#endif
#include "crowbar.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef _WIN32
#include <windows.h>
#include <direct.h>
#define CROWBAR_MKDIR(p) _mkdir(p)
#else
#include <sys/stat.h>
#include <sys/types.h>
#define CROWBAR_MKDIR(p) mkdir(p, 0755)
#endif

#if defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L && !defined(__STDC_NO_ATOMICS__)
#include <stdatomic.h>
static atomic_flag crowbar_lock_flag = ATOMIC_FLAG_INIT;
static void crowbar_lock(void) { while (atomic_flag_test_and_set(&crowbar_lock_flag)) { } }
static void crowbar_unlock_mutex(void) { atomic_flag_clear(&crowbar_lock_flag); }
#elif defined(_WIN32)
static volatile LONG crowbar_lock_flag = 0;
static void crowbar_lock(void) { while (InterlockedExchange(&crowbar_lock_flag, 1)) Sleep(0); }
static void crowbar_unlock_mutex(void) { InterlockedExchange(&crowbar_lock_flag, 0); }
#else
static void crowbar_lock(void) { }
static void crowbar_unlock_mutex(void) { }
#endif

static char crowbar_path[4096];

const char *crowbar_trophy_file(void) {
    const char *file = getenv("PS4RT_TROPHY_FILE");
    if (file && file[0]) return file;
    const char *data = getenv("PS4RT_DATA_DIR");
    if (data && data[0]) {
        snprintf(crowbar_path, sizeof(crowbar_path), "%s/user/trophies.json", data);
        return crowbar_path;
    }
    return "user/trophies.json";
}

const char *crowbar_version(void) {
    const char *v = getenv("CROWBAR");
    return (v && v[0]) ? v : NULL;
}

/* Creates every missing folder above `path`. */
static void crowbar_make_parents(const char *path) {
    char buf[4096];
    size_t n = strlen(path);
    if (n >= sizeof(buf)) return;
    memcpy(buf, path, n + 1);
    for (size_t i = 1; i < n; i++) {
        if (buf[i] == '/' || buf[i] == '\\') {
            char c = buf[i];
            buf[i] = 0;
            if (!(i == 2 && buf[1] == ':')) CROWBAR_MKDIR(buf); /* skip "C:" */
            buf[i] = c;
        }
    }
}

static int crowbar_replace(const char *tmp, const char *path) {
#ifdef _WIN32
    return MoveFileExA(tmp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) ? 0 : -1;
#else
    return rename(tmp, path);
#endif
}

static int crowbar_record(int id, const char *path) {
    static char body[65536];
    static char saved[CROWBAR_MAX_TROPHIES][40];
    int seen[CROWBAR_MAX_TROPHIES];
    memset(seen, 0, sizeof(seen));
    memset(saved, 0, sizeof(saved));

    size_t n = 0;
    FILE *in = fopen(path, "rb");
    if (in) { n = fread(body, 1, sizeof(body) - 1, in); fclose(in); }
    body[n] = 0;

    /* Reads every "<digits>": "<date>" pair, whatever the spacing or the leading zeros. */
    for (char *c = body; (c = strchr(c, '"')) != NULL; ) {
        char *p = c + 1;
        int number = 0, digits = 0;
        while (*p >= '0' && *p <= '9' && digits < 4) { number = number * 10 + (*p - '0'); p++; digits++; }
        if (digits == 0 || *p != '"') { c++; continue; }
        p++;
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
        if (*p != ':') { c++; continue; }
        p++;
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
        if (*p != '"') { c++; continue; }
        p++;
        size_t len = strcspn(p, "\"");
        if (number < CROWBAR_MAX_TROPHIES) {
            seen[number] = 1;
            if (len > sizeof(saved[0]) - 1) len = sizeof(saved[0]) - 1;
            memcpy(saved[number], p, len);
            saved[number][len] = 0;
        }
        c = p + len;
    }

    if (seen[id]) return 0;

    time_t now = time(NULL);
    struct tm parts;
#ifdef _WIN32
    gmtime_s(&parts, &now);
#else
    gmtime_r(&now, &parts);
#endif
    strftime(saved[id], sizeof(saved[id]), "%Y-%m-%dT%H:%M:%SZ", &parts);
    seen[id] = 1;

    crowbar_make_parents(path);
    char tmp[4200];
    snprintf(tmp, sizeof(tmp), "%s.tmp", path);
    FILE *out = fopen(tmp, "wb");
    if (!out) return -1;
    fputs("{\n  \"unlocked\": {", out);
    int first = 1;
    for (int k = 0; k < CROWBAR_MAX_TROPHIES; k++) {
        if (!seen[k]) continue;
        fprintf(out, "%s\n    \"%03d\": \"%s\"", first ? "" : ",", k, saved[k]);
        first = 0;
    }
    fputs("\n  }\n}\n", out);
    if (fclose(out) != 0) { remove(tmp); return -1; }
    if (crowbar_replace(tmp, path) != 0) { remove(tmp); return -1; }
    return 1;
}

int crowbar_unlock(int id) {
    if (id < 0 || id >= CROWBAR_MAX_TROPHIES) return -1;
    crowbar_lock();
    int result = crowbar_record(id, crowbar_trophy_file());
    crowbar_unlock_mutex();
    return result;
}
