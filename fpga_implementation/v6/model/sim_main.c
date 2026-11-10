/* FECG v6 system model: bit-accurate RTL model + PC brain, connected through the
   message protocol.  sim_main <in.i16>  ->  "t fhr_x10 src" per output beat.
   With V6_TRACE=<file> every frame is logged as "dir cmd len" (U = uplink, D = downlink). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "proto.h"
#include "fpga_model.h"
#include "brain.h"

#define QMAX 4096
static struct { int cmd, len; uint8_t *p; } q[QMAX];
static int qn;
static FILE *trace;
static long up_bytes, down_bytes;

static void deliver(void)
{
    for (int i = 0; i < qn; i++) { br_rx(q[i].cmd, q[i].p, q[i].len); free(q[i].p); }
    qn = 0;
}
static void up(int cmd, const uint8_t *p, int len)
{
    up_bytes += len + 6;
    if (trace) fprintf(trace, "U %02X %d\n", cmd, len);
    if (cmd == C_OUT) printf("%u %u %u\n", get32(p), get16u(p + 4), p[6]);
    if (qn == QMAX) deliver();
    q[qn].cmd = cmd; q[qn].len = len; q[qn].p = malloc(len ? len : 1); memcpy(q[qn].p, p, len); qn++;
}
static void down(int cmd, const uint8_t *p, int len)
{
    down_bytes += len + 6;
    if (trace) fprintf(trace, "D %02X %d\n", cmd, len);
    fm_rx(cmd, p, len);
}

int main(int argc, char **argv)
{
    if (argc < 2) return 1;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 1;
    if (getenv("V6_TRACE")) trace = fopen(getenv("V6_TRACE"), "w");
    br_reset(down);
    fm_reset(up, deliver);
    int16_t x[4]; long n = 0;
    while (fread(x, sizeof(int16_t), 4, f) == 4) { fm_push(x); deliver(); n++; }
    fclose(f);
    fprintf(stderr, "samples %ld  uplink %ld B  downlink(responses) %ld B  overflow %d\n", n, up_bytes, down_bytes, fm_overflow);
    return fm_overflow ? 4 : 0;
}
