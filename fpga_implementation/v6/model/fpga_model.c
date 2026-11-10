/*
 * FECG v6 - bit-accurate model of the RTL (integer only).
 *
 * Everything that runs at the sample rate is here: filters, maternal detectors,
 * per-lead maternal cancellation (lag search, history sums, projection onto the
 * PC-supplied basis), 16 spatial projections, band-pass, energy envelopes,
 * blanking, beat trackers, threshold detectors, feature capture, envelope block
 * medians, output beats and FHR.  The low-rate decisions come from the PC brain
 * as responses to requests; the model stalls on a request until the response is
 * there, exactly like the hardware.
 *
 * Number formats: raw ADC int16; filter data Q8 in int32; coefficients Q28;
 * products/accumulators int64; Z and Xf stored as int16; envelopes stored as
 * 16-bit monotonic codes (enc_e, 8 significant bits).
 */
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include "proto.h"
#include "coef_q28.h"
#include "fpga_model.h"

typedef int64_t i64;

#define ZRING 4096
#define ZI(s) ((s) & (ZRING - 1))
#define ERING 2048
#define BRING 256
#define PKR 32           /* per-track beat ring (FPGA side) */
#define MPKR 96          /* maternal detector train ring */
#define MPKQ 512         /* emitted maternal peaks ring */

static i64 rnd(i64 a, int s) { return (a + ((i64)1 << (s - 1))) >> s; }
static int16_t sat16(i64 v) { return (int16_t)(v > 32767 ? 32767 : v < -32768 ? -32768 : v); }
static i64 iabs(i64 v) { return v < 0 ? -v : v; }

int fm_overflow;         /* set if any value leaves its declared hardware width */
static void chk(i64 v, int bits) { i64 m = (i64)1 << (bits - 1); if (v >= m || v < -m) fm_overflow = 1; }

/* ─────────── filters ─────────── */
typedef struct { i64 z1[4], z2[4]; } sos_t;
static int32_t sos_q(const int32_t (*c)[5], int ns, sos_t *s, int32_t x)
{
    i64 xv = x;
    for (int i = 0; i < ns; i++) {
        i64 y = rnd((i64)c[i][0] * xv + s->z1[i], 28);
        chk(y, 32);
        s->z1[i] = (i64)c[i][1] * xv - (i64)c[i][3] * y + s->z2[i];
        s->z2[i] = (i64)c[i][2] * xv - (i64)c[i][4] * y;
        chk(s->z1[i], 62); chk(s->z2[i], 62);
        xv = y;
    }
    return (int32_t)xv;
}
typedef struct { i64 B; } hp_t;                      /* baseline, Q16 */
static int32_t hp_q(hp_t *h, int x)                  /* returns Q8 */
{
    i64 y = ((i64)x << 8) - rnd(h->B, 8);
    h->B += (((i64)x << 16) - h->B) >> 6;
    return (int32_t)y;
}
typedef struct { i64 r[40]; int w, i; i64 sum; } mwi_t;
static i64 mwi_q(mwi_t *m, i64 sq)
{
    m->sum += sq - m->r[m->i];
    m->r[m->i] = sq;
    if (++m->i == m->w) m->i = 0;
    chk(m->sum, 62);
    return m->sum;
}

/* ─────────── threshold detector (integer version of v5 det_step) ─────────── */
typedef struct {
    int det_start, warmup, refr, loc, rr_min;
    i64 peak, noise, wmax, wsum;
    int enabled, last;
    i64 e1, e2;
    i64 ab[32];
    int pend; i64 pend_v;
} det_t;
static void det_init(det_t *d, int det_start, int warmup, int refr, int loc, int rr_min)
{
    memset(d, 0, sizeof(*d));
    d->det_start = det_start; d->warmup = warmup; d->refr = refr; d->loc = loc; d->rr_min = rr_min;
    d->last = -1000000000; d->pend = -1;
}
static int det_step(det_t *d, int t, i64 e, i64 ab)    /* warmup must be 512 */
{
    int out = -1;
    d->ab[t & 31] = ab;
    if (t >= d->det_start) {
        if (t < d->det_start + d->warmup) {
            if (e > d->wmax) d->wmax = e;
            d->wsum += e;
            if (t == d->det_start + d->warmup - 1) {
                d->peak = d->wmax; d->noise = d->wsum >> 9;
                d->enabled = d->peak > d->noise;
            }
        } else if (d->enabled && t >= 2) {
            int m = t - 1;
            i64 v = d->e1, vp = d->e2;
            if (vp < v && v >= e) {
                i64 thr = (d->peak + 3 * d->noise) >> 2;
                if (v > thr && m - d->last >= d->refr) {
                    int lo = t - (d->loc - 1); if (lo < 0) lo = 0;
                    int best = lo; i64 bv = d->ab[lo & 31];
                    for (int i = lo + 1; i <= t; i++) if (d->ab[i & 31] > bv) { bv = d->ab[i & 31]; best = i; }
                    if (d->pend >= 0 && best - d->pend < d->rr_min) {
                        if (bv > d->pend_v) { d->pend = best; d->pend_v = bv; }
                    } else {
                        out = d->pend;
                        d->pend = best; d->pend_v = bv;
                    }
                    d->last = m;
                    d->peak += (v - d->peak) >> 3;
                } else if (v <= thr) {
                    d->noise += (v - d->noise) >> 3;
                }
            }
        }
    }
    d->e2 = d->e1; d->e1 = e;
    if (out < 0 && d->pend >= 0 && t - (d->loc - 1) - d->pend >= d->rr_min) { out = d->pend; d->pend = -1; }
    return out;
}

/* ─────────── state ─────────── */
typedef struct {
    int kind, src, blank;
    int wq[4];
    sos_t bp; mwi_t mw; uint16_t ehold; int blank_until;
    uint16_t e[ERING];
    int32_t bpr[BRING];
    int st, t, R, ts, a, misses, nrr, namp, rrs[8]; i64 amps[8];
    int dec, first_done, started;
    det_t det;
    int pk[PKR]; int npk, nfeat;
} track_t;

static struct {
    int T;
    hp_t hp[NL]; sos_t lp[NL], mat[NL];
    int16_t xf[ZRING][NL], z[ZRING][NL];
    int32_t Ym[MAT_INIT][NL];
    i64 cov[10];
    int Vq[NL][NL]; int have_V;
    det_t mdet[NL]; mwi_t mmwi[NL];
    int mtr[NL][MPKR]; int nmtr[NL];
    int mk, mseg_t, mseg_end, mlast;
    int mpk[MPKQ]; int nmpk, mproc;
    int nhist, hhead;
    int16_t hist[KHIST][LSEG][NL];
    int32_t hsum[LSEG][NL];
    int32_t tap[LSEG];                 /* Q15 */
    int ntr, calibrated;
    sos_t bp0z, bp0x; mwi_t mw0z, mw0x;
    int mblank_ptr;
    int sel_next, sel_k, sel_t, sel_end, out_last, rrbuf[5], nrr, emitted_upto, fhr_x10;
    int zc_ptr;
    track_t tr[MAXTR];
    /* response buffers (written by fm_rx) */
    int r_v, r_mk, r_basis, r_cal, r_sel;
    int rv_V[NL][NL], rv_mk, rv_nb[NL], rv_ntr, rv_sel;
    int32_t rv_bo[NL][3][LSEG];
    int rv_kind[MAXTR], rv_src[MAXTR], rv_blank[MAXTR], rv_w[MAXTR][4];
} S;

static fm_emit_fn EMIT;
static fm_need_fn NEED;

static void wait_rsp(int *flag, const char *what)
{
    if (!*flag) NEED();
    if (!*flag) { fprintf(stderr, "fpga_model: no response for %s at T=%d\n", what, S.T); exit(3); }
    *flag = 0;
}

void fm_rx(int cmd, const uint8_t *p, int len)
{
    (void)len;
    switch (cmd) {
    case C_RSP_V:
        for (int k = 0; k < NL; k++) for (int l = 0; l < NL; l++) S.rv_V[k][l] = get16s(p + 2 * (k * NL + l));
        S.r_v = 1; break;
    case C_RSP_MK: S.rv_mk = p[0]; S.r_mk = 1; break;
    case C_RSP_BASIS: {
        int o = 4;
        for (int l = 0; l < NL; l++) {
            S.rv_nb[l] = p[l];
            for (int c = 0; c < S.rv_nb[l]; c++) for (int i = 0; i < LSEG; i++) { S.rv_bo[l][c][i] = get24s(p + o); o += 3; }
        }
        S.r_basis = 1; break;
    }
    case C_RSP_CAL: {
        S.rv_ntr = p[0]; int o = 1;
        for (int k = 0; k < S.rv_ntr; k++) {
            S.rv_kind[k] = p[o]; S.rv_src[k] = p[o + 1]; S.rv_blank[k] = p[o + 2]; o += 3;
            for (int l = 0; l < 4; l++) { S.rv_w[k][l] = get16s(p + o); o += 2; }
        }
        S.r_cal = 1; break;
    }
    case C_RSP_SEL: S.rv_sel = p[0]; S.r_sel = 1; break;
    default: break;
    }
}

static void emit_u32(int cmd, uint32_t v) { uint8_t b[4]; put32(b, v); EMIT(cmd, b, 4); }

void fm_reset(fm_emit_fn emit, fm_need_fn need)
{
    EMIT = emit; NEED = need;
    memset(&S, 0, sizeof(S));
    for (int i = 0; i < LSEG; i++) S.tap[i] = 32768;
    for (int i = 0; i < 8; i++) { int v = (int)((i * 32768 + 3) / 7); S.tap[i] = v; S.tap[LSEG - 1 - i] = v; }
    S.mw0z.w = S.mw0x.w = 30;
    S.mk = -1; S.mlast = -1;
    S.sel_k = -1; S.sel_next = SEL_START; S.out_last = -1; S.emitted_upto = -1;
    S.zc_ptr = CAL_BEGIN;
}

/* ─────────── maternal ─────────── */
static void mat_det_step(int t, const int32_t *ym)
{
    for (int k = 0; k < NL; k++) {
        i64 acc = 0;
        for (int l = 0; l < NL; l++) acc += (i64)ym[l] * S.Vq[k][l];
        i64 y = rnd(acc, W_FRAC);
        chk(y, 32);
        int p = det_step(&S.mdet[k], t, mwi_q(&S.mmwi[k], y * y), iabs(y));
        if (p >= 0) {
            S.mtr[k][S.nmtr[k] % MPKR] = p; S.nmtr[k]++;
            uint8_t b[5]; b[0] = (uint8_t)k; put32(b + 1, (uint32_t)p); EMIT(C_MDET, b, 5);
        }
    }
}
static void mat_emit(int p)
{
    if (S.nmpk > 0 && p - S.mpk[(S.nmpk - 1) & (MPKQ - 1)] < MAT_REFR) return;
    S.mpk[S.nmpk & (MPKQ - 1)] = p; S.nmpk++;
    emit_u32(C_MPK, (uint32_t)p);
}
static void mat_flush(void)
{
    int k = S.mk, n = S.nmtr[k], first = n > MPKR ? n - MPKR : 0;
    for (int i = first; i < n; i++) {
        int p = S.mtr[k][i % MPKR];
        if (p >= S.mseg_t && p < S.mseg_end && p > S.mlast) { mat_emit(p); S.mlast = p; }
    }
}
static int req_mk(int t)
{
    emit_u32(C_REQ_MK, (uint32_t)t);
    wait_rsp(&S.r_mk, "MK");
    return S.rv_mk;
}

/* ─────────── maternal cancellation of one beat ─────────── */
static void cancel_beat(int p)
{
    int nh = S.nhist < KHIST ? S.nhist : KHIST, lag = 0;
    if (nh >= 1) {
        i64 bc = 0; int bk = 0;
        for (int k = -SEARCH; k <= SEARCH; k++) {
            i64 c = 0;
            for (int i = 0; i < LSEG; i++) for (int l = 0; l < NL; l++) c += (i64)S.xf[ZI(p + k - L1 + i)][l] * S.hsum[i][l];
            if (k == -SEARCH || c > bc) { bc = c; bk = k; }
        }
        lag = bk;
    }
    p += lag;
    int16_t seg[LSEG][NL];
    for (int i = 0; i < LSEG; i++) for (int l = 0; l < NL; l++) seg[i][l] = S.xf[ZI(p - L1 + i)][l];
    if (nh >= WARMB) {
        wait_rsp(&S.r_basis, "BASIS");
        for (int l = 0; l < NL; l++) {
            int nb = S.rv_nb[l];
            if (nb == 0) continue;
            i64 c[3];                                   /* projections, Q8 */
            for (int j = 0; j < nb; j++) { i64 a = 0; for (int i = 0; i < LSEG; i++) a += (i64)S.rv_bo[l][j][i] * seg[i][l]; chk(a, 48); c[j] = rnd(a, BO_FRAC - 8); }
            for (int i = 0; i < LSEG; i++) {
                i64 f = 0;
                for (int j = 0; j < nb; j++) f += c[j] * S.rv_bo[l][j][i];                    /* Q30 */
                i64 fq8 = rnd(f, BO_FRAC);
                i64 zq8 = ((i64)seg[i][l] << 8) - rnd(fq8 * S.tap[i], 15);
                S.z[ZI(p - L1 + i)][l] = sat16(rnd(zq8, 8));
            }
        }
    }
    /* history (most recent KHIST beats) */
    int hh = S.hhead;
    for (int i = 0; i < LSEG; i++) for (int l = 0; l < NL; l++) {
        if (S.nhist >= KHIST) S.hsum[i][l] -= S.hist[hh][i][l];
        S.hist[hh][i][l] = seg[i][l];
        S.hsum[i][l] += seg[i][l];
    }
    S.hhead = (S.hhead + 1) % KHIST;
    if (S.nhist < KHIST) S.nhist++;
    uint8_t b[4 + LSEG * NL * 2];
    put32(b, (uint32_t)p);
    for (int i = 0; i < LSEG; i++) for (int l = 0; l < NL; l++) put16(b + 4 + 2 * (i * NL + l), seg[i][l]);
    EMIT(C_SEG, b, sizeof(b));
}

/* ─────────── tracks ─────────── */
static uint16_t eget(track_t *tr, int s) { return tr->e[s & (ERING - 1)]; }

static int autocorr_rr(track_t *tr, int ts, int len)
{
    /* block floating point: scale so the largest value has 15 bits */
    uint16_t mx = 0;
    for (int i = 0; i < len; i++) if (eget(tr, ts + i) > mx) mx = eget(tr, ts + i);
    uint64_t vmax = dec_e(mx); int sh = 0;
    while ((vmax >> sh) >= 32768) sh++;
    static int32_t v[1000];
    i64 sum = 0;
    for (int i = 0; i < len; i++) { v[i] = (int32_t)(dec_e(eget(tr, ts + i)) >> sh); sum += v[i]; }
    for (int i = 0; i < len; i++) v[i] = (int32_t)((i64)len * v[i] - sum);     /* len * (v - mean) */
    int lo = FS * 60 / 200, hi = FS * 60 / 90, best = lo; i64 bv = 0;
    for (int lag = lo; lag <= hi; lag++) {
        i64 s = 0;
        for (int i = 0; i + lag < len; i++) s += (i64)v[i] * v[i + lag];
        if (lag == lo || s > bv) { bv = s; best = lag; }
    }
    return best;
}
static int localise(track_t *tr, int m)
{
    int lo = m - 25, best = lo; i64 bv = iabs(tr->bpr[lo & (BRING - 1)]);
    for (int i = lo + 1; i <= m; i++) { i64 v = iabs(tr->bpr[i & (BRING - 1)]); if (v > bv) { bv = v; best = i; } }
    return best;
}
static void add_beat(int k, int q)
{
    track_t *tr = &S.tr[k];
    tr->pk[tr->npk % PKR] = q; tr->npk++;
    uint8_t b[5]; b[0] = (uint8_t)k; put32(b + 1, (uint32_t)q); EMIT(C_BEAT, b, 5);
}
static int argmax_e(track_t *tr, int lo, int hi)
{
    int m = lo; uint16_t v = eget(tr, lo);
    for (int i = lo + 1; i <= hi; i++) if (eget(tr, i) > v) { v = eget(tr, i); m = i; }
    return m;
}
static void isort64(i64 *a, int n) { for (int i = 1; i < n; i++) { i64 v = a[i]; int j = i - 1; while (j >= 0 && a[j] > v) { a[j + 1] = a[j]; j--; } a[j + 1] = v; } }
static void isort(int *a, int n) { for (int i = 1; i < n; i++) { int v = a[i], j = i - 1; while (j >= 0 && a[j] > v) { a[j + 1] = a[j]; j--; } a[j + 1] = v; } }
/* accept iff e > 0.25 * median(amps) */
static int amp_ok(track_t *tr, i64 e)
{
    i64 b[8]; int n = tr->namp < 8 ? tr->namp : 8;
    for (int i = 0; i < n; i++) b[i] = tr->amps[(tr->namp - n + i) & 7];
    isort64(b, n);
    if (n & 1) return 4 * e > b[n / 2];
    return 8 * e > b[n / 2 - 1] + b[n / 2];
}
static int rr_median5(track_t *tr)
{
    int b[5], n = tr->nrr < 5 ? tr->nrr : 5;
    for (int i = 0; i < n; i++) b[i] = tr->rrs[(tr->nrr - n + i) & 7];
    isort(b, n);
    int m = (n & 1) ? b[n / 2] : (b[n / 2 - 1] + b[n / 2]) >> 1;
    if (m < 60) m = 60;
    if (m > 190) m = 190;
    return m;
}
#define TRK_LO 70
#define TRK_HI 130
static void tracker_step(int k, int s)
{
    track_t *tr = &S.tr[k];
    if (s != tr->dec) return;
    for (;;) {
        if (tr->st == 0) {
            tr->R = autocorr_rr(tr, tr->ts, 1000);
            tr->a = tr->ts + 1000;
            tr->st = 1; tr->dec = tr->a + tr->R - 1;
            if (tr->dec > s) return;
        }
        if (tr->st == 1) {
            int m = argmax_e(tr, tr->a, tr->a + tr->R - 1);
            tr->t = m;
            if (!tr->first_done) { add_beat(k, localise(tr, m)); tr->first_done = 1; }
            else { if (tr->R < 60) tr->R = 60; if (tr->R > 190) tr->R = 190; }
            tr->nrr = 0; tr->rrs[tr->nrr++ & 7] = tr->R;
            tr->namp = 0; tr->amps[tr->namp++ & 7] = (i64)dec_e(eget(tr, m));
            tr->misses = 0;
            tr->st = 2; tr->dec = tr->t + (TRK_HI * tr->R) / 100;
            if (tr->dec > s) return;
        }
        if (tr->st == 2) {
            int lo = tr->t + (TRK_LO * tr->R) / 100, hi = tr->t + (TRK_HI * tr->R) / 100;
            int m = argmax_e(tr, lo, hi);
            i64 em = (i64)dec_e(eget(tr, m));
            if (amp_ok(tr, em)) {
                int rr = m - tr->t;
                tr->t = m;
                add_beat(k, localise(tr, m));
                tr->amps[tr->namp++ & 7] = em;
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
            tr->dec = tr->t + (TRK_HI * tr->R) / 100;
            if (tr->dec > s) return;
        }
    }
}
static void capture_features(int k, int s)
{
    track_t *tr = &S.tr[k];
    while (tr->nfeat < tr->npk) {
        int q = tr->pk[tr->nfeat % PKR];
        if (s < q + 40) break;
        uint8_t b[1 + 4 + 31 * 4 + 2];
        b[0] = (uint8_t)k; put32(b + 1, (uint32_t)q);
        for (int i = 0; i < 31; i++) put32(b + 5 + 4 * i, (uint32_t)tr->bpr[(q - 15 + i) & (BRING - 1)]);
        uint16_t m = eget(tr, q + 13);
        for (int i = q + 14; i < q + 40; i++) if (eget(tr, i) > m) m = eget(tr, i);
        put16(b + 5 + 124, m);
        EMIT(C_FEAT, b, sizeof(b));
        tr->nfeat++;
    }
}
static uint16_t median125(track_t *tr, int s)      /* 63rd smallest of e[s-124..s] */
{
    uint16_t b[125];
    for (int i = 0; i < 125; i++) b[i] = eget(tr, s - 124 + i);
    for (int i = 1; i < 125; i++) { uint16_t v = b[i]; int j = i - 1; while (j >= 0 && b[j] > v) { b[j + 1] = b[j]; j--; } b[j + 1] = v; }
    return b[62];
}

static void emit_beats(void)
{
    if (S.sel_k < 0) return;
    track_t *tr = &S.tr[S.sel_k];
    int first = tr->npk > PKR ? tr->npk - PKR : 0;
    for (int i = first; i < tr->npk; i++) {
        int q = tr->pk[i % PKR];
        if (q < S.sel_t || q >= S.sel_end || q <= S.out_last) continue;
        S.out_last = q;
        int tb = q - LAT_OUT; if (tb < 0) tb = 0;
        if (S.emitted_upto >= 0) {
            int rr = tb - S.emitted_upto;
            if (rr >= 50 && rr <= 300) {
                if (S.nrr < 5) S.rrbuf[S.nrr++] = rr;
                else { for (int j = 0; j < 4; j++) S.rrbuf[j] = S.rrbuf[j + 1]; S.rrbuf[4] = rr; }
                int b[5]; memcpy(b, S.rrbuf, sizeof(b)); isort(b, S.nrr);
                int n = S.nrr;
                if (n & 1) { int M = b[n / 2]; S.fhr_x10 = (300000 + M) / (2 * M); }
                else { int M2 = b[n / 2 - 1] + b[n / 2]; S.fhr_x10 = (600000 + M2) / (2 * M2); }
            }
        }
        S.emitted_upto = tb;
        uint8_t o[7]; put32(o, (uint32_t)tb); put16(o + 4, S.fhr_x10); o[6] = (uint8_t)S.sel_k;
        EMIT(C_OUT, o, 7);
    }
}

static void calibrate(void)
{
    EMIT(C_REQ_CAL, 0, 0);
    wait_rsp(&S.r_cal, "CAL");
    S.ntr = S.rv_ntr;
    for (int k = 0; k < S.ntr; k++) {
        track_t *tr = &S.tr[k];
        memset(tr, 0, sizeof(*tr));
        tr->kind = S.rv_kind[k]; tr->src = S.rv_src[k]; tr->blank = S.rv_blank[k];
        memcpy(tr->wq, S.rv_w[k], sizeof(tr->wq));
        tr->bp = tr->src ? S.bp0x : S.bp0z;
        tr->mw = tr->src ? S.mw0x : S.mw0z;
        tr->dec = T0_TRACK + 1000 - 1;
        if (tr->kind == 1) det_init(&tr->det, T0_TRACK, 512, 50, 26, 50);
    }
    S.calibrated = 1;
}

/* ─────────── per-sample driver ─────────── */
void fm_push(const int16_t x[4])
{
    int T = S.T;
    const int lagm = MAT_REFR + MAT_LOC - 1;
    int32_t ym[NL];
    for (int l = 0; l < NL; l++) {
        int32_t h = hp_q(&S.hp[l], x[l]);
        int32_t xf = sos_q(LP_Q, LP_NS, &S.lp[l], h);
        S.xf[ZI(T)][l] = S.z[ZI(T)][l] = sat16(rnd(xf, 8));
        ym[l] = sos_q(MAT_Q, MAT_NS, &S.mat[l], h);
    }
    /* maternal detection */
    if (T < MAT_INIT) {
        memcpy(S.Ym[T], ym, sizeof(ym));
        if (T >= MAT_COV0) { int c = 0; for (int a = 0; a < NL; a++) for (int b = a; b < NL; b++) S.cov[c++] += (i64)ym[a] * ym[b]; }
        if (T == MAT_INIT - 1) {
            uint8_t b[80]; for (int c = 0; c < 10; c++) put64(b + 8 * c, S.cov[c]);
            EMIT(C_COV, b, 80);
            wait_rsp(&S.r_v, "V");
            memcpy(S.Vq, S.rv_V, sizeof(S.Vq));
            for (int k = 0; k < NL; k++) { det_init(&S.mdet[k], 0, 512, MAT_REFR, MAT_LOC, MAT_REFR); memset(&S.mmwi[k], 0, sizeof(mwi_t)); S.mmwi[k].w = MAT_MWI; }
            for (int t = 0; t < MAT_INIT; t++) mat_det_step(t, S.Ym[t]);
            S.have_V = 1;
        }
    } else {
        mat_det_step(T, ym);
    }
    if (S.have_V) {
        if (T == MAT_INIT + lagm) {
            int k0 = req_mk(MAT_INIT);
            int n = S.nmtr[k0], f = n > MPKR ? n - MPKR : 0;
            for (int i = f; i < n; i++) { int p = S.mtr[k0][i % MPKR]; if (p < MAT_INIT) { mat_emit(p); S.mlast = p; } }
            S.mk = k0; S.mseg_t = MAT_INIT; S.mseg_end = MAT_INIT + MAT_HOP;
        } else if (S.mk >= 0 && T == S.mseg_end + lagm) {
            mat_flush();
            S.mk = req_mk(S.mseg_end); S.mseg_t = S.mseg_end; S.mseg_end += MAT_HOP;
        }
        if (S.mk >= 0) mat_flush();
    }
    /* maternal cancellation */
    while (S.mproc < S.nmpk) {
        int p = S.mpk[S.mproc & (MPKQ - 1)];
        if (p + L2 + SEARCH > T) break;
        if (p - L1 - SEARCH >= 0 && p - L1 - SEARCH > T - ZRING + 1) cancel_beat(p);
        S.mproc++;
    }
    /* calibration data to the PC */
    if (T > MAT_INIT + lagm + L2 + SEARCH && S.zc_ptr < CAL_END && S.zc_ptr <= T - DZ) {
        static uint8_t b[6 + 16 * 2048];
        int s0 = S.zc_ptr, n = 0;
        while (S.zc_ptr < CAL_END && S.zc_ptr <= T - DZ && n < 2048) {
            for (int l = 0; l < NL; l++) {
                put16(b + 6 + 16 * n + 2 * l, S.z[ZI(S.zc_ptr)][l]);
                put16(b + 6 + 16 * n + 8 + 2 * l, S.xf[ZI(S.zc_ptr)][l]);
            }
            S.zc_ptr++; n++;
        }
        put32(b, (uint32_t)s0); put16(b + 4, n);
        EMIT(C_CALDATA, b, 6 + 16 * n);
    }
    /* Z-time processing */
    int s = T - DZ;
    if (s >= 0) {
        if (!S.calibrated) {
            if (s == CAL_END) calibrate();
            else {
                int32_t bz = sos_q(BP_Q, BP_NS, &S.bp0z, (int32_t)S.z[ZI(s)][0] << 8);  mwi_q(&S.mw0z, (i64)bz * bz);
                int32_t bx = sos_q(BP_Q, BP_NS, &S.bp0x, (int32_t)S.xf[ZI(s)][0] << 8); mwi_q(&S.mw0x, (i64)bx * bx);
            }
        }
        if (S.calibrated) {
            int bstart = 0;
            while (S.mblank_ptr < S.nmpk && S.mpk[S.mblank_ptr & (MPKQ - 1)] <= s) { if (S.mpk[S.mblank_ptr & (MPKQ - 1)] == s) bstart = 1; S.mblank_ptr++; }
            int rr = s - (CAL_END - 1); if (rr > 64) rr = 64;
            for (int k = 0; k < S.ntr; k++) {
                track_t *tr = &S.tr[k];
                i64 acc = 0;
                for (int l = 0; l < NL; l++) {
                    int w0 = (l == 0) ? (1 << W_FRAC) : 0;
                    i64 w = (i64)w0 * 64 + (i64)(tr->wq[l] - w0) * rr;          /* Q20 */
                    acc += w * (tr->src ? S.xf[ZI(s)][l] : S.z[ZI(s)][l]);
                }
                int32_t y = (int32_t)rnd(acc, W_FRAC + 6 - 8);                    /* Q8 */
                int32_t bp = sos_q(BP_Q, BP_NS, &tr->bp, y);
                uint16_t ec = enc_e((uint64_t)mwi_q(&tr->mw, (i64)bp * bp));
                if (tr->blank) {
                    if (bstart) { tr->ehold = eget(tr, s - 1); tr->blank_until = s + 45; }
                    if (s < tr->blank_until) ec = tr->ehold;
                }
                tr->e[s & (ERING - 1)] = ec;
                tr->bpr[s & (BRING - 1)] = bp;
                if (tr->kind == 0) {
                    if (s >= T0_TRACK) { if (!tr->started) { tr->started = 1; tr->ts = T0_TRACK; } tracker_step(k, s); }
                } else {
                    int p = det_step(&tr->det, s, (i64)dec_e(ec), iabs(bp));
                    if (p >= 0) add_beat(k, p);
                }
                capture_features(k, s);
                if (s >= CAL_END + 124 && ((s + 1 - SEL_START) % 125 + 125) % 125 == 0) {
                    uint8_t b[3]; b[0] = (uint8_t)k; put16(b + 1, median125(tr, s)); EMIT(C_BMED, b, 3);
                }
            }
            if (s == S.sel_next + SEL_LAG) {
                emit_beats();
                emit_u32(C_REQ_SEL, (uint32_t)S.sel_next);
                wait_rsp(&S.r_sel, "SEL");
                S.sel_k = S.rv_sel; S.sel_t = S.sel_next; S.sel_end = S.sel_next + SEL_HOP;
                S.sel_next += SEL_HOP;
            }
            emit_beats();
        }
    }
    S.T = T + 1;
}

/* end of a SAMPLES frame: all its samples are processed */
void fm_done(void) { emit_u32(C_DONE, (uint32_t)S.T); }
