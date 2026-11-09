/*
 * FECG v5 streaming algorithm (runs on the MicroBlaze; the same file builds on
 * the PC as the reference model).  Single precision, static memory, strictly
 * causal: every decision at input sample T uses only samples <= T.
 *
 * Pipeline (time axis "s" = Z-time = T - DZ):
 *   1. per lead: HP1 -> LP (front end) = Xf ;  HP1 -> 5-25 Hz = Ym (maternal band)
 *   2. maternal R peaks: PCA of Ym on [256, 2500), one FPGA-style detector per PC,
 *      every 5 s the train that looks most like a mother (slowest regular 40-130 bpm)
 *   3. per-lead maternal cancellation: aligned beat history (last K beats), basis =
 *      mean + top-2 PCs, least-squares fit, subtract (tapered)  ->  Z
 *   4. at s = CAL_END: candidate spatial filters on BP(Z) and BP(Xf) over
 *      [CAL_BEGIN, CAL_END): unit leads, PCA, self-referencing GEVD (maternal-
 *      coincident beats excluded)
 *   5. one tracker per candidate (RR-predictive tracker or threshold detector)
 *   6. every 5 s choose the candidate with the best label-free quality over the
 *      trailing 10 s (morphology consistency x acceptance x log prominence,
 *      x maternal-coincidence penalty); output its beats; FHR = median of 5 RR.
 */
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include "fecg_v5.h"

#include <stdint.h>
#ifdef FECG_MB                 /* MicroBlaze: slow AXI BRAM for rarely-touched data */
#define SLOWMEM __attribute__((section(".bigdata")))
#else
#define SLOWMEM
#endif

/* ─────────────────────────── constants ─────────────────────────── */
#define NL 4
#define FS 250
#define MAT_INIT 2500
#define MAT_HOP 1250
#define MAT_LOOK 5000
#define MAT_MWI 38
#define MAT_LOC 30

#define CAL_BEGIN 750
#define CAL_END 3750
#define CAL_LEN (CAL_END - CAL_BEGIN)
#define CAL_WARM 512
#define T0_TRACK (CAL_END + 127)
#define SEL_START (CAL_END + 127 + 1000)
#define SEL_HOP 1250
#define SEL_LOOK 2500
#define SEL_LAG 150
#define DZ 176
#define L1 40
#define L2 110
#define LSEG (L1 + L2)
#define SEARCH 4
#define KHIST 20
#define WARMB 4

#ifndef ZRING
#define ZRING 3072           /* Z / Xf history: covers the start-up burst back to CAL_BEGIN */
#endif
#define ZI(s) ((s) % ZRING)
#define ERING 1280           /* tracker envelope history (bf16) */
#define BRING 256            /* bp / |bp| history */
#define PKRING 96
#define MAXTR 16
#define LAT_OUT 13

/* ─────────────────────────── filters ─────────────────────────── */
#include "fecg_v5_coef.h"

typedef struct { float z1[4], z2[4]; } sos_t;

static float sos_step(const float (*c)[5], int ns, sos_t *s, float x)
{
    for (int i = 0; i < ns; i++) {
        float y = c[i][0] * x + s->z1[i];
        s->z1[i] = c[i][1] * x - c[i][3] * y + s->z2[i];
        s->z2[i] = c[i][2] * x - c[i][4] * y;
        x = y;
    }
    return x;
}

#define HP_A (1.0f / 64.0f)
typedef struct { float b; } hp_t;
static float hp_step(hp_t *h, float x)
{
    float y = x - h->b;
    h->b = (1.0f - HP_A) * h->b + HP_A * x;
    return y;
}

typedef struct { float r[40]; int w, i; float sum; } mwi_t;
static float mwi_step(mwi_t *m, float sq)
{
    m->sum += sq - m->r[m->i];
    m->r[m->i] = sq;
    if (++m->i == m->w) {
        m->i = 0;
        float s = 0.0f;
        for (int k = 0; k < m->w; k++) s += m->r[k];
        m->sum = s;
    }
    return m->sum > 0.0f ? m->sum : 0.0f;
}

/* compact storage (int16 samples, bfloat16 envelopes) */
static int16_t sat16(float x)
{
    float r = floorf(x + 0.5f);
    if (r > 32767.0f) r = 32767.0f;
    if (r < -32768.0f) r = -32768.0f;
    return (int16_t)r;
}
static uint16_t f2bf(float f)          /* float -> bfloat16, round to nearest even */
{
    uint32_t u; memcpy(&u, &f, 4);
    return (uint16_t)((u + 0x7FFFu + ((u >> 16) & 1u)) >> 16);
}
static float bf2f(uint16_t b)
{
    uint32_t u = (uint32_t)b << 16; float f; memcpy(&f, &u, 4);
    return f;
}

/* ─────────────────────────── small math ─────────────────────────── */
static void isort(int *a, int n)
{
    for (int i = 1; i < n; i++) { int v = a[i], j = i - 1; while (j >= 0 && a[j] > v) { a[j + 1] = a[j]; j--; } a[j + 1] = v; }
}
static void fsort(float *a, int n)
{
    for (int i = 1; i < n; i++) { float v = a[i]; int j = i - 1; while (j >= 0 && a[j] > v) { a[j + 1] = a[j]; j--; } a[j + 1] = v; }
}
static float imedian(const int *a, int n)          /* numpy median of ints */
{
    int b[128]; if (n > 128) n = 128;
    memcpy(b, a, n * sizeof(int)); isort(b, n);
    return (n & 1) ? (float)b[n / 2] : 0.5f * (float)(b[n / 2 - 1] + b[n / 2]);
}
static float fselect(float *a, int n, int k)        /* k-th smallest, reorders a */
{
    int lo = 0, hi = n - 1;
    while (hi > lo) {
        float piv = a[(lo + hi) >> 1];
        int i = lo, j = hi;
        while (i <= j) {
            while (a[i] < piv) i++;
            while (a[j] > piv) j--;
            if (i <= j) { float t = a[i]; a[i] = a[j]; a[j] = t; i++; j--; }
        }
        if (k <= j) hi = j;
        else if (k >= i) lo = i;
        else break;
    }
    return a[k];
}
static float fmedian(float *b, int n)               /* reorders b */
{
    if (n <= 0) return 0.0f;
    if (n < 12) { fsort(b, n); return (n & 1) ? b[n / 2] : 0.5f * (b[n / 2 - 1] + b[n / 2]); }
    float hi = fselect(b, n, n / 2);
    if (n & 1) return hi;
    float lo = b[0];                                 /* max of the lower part */
    for (int i = 1; i < n / 2; i++) if (b[i] > lo) lo = b[i];
    return 0.5f * (lo + hi);
}

/* symmetric Jacobi eigen-decomposition, n <= 20; A destroyed; ascending order */
#define JMAX 20
static void jacobi(float *A, int n, float *ev, float *V)
{
    for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) V[i * n + j] = (i == j) ? 1.0f : 0.0f;
    for (int sweep = 0; sweep < 30; sweep++) {
        float off = 0.0f, tot = 0.0f;
        for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) { float a = A[i * n + j] * A[i * n + j]; tot += a; if (i != j) off += a; }
        if (off <= 1e-12f * tot || off == 0.0f) break;
        for (int p = 0; p < n - 1; p++) for (int q = p + 1; q < n; q++) {
            float apq = A[p * n + q];
            if (apq == 0.0f) continue;
            float app = A[p * n + p], aqq = A[q * n + q];
            float theta = (aqq - app) / (2.0f * apq);
            float t = (theta >= 0 ? 1.0f : -1.0f) / (fabsf(theta) + sqrtf(theta * theta + 1.0f));
            float c = 1.0f / sqrtf(t * t + 1.0f), s = t * c;
            for (int k = 0; k < n; k++) {
                float akp = A[k * n + p], akq = A[k * n + q];
                A[k * n + p] = c * akp - s * akq; A[k * n + q] = s * akp + c * akq;
            }
            for (int k = 0; k < n; k++) {
                float apk = A[p * n + k], aqk = A[q * n + k];
                A[p * n + k] = c * apk - s * aqk; A[q * n + k] = s * apk + c * aqk;
            }
            for (int k = 0; k < n; k++) {
                float vkp = V[k * n + p], vkq = V[k * n + q];
                V[k * n + p] = c * vkp - s * vkq; V[k * n + q] = s * vkp + c * vkq;
            }
        }
    }
    for (int i = 0; i < n; i++) ev[i] = A[i * n + i];
    /* sort ascending (selection sort on columns) */
    for (int i = 0; i < n - 1; i++) {
        int m = i;
        for (int j = i + 1; j < n; j++) if (ev[j] < ev[m]) m = j;
        if (m != i) {
            float t = ev[i]; ev[i] = ev[m]; ev[m] = t;
            for (int k = 0; k < n; k++) { float u = V[k * n + i]; V[k * n + i] = V[k * n + m]; V[k * n + m] = u; }
        }
    }
}

/* top generalised eigenvector of (A, B), 4x4, B SPD: B = L L^T, C = L^-1 A L^-T */
static int gen_top4(const float *A, const float *B, float *w)
{
    float L[16] = {0};
    for (int i = 0; i < 4; i++) for (int j = 0; j <= i; j++) {
        float s = B[i * 4 + j];
        for (int k = 0; k < j; k++) s -= L[i * 4 + k] * L[j * 4 + k];
        if (i == j) { if (s <= 0.0f) return 0; L[i * 4 + i] = sqrtf(s); }
        else L[i * 4 + j] = s / L[j * 4 + j];
    }
    float T[16], C[16];
    /* T = L^-1 A  (forward substitution per column) */
    for (int c = 0; c < 4; c++) for (int i = 0; i < 4; i++) {
        float s = A[i * 4 + c];
        for (int k = 0; k < i; k++) s -= L[i * 4 + k] * T[k * 4 + c];
        T[i * 4 + c] = s / L[i * 4 + i];
    }
    /* C = T L^-T  ->  C^T = L^-1 T^T */
    for (int r = 0; r < 4; r++) for (int i = 0; i < 4; i++) {
        float s = T[r * 4 + i];
        for (int k = 0; k < i; k++) s -= L[i * 4 + k] * C[r * 4 + k];
        C[r * 4 + i] = s / L[i * 4 + i];
    }
    for (int i = 0; i < 4; i++) for (int j = 0; j < i; j++) { float a = 0.5f * (C[i * 4 + j] + C[j * 4 + i]); C[i * 4 + j] = C[j * 4 + i] = a; }
    float ev[4], V[16];
    jacobi(C, 4, ev, V);
    float u[4]; for (int i = 0; i < 4; i++) u[i] = V[i * 4 + 3];
    /* w = L^-T u  (back substitution) */
    for (int i = 3; i >= 0; i--) {
        float s = u[i];
        for (int k = i + 1; k < 4; k++) s -= L[k * 4 + i] * w[k];
        w[i] = s / L[i * 4 + i];
    }
    return 1;
}

static void unit4(float *w)           /* largest-|.| component positive, unit norm */
{
    int m = 0;
    for (int i = 1; i < 4; i++) if (fabsf(w[i]) > fabsf(w[m])) m = i;
    float sg = w[m] < 0 ? -1.0f : 1.0f, n = 0.0f;
    for (int i = 0; i < 4; i++) n += w[i] * w[i];
    n = sqrtf(n);
    if (n <= 0.0f) { w[0] = 1.0f; w[1] = w[2] = w[3] = 0.0f; return; }
    for (int i = 0; i < 4; i++) w[i] = sg * w[i] / n;
}
static void norm4(float *w)
{
    float n = 0.0f;
    for (int i = 0; i < 4; i++) n += w[i] * w[i];
    n = sqrtf(n);
    if (n <= 0.0f) { w[0] = 1.0f; w[1] = w[2] = w[3] = 0.0f; return; }
    for (int i = 0; i < 4; i++) w[i] /= n;
}

/* ─────────────────────────── threshold detector (detect2, no search-back) ─────── */
typedef struct {
    int det_start, warmup, refr, loc, rr_min;
    float peak, noise, wmax, wsum;
    int enabled, last;
    float e1, e2;            /* e[t-1], e[t-2] */
    float ab[32];            /* |y| ring, index t & 31 */
    int pend; float pend_v;  /* pending raw peak (can still be replaced) */
} det_t;

static void det_init(det_t *d, int det_start, int warmup, int refr, int loc, int rr_min)
{
    memset(d, 0, sizeof(*d));
    d->det_start = det_start; d->warmup = warmup; d->refr = refr; d->loc = loc; d->rr_min = rr_min;
    d->last = -1000000000; d->pend = -1;
}

/* one sample; returns a FINAL raw peak (>=0) or -1 */
static int det_step(det_t *d, int t, float e, float ab)
{
    int out = -1;
    d->ab[t & 31] = ab;
    if (t >= d->det_start) {
        if (t < d->det_start + d->warmup) {
            if (e > d->wmax) d->wmax = e;
            d->wsum += e;
            if (t == d->det_start + d->warmup - 1) {
                d->peak = d->wmax; d->noise = d->wsum / (float)d->warmup;
                d->enabled = d->peak > d->noise;
            }
        } else if (d->enabled && t >= 2) {
            int m = t - 1;
            float v = d->e1, vp = d->e2;
            if (vp < v && v >= e) {
                float thr = 0.25f * d->peak + 0.75f * d->noise;
                if (v > thr && m - d->last >= d->refr) {
                    int lo = t - (d->loc - 1); if (lo < 0) lo = 0;
                    int best = lo; float bv = d->ab[lo & 31];
                    for (int i = lo + 1; i <= t; i++) if (d->ab[i & 31] > bv) { bv = d->ab[i & 31]; best = i; }
                    if (d->pend >= 0 && best - d->pend < d->rr_min) {
                        if (bv > d->pend_v) { d->pend = best; d->pend_v = bv; }
                    } else {
                        out = d->pend;                  /* previous one is final now */
                        d->pend = best; d->pend_v = bv;
                    }
                    d->last = m;
                    d->peak += (v - d->peak) / 8.0f;
                } else if (v <= thr) {
                    d->noise += (v - d->noise) / 8.0f;
                }
            }
        }
    }
    d->e2 = d->e1; d->e1 = e;
    /* pending peak can no longer be replaced once t - (loc-1) - pend >= rr_min */
    if (out < 0 && d->pend >= 0 && t - (d->loc - 1) - d->pend >= d->rr_min) { out = d->pend; d->pend = -1; }
    return out;
}

/* ─────────────────────────── configuration ─────────────────────────── */
fecg_cfg_t fecg_cfg = {
    .mat_refr = 75, .mat_lo = 40.0f, .mat_hi = 130.0f,
    .gate = 1000.0f, .c0 = 0.3f, .c1 = 0.6f, .floor = 0.0f,
    .use_canc = 1, .use_rawT = 1, .use_rawD = 1, .mat_minfrac = 0.0f, .pen_minfrac = 0.1f, .cand_mask = 0xF0F, .sel_look = 5000, .hyst = 0.0f, .reg_pow = 2.0f,
};

/* ─────────────────────────── state ─────────────────────────── */
typedef struct {
    int kind;            /* 0 tracker, 1 threshold detector */
    int src;             /* 0 = Z (cancelled), 1 = Xf (raw) */
    int blank;           /* maternal blanking of the envelope */
    float w[4];
    sos_t bp; mwi_t mw; float ehold; int blank_until;
    uint16_t e[ERING];   /* envelope ring (bf16), index s % ERING */
    float bpr[BRING];    /* bp ring, index s & (BRING-1) */
    /* tracker */
    int st, t, R, ts, a, misses, nrr, namp, rrs[8]; float amps[8];
    int dec;             /* sample at which the next decision is due */
    int first_done, started;
    det_t det;
    /* beats + features */
    int pk[PKRING]; int8_t pcc[PKRING][31]; float pem[PKRING]; int npk; int nfeat;
    /* block medians of e for the prominence normaliser */
    float bmed[64]; int nb;
} track_t;

static struct {
    int T;                              /* input sample index */
    hp_t hp[NL], hpm[NL];
    sos_t lp[NL], mat[NL];
    int16_t xf[ZRING][NL];              /* Xf ring (unmodified) */
    int16_t z[ZRING][NL];               /* Z ring (maternal-cancelled) */
    /* maternal */
    float V[16]; int have_V; float pcfrac[NL];
    det_t mdet[NL]; mwi_t mmwi[NL];
    int mtr[NL][PKRING]; int nmtr[NL];  /* final peaks per train */
    int mk, mseg_t, mseg_end, mlast;    /* current train, segment [t, end) */
    float mrate_prev;
    int mpk[512]; int nmpk;             /* emitted maternal peaks (ring 512) */
    int mproc;                          /* next maternal peak to cancel */
    /* canceller history */
    int nhist, hhead;
    int32_t hsum[LSEG][NL];             /* exact sum of the history beats */
    float Q[NL][KHIST][2];              /* warm start of the top-2 eigenvectors per lead */
    float taper[LSEG];
    /* tracks */
    int ntr; int calibrated;
    sos_t bp0z, bp0x; mwi_t mw0z, mw0x;
    int mblank_ptr;
    /* selection */
    int sel_next, sel_k, sel_t, sel_end, out_last; int rrbuf[5], nrr;
    int emitted_upto; float fhr;
    int zc_ptr;                         /* next Z-time sample to copy into the calibration buffers */
} S;

static SLOWMEM int16_t HIST[KHIST][LSEG][NL];   /* canceller beat history */
static SLOWMEM float GRAW[NL][KHIST][KHIST];      /* raw Gram matrix of the history, per lead */
/* Buffers that are never alive at the same time share memory:
   before calibration: Zc/Xc (int16 calibration copies) + Ym (maternal init) / Yc (band-passed);
   after calibration: the trackers. */
static union {
    struct {
        int16_t Zc[CAL_LEN][NL], Xc[CAL_LEN][NL];
        union { float Ym[MAT_INIT][NL]; float Yc[CAL_LEN][NL]; } u;
    } c;
    track_t tr[MAXTR];
} U;
#define TR (U.tr)
#define Ym (U.c.u.Ym)
#define Yc (U.c.u.Yc)

/* ─────────────────────────── helpers ─────────────────────────── */
static float zget(int s, int l) { return (float)S.z[ZI(s)][l]; }
static float xget(int s, int l) { return (float)S.xf[ZI(s)][l]; }

static void train_stats(const int *pk, int npk, int t0, int t1, float *rate, float *reg)
{
    int p[PKRING], n = 0;
    int first = npk > PKRING ? npk - PKRING : 0;
    for (int i = first; i < npk; i++) { int v = pk[i % PKRING]; if (v >= t0 && v < t1) p[n++] = v; }
    *rate = 0.0f; *reg = 0.0f;
    if (n < 4) return;
    int rr[PKRING];
    for (int i = 0; i < n - 1; i++) rr[i] = p[i + 1] - p[i];
    float med = imedian(rr, n - 1);
    int ok = 0;
    for (int i = 0; i < n - 1; i++) if (fabsf((float)rr[i] - med) <= 0.15f * med) ok++;
    *rate = 60.0f * FS / med;
    *reg = (float)ok / (float)(n - 1);
}

static int mat_choose(int t, int prev)
{
    float rate[NL], reg[NL];
    int t0 = t - MAT_LOOK; if (t0 < 512) t0 = 512;
    for (int k = 0; k < NL; k++) train_stats(S.mtr[k], S.nmtr[k], t0, t, &rate[k], &reg[k]);
    int best = -1;
    for (int k = 0; k < NL; k++)
        if (reg[k] >= 0.6f && rate[k] >= fecg_cfg.mat_lo && rate[k] <= fecg_cfg.mat_hi && S.pcfrac[k] >= fecg_cfg.mat_minfrac &&
            (best < 0 || rate[k] < rate[best] * 0.9f)) best = k;
    if (best >= 0) return best;
    if (prev >= 0) return prev;
    best = 0;
    for (int k = 1; k < NL; k++) if (reg[k] > reg[best]) best = k;
    return best;
}

static void mat_emit(int p)
{
    if (S.nmpk > 0 && p - S.mpk[(S.nmpk - 1) & 511] < fecg_cfg.mat_refr) return;
    S.mpk[S.nmpk & 511] = p; S.nmpk++;
}

/* emit final peaks of the current train inside the current segment */
static void mat_flush(void)
{
    int k = S.mk, n = S.nmtr[k];
    int first = n > PKRING ? n - PKRING : 0;
    for (int i = first; i < n; i++) {
        int p = S.mtr[k][i % PKRING];
        if (p >= S.mseg_t && p < S.mseg_end && p > S.mlast) { mat_emit(p); S.mlast = p; }
    }
}

/* ─────────────────────────── maternal cancellation of one beat ─────────── */
/* top-2 eigenpairs of a symmetric n x n matrix by subspace iteration (warm-started) */
static void top2(const float *G, int n, float Q[][2], float *lam)
{
    float Z[KHIST][2];
    for (int it = 0; it < 12; it++) {
        for (int i = 0; i < n; i++) {
            float a = 0.0f, b = 0.0f;
            for (int j = 0; j < n; j++) { a += G[i * n + j] * Q[j][0]; b += G[i * n + j] * Q[j][1]; }
            Z[i][0] = a; Z[i][1] = b;
        }
        float n0 = 0.0f; for (int i = 0; i < n; i++) n0 += Z[i][0] * Z[i][0];
        n0 = sqrtf(n0); if (n0 <= 0.0f) n0 = 1.0f;
        float d = 0.0f;
        for (int i = 0; i < n; i++) { Q[i][0] = Z[i][0] / n0; d += Q[i][0] * Z[i][1]; }
        float n1 = 0.0f;
        for (int i = 0; i < n; i++) { Z[i][1] -= d * Q[i][0]; n1 += Z[i][1] * Z[i][1]; }
        n1 = sqrtf(n1); if (n1 <= 0.0f) n1 = 1.0f;
        for (int i = 0; i < n; i++) Q[i][1] = Z[i][1] / n1;
    }
    /* Rayleigh-Ritz on the 2-D subspace */
    float t00 = 0.0f, t01 = 0.0f, t11 = 0.0f;
    for (int i = 0; i < n; i++) {
        float a = 0.0f, b = 0.0f;
        for (int j = 0; j < n; j++) { a += G[i * n + j] * Q[j][0]; b += G[i * n + j] * Q[j][1]; }
        t00 += Q[i][0] * a; t01 += Q[i][0] * b; t11 += Q[i][1] * b;
    }
    float tr = 0.5f * (t00 + t11), df = 0.5f * (t00 - t11);
    float rad = sqrtf(df * df + t01 * t01);
    lam[0] = tr + rad; lam[1] = tr - rad;
    float c = 1.0f, sn = 0.0f;
    if (t01 != 0.0f) {
        float th = (t11 - t00) / (2.0f * t01);
        float t = (th >= 0 ? 1.0f : -1.0f) / (fabsf(th) + sqrtf(th * th + 1.0f));
        c = 1.0f / sqrtf(t * t + 1.0f); sn = t * c;
        /* rotation diagonalises T; pick the column with the larger eigenvalue first */
        float a0 = c * c * t00 - 2.0f * sn * c * t01 + sn * sn * t11;
        float a1 = sn * sn * t00 + 2.0f * sn * c * t01 + c * c * t11;
        for (int i = 0; i < n; i++) {
            float q0 = c * Q[i][0] - sn * Q[i][1], q1 = sn * Q[i][0] + c * Q[i][1];
            if (a0 >= a1) { Q[i][0] = q0; Q[i][1] = q1; } else { Q[i][0] = q1; Q[i][1] = q0; }
        }
    }
}

static void cancel_beat(int p)
{
    static float seg[LSEG][NL];
    static float mu[LSEG], basis[3][LSEG], G[KHIST * KHIST];
    int lag = 0;
    int nh = S.nhist < KHIST ? S.nhist : KHIST;
    if (nh >= 1) {
        float bc = 0.0f; int bk = 0;
        for (int k = -SEARCH; k <= SEARCH; k++) {
            float c = 0.0f;
            int zi = ZI(p + k - L1);
            for (int i = 0; i < LSEG; i++) {
                for (int l = 0; l < NL; l++) c += (float)S.xf[zi][l] * ((float)S.hsum[i][l] / (float)nh);
                if (++zi == ZRING) zi = 0;
            }
            if (k == -SEARCH || c > bc) { bc = c; bk = k; }
        }
        lag = bk;
    }
    p += lag;
    {
        int zi = ZI(p - L1);
        for (int i = 0; i < LSEG; i++) {
            for (int l = 0; l < NL; l++) seg[i][l] = (float)S.xf[zi][l];
            if (++zi == ZRING) zi = 0;
        }
    }
    if (nh >= WARMB) {
        for (int l = 0; l < NL; l++) {
            for (int i = 0; i < LSEG; i++) mu[i] = (float)S.hsum[i][l] / (float)nh;
            int nb = 1;
            memcpy(basis[0], mu, sizeof(mu));
            if (nh >= 3) {
                /* centred Gram from the raw Gram: G_ab = R_ab - r_a - r_b + m, r_a = (1/n) sum_b R_ab */
                float r[KHIST], m = 0.0f;
                for (int a = 0; a < nh; a++) { float t = 0.0f; for (int b = 0; b < nh; b++) t += GRAW[l][a][b]; r[a] = t / (float)nh; m += r[a]; }
                m /= (float)nh;
                for (int a = 0; a < nh; a++) for (int b = 0; b < nh; b++) G[a * nh + b] = GRAW[l][a][b] - r[a] - r[b] + m;
                if (S.Q[l][0][0] == 0.0f && S.Q[l][1][1] == 0.0f) {
                    for (int a = 0; a < KHIST; a++) { S.Q[l][a][0] = (a == 0); S.Q[l][a][1] = (a == 1); }
                }
                float lam[2];
                top2(G, nh, S.Q[l], lam);
                float lmax = lam[0] > 0.0f ? lam[0] : 1.0f;
                for (int c = 0; c < 2; c++) {
                    if (!(lam[c] > 1e-6f * lmax)) break;
                    float sv = sqrtf(lam[c]);
                    for (int i = 0; i < LSEG; i++) basis[nb][i] = 0.0f;
                    for (int h = 0; h < nh; h++) {
                        float qh = S.Q[l][h][c] / sv;
                        for (int i = 0; i < LSEG; i++) basis[nb][i] += ((float)HIST[h][i][l] - mu[i]) * qh;
                    }
                    nb++;
                }
            }
            /* least squares: (B^T B) c = B^T seg */
            float M[3][4] = {{0}};
            for (int a = 0; a < nb; a++) {
                for (int b = 0; b < nb; b++) { float t = 0.0f; for (int i = 0; i < LSEG; i++) t += basis[a][i] * basis[b][i]; M[a][b] = t; }
                float t = 0.0f; for (int i = 0; i < LSEG; i++) t += basis[a][i] * seg[i][l]; M[a][3] = t;
            }
            float coef[3] = {0};
            int ok = 1;
            for (int c = 0; c < nb; c++) {           /* Gauss-Jordan with partial pivot */
                int pv = c;
                for (int rr = c + 1; rr < nb; rr++) if (fabsf(M[rr][c]) > fabsf(M[pv][c])) pv = rr;
                if (fabsf(M[pv][c]) < 1e-20f) { ok = 0; break; }
                if (pv != c) for (int j = 0; j < 4; j++) { float t = M[c][j]; M[c][j] = M[pv][j]; M[pv][j] = t; }
                for (int rr = 0; rr < nb; rr++) if (rr != c) {
                    float f = M[rr][c] / M[c][c];
                    for (int j = c; j < 4; j++) M[rr][j] -= f * M[c][j];
                }
            }
            if (!ok) continue;
            for (int c = 0; c < nb; c++) coef[c] = M[c][3] / M[c][c];
            int zi = ZI(p - L1);
            for (int i = 0; i < LSEG; i++) {
                float fit = 0.0f; for (int c = 0; c < nb; c++) fit += coef[c] * basis[c][i];
                S.z[zi][l] = sat16(seg[i][l] - fit * S.taper[i]);
                if (++zi == ZRING) zi = 0;
            }
        }
    }
    /* history ring (most recent KHIST beats): exact sums + raw Gram row of the new beat */
    int hh = S.hhead;
    for (int i = 0; i < LSEG; i++) for (int l = 0; l < NL; l++) {
        if (S.nhist >= KHIST) S.hsum[i][l] -= HIST[hh][i][l];
        int16_t v = (int16_t)seg[i][l];
        HIST[hh][i][l] = v;
        S.hsum[i][l] += v;
    }
    int nn = S.nhist < KHIST ? S.nhist + 1 : KHIST;
    for (int l = 0; l < NL; l++)
        for (int b = 0; b < nn; b++) {
            float t = 0.0f;
            for (int i = 0; i < LSEG; i++) t += seg[i][l] * (float)HIST[b][i][l];
            GRAW[l][hh][b] = t; GRAW[l][b][hh] = t;
        }
    S.hhead = (S.hhead + 1) % KHIST;
    if (S.nhist < KHIST) S.nhist++;
}

/* ─────────────────────────── calibration (candidates) ─────────────────── */

static void cal_bandpass(int src)
{
    sos_t f[NL]; memset(f, 0, sizeof(f));
    for (int i = 0; i < CAL_LEN; i++) for (int l = 0; l < NL; l++) {
        float x = (float)(src ? U.c.Xc[i][l] : U.c.Zc[i][l]);
        Yc[i][l] = sos_step(BP_SOS, BP_SOS_NS, &f[l], x);
    }
}

static int cal_mpk(int *m)    /* maternal peaks in [CAL_BEGIN+512, CAL_END) relative to CAL_BEGIN */
{
    int n = 0, first = S.nmpk > 512 ? S.nmpk - 512 : 0;
    for (int i = first; i < S.nmpk; i++) { int p = S.mpk[i & 511]; if (p >= CAL_BEGIN + CAL_WARM && p < CAL_END) m[n++] = p - CAL_BEGIN; }
    return n;
}

/* AB.detect on y = Yc @ w (warm-up 512 from 0, mwi 30, refractory/rr_min 50, loc 26) */
static int cal_detect(const float *w, int *pk, int maxpk)
{
    det_t d; mwi_t mw; memset(&mw, 0, sizeof(mw)); mw.w = 30;
    det_init(&d, 0, CAL_WARM, 50, 26, 50);
    int n = 0;
    for (int t = 0; t < CAL_LEN; t++) {
        float y = Yc[t][0] * w[0] + Yc[t][1] * w[1] + Yc[t][2] * w[2] + Yc[t][3] * w[3];
        int p = det_step(&d, t, mwi_step(&mw, y * y), fabsf(y));
        if (p >= 0 && n < maxpk) pk[n++] = p;
    }
    if (d.pend >= 0 && n < maxpk) pk[n++] = d.pend;
    return n;
}

static void refine(const float *C2, const float *w0, const int *m, int nm, float *wout)
{
    float w[4]; memcpy(w, w0, sizeof(w)); unit4(w);
    for (int it = 0; it < 3; it++) {
        int pk[256], n = cal_detect(w, pk, 256), k = 0;
        for (int i = 0; i < n; i++) {
            if (pk[i] < CAL_WARM) continue;
            int near = 0;
            for (int j = 0; j < nm; j++) if (abs(pk[i] - m[j]) <= 6) { near = 1; break; }
            if (!near) pk[k++] = pk[i];
        }
        if (k < 4) break;
        float Cf[16] = {0}; int cnt = 0;
        for (int i = 0; i < k; i++) for (int o = -4; o <= 4; o++) {
            int t = pk[i] + o;
            if (t < 0 || t >= CAL_LEN) continue;
            for (int a = 0; a < 4; a++) for (int b = 0; b < 4; b++) Cf[a * 4 + b] += Yc[t][a] * Yc[t][b];
            cnt++;
        }
        for (int a = 0; a < 16; a++) Cf[a] /= (float)(cnt > 0 ? cnt : 1);
        float wn[4];
        if (!gen_top4(Cf, C2, wn)) break;
        unit4(wn); memcpy(w, wn, sizeof(w));
    }
    memcpy(wout, w, sizeof(w));
}

static void track_setup(track_t *tr, int kind, int src, int blank, const float *w)
{
    memset(tr, 0, sizeof(*tr));
    tr->kind = kind; tr->src = src; tr->blank = blank;
    memcpy(tr->w, w, sizeof(tr->w)); norm4(tr->w);
    tr->bp = src ? S.bp0x : S.bp0z;
    tr->mw = src ? S.mw0x : S.mw0z;
    tr->st = 0; tr->dec = T0_TRACK + 1000 - 1;
    if (kind == 1) det_init(&tr->det, T0_TRACK, 512, 50, 26, 50);
}

static void calibrate(void)
{
    int m[64], nm = cal_mpk(m);
    static float cands[2][12][4];
    S.ntr = 0;
    for (int src = 0; src < 2; src++) {
        if (src == 0 && !fecg_cfg.use_canc) continue;
        if (src == 1 && !fecg_cfg.use_rawT && !fecg_cfg.use_rawD) continue;
        cal_bandpass(src);
        float C[16] = {0};
        for (int t = CAL_WARM; t < CAL_LEN; t++) for (int a = 0; a < 4; a++) for (int b = 0; b < 4; b++) C[a * 4 + b] += Yc[t][a] * Yc[t][b];
        for (int a = 0; a < 16; a++) C[a] /= (float)(CAL_LEN - CAL_WARM);
        float A[16], ev[4], V[16], C2[16];
        memcpy(A, C, sizeof(A)); jacobi(A, 4, ev, V);
        float tr_ = C[0] + C[5] + C[10] + C[15];
        memcpy(C2, C, sizeof(C2));
        for (int i = 0; i < 4; i++) C2[i * 4 + i] += 1e-6f * tr_ / 4.0f;
        float (*cd)[4] = cands[src]; int nc = 0;
        for (int i = 0; i < 4; i++) { for (int j = 0; j < 4; j++) cd[nc][j] = (i == j); nc++; }
        for (int j = 0; j < 4; j++) { for (int i = 0; i < 4; i++) cd[nc][i] = V[i * 4 + j]; nc++; }
        for (int j = 0; j < 4; j++) { float v0[4]; for (int i = 0; i < 4; i++) v0[i] = V[i * 4 + j]; refine(C2, v0, m, nm, cd[nc]); nc++; }
    }
    /* the trackers overwrite the calibration buffers (shared memory): set them up last */
    if (fecg_cfg.use_canc)
        for (int c = 0; c < 12; c++) if (((fecg_cfg.cand_mask >> c) & 1) && S.ntr < MAXTR) track_setup(&TR[S.ntr++], 0, 0, 1, cands[0][c]);
    if (fecg_cfg.use_rawT) for (int c = 8; c < 12 && S.ntr < MAXTR; c++) track_setup(&TR[S.ntr++], 0, 1, 0, cands[1][c]);
    if (fecg_cfg.use_rawD) for (int c = 8; c < 12 && S.ntr < MAXTR; c++) track_setup(&TR[S.ntr++], 1, 1, 0, cands[1][c]);
    S.calibrated = 1;
}

/* ─────────────────────────── tracker ─────────────────────────── */
static float eget(track_t *tr, int s) { return bf2f(tr->e[s % ERING]); }

static int autocorr_rr(track_t *tr, int ts, int len)
{
    float mean = 0.0f;
    for (int i = 0; i < len; i++) mean += eget(tr, ts + i);
    mean /= (float)len;
    int lo = FS * 60 / 200, hi = FS * 60 / 90;          /* 75 .. 166 */
    int best = lo; float bv = -1e38f;
    for (int lag = lo; lag <= hi; lag++) {
        float s = 0.0f;
        for (int i = 0; i + lag < len; i++) s += (eget(tr, ts + i) - mean) * (eget(tr, ts + i + lag) - mean);
        if (s > bv) { bv = s; best = lag; }
    }
    return best;
}

static int localise(track_t *tr, int m)
{
    int lo = m - 25, best = lo; float bv = fabsf(tr->bpr[lo & (BRING - 1)]);
    for (int i = lo + 1; i <= m; i++) { float v = fabsf(tr->bpr[i & (BRING - 1)]); if (v > bv) { bv = v; best = i; } }
    return best;
}

#ifdef FECG_DEBUG
void (*fecg_dbg_beat)(int k, int q) = 0;
#endif
static void add_beat(track_t *tr, int q)
{
#ifdef FECG_DEBUG
    if (fecg_dbg_beat) fecg_dbg_beat((int)(tr - TR), q);
#endif
    tr->pk[tr->npk % PKRING] = q; tr->npk++;
}

static int argmax_e(track_t *tr, int lo, int hi)   /* inclusive */
{
    int m = lo; float v = eget(tr, lo);
    for (int i = lo + 1; i <= hi; i++) if (eget(tr, i) > v) { v = eget(tr, i); m = i; }
    return m;
}

static float amp_median(track_t *tr)
{
    float b[8]; int n = tr->namp < 8 ? tr->namp : 8;
    for (int i = 0; i < n; i++) b[i] = tr->amps[(tr->namp - n + i) & 7];
    return fmedian(b, n);
}
static int rr_median5(track_t *tr)
{
    int b[5]; int n = tr->nrr < 5 ? tr->nrr : 5;
    for (int i = 0; i < n; i++) b[i] = tr->rrs[(tr->nrr - n + i) & 7];
    float m = imedian(b, n);
    if (m < 60.0f) m = 60.0f;
    if (m > 190.0f) m = 190.0f;
    return (int)m;
}

/* states: 0 wait autocorr at dec, 1 wait anchor at dec, 2 running (decision at dec) */
static void tracker_step(track_t *tr, int s)
{
    if (s != tr->dec) return;
    for (;;) {
        if (tr->st == 0) {
            int ts = tr->ts;
            tr->R = autocorr_rr(tr, ts, 1000);
            tr->a = ts + 1000;
            tr->st = 1; tr->dec = tr->a + tr->R - 1;
            if (tr->dec > s) return;
        }
        if (tr->st == 1) {
            int m = argmax_e(tr, tr->a, tr->a + tr->R - 1);
            tr->t = m;
            if (tr->first_done == 0) { add_beat(tr, localise(tr, m)); tr->first_done = 1; }
            else { if (tr->R < 60) tr->R = 60; if (tr->R > 190) tr->R = 190; }
            tr->nrr = 0; tr->rrs[tr->nrr++ & 7] = tr->R;
            tr->namp = 0; tr->amps[tr->namp++ & 7] = eget(tr, m);
            tr->misses = 0;
            tr->st = 2; tr->dec = tr->t + (13 * tr->R) / 10;
            if (tr->dec > s) return;
        }
        if (tr->st == 2) {
            int lo = tr->t + (7 * tr->R) / 10, hi = tr->t + (13 * tr->R) / 10;
            int m = argmax_e(tr, lo, hi);
            if (eget(tr, m) > 0.25f * amp_median(tr)) {
                int rr = m - tr->t;
                tr->t = m;
                add_beat(tr, localise(tr, m));
                tr->amps[tr->namp++ & 7] = eget(tr, m);
                tr->rrs[tr->nrr++ & 7] = rr;
                tr->R = rr_median5(tr);
                tr->misses = 0;
            } else {
                tr->t += tr->R;
                tr->misses++;
                if (tr->misses >= 4) {
                    int ts = tr->t - 1000; if (ts < T0_TRACK) ts = T0_TRACK;
                    tr->ts = ts; tr->st = 0; tr->dec = ts + 999;
                    if (tr->dec > s) return;
                    continue;
                }
            }
            tr->dec = tr->t + (13 * tr->R) / 10;
            if (tr->dec > s) return;
        }
    }
}

/* ─────────────────────────── deterministic log (same result on PC and MicroBlaze) ── */
static float mylogf(float x)
{
    if (!(x > 0.0f)) return -1e30f;
    int e; float m = frexpf(x, &e);           /* x = m 2^e, m in [0.5,1) */
    if (m < 0.70710678f) { m *= 2.0f; e -= 1; }
    float z = (m - 1.0f) / (m + 1.0f), z2 = z * z;
    float s = z * (2.0f + z2 * (0.6666667f + z2 * (0.4f + z2 * (0.2857143f + z2 * 0.2222222f))));
    return s + (float)e * 0.69314718f;
}

/* ─────────────────────────── features / selection ─────────────────────────── */
static void capture_features(track_t *tr, int s)
{
    while (tr->nfeat < tr->npk) {
        int q = tr->pk[tr->nfeat % PKRING];
        if (s < q + 40) break;
        int8_t *w = tr->pcc[tr->nfeat % PKRING];
        float mx = 0.0f;
        for (int i = 0; i < 31; i++) { float v = fabsf(tr->bpr[(q - 15 + i) & (BRING - 1)]); if (v > mx) mx = v; }
        float sc = mx > 0.0f ? 127.0f / mx : 0.0f;
        for (int i = 0; i < 31; i++) w[i] = (int8_t)floorf(tr->bpr[(q - 15 + i) & (BRING - 1)] * sc + 0.5f);
        float m = eget(tr, q + 13);
        for (int i = q + 14; i < q + 40; i++) if (eget(tr, i) > m) m = eget(tr, i);
        tr->pem[tr->nfeat % PKRING] = m;
        tr->nfeat++;
    }
}

static float window_quality(track_t *tr, int t0, int t1)
{
    int idx[PKRING], n = 0;
    int first = tr->npk > PKRING ? tr->npk - PKRING : 0;
    for (int i = first; i < tr->npk; i++) { int q = tr->pk[i % PKRING]; if (q >= t0 + 16 && q < t1 - 16 && i < tr->nfeat) idx[n++] = i; }
    if (n < 4) return 0.0f;
    int rr[PKRING];
    for (int i = 0; i < n - 1; i++) rr[i] = tr->pk[idx[i + 1] % PKRING] - tr->pk[idx[i] % PKRING];
    float R = imedian(rr, n - 1);
    float rate = 60.0f * FS / R;
    if (rate < 80.0f || rate > 220.0f) return 0.0f;
    float expct = (float)(t1 - t0) / R; if (expct < 1.0f) expct = 1.0f;
    float acc = (float)n / expct; if (acc > 1.0f) acc = 1.0f;
    float T[31], col[PKRING];
    for (int j = 0; j < 31; j++) { for (int i = 0; i < n; i++) col[i] = (float)tr->pcc[idx[i] % PKRING][j]; T[j] = fmedian(col, n); }
    float tm = 0.0f; for (int j = 0; j < 31; j++) tm += T[j]; tm /= 31.0f;
    float tn = 0.0f; for (int j = 0; j < 31; j++) { T[j] -= tm; tn += T[j] * T[j]; }
    tn = sqrtf(tn);
    float cc[PKRING], em[PKRING];
    for (int i = 0; i < n; i++) {
        const int8_t *w = tr->pcc[idx[i] % PKRING];
        float wm = 0.0f; for (int j = 0; j < 31; j++) wm += (float)w[j]; wm /= 31.0f;
        float d = 0.0f, wn = 0.0f;
        for (int j = 0; j < 31; j++) { float a = (float)w[j] - wm; d += a * T[j]; wn += a * a; }
        cc[i] = d / (sqrtf(wn) * tn + 1e-12f);
        em[i] = tr->pem[idx[i] % PKRING];
    }
    float c = fmedian(cc, n);
    float pe = fmedian(em, n);
    /* prominence normaliser: median of the 125-sample block medians inside [t0, t1) */
    float bm[64]; int nb = 0;
    int nbk = tr->nb < 64 ? tr->nb : 64;
    for (int i = 0; i < nbk && i < (t1 - t0) / 125; i++) bm[nb++] = tr->bmed[(tr->nb - 1 - i) & 63];
    float med = nb ? fmedian(bm, nb) : 0.0f;
    float prom = pe / (med + 1e-12f);
    if (c < 0.0f) c = 0.0f;
    float q = c * acc * mylogf(1.0f + prom);
    if (fecg_cfg.reg_pow > 0.0f) {
        int ok = 0;
        for (int i = 0; i < n - 1; i++) if (fabsf((float)rr[i] - R) <= 0.15f * R) ok++;
        float reg = (float)ok / (float)(n - 1);
        for (int i = 0; i < (int)fecg_cfg.reg_pow; i++) q *= reg;
    }
    return q;
}

static float coincidence_penalty(track_t *tr, int t0, int t1)
{
    int m[64], nm = 0, first = S.nmpk > 512 ? S.nmpk - 512 : 0;
    for (int i = first; i < S.nmpk && nm < 64; i++) { int p = S.mpk[i & 511]; if (p >= t0 - 20 && p < t1 + 20) m[nm++] = p; }
    float mr = 1e9f;
    if (nm > 3) { int rr[64]; for (int i = 0; i < nm - 1; i++) rr[i] = m[i + 1] - m[i]; mr = 60.0f * FS / imedian(rr, nm - 1); }
    if (!(mr < fecg_cfg.gate) || S.mk < 0 || S.pcfrac[S.mk] < fecg_cfg.pen_minfrac) return 1.0f;
    int n = 0, hit = 0, f = tr->npk > PKRING ? tr->npk - PKRING : 0;
    for (int i = f; i < tr->npk; i++) {
        int q = tr->pk[i % PKRING];
        if (q < t0 || q >= t1) continue;
        n++;
        for (int j = 0; j < nm; j++) if (abs(m[j] - q) <= 12) { hit++; break; }
    }
    float c = n ? (float)hit / (float)n : 0.0f;
    float pen = (fecg_cfg.c1 - c) / (fecg_cfg.c1 - fecg_cfg.c0);
    if (pen < 0.0f) pen = 0.0f;
    if (pen > 1.0f) pen = 1.0f;
    if (pen < fecg_cfg.floor) pen = fecg_cfg.floor;
    return pen;
}

static int emit_beats(fecg_beat_t *out, int nout, int max_out)
{
    if (S.sel_k < 0) return nout;
    track_t *tr = &TR[S.sel_k];
    int first = tr->npk > PKRING ? tr->npk - PKRING : 0;
    for (int i = first; i < tr->npk && nout < max_out; i++) {
        int q = tr->pk[i % PKRING];
        if (q < S.sel_t || q >= S.sel_end || q <= S.out_last) continue;
        S.out_last = q;
        int tb = q - LAT_OUT; if (tb < 0) tb = 0;
        if (S.emitted_upto >= 0) {
            int rr = tb - S.emitted_upto;
            if (rr >= 50 && rr <= 300) {
                if (S.nrr < 5) S.rrbuf[S.nrr++] = rr;
                else { for (int k = 0; k < 4; k++) S.rrbuf[k] = S.rrbuf[k + 1]; S.rrbuf[4] = rr; }
                S.fhr = 60.0f * FS / imedian(S.rrbuf, S.nrr);
            }
        }
        S.emitted_upto = tb;
        out[nout].t = (uint32_t)tb;
        out[nout].fhr_x10 = (uint16_t)(S.fhr * 10.0f + 0.5f);
        out[nout].src = (uint8_t)S.sel_k;
        out[nout].flags = 0;
        nout++;
    }
    return nout;
}

static int do_select(int t, fecg_beat_t *out, int nout, int max_out)
{
    nout = emit_beats(out, nout, max_out);        /* flush the old segment */
    int best = 0; float bq = -1.0f;
    for (int k = 0; k < S.ntr; k++) {
        int lk = fecg_cfg.sel_look;
        float q = window_quality(&TR[k], t - lk, t) * coincidence_penalty(&TR[k], t - lk, t);
        if (k == S.sel_k) q *= 1.0f + fecg_cfg.hyst;
        if (q > bq) { bq = q; best = k; }
    }
    S.sel_k = best; S.sel_t = t; S.sel_end = t + SEL_HOP;
    return nout;
}

/* ─────────────────────────── per-sample driver ─────────────────────────── */
void fecg_reset(void)
{
    memset(&S, 0, sizeof(S));
    memset(&U, 0, sizeof(U));
    memset(HIST, 0, sizeof(HIST));
    memset(GRAW, 0, sizeof(GRAW));
    for (int i = 0; i < LSEG; i++) S.taper[i] = 1.0f;
    for (int i = 0; i < 8; i++) { S.taper[i] = (float)i / 7.0f; S.taper[LSEG - 1 - i] = (float)i / 7.0f; }
    S.mw0z.w = S.mw0x.w = 30;
    S.mk = -1; S.mlast = -1; S.mseg_t = S.mseg_end = 0;
    S.sel_k = -1; S.sel_next = SEL_START; S.out_last = -1; S.emitted_upto = -1;
    S.zc_ptr = CAL_BEGIN;
}

static void mat_det_step(int t, const float *ym)
{
    for (int k = 0; k < NL; k++) {
        const int col = NL - 1 - k;                     /* PC1 = largest eigenvalue */
        float y = 0.0f;
        for (int l = 0; l < NL; l++) y += ym[l] * S.V[l * 4 + col];
        int p = det_step(&S.mdet[k], t, mwi_step(&S.mmwi[k], y * y), fabsf(y));
        if (p >= 0) { S.mtr[k][S.nmtr[k] % PKRING] = p; S.nmtr[k]++; }
    }
}

int fecg_push(const int16_t x[4], fecg_beat_t *out, int max_out)
{
    int T = S.T, nout = 0;
    const int refr = fecg_cfg.mat_refr, lagm = refr + MAT_LOC - 1;
    float ym[NL];
    for (int l = 0; l < NL; l++) {
        float h = hp_step(&S.hp[l], (float)x[l]);
        float xf = sos_step(LP_SOS, LP_SOS_NS, &S.lp[l], h);
        S.xf[ZI(T)][l] = sat16(xf);
        S.z[ZI(T)][l] = sat16(xf);
        ym[l] = sos_step(MAT_SOS, MAT_SOS_NS, &S.mat[l], h);
    }
    /* 2. maternal detection */
    if (T < MAT_INIT) {
        memcpy(Ym[T], ym, sizeof(ym));
        if (T == MAT_INIT - 1) {
            float C[16] = {0}, ev[4];
            for (int t = 256; t < MAT_INIT; t++) for (int a = 0; a < 4; a++) for (int b = 0; b < 4; b++) C[a * 4 + b] += Ym[t][a] * Ym[t][b];
            jacobi(C, 4, ev, S.V);
            { float es = 1e-30f; for (int k = 0; k < NL; k++) es += ev[k] > 0 ? ev[k] : 0; for (int k = 0; k < NL; k++) S.pcfrac[k] = (ev[NL - 1 - k] > 0 ? ev[NL - 1 - k] : 0) / es; }
            for (int k = 0; k < NL; k++) { det_init(&S.mdet[k], 0, 512, refr, MAT_LOC, refr); memset(&S.mmwi[k], 0, sizeof(mwi_t)); S.mmwi[k].w = MAT_MWI; }
            for (int t = 0; t < MAT_INIT; t++) mat_det_step(t, Ym[t]);
            S.have_V = 1;
        }
    } else {
        mat_det_step(T, ym);
    }
    if (S.have_V) {
        if (T == MAT_INIT + lagm) {
            int k0 = mat_choose(MAT_INIT, -1);
            int n = S.nmtr[k0], f = n > PKRING ? n - PKRING : 0;
            for (int i = f; i < n; i++) { int p = S.mtr[k0][i % PKRING]; if (p < MAT_INIT) { mat_emit(p); S.mlast = p; } }
            S.mk = mat_choose(MAT_INIT, k0); S.mseg_t = MAT_INIT; S.mseg_end = MAT_INIT + MAT_HOP;
        } else if (S.mk >= 0 && T == S.mseg_end + lagm) {
            mat_flush();
            S.mk = mat_choose(S.mseg_end, S.mk); S.mseg_t = S.mseg_end; S.mseg_end += MAT_HOP;
        }
        if (S.mk >= 0) mat_flush();
    }
    /* 3. maternal cancellation (beat p is final and x[p+L2+SEARCH] has arrived) */
    while (S.mproc < S.nmpk) {
        int p = S.mpk[S.mproc & 511];
        if (p + L2 + SEARCH > T) break;
        if (p - L1 - SEARCH >= 0 && p - L1 - SEARCH > T - ZRING + 1) cancel_beat(p);
        S.mproc++;
    }
    /* calibration copies: Z(s) is final once s <= T - DZ and the start-up burst of
       maternal beats (all peaks before MAT_INIT, emitted at MAT_INIT + lagm) is cancelled */
    if (T > MAT_INIT + lagm + L2 + SEARCH)
        while (S.zc_ptr < CAL_END && S.zc_ptr <= T - DZ) {
            for (int l = 0; l < NL; l++) {
                U.c.Zc[S.zc_ptr - CAL_BEGIN][l] = S.z[ZI(S.zc_ptr)][l];
                U.c.Xc[S.zc_ptr - CAL_BEGIN][l] = S.xf[ZI(S.zc_ptr)][l];
            }
            S.zc_ptr++;
        }
    /* 4-6. Z-time processing */
    int s = T - DZ;
    if (s >= 0) {
        if (!S.calibrated) {
            if (s == CAL_END) calibrate();
            else {
                float bz = sos_step(BP_SOS, BP_SOS_NS, &S.bp0z, zget(s, 0)); mwi_step(&S.mw0z, bz * bz);
                float bx = sos_step(BP_SOS, BP_SOS_NS, &S.bp0x, xget(s, 0)); mwi_step(&S.mw0x, bx * bx);
            }
        }
        if (S.calibrated) {
            int bstart = 0;
            while (S.mblank_ptr < S.nmpk && S.mpk[S.mblank_ptr & 511] <= s) { if (S.mpk[S.mblank_ptr & 511] == s) bstart = 1; S.mblank_ptr++; }
            float r = (float)(s - (CAL_END - 1)); if (r > 64.0f) r = 64.0f; r /= 64.0f;
            const int zis = ZI(s);
            for (int k = 0; k < S.ntr; k++) {
                track_t *tr = &TR[k];
                float y = 0.0f;
                for (int l = 0; l < NL; l++) {
                    float w0 = (l == 0) ? 1.0f : 0.0f, w = w0 + r * (tr->w[l] - w0);
                    y += w * (float)(tr->src ? S.xf[zis][l] : S.z[zis][l]);
                }
                float bp = sos_step(BP_SOS, BP_SOS_NS, &tr->bp, y);
                float e = mwi_step(&tr->mw, bp * bp);
                if (tr->blank) {
                    if (bstart) { tr->ehold = eget(tr, s - 1); tr->blank_until = s + 45; }
                    if (s < tr->blank_until) e = tr->ehold;
                }
                tr->e[s % ERING] = f2bf(e);
                e = bf2f(tr->e[s % ERING]);
                tr->bpr[s & (BRING - 1)] = bp;
                if (tr->kind == 0) {
                    if (s >= T0_TRACK) { if (!tr->started) { tr->started = 1; tr->ts = T0_TRACK; } tracker_step(tr, s); }
                } else {
                    int p = det_step(&tr->det, s, e, fabsf(bp));
                    if (p >= 0) add_beat(tr, p);
                }
                capture_features(tr, s);
                if (s >= CAL_END + 124 && ((s + 1 - SEL_START) % 125 + 125) % 125 == 0) {
                    float b[125];
                    for (int i = 0; i < 125; i++) b[i] = eget(tr, s - 124 + i);
                    tr->bmed[tr->nb & 63] = fmedian(b, 125); tr->nb++;
                }
            }
            if (s == S.sel_next + SEL_LAG) { nout = do_select(S.sel_next, out, nout, max_out); S.sel_next += SEL_HOP; }
            nout = emit_beats(out, nout, max_out);
        }
    }
    S.T = T + 1;
    return nout;
}
