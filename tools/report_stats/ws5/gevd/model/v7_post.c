/* FECG v7-DL ("delayed live"): look-ahead track selection on the FPGA, bit-accurate model.
 *
 * Runs next to the v6.1 units and only listens to them: it taps every uplink frame the units
 * produce (BEAT, FEAT, MPK, COV) and two PC responses (RSP_V, RSP_MK), keeps the recent beats of
 * all 16 tracks, and decides the final beats with a fixed delay:
 *   - segment i = [i*625, (i+1)*625), i >= 7.  When the sample counter reaches
 *       T = (i + 1 + V7_WF) * 625 + V7_M
 *     every track is scored over the window [(i - V7_WP)*625, (i + 1 + V7_WF)*625)  (past AND
 *     future of the segment) with an integer log2 (Q8) quality:
 *       shape consistency |mean of normalised beat snapshots| * completeness * regularity^2
 *       * rate prior * maternal-coincidence penalty * (0.5 + agreement with the other tracks)
 *   - one Viterbi step over the 16 tracks (switching costs 1 nat, free when the two tracks agree
 *     on > 80% of the segment's beats); segment i - V7_LV is decided by backtracking;
 *   - the decided beats go through V7_IT passes of beat clean-up (fill one missed beat, drop a
 *     split beat) and a centred 5-interval median FHR, and leave as OUT7 frames.
 * FLUSH (end of the recording) finishes everything with the data available and sends END7.
 * Uplink frames added: 0x8D OUT7 u32 t, u16 fhr_x10, u8 src;  0x8E END7 u32 number of OUT7.
 * Downlink frame added: 0x03 FLUSH (no payload).
 * Compiled only with -DV7 (which implies V61). */
#include "proto.h"
#ifdef V7
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "v7_post.h"

#define SEGL 625
#define SEG0 7                       /* first segment: [4375, 5000) */
#define NBR 256                      /* beats kept per track */
#define NSL 16                       /* shape-sum slots per track (segments) */
#define NMP 256                      /* maternal peaks kept */
#define NST 64                       /* clean-up stage rings */
#define NBP 16                       /* back-pointer rows */
#define SQ 10                        /* normalised snapshot entries Q10 */
#define FLOOR (-2551)                /* 256*log2(1e-3) */
#define SW 369                       /* switch cost: 1 nat = 1.4427 bits, Q8 */
#define WLEN ((V7_WP + 1 + V7_WF) * SEGL)

typedef struct { int32_t b[NST]; uint8_t src[NST]; int n, i, started; int32_t last; } stage_t;

static struct {
    v7_emit_fn emit;
    int32_t bq[16][NBR]; int bn[16];                 /* beat rings */
    int32_t ss[16][NSL][31]; int sn[16][NSL]; int sg[16][NSL];   /* shape sums per segment slot */
    int32_t mp[NMP]; uint8_t mpk[NMP]; int mn;       /* maternal peaks + train index */
    int64_t cov[10]; int16_t V[16]; int have_cov, have_v, gate_ok, gate[4], curmk;
    int iseg, nproc, vinit; int32_t Vt[16]; uint8_t bp[NBP][16];
    int dec_next;                                    /* next segment to decide */
    stage_t st[V7_IT + 1];                           /* clean-up passes, then the FHR stage */
    int nout, Tnow, fl;
    int dh[600];                                     /* delay histogram, 0.1-s bins (statistics only) */
} X;

/* 256*log2(1 + f/64), f = 0..63 */
static const uint8_t LG[64] = {
    0, 6, 11, 17, 22, 28, 33, 38, 44, 49, 54, 59, 63, 68, 73, 78, 82, 87, 92, 96, 100, 105, 109, 113,
    118, 122, 126, 130, 134, 138, 142, 146, 150, 154, 157, 161, 165, 169, 172, 176, 179, 183, 186, 190,
    193, 197, 200, 203, 207, 210, 213, 216, 220, 223, 226, 229, 232, 235, 238, 241, 244, 247, 250, 253};

static int lg2q8(uint64_t x)                         /* x >= 1 */
{
    int e = 63; while (!((x >> e) & 1)) e--;
    int f = e >= 6 ? (int)((x >> (e - 6)) & 63) : (int)((x << (6 - e)) & 63);
    return 256 * e + LG[f];
}

/* rate prior 256*log2(max(0.2, (15000/R - 80)/40)) for R = 126..187 */
static int prior_q8(int R)
{
    static const int16_t P[62] = {
        -9, -18, -27, -36, -45, -55, -64, -73, -83, -93, -103, -113, -123, -133, -143, -154, -164, -175,
        -186, -197, -209, -220, -232, -244, -256, -268, -281, -294, -307, -321, -335, -349, -364, -379,
        -394, -410, -427, -444, -462, -480, -499, -519, -539, -561, -584, -594, -594, -594, -594, -594,
        -594, -594, -594, -594, -594, -594, -594, -594, -594, -594, -594, -594};
    return R <= 125 ? 0 : P[R - 126];
}

static int32_t g32(const uint8_t *p) { return (int32_t)((uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24); }
static int iabs(int v) { return v < 0 ? -v : v; }

static uint32_t isqrt64(uint64_t v)                  /* floor(sqrt(v)), bit by bit as in the RTL */
{
    uint64_t r = 0, b = 1ull << 62;
    while (b > v) b >>= 2;
    while (b) {
        if (v >= r + b) { v -= r + b; r = (r >> 1) + b; } else r >>= 1;
        b >>= 2;
    }
    return (uint32_t)r;
}

/* lower median of v[0..n-1] (n >= 1), by counting as the RTL does */
static int lmed(const int32_t *v, int n)
{
    int want = (n - 1) / 2;
    for (int a = 0; a < n; a++) {
        int lt = 0, le = 0;
        for (int b = 0; b < n; b++) { lt += v[b] < v[a]; le += v[b] <= v[a]; }
        if (lt <= want && want < le) return v[a];
    }
    return v[0];
}

void v7_reset(v7_emit_fn emit)
{
    memset(&X, 0, sizeof(X));
    X.emit = emit;
    X.iseg = SEG0; X.dec_next = SEG0; X.curmk = 0;
    for (int k = 0; k < 16; k++) for (int s = 0; s < NSL; s++) X.sg[k][s] = -1;
}

/* ------------------------------------------------------------------ taps */
static void add_shape(int k, int32_t q, const uint8_t *p)
{
    int32_t s[31]; int64_t mx = 0;
    for (int i = 0; i < 31; i++) { s[i] = g32(p + 4 * i); int64_t a = s[i] < 0 ? -(int64_t)s[i] : s[i]; if (a > mx) mx = a; }
    int sh = 0; while ((mx >> sh) >= 32768) sh++;
    int32_t sum = 0, d[31];
    for (int i = 0; i < 31; i++) { s[i] >>= sh; sum += s[i]; }
    uint64_t E = 0;
    for (int i = 0; i < 31; i++) { d[i] = 31 * s[i] - sum; E += (uint64_t)((int64_t)d[i] * d[i]); }
    uint32_t nr = isqrt64(E);
    int g = q / SEGL, sl = g % NSL;
    if (X.sg[k][sl] != g) { X.sg[k][sl] = g; X.sn[k][sl] = 0; memset(X.ss[k][sl], 0, sizeof(X.ss[k][sl])); }
    X.sn[k][sl]++;
    if (nr == 0) return;
    for (int i = 0; i < 31; i++) {
        int32_t a = iabs(d[i]) << SQ;
        int32_t v = (int32_t)((uint32_t)a / nr);
        X.ss[k][sl][i] += d[i] < 0 ? -v : v;
    }
}

void v7_up(int cmd, const uint8_t *p, int len)
{
    (void)len;
    switch (cmd) {
    case C_COV: for (int c = 0; c < 10; c++) { uint64_t v = 0; for (int b = 7; b >= 0; b--) v = v << 8 | p[8 * c + b]; X.cov[c] = (int64_t)v; } X.have_cov = 1; break;
    case C_BEAT: { int k = p[0] & 15; X.bq[k][X.bn[k] % NBR] = g32(p + 1); X.bn[k]++; break; }
    case C_FEAT: add_shape(p[0] & 15, g32(p + 1), p + 5); break;
    case C_MPK: X.mp[X.mn % NMP] = g32(p); X.mpk[X.mn % NMP] = (uint8_t)X.curmk; X.mn++; break;
    default: break;
    }
}

void v7_rsp(int cmd, const uint8_t *p, int len)
{
    (void)len;
    if (cmd == C_RSP_V) { for (int i = 0; i < 16; i++) X.V[i] = (int16_t)(p[2 * i] | p[2 * i + 1] << 8); X.have_v = 1; }
    else if (cmd == C_RSP_MK) X.curmk = p[0] & 3;
}

/* maternal train k is trusted when its PCA energy is >= 10% of the total: 10 v'Cv >= trace(C) */
static void make_gates(void)
{
    static const int ix[4][4] = {{0, 1, 2, 3}, {1, 4, 5, 6}, {2, 5, 7, 8}, {3, 6, 8, 9}};
    int64_t dmax = X.cov[0];
    if (X.cov[4] > dmax) dmax = X.cov[4];
    if (X.cov[7] > dmax) dmax = X.cov[7];
    if (X.cov[9] > dmax) dmax = X.cov[9];
    int sh = 0; while ((dmax >> sh) >= (1 << 24)) sh++;
    int64_t tr = (X.cov[0] >> sh) + (X.cov[4] >> sh) + (X.cov[7] >> sh) + (X.cov[9] >> sh);
    for (int k = 0; k < 4; k++) {
        int64_t lam = 0;
        for (int a = 0; a < 4; a++) for (int b = 0; b < 4; b++)
            lam += (int64_t)((int32_t)X.V[4 * k + a] * X.V[4 * k + b]) * (X.cov[ix[a][b]] >> sh);
        X.gate[k] = 10 * lam >= (tr << 28);
    }
    X.gate_ok = 1;
}

/* beats of track k in [t0, t1), ascending; returns the count */
static int beats(int k, int32_t t0, int32_t t1, int32_t *o)
{
    int n = 0, m = X.bn[k] < NBR ? X.bn[k] : NBR;
    int j = 0;
    for (; j < m; j++) { int32_t q = X.bq[k][(X.bn[k] - 1 - j) % NBR]; if (q < t0) break; }
    for (j = j - 1; j >= 0; j--) { int32_t q = X.bq[k][(X.bn[k] - 1 - j) % NBR]; if (q < t1) o[n++] = q; }
    return n;
}

/* number of a[] with some b[] within +-tol (both ascending) */
static int near(const int32_t *a, int na, const int32_t *b, int nb, int tol)
{
    int h = 0, j = 0;
    for (int i = 0; i < na; i++) {
        while (j < nb && b[j] < a[i] - tol) j++;
        if (j < nb && b[j] <= a[i] + tol) h++;
    }
    return h;
}

static int quality(int k, int i)
{
    int32_t w0 = (i - V7_WP) * SEGL, w1 = (i + 1 + V7_WF) * SEGL;
    int32_t q[NBR], rr[NBR], o[NBR];
    int n = beats(k, w0, w1, q);
    if (n < 4) return FLOOR;
    for (int j = 0; j < n - 1; j++) rr[j] = q[j + 1] - q[j];
    int R = lmed(rr, n - 1);
    if (R < 69 || R > 187) return FLOOR;
    int ok = 0;
    for (int j = 0; j < n - 1; j++) ok += 20 * iabs(rr[j] - R) <= 3 * R;
    if (!ok) return FLOOR;
    /* shape */
    int64_t S[31] = {0}; int ns = 0;
    for (int g = i - V7_WP; g <= i + V7_WF; g++) {
        int sl = g % NSL;
        if (X.sg[k][sl] != g) continue;
        ns += X.sn[k][sl];
        for (int d = 0; d < 31; d++) S[d] += X.ss[k][sl][d];
    }
    uint64_t E = 0;
    for (int d = 0; d < 31; d++) E += (uint64_t)(S[d] * S[d]);
    if (ns < 3 || E == 0) return FLOOR;
    int L = (lg2q8(E) >> 1) - lg2q8((uint64_t)ns) - 256 * SQ;
    /* completeness */
    int la = lg2q8((uint64_t)n) + lg2q8((uint64_t)R) - lg2q8(WLEN);
    L += la < 0 ? la : 0;
    /* regularity^2 */
    L += 2 * (lg2q8((uint64_t)ok) - lg2q8((uint64_t)(n - 1)));
    L += prior_q8(R);
    /* maternal coincidence */
    int nm = 0, m = X.mn < NMP ? X.mn : NMP;
    int32_t mp[NMP];
    for (int j = m - 1; j >= 0; j--) {
        int x = (X.mn - 1 - j) % NMP;
        if (X.gate[X.mpk[x]] && X.mp[x] >= w0 - 20 && X.mp[x] < w1 + 20) mp[nm++] = X.mp[x];
    }
    if (nm > 3) {
        int h = near(q, n, mp, nm, 12);
        if (6 * n <= 10 * h) return FLOOR;
        int lm = lg2q8((uint64_t)(6 * n - 10 * h)) - lg2q8((uint64_t)(3 * n));
        L += lm < 0 ? lm : 0;
    }
    /* agreement with the other tracks that have produced beats */
    int act = 0, sh = 0;
    for (int j = 0; j < 16; j++) {
        if (j == k || X.bn[j] == 0) continue;
        act++;
        int no = beats(j, w0 - 8, w1 + 8, o);
        sh += near(q, n, o, no, 8);
    }
    if (act == 0) L -= 256;
    else L += lg2q8((uint64_t)(n * act + 2 * sh)) - lg2q8((uint64_t)(2 * n * act));
    return L < FLOOR ? FLOOR : L;
}

/* ------------------------------------------------------------------ output side */
static void emit_out(int32_t t, int f10, int src)
{
    uint8_t b[7]; put32(b, (uint32_t)t); b[4] = f10; b[5] = f10 >> 8; b[6] = src;
    X.emit(C_OUT7, b, 7); X.nout++;
    if (!X.fl) { int d = (X.Tnow - t) / 25; X.dh[d < 0 ? 0 : d > 599 ? 599 : d]++; }
}

static void push(int s, int32_t q, int src)
{
    stage_t *a = &X.st[s];
    a->b[a->n % NST] = q; a->src[a->n % NST] = (uint8_t)src; a->n++;
}

/* nearest beat of any track within +-R/5 of e (ties: earlier); -1 if none */
static int32_t pool_near(int32_t e, int R)
{
    int32_t best = -1, o[NBR];
    for (int k = 0; k < 16; k++) {
        int n = beats(k, e - R, e + R + 1, o);
        for (int j = 0; j < n; j++) {
            if (5 * iabs(o[j] - e) > R) continue;
            if (best < 0 || iabs(o[j] - e) < iabs(best - e) || (iabs(o[j] - e) == iabs(best - e) && o[j] < best)) best = o[j];
        }
    }
    return best;
}

static void run_stages(int fin)
{
    for (int s = 0; s < V7_IT; s++) {
        stage_t *a = &X.st[s];
#define B(j) a->b[(j) % NST]
        if (!a->started && a->n > 0) { a->started = 1; a->last = B(0); push(s + 1, B(0), a->src[0]); a->i = 1; }
        while (a->i < a->n && (fin || a->i + 4 < a->n || X.Tnow - B(a->i) >= V7_DL)) {
            int i = a->i, lo = i - 5 < 0 ? 0 : i - 5, hi = i + 4 < a->n - 1 ? i + 4 : a->n - 1;
            int32_t rr[9]; int c = 0;
            for (int j = lo; j < hi; j++) rr[c++] = B(j + 1) - B(j);
            int R = lmed(rr, c);
            int32_t gap = B(i) - a->last;
            if (8 * R < 5 * gap && 2 * gap < 5 * R) {
                int32_t e = a->last + gap / 2, f = pool_near(e, R);
                a->last = f >= 0 ? f : e;
                push(s + 1, a->last, 16);
            }
            if (20 * gap < 11 * R && i + 1 < a->n && iabs(B(i + 1) - a->last - R) < iabs(B(i + 1) - B(i) - R)) { a->i++; continue; }
            a->last = B(i); push(s + 1, B(i), a->src[i % NST]); a->i++;
        }
#undef B
    }
    /* centred FHR: interval e uses rr[e-2 .. e+2] */
    stage_t *f = &X.st[V7_IT];
#define C(j) f->b[(j) % NST]
    while (f->i < f->n && (fin || f->i + 3 < f->n || X.Tnow - C(f->i) >= V7_DL)) {
        int e = f->i, lo = e - 2 < 0 ? 0 : e - 2, hi = e + 3 < f->n - 1 ? e + 3 : f->n - 1, f10 = 0;
        if (e + 1 < f->n) {
            int32_t rr[5]; int c = 0;
            for (int j = lo; j < hi; j++) rr[c++] = C(j + 1) - C(j);
            int r = lmed(rr, c);
            if (r >= 50 && r <= 300) f10 = (150000 + r / 2) / r;
        }
        emit_out(C(e) - LAT_OUT, f10, f->src[e % NST]);
        f->i++;
    }
#undef C
}

static void take(int j, int k)
{
    int32_t o[NBR];
    int n = beats(k, j * SEGL, (j + 1) * SEGL, o);
    for (int x = 0; x < n; x++) push(0, o[x], k);
}

static void seg_step(int i)
{
    if (!X.gate_ok && X.have_cov && X.have_v) make_gates();
    int LQ[16];
    for (int k = 0; k < 16; k++) LQ[k] = quality(k, i);
    int32_t sb[16][NBR]; int nb[16];
    for (int k = 0; k < 16; k++) nb[k] = beats(k, i * SEGL, (i + 1) * SEGL, sb[k]);
    uint8_t *bp = X.bp[i % NBP];
    if (!X.vinit) { for (int k = 0; k < 16; k++) { X.Vt[k] = LQ[k]; bp[k] = (uint8_t)k; } X.vinit = 1; }
    else {
        int32_t nv[16], mx = 0;
        for (int y = 0; y < 16; y++) {
            int best = -1; int32_t bv = 0;
            for (int x = 0; x < 16; x++) {
                int d = x == y ? 0 : SW;
                if (x != y && nb[x] && nb[y] && 5 * near(sb[x], nb[x], sb[y], nb[y], 8) > 4 * nb[x]) d = 0;
                int32_t v = X.Vt[x] - d;
                if (best < 0 || v > bv) { best = x; bv = v; }
            }
            bp[y] = (uint8_t)best; nv[y] = bv + LQ[y];
            if (y == 0 || nv[y] > mx) mx = nv[y];
        }
        for (int y = 0; y < 16; y++) X.Vt[y] = nv[y] - mx;      /* keep the numbers small */
    }
    X.nproc = i;
}

static int argmax_v(void)
{
    int b = 0;
    for (int k = 1; k < 16; k++) if (X.Vt[k] > X.Vt[b]) b = k;
    return b;
}

void v7_sample(int T)
{
    if (T != (X.iseg + 1 + V7_WF) * SEGL + V7_M) return;
    X.Tnow = T;
    int i = X.iseg++;
    seg_step(i);
    if (i - V7_LV >= SEG0) {
        int k = argmax_v();
        for (int x = i; x > i - V7_LV; x--) k = X.bp[x % NBP][k];
        take(i - V7_LV, k);
        X.dec_next = i - V7_LV + 1;
        run_stages(0);
    }
}

void v7_flush(int n)
{
    X.fl = 1;
    while (X.iseg * SEGL < n) seg_step(X.iseg++);
    if (X.vinit) {
        int path[NBP], last = X.iseg - 1, k = argmax_v();
        for (int x = last; x >= X.dec_next; x--) { path[x % NBP] = k; k = X.bp[x % NBP][k]; }
        for (int j = X.dec_next; j <= last; j++) { take(j, path[j % NBP]); run_stages(0); }
        X.dec_next = last + 1;
    }
    run_stages(1);
    if (getenv("V7_DELAY")) {                                 /* delay statistics of the live part */
        int tot = 0, c = 0, med = -1, p99 = -1, mx = 0;
        for (int d = 0; d < 600; d++) { tot += X.dh[d]; if (X.dh[d]) mx = d; }
        for (int d = 0; d < 600; d++) { c += X.dh[d]; if (med < 0 && 2 * c >= tot) med = d; if (p99 < 0 && 100 * c >= 99 * tot) p99 = d; }
        fprintf(stderr, "v7 delay %d %d %d %d\n", tot, med, p99, mx);
    }
    uint8_t b[4]; put32(b, (uint32_t)X.nout);
    X.emit(C_END7, b, 4);
}
#endif
