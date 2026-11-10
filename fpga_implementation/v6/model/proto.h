/* FECG v6 (RTL + PC brain): shared constants and the UART message protocol.
 *
 * Frame: A5 5A cmd len_lo len_hi payload[len] xor8(cmd, len bytes, payload)
 * All multi-byte fields little-endian.
 *
 * Downlink (PC -> FPGA)
 *   0x01 RESET
 *   0x02 SAMPLES   n x 4 x s16 raw ADC (n <= 256)
 *   0x10 RSP_V     4 detectors x 4 leads s16 Q14 (maternal PCA projections, PC1 first)
 *   0x11 RSP_MK    u8 maternal train index
 *   0x12 RSP_BASIS 4 x u8 nb[lead]; then per lead nb x 150 s24 (Q BO_FRAC), orthonormal
 *   0x13 RSP_CAL   u8 ntr; per track u8 kind, u8 src, u8 blank, 4 x s16 Q14 weights
 *   0x14 RSP_SEL   u8 selected track
 * Uplink (FPGA -> PC)
 *   0x80 COV       10 x s64: maternal-band covariance (upper triangle a<=b) over [256, 2500)
 *   0x81 MDET      u8 train, u32 peak       (final peak of maternal detector k)
 *   0x82 REQ_MK    u32 t                    (choose the maternal train at time t)
 *   0x83 MPK       u32 p                    (emitted maternal R peak)
 *   0x84 SEG       u32 p, 150 x 4 s16       (aligned beat segment added to the history)
 *   0x85 CALDATA   u32 s0, u16 n, n x (4 s16 Z, 4 s16 Xf)
 *   0x86 REQ_CAL
 *   0x87 BEAT      u8 k, u32 q              (track beat)
 *   0x88 FEAT      u8 k, u32 q, 31 x s32 bp (Q8), u16 pem (enc)
 *   0x89 BMED      u8 k, u16 median (enc)   (125-sample envelope block median)
 *   0x8A REQ_SEL   u32 t
 *   0x8B OUT       u32 t, u16 fhr_x10, u8 src
 *   0x8C DONE      u32 T                    (all samples received so far processed)
 */
#ifndef V6_PROTO_H
#define V6_PROTO_H
#include <stdint.h>

#define NL 4
#define FS 250
#define MAT_INIT 2500
#define MAT_HOP 1250
#define MAT_COV0 256
#define MAT_MWI 38
#define MAT_LOC 30
#define MAT_REFR 75
#define CAL_BEGIN 750
#define CAL_END 3750
#define CAL_LEN (CAL_END - CAL_BEGIN)
#define T0_TRACK (CAL_END + 127)
#define SEL_START (CAL_END + 127 + 1000)
#define SEL_HOP 625
#define SEL_LAG 150
#define DZ 176
#define L1 40
#define L2 110
#define LSEG (L1 + L2)
#define SEARCH 4
#define KHIST 20
#define WARMB 4
#define MAXTR 16
#define LAT_OUT 13
#define BO_FRAC 22          /* orthonormal basis entries: s24, |v| <= 1 */
#define W_FRAC 14           /* spatial weights Q14 */

enum {
    C_RESET = 0x01, C_SAMPLES = 0x02,
    C_RSP_V = 0x10, C_RSP_MK = 0x11, C_RSP_BASIS = 0x12, C_RSP_CAL = 0x13, C_RSP_SEL = 0x14,
    C_COV = 0x80, C_MDET = 0x81, C_REQ_MK = 0x82, C_MPK = 0x83, C_SEG = 0x84, C_CALDATA = 0x85,
    C_REQ_CAL = 0x86, C_BEAT = 0x87, C_FEAT = 0x88, C_BMED = 0x89, C_REQ_SEL = 0x8A, C_OUT = 0x8B,
    C_DONE = 0x8C
};

/* envelope code: monotonic 8-significant-bit float of a non-negative integer
   (x < 256: code = x; else code = 128*E + m - 128, x ~ m << (E-1), m in [128, 255]) */
static inline uint16_t enc_e(uint64_t x)
{
    if (x < 256) return (uint16_t)x;
    int n = 63; while (!((x >> n) & 1)) n--;          /* leading one */
    int sh = n - 7;
    uint64_t m = x >> sh, r = x & ((1ull << sh) - 1), half = 1ull << (sh - 1);
    if (r > half || (r == half && (m & 1))) m++;
    if (m == 256) { m = 128; sh++; }
    return (uint16_t)(((sh + 1) << 7) + (int)(m - 128));
}
static inline uint64_t dec_e(uint16_t c)
{
    int E = c >> 7;
    if (E <= 1) return c;
    return (uint64_t)(128 + (c & 127)) << (E - 1);
}

/* little-endian helpers */
static inline void put16(uint8_t *p, int v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static inline void put24(uint8_t *p, int32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); }
static inline void put32(uint8_t *p, uint32_t v) { for (int i = 0; i < 4; i++) p[i] = (uint8_t)(v >> (8 * i)); }
static inline void put64(uint8_t *p, int64_t v) { for (int i = 0; i < 8; i++) p[i] = (uint8_t)((uint64_t)v >> (8 * i)); }
static inline int get16s(const uint8_t *p) { return (int16_t)(p[0] | (p[1] << 8)); }
static inline unsigned get16u(const uint8_t *p) { return (unsigned)(p[0] | (p[1] << 8)); }
static inline int32_t get24s(const uint8_t *p) { int32_t v = p[0] | (p[1] << 8) | (p[2] << 16); return (v << 8) >> 8; }
static inline uint32_t get32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }
static inline int64_t get64(const uint8_t *p) { uint64_t v = 0; for (int i = 7; i >= 0; i--) v = (v << 8) | p[i]; return (int64_t)v; }

#endif
