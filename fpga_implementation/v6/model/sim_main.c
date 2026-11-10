/* FECG v6 system model: bit-accurate RTL model + PC brain, connected through the
   message protocol, with the board host's lock-step framing (SAMPLES chunks of
   CHUNK samples, each answered by DONE).
     sim_main <in.i16>            ->  "t fhr_x10 src" per output beat (stdout)
   V6_DUMP=<prefix> writes the golden streams for the RTL testbench:
     <prefix>_up.hex      every uplink byte (A5 5A cmd len payload xor), one hex byte per line
     <prefix>_script.txt  host actions in order:
         "S nbytes b0 b1 ..."    send this SAMPLES frame (the previous one must have been answered by DONE)
         "R i nbytes b0 b1 ..."  send this response frame once uplink frame i (0-based) has arrived
         "E"                     end: wait for the last DONE */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "proto.h"
#include "fpga_model.h"
#include "brain.h"

#define CHUNK 64
#define QMAX 4096
static struct { int cmd, len; uint8_t *p; } q[QMAX];
static int qn;
static long n_up, cur_idx = -1, up_bytes, down_bytes;
static FILE *fup, *fscr;

/* lines = 1: one byte per line (up.hex); lines = 0: "nbytes b0 b1 ..." on one line (script) */
static void frame_bytes(FILE *f, int cmd, const uint8_t *p, int len, int lines)
{
    uint8_t h[5] = {0xA5, 0x5A, (uint8_t)cmd, (uint8_t)len, (uint8_t)(len >> 8)};
    uint8_t x = h[2] ^ h[3] ^ h[4];
    const char *sep = lines ? "\n" : " ";
    for (int i = 0; i < len; i++) x ^= p[i];
    if (!lines) fprintf(f, "%d ", len + 6);
    for (int i = 0; i < 5; i++) fprintf(f, "%02X%s", h[i], sep);
    for (int i = 0; i < len; i++) fprintf(f, "%02X%s", p[i], sep);
    fprintf(f, "%02X\n", x);
}
static void deliver(void)
{
    for (int i = 0; i < qn; i++) { cur_idx++; br_rx(q[i].cmd, q[i].p, q[i].len); free(q[i].p); }
    qn = 0;
}
static void up(int cmd, const uint8_t *p, int len)
{
    up_bytes += len + 6;
    if (fup) frame_bytes(fup, cmd, p, len, 1);
    if (cmd == C_OUT) printf("%u %u %u\n", get32(p), get16u(p + 4), p[6]);
    n_up++;
    if (qn == QMAX) deliver();
    q[qn].cmd = cmd; q[qn].len = len; q[qn].p = malloc(len ? len : 1); memcpy(q[qn].p, p, len); qn++;
}
static void down(int cmd, const uint8_t *p, int len)
{
    down_bytes += len + 6;
    if (fscr) { fprintf(fscr, "R %ld ", cur_idx); frame_bytes(fscr, cmd, p, len, 0); }
    fm_rx(cmd, p, len);
}

int main(int argc, char **argv)
{
    if (argc < 2) return 1;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 1;
    const char *dump = getenv("V6_DUMP");
    if (dump) {
        char fn[512];
        snprintf(fn, sizeof(fn), "%s_up.hex", dump); fup = fopen(fn, "w");
        snprintf(fn, sizeof(fn), "%s_script.txt", dump); fscr = fopen(fn, "w");
    }
    br_reset(down);
    fm_reset(up, deliver);
    int16_t x[CHUNK][4]; long n = 0; int m;
    while ((m = (int)fread(x, 8, CHUNK, f)) > 0) {
        if (fscr) { fprintf(fscr, "S "); frame_bytes(fscr, C_SAMPLES, (const uint8_t *)x, 8 * m, 0); }
        for (int i = 0; i < m; i++) { fm_push(x[i]); deliver(); }
        fm_done();
        deliver();
        n += m;
    }
    fclose(f);
    if (fup) fclose(fup);
    if (fscr) { fprintf(fscr, "E\n"); fclose(fscr); }
    fprintf(stderr, "samples %ld  uplink %ld B (%ld frames)  downlink(responses) %ld B  overflow %d\n", n, up_bytes, n_up, down_bytes, fm_overflow);
    return fm_overflow ? 4 : 0;
}
