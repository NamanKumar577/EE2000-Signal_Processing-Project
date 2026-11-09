/*
 * FECG v5 firmware: lock-step framed protocol over UART16550 (polling).
 * Frame (both directions): A5 5A cmd len_lo len_hi payload[len] xor8(cmd,len,payload)
 *   0x01 RESET            -> 0x81 (empty)
 *   0x02 SAMPLES N*4 i16  -> 0x82 u32 cycles, u16 nbeats, nbeats * {u32 t, u16 fhr_x10, u8 src, u8 flags}
 *   0x03 PING             -> 0x83 "FECG-v5 <clockHz> <baud>"
 *   0x04 BENCH            -> 0x84 u32 cycles x 5:
 *                            [0] 99,840 float MACs   [1] 10,000 float div+add
 *                            [2] 10,000 sqrtf+add    [3] 99,840 int16 MACs
 *                            [4] 100,000 empty volatile loop iterations
 *   0x05 MEMTEST          -> 0x85 u32 words, u32 errors, u32 cycles  (32 KB AXI BRAM .bigdata)
 * Bad checksum / unknown cmd -> 0xEE with the offending cmd byte.
 */
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "platform.h"
#include "fecg_algo.h"

#define U_RBR  (UART_BASE + 0x1000)
#define U_THR  (UART_BASE + 0x1000)
#define U_DLL  (UART_BASE + 0x1000)
#define U_DLM  (UART_BASE + 0x1004)
#define U_FCR  (UART_BASE + 0x1008)
#define U_LCR  (UART_BASE + 0x100C)
#define U_MCR  (UART_BASE + 0x1010)
#define U_LSR  (UART_BASE + 0x1014)

#define MAX_N     256
#define MAX_BEATS 64

static uint8_t rxbuf[MAX_N * 8 + 8];
static uint8_t txbuf[6 + MAX_BEATS * 8 + 8];
static fecg_beat_t beats[MAX_BEATS];

static void uart_init(void)
{
    uint32_t div = (SYS_CLK_HZ + 8u * UART_BAUD) / (16u * UART_BAUD);
    REG(U_LCR) = 0x80;
    REG(U_DLL) = div & 0xFF;
    REG(U_DLM) = (div >> 8) & 0xFF;
    REG(U_LCR) = 0x03;              /* 8N1 */
    REG(U_FCR) = 0x07;              /* FIFO on, clear */
    REG(U_MCR) = 0x00;
}

static inline uint8_t uart_getc(void)
{
    while (!(REG(U_LSR) & 0x01)) {}
    return (uint8_t)REG(U_RBR);
}

static void uart_write(const uint8_t *p, int n)
{
    while (n > 0) {
        while (!(REG(U_LSR) & 0x20)) {}          /* TX FIFO empty -> room for 16 */
        int k = n < 16 ? n : 16;
        for (int i = 0; i < k; i++) REG(U_THR) = p[i];
        p += k;
        n -= k;
    }
}

static inline uint32_t timer_now(void) { return REG(TIMER_BASE + 0x08); }

static void timer_init(void)
{
    REG(TIMER_BASE + 0x04) = 0;      /* TLR0 */
    REG(TIMER_BASE + 0x00) = 0x20;   /* LOAD0 */
    REG(TIMER_BASE + 0x00) = 0x90;   /* ENT0 | ARHT0, count up */
}

static void send_frame(uint8_t cmd, const uint8_t *pl, int len)
{
    uint8_t h[5] = {0xA5, 0x5A, cmd, (uint8_t)len, (uint8_t)(len >> 8)};
    uint8_t x = cmd ^ h[3] ^ h[4];
    for (int i = 0; i < len; i++) x ^= pl[i];
    uart_write(h, 5);
    if (len) uart_write(pl, len);
    uart_write(&x, 1);
}

static void put32(uint8_t *p, uint32_t v)
{
    p[0] = v; p[1] = v >> 8; p[2] = v >> 16; p[3] = v >> 24;
}

/* ---- FPU / CPU micro-benchmark (volatile sinks keep the work) */
static volatile float fsink;
static volatile int32_t isink;
static float ba[256], bb[256];
static int16_t ia16[256];

static void bench(void)
{
    uint32_t c[5], t0;
    for (int i = 0; i < 256; i++) {
        ba[i] = 0.001f * i; bb[i] = 1.0f - 0.002f * i; ia16[i] = (int16_t)(i * 37 - 4000);
    }
    float acc = 0.f;
    t0 = timer_now();
    for (int r = 0; r < 390; r++)
        for (int i = 0; i < 256; i++) acc += ba[i] * bb[i];
    c[0] = timer_now() - t0; fsink = acc;

    float d = 1.f;
    t0 = timer_now();
    for (int i = 0; i < 10000; i++) d = d / 1.0001f + ba[i & 255];
    c[1] = timer_now() - t0; fsink = d;

    float s = 0.f;
    t0 = timer_now();
    for (int i = 0; i < 10000; i++) s += sqrtf(ba[i & 255] + (float)i);
    c[2] = timer_now() - t0; fsink = s;

    int32_t ia = 0;
    t0 = timer_now();
    for (int r = 0; r < 390; r++)
        for (int i = 0; i < 256; i++) ia += ia16[i] * ia16[i ^ 1];
    c[3] = timer_now() - t0; isink = ia;

    t0 = timer_now();
    for (volatile int i = 0; i < 100000; i++) {}
    c[4] = timer_now() - t0;

    uint8_t pl[20];
    for (int i = 0; i < 5; i++) put32(pl + 4 * i, c[i]);
    send_frame(0x84, pl, 20);
}

/* ---- 0x05 MEMTEST: pattern test of the 32 KB AXI BRAM (.bigdata) -> 0x85 u32 words, u32 errors, u32 cycles */
/* Uses the raw region (no symbol), so it reserves nothing; it DESTROYS .bigdata contents -> it is
 * followed by fecg_reset(). */
#define BIG_WORDS (32768 / 4)
#define bigtest ((volatile uint32_t *)0xC0000000u)

static void memtest(void)
{
    uint32_t err = 0, t0 = timer_now();
    for (int pass = 0; pass < 2; pass++) {
        for (uint32_t i = 0; i < BIG_WORDS; i++) bigtest[i] = pass ? ~(i * 2654435761u) : i * 2654435761u;
        for (uint32_t i = 0; i < BIG_WORDS; i++)
            err += bigtest[i] != (pass ? ~(i * 2654435761u) : i * 2654435761u);
    }
    uint8_t pl[12];
    put32(pl, BIG_WORDS); put32(pl + 4, err); put32(pl + 8, timer_now() - t0);
    send_frame(0x85, pl, 12);
}

static void u32dec(char *s, uint32_t v)
{
    char t[12];
    int n = 0;
    do { t[n++] = '0' + v % 10; v /= 10; } while (v);
    while (n) *s++ = t[--n];
    *s = 0;
}

static void err(uint8_t cmd) { send_frame(0xEE, &cmd, 1); }

int main(void)
{
    uart_init();
    timer_init();
    REG(GPIO_BASE + 0x04) = 0;       /* all outputs */
    REG(GPIO_BASE) = 0x01;
    fecg_reset();
    uint32_t blocks = 0;

    for (;;) {
        /* sync on A5 5A */
        uint8_t b = uart_getc();
        if (b != 0xA5) continue;
        do { b = uart_getc(); } while (b == 0xA5);
        if (b != 0x5A) continue;

        uint8_t cmd = uart_getc();
        uint8_t l0 = uart_getc(), l1 = uart_getc();
        int len = l0 | (l1 << 8);
        if (len > MAX_N * 8) { err(cmd); continue; }
        uint8_t x = cmd ^ l0 ^ l1;
        for (int i = 0; i < len; i++) { rxbuf[i] = uart_getc(); x ^= rxbuf[i]; }
        if (uart_getc() != x) { err(cmd); continue; }

        switch (cmd) {
        case 0x01:
            fecg_reset();
            blocks = 0;
            send_frame(0x81, 0, 0);
            break;
        case 0x02: {
            int n = len / 8, nb = 0;
            uint32_t t0 = timer_now();
            for (int k = 0; k < n; k++) {
                int16_t s[4];
                for (int c = 0; c < 4; c++)
                    s[c] = (int16_t)(rxbuf[8 * k + 2 * c] | (rxbuf[8 * k + 2 * c + 1] << 8));
                nb += fecg_push(s, beats + nb, MAX_BEATS - nb);
            }
            uint32_t cyc = timer_now() - t0;
            put32(txbuf, cyc);
            txbuf[4] = nb; txbuf[5] = nb >> 8;
            for (int i = 0; i < nb; i++) {
                uint8_t *p = txbuf + 6 + 8 * i;
                put32(p, beats[i].t);
                p[4] = beats[i].fhr_x10; p[5] = beats[i].fhr_x10 >> 8;
                p[6] = beats[i].src; p[7] = beats[i].flags;
            }
            send_frame(0x82, txbuf, 6 + 8 * nb);
            REG(GPIO_BASE) = 0x01 | ((++blocks >> 2) & 0xFE);
            break;
        }
        case 0x03: {
            char v[48] = "FECG-v5 ";
            u32dec(v + strlen(v), SYS_CLK_HZ);
            strcat(v, " ");
            u32dec(v + strlen(v), UART_BAUD);
            send_frame(0x83, (const uint8_t *)v, strlen(v));
            break;
        }
        case 0x04:
            bench();
            break;
        case 0x05:
            memtest();
            fecg_reset();
            break;
        default:
            err(cmd);
        }
    }
}
