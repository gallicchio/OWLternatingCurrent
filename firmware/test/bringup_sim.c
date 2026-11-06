/* bringup_sim.c: the bring-up console (src/bringup_cmd.c) on a simulated board, for
 * driving from a script before there is a board.
 *
 *     make -C firmware/test bringup_sim
 *     firmware/test/bringup_sim            (command lines on stdin, JSON lines on stdout)
 *
 * The boot lines come first, as from the board.  Each line out is flushed.  `reboot`
 * prints the boot lines again; `bootsel` exits (the board leaves USB).  The knobs are
 * environment variables (bringup_board_sim.h): OWL_SIM_NO12V=1, OWL_SIM_USB_OFF=1,
 * OWL_SIM_MISSING=0x32,0x29, OWL_SIM_TOKEN=owl|cat, OWL_SIM_NFAULT=1,
 * OWL_SIM_SHORT=pend2, OWL_SIM_OSC_DEAD=1, OWL_SIM_SDA_STUCK=1, OWL_SIM_BUTTON=1,
 * OWL_SIM_REALTIME=1 (waits take real time, so a walk or a sweep can be interrupted).
 */
#define _DEFAULT_SOURCE
#include "bringup_board_sim.h"
#include <poll.h>
#include <stdio.h>
#include <string.h>

static void print_line(const char *line)
{
    fputs(line, stdout);
    fputc('\n', stdout);
    fflush(stdout);
}

/* a character waiting on stdin (only meaningful when waits take real time) */
static bool stdin_pending(void)
{
    struct pollfd p = {.fd = 0, .events = POLLIN};
    return poll(&p, 1, 0) > 0 && (p.revents & POLLIN);
}

int main(void)
{
    sim_from_env();
    sim_line_out = print_line;
    sim_stdin_pending = stdin_pending;
    bringup_init(&SIM_OPS);
    char line[512];
    while (fgets(line, sizeof line, stdin)) {
        for (char *c = line; *c; c++)
            bringup_feed(*c);
        if (!strchr(line, '\n'))
            bringup_feed('\n');                     /* the last line without a newline */
        if (sim.bootsel)
            return 0;
        if (sim.rebooted) {
            sim_reset();
            bringup_init(&SIM_OPS);
        }
    }
    return 0;
}
