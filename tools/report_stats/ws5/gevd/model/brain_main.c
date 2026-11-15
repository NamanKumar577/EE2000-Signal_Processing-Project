/* FECG v6 PC brain as a pipe for the board host: reads uplink frames (A5 5A cmd len
   payload xor) on stdin, writes response frames on stdout. */
#include <stdio.h>
#include <io.h>
#include <fcntl.h>
#include "proto.h"
#include "brain.h"

static void send(int cmd, const uint8_t *p, int len)
{
    uint8_t h[5] = {0xA5, 0x5A, (uint8_t)cmd, (uint8_t)len, (uint8_t)(len >> 8)};
    uint8_t x = h[2] ^ h[3] ^ h[4];
    for (int i = 0; i < len; i++) x ^= p[i];
    fwrite(h, 1, 5, stdout); fwrite(p, 1, len, stdout); fputc(x, stdout);
    fflush(stdout);
}

int main(void)
{
    static uint8_t p[65536];
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
    br_reset(send);
    for (;;) {
        int a = getchar();
        if (a == EOF) return 0;
        if (a != 0xA5) continue;
        if (getchar() != 0x5A) continue;
        int cmd = getchar(), lo = getchar(), hi = getchar();
        if (hi == EOF) return 0;
        int len = lo | (hi << 8);
        if ((int)fread(p, 1, len, stdin) != len) return 0;
        int x = getchar();
        uint8_t c = (uint8_t)(cmd ^ lo ^ hi);
        for (int i = 0; i < len; i++) c ^= p[i];
        if (c != (uint8_t)x) { fprintf(stderr, "brain: bad checksum cmd %02X\n", cmd); return 2; }
        if (cmd == C_RESET) { br_reset(send); continue; }
        br_rx(cmd, p, len);
    }
}
