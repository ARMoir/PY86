/* A tiny 8086 DOS launcher that measures the actual child EXE load.
 * A self-contained DOS executable, built by Open Watcom C16.
 * Use: START86 PY86 DEMO.PY
 *
 * Before spawning the child, place BIOS timer ticks in the DOS environment.
 * PY86 exposes the corresponding elapsed milliseconds as time.launch_ms().
 * This covers the child MZ loader, native initialization, parser and the
 * first Python statements (unlike a timer that starts inside PY86 main()).
 * It excludes loading this small START86.EXE itself.
 */
#include <stdio.h>
#include <stdlib.h>
#include <process.h>
#include <dos.h>
#include <i86.h>

#define PY86_TICKS_PER_DAY 1573040UL

static unsigned long bios_ticks(void) {
    union REGS in_regs, out_regs;
    in_regs.h.ah = 0;
    int86(0x1a, &in_regs, &out_regs);
    return ((unsigned long)out_regs.x.cx << 16) | out_regs.x.dx;
}

int main(int argc, char **argv) {
    static char stamp[64];
    int rc;
    if (argc < 2) {
        fputs("Usage: START86 PY86 [script.py or arguments]\n", stderr);
        return 2;
    }
    /* Static storage remains valid throughout the child process launch. */
    sprintf(stamp, "PY86_LAUNCH_TICKS=%lu", bios_ticks());
    if (putenv(stamp) != 0) {
        fputs("START86: unable to set launch timestamp\n", stderr);
        return 2;
    }
    /* P_WAIT passes the updated environment to the DOS child and returns
     * its ERRORLEVEL to preserve the usual RUNTEST.BAT failure semantics. */
    rc = spawnvp(P_WAIT, argv[1], (const char * const *)&argv[1]);
    if (rc < 0) {
        perror("START86: cannot launch PY86");
        return 127;
    }
    return rc;
}
