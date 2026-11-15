/*
 * FECG v6 - PC brain.  Makes the five low-rate decisions for the FPGA, using only
 * the messages the FPGA sends (it never sees the recording):
 *   COV      -> maternal PCA projections (RSP_V)                      once, 10 s
 *   REQ_MK   -> maternal train choice (RSP_MK)                        every 5 s
 *   SEG      -> template basis for the next maternal beat (RSP_BASIS) per maternal beat
 *   REQ_CAL  -> 16 spatial filters, self-referencing GEVD (RSP_CAL)    once, 15 s
 *   REQ_SEL  -> label-free candidate selection (RSP_SEL)               every 2.5 s
 * The algorithms are the v5 ones (fpga_implementation/v5/algo/fecg_v5.c).
 */
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include <stdio.h>
#include "proto.h"
#include "brain.h"
#include "../../v5/algo/fecg_v5_coef.h"

#define PKRING 96
#define CAL_WARM 512

static br_send_fn SEND;

static struct {
    float pcfrac[NL];
    int mtr[NL][PKRING], nmtr[NL];
    int mk;
    int mpk[512], nmpk;
    /* canceller history */
    int nhist, hhead;
    int16_t hist[KHIST][LSEG][NL];
    int32_t hsum[LSEG][NL];
    float graw[NL][KHIST][KHIST];
    float Q[NL][KHIST][2];
    /* calibration data */
    int16_t Zc[CAL_LEN][NL], Xc[CAL_LEN][NL];
    float Yc[CAL_LEN][NL];
    /* tracks */
    int ntr;
    float prev_rate;
    int cal_base, cal_open, ncal;           /* calibration window start, data being received, calibrations done */
    double wsent[MAXTR][4];                 /* weights sent at the last calibration */
    struct { int pk[PKRING], npk, nfeat; int8_t pcc[PKRING][31]; float pem[PKRING]; float bmed[64]; int nb; } tr[MAXTR];
} B;

/* ─────────── small math (v5) ─────────── */
static void isort(int *a, int n) { for (int i = 1; i < n; i++) { int v = a[i], j = i - 1; while (j >= 0 && a[j] > v) { a[j + 1] = a[j]; j--; } a[j + 1] = v; } }
static void fsort(float *a, int n) { for (int i = 1; i < n; i++) { float v = a[i]; int j = i - 1; while (j >= 0 && a[j] > v) { a[j + 1] = a[j]; j--; } a[j + 1] = v; } }
static float imedian(const int *a, int n)
{
    int b[128]; if (n > 128) n = 128;
    memcpy(b, a, n * sizeof(int)); isort(b, n);
    return (n & 1) ? (float)b[n / 2] : 0.5f * (float)(b[n / 2 - 1] + b[n / 2]);
}
static float fmedian(float *b, int n)
{
    if (n <= 0) return 0.0f;
    fsort(b, n);
    return (n & 1) ? b[n / 2] : 0.5f * (b[n / 2 - 1] + b[n / 2]);
}
static void jacobi(double *A, int n, double *ev, double *V)
{
    for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) V[i * n + j] = (i == j) ? 1.0 : 0.0;
    for (int sweep = 0; sweep < 50; sweep++) {
        double off = 0.0, tot = 0.0;
        for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) { double a = A[i * n + j] * A[i * n + j]; tot += a; if (i != j) off += a; }
        if (off <= 1e-24 * tot || off == 0.0) break;
        for (int p = 0; p < n - 1; p++) for (int q = p + 1; q < n; q++) {
            double apq = A[p * n + q];
            if (apq == 0.0) continue;
            double theta = (A[q * n + q] - A[p * n + p]) / (2.0 * apq);
            double t = (theta >= 0 ? 1.0 : -1.0) / (fabs(theta) + sqrt(theta * theta + 1.0));
            double c = 1.0 / sqrt(t * t + 1.0), s = t * c;
            for (int k = 0; k < n; k++) { double akp = A[k * n + p], akq = A[k * n + q]; A[k * n + p] = c * akp - s * akq; A[k * n + q] = s * akp + c * akq; }
            for (int k = 0; k < n; k++) { double apk = A[p * n + k], aqk = A[q * n + k]; A[p * n + k] = c * apk - s * aqk; A[q * n + k] = s * apk + c * aqk; }
            for (int k = 0; k < n; k++) { double vkp = V[k * n + p], vkq = V[k * n + q]; V[k * n + p] = c * vkp - s * vkq; V[k * n + q] = s * vkp + c * vkq; }
        }
    }
    for (int i = 0; i < n; i++) ev[i] = A[i * n + i];
    for (int i = 0; i < n - 1; i++) {
        int m = i;
        for (int j = i + 1; j < n; j++) if (ev[j] < ev[m]) m = j;
        if (m != i) {
            double t = ev[i]; ev[i] = ev[m]; ev[m] = t;
            for (int k = 0; k < n; k++) { double u = V[k * n + i]; V[k * n + i] = V[k * n + m]; V[k * n + m] = u; }
        }
    }
}
static int gen_top4(const double *A, const double *Bm, double *w)
{
    double L[16] = {0};
    for (int i = 0; i < 4; i++) for (int j = 0; j <= i; j++) {
        double s = Bm[i * 4 + j];
        for (int k = 0; k < j; k++) s -= L[i * 4 + k] * L[j * 4 + k];
        if (i == j) { if (s <= 0.0) return 0; L[i * 4 + i] = sqrt(s); }
        else L[i * 4 + j] = s / L[j * 4 + j];
    }
    double T[16], C[16];
    for (int c = 0; c < 4; c++) for (int i = 0; i < 4; i++) {
        double s = A[i * 4 + c];
        for (int k = 0; k < i; k++) s -= L[i * 4 + k] * T[k * 4 + c];
        T[i * 4 + c] = s / L[i * 4 + i];
    }
    for (int r = 0; r < 4; r++) for (int i = 0; i < 4; i++) {
        double s = T[r * 4 + i];
        for (int k = 0; k < i; k++) s -= L[i * 4 + k] * C[r * 4 + k];
        C[r * 4 + i] = s / L[i * 4 + i];
    }
    for (int i = 0; i < 4; i++) for (int j = 0; j < i; j++) { double a = 0.5 * (C[i * 4 + j] + C[j * 4 + i]); C[i * 4 + j] = C[j * 4 + i] = a; }
    double ev[4], V[16];
    jacobi(C, 4, ev, V);
    double u[4]; for (int i = 0; i < 4; i++) u[i] = V[i * 4 + 3];
    for (int i = 3; i >= 0; i--) {
        double s = u[i];
        for (int k = i + 1; k < 4; k++) s -= L[k * 4 + i] * w[k];
        w[i] = s / L[i * 4 + i];
    }
#ifdef WS5_LOG
    { double na = 0.0, nb = 0.0;                       /* logging only: Rayleigh quotient of the returned w */
      for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) { na += w[i] * A[i * 4 + j] * w[j]; nb += w[i] * Bm[i * 4 + j] * w[j]; }
      fprintf(stderr, "WS5GEVD %.9e %.9e %.9e\n", na / nb, ev[3], ev[0]); }
#endif
    return 1;
}
static void unit4(double *w)
{
    int m = 0;
    for (int i = 1; i < 4; i++) if (fabs(w[i]) > fabs(w[m])) m = i;
    double sg = w[m] < 0 ? -1.0 : 1.0, n = 0.0;
    for (int i = 0; i < 4; i++) n += w[i] * w[i];
    n = sqrt(n);
    if (n <= 0.0) { w[0] = 1.0; w[1] = w[2] = w[3] = 0.0; return; }
    for (int i = 0; i < 4; i++) w[i] = sg * w[i] / n;
}
static int q14(double v) { double r = floor(v * (1 << W_FRAC) + 0.5); return (int)(r > 32767 ? 32767 : r < -32768 ? -32768 : r); }

/* ─────────── 1. maternal PCA ─────────── */
static void on_cov(const uint8_t *p)
{
    double C[16], V[16], ev[4];
    int c = 0;
    for (int a = 0; a < NL; a++) for (int b = a; b < NL; b++) { double v = (double)get64(p + 8 * c++); C[a * 4 + b] = C[b * 4 + a] = v; }
    jacobi(C, 4, ev, V);
    double es = 1e-300; for (int k = 0; k < NL; k++) es += ev[k] > 0 ? ev[k] : 0;
    for (int k = 0; k < NL; k++) B.pcfrac[k] = (float)((ev[NL - 1 - k] > 0 ? ev[NL - 1 - k] : 0) / es);
    uint8_t o[32];
    for (int k = 0; k < NL; k++) for (int l = 0; l < NL; l++) put16(o + 2 * (k * NL + l), q14(V[l * 4 + (NL - 1 - k)]));
    SEND(C_RSP_V, o, 32);
}

/* ─────────── 2. maternal train choice ─────────── */
static void train_stats(const int *pk, int npk, int t0, int t1, float *rate, float *reg)
{
    int p[PKRING], n = 0, first = npk > PKRING ? npk - PKRING : 0;
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
    int t0 = t - 5000; if (t0 < 512) t0 = 512;
    for (int k = 0; k < NL; k++) train_stats(B.mtr[k], B.nmtr[k], t0, t, &rate[k], &reg[k]);
    int best = -1;
    for (int k = 0; k < NL; k++)
        if (reg[k] >= 0.6f && rate[k] >= 40.0f && rate[k] <= 130.0f && (best < 0 || rate[k] < rate[best] * 0.9f)) best = k;
    if (best >= 0) return best;
    if (prev >= 0) return prev;
    best = 0;
    for (int k = 1; k < NL; k++) if (reg[k] > reg[best]) best = k;
    return best;
}

/* ─────────── 3. template basis ─────────── */
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
    float t00 = 0.0f, t01 = 0.0f, t11 = 0.0f;
    for (int i = 0; i < n; i++) {
        float a = 0.0f, b = 0.0f;
        for (int j = 0; j < n; j++) { a += G[i * n + j] * Q[j][0]; b += G[i * n + j] * Q[j][1]; }
        t00 += Q[i][0] * a; t01 += Q[i][0] * b; t11 += Q[i][1] * b;
    }
    float tr = 0.5f * (t00 + t11), df = 0.5f * (t00 - t11);
    float rad = sqrtf(df * df + t01 * t01);
    lam[0] = tr + rad; lam[1] = tr - rad;
    if (t01 != 0.0f) {
        float th = (t11 - t00) / (2.0f * t01);
        float t = (th >= 0 ? 1.0f : -1.0f) / (fabsf(th) + sqrtf(th * th + 1.0f));
        float c = 1.0f / sqrtf(t * t + 1.0f), sn = t * c;
        float a0 = c * c * t00 - 2.0f * sn * c * t01 + sn * sn * t11;
        float a1 = sn * sn * t00 + 2.0f * sn * c * t01 + c * c * t11;
        for (int i = 0; i < n; i++) {
            float q0 = c * Q[i][0] - sn * Q[i][1], q1 = sn * Q[i][0] + c * Q[i][1];
            if (a0 >= a1) { Q[i][0] = q0; Q[i][1] = q1; } else { Q[i][0] = q1; Q[i][1] = q0; }
        }
    }
}

static void on_seg(const uint8_t *p)
{
    /* add the beat to the history (exactly as the FPGA does) */
    int hh = B.hhead;
    float seg[LSEG][NL];
    for (int i = 0; i < LSEG; i++) for (int l = 0; l < NL; l++) {
        int16_t v = (int16_t)get16s(p + 4 + 2 * (i * NL + l));
        seg[i][l] = v;
        if (B.nhist >= KHIST) B.hsum[i][l] -= B.hist[hh][i][l];
        B.hist[hh][i][l] = v;
        B.hsum[i][l] += v;
    }
    int nn = B.nhist < KHIST ? B.nhist + 1 : KHIST;
    for (int l = 0; l < NL; l++)
        for (int b = 0; b < nn; b++) {
            float t = 0.0f;
            for (int i = 0; i < LSEG; i++) t += seg[i][l] * (float)B.hist[b][i][l];
            B.graw[l][hh][b] = t; B.graw[l][b][hh] = t;
        }
    B.hhead = (B.hhead + 1) % KHIST;
    if (B.nhist < KHIST) B.nhist++;
    int nh = B.nhist;
    if (nh < WARMB) return;            /* the FPGA will not ask for a basis yet */

    /* basis for the next beat: mean + top-2 PCs of the history, orthonormalised */
    static uint8_t o[4 + NL * 3 * LSEG * 3];
    int off = 4;
    for (int l = 0; l < NL; l++) {
        static float basis[3][LSEG]; float mu[LSEG], G[KHIST * KHIST];
        for (int i = 0; i < LSEG; i++) mu[i] = (float)B.hsum[i][l] / (float)nh;
        int nb = 1;
        memcpy(basis[0], mu, sizeof(mu));
        float r[KHIST], m = 0.0f;
        for (int a = 0; a < nh; a++) { float t = 0.0f; for (int b = 0; b < nh; b++) t += B.graw[l][a][b]; r[a] = t / (float)nh; m += r[a]; }
        m /= (float)nh;
        for (int a = 0; a < nh; a++) for (int b = 0; b < nh; b++) G[a * nh + b] = B.graw[l][a][b] - r[a] - r[b] + m;
        if (B.Q[l][0][0] == 0.0f && B.Q[l][1][1] == 0.0f)
            for (int a = 0; a < KHIST; a++) { B.Q[l][a][0] = (a == 0); B.Q[l][a][1] = (a == 1); }
        float lam[2];
        top2(G, nh, B.Q[l], lam);
        float lmax = lam[0] > 0.0f ? lam[0] : 1.0f;
        for (int c = 0; c < 2; c++) {
            if (!(lam[c] > 1e-6f * lmax)) break;
            float sv = sqrtf(lam[c]);
            for (int i = 0; i < LSEG; i++) basis[nb][i] = 0.0f;
            for (int h = 0; h < nh; h++) {
                float qh = B.Q[l][h][c] / sv;
                for (int i = 0; i < LSEG; i++) basis[nb][i] += ((float)B.hist[h][i][l] - mu[i]) * qh;
            }
            nb++;
        }
        /* modified Gram-Schmidt (double): same span -> same least-squares fit */
        double ob[3][LSEG]; int no = 0;
        for (int c = 0; c < nb; c++) {
            double v[LSEG], n0 = 0.0, n1 = 0.0;
            for (int i = 0; i < LSEG; i++) { v[i] = basis[c][i]; n0 += v[i] * v[i]; }
            for (int j = 0; j < no; j++) {
                double d = 0.0; for (int i = 0; i < LSEG; i++) d += ob[j][i] * v[i];
                for (int i = 0; i < LSEG; i++) v[i] -= d * ob[j][i];
            }
            for (int i = 0; i < LSEG; i++) n1 += v[i] * v[i];
            if (!(n1 > 1e-12 * n0) || n0 <= 0.0) continue;
            n1 = sqrt(n1);
            for (int i = 0; i < LSEG; i++) ob[no][i] = v[i] / n1;
            no++;
        }
        o[l] = (uint8_t)no;
        for (int c = 0; c < no; c++) for (int i = 0; i < LSEG; i++) {
            double q = floor(ob[c][i] * (double)(1 << BO_FRAC) + 0.5);
            if (q > 8388607) q = 8388607;
            if (q < -8388608) q = -8388608;
            put24(o + off, (int32_t)q); off += 3;
        }
    }
    SEND(C_RSP_BASIS, o, off);
}

/* ─────────── 4. calibration: unit leads + self-referencing GEVD ─────────── */
typedef struct { float z1[4], z2[4]; } fsos_t;
static float fsos(const float (*c)[5], int ns, fsos_t *s, float x)
{
    for (int i = 0; i < ns; i++) {
        float y = c[i][0] * x + s->z1[i];
        s->z1[i] = c[i][1] * x - c[i][3] * y + s->z2[i];
        s->z2[i] = c[i][2] * x - c[i][4] * y;
        x = y;
    }
    return x;
}
typedef struct {
    int det_start, warmup, refr, loc, rr_min;
    float peak, noise, wmax, wsum;
    int enabled, last;
    float e1, e2, ab[32];
    int pend; float pend_v;
} fdet_t;
static int fdet_step(fdet_t *d, int t, float e, float ab)
{
    int out = -1;
    d->ab[t & 31] = ab;
    if (t >= d->det_start) {
        if (t < d->det_start + d->warmup) {
            if (e > d->wmax) d->wmax = e;
            d->wsum += e;
            if (t == d->det_start + d->warmup - 1) { d->peak = d->wmax; d->noise = d->wsum / (float)d->warmup; d->enabled = d->peak > d->noise; }
        } else if (d->enabled && t >= 2) {
            int m = t - 1;
            float v = d->e1, vp = d->e2;
            if (vp < v && v >= e) {
                float thr = 0.25f * d->peak + 0.75f * d->noise;
                if (v > thr && m - d->last >= d->refr) {
                    int lo = t - (d->loc - 1); if (lo < 0) lo = 0;
                    int best = lo; float bv = d->ab[lo & 31];
                    for (int i = lo + 1; i <= t; i++) if (d->ab[i & 31] > bv) { bv = d->ab[i & 31]; best = i; }
                    if (d->pend >= 0 && best - d->pend < d->rr_min) { if (bv > d->pend_v) { d->pend = best; d->pend_v = bv; } }
                    else { out = d->pend; d->pend = best; d->pend_v = bv; }
                    d->last = m;
                    d->peak += (v - d->peak) / 8.0f;
                } else if (v <= thr) d->noise += (v - d->noise) / 8.0f;
            }
        }
    }
    d->e2 = d->e1; d->e1 = e;
    if (out < 0 && d->pend >= 0 && t - (d->loc - 1) - d->pend >= d->rr_min) { out = d->pend; d->pend = -1; }
    return out;
}
static void cal_bandpass(int src)
{
    fsos_t f[NL]; memset(f, 0, sizeof(f));
    for (int i = 0; i < CAL_LEN; i++) for (int l = 0; l < NL; l++)
        B.Yc[i][l] = fsos(BP_SOS, BP_SOS_NS, &f[l], (float)(src ? B.Xc[i][l] : B.Zc[i][l]));
}
static int cal_detect(const double *w, int *pk, int maxpk)
{
    fdet_t d; memset(&d, 0, sizeof(d));
    d.warmup = CAL_WARM; d.refr = 50; d.loc = 26; d.rr_min = 50; d.last = -1000000000; d.pend = -1;
    float r[30] = {0}, sum = 0.0f; int ri = 0;
    int n = 0;
    for (int t = 0; t < CAL_LEN; t++) {
        float y = (float)(B.Yc[t][0] * w[0] + B.Yc[t][1] * w[1] + B.Yc[t][2] * w[2] + B.Yc[t][3] * w[3]);
        sum += y * y - r[ri]; r[ri] = y * y; if (++ri == 30) { ri = 0; float s = 0; for (int k = 0; k < 30; k++) s += r[k]; sum = s; }
        int p = fdet_step(&d, t, sum > 0 ? sum : 0, fabsf(y));
        if (p >= 0 && n < maxpk) pk[n++] = p;
    }
    if (d.pend >= 0 && n < maxpk) pk[n++] = d.pend;
    return n;
}
static void refine(const double *C2, const double *w0, const int *m, int nm, double *wout)
{
    double w[4]; memcpy(w, w0, sizeof(w)); unit4(w);
    for (int it = 0; it < 3; it++) {
        int pk[256], n = cal_detect(w, pk, 256), k = 0;
        for (int i = 0; i < n; i++) {
            if (pk[i] < CAL_WARM) continue;
            int near = 0;
            for (int j = 0; j < nm; j++) if (abs(pk[i] - m[j]) <= 6) { near = 1; break; }
            if (!near) pk[k++] = pk[i];
        }
        if (k < 4) break;
        double Cf[16] = {0}; int cnt = 0;
        for (int i = 0; i < k; i++) for (int o = -4; o <= 4; o++) {
            int t = pk[i] + o;
            if (t < 0 || t >= CAL_LEN) continue;
            for (int a = 0; a < 4; a++) for (int b = 0; b < 4; b++) Cf[a * 4 + b] += (double)B.Yc[t][a] * B.Yc[t][b];
            cnt++;
        }
        for (int a = 0; a < 16; a++) Cf[a] /= (double)(cnt > 0 ? cnt : 1);
        double wn[4];
        if (!gen_top4(Cf, C2, wn)) break;
        unit4(wn); memcpy(w, wn, sizeof(w));
    }
    memcpy(wout, w, sizeof(w));
}
#ifndef RECAL_KEEP
#define RECAL_KEEP 0            /* 1: at a recalibration keep a track's old filter unless the new one scores higher */
#endif
/* label-free filter quality on the current calibration window: regular, complete, non-maternal beat train */
static double cal_quality(const double *w, const int *m, int nm)
{
    int pk[256], n0 = cal_detect(w, pk, 256), n = 0;
    for (int i = 0; i < n0; i++) if (pk[i] >= CAL_WARM) pk[n++] = pk[i];
    if (n < 4) return 0.0;
    int rr[256];
    for (int i = 0; i < n - 1; i++) rr[i] = pk[i + 1] - pk[i];
    float med = imedian(rr, n - 1);
    double rate = 60.0 * FS / med;
    if (rate < 80.0 || rate > 220.0) return 0.0;
    int ok = 0, hit = 0;
    for (int i = 0; i < n - 1; i++) if (fabsf((float)rr[i] - med) <= 0.15f * med) ok++;
    for (int i = 0; i < n; i++) for (int j = 0; j < nm; j++) if (abs(pk[i] - m[j]) <= 12) { hit++; break; }
    double acc = (double)n * med / (double)(CAL_LEN - CAL_WARM); if (acc > 1.0) acc = 1.0;
    return ((double)ok / (n - 1)) * acc * (1.0 - (double)hit / n);
}
static void on_req_cal(void)
{
    int m[64], nm = 0, first = B.nmpk > 512 ? B.nmpk - 512 : 0;
    for (int i = first; i < B.nmpk && nm < 64; i++) { int p = B.mpk[i & 511]; if (p >= B.cal_base + CAL_WARM && p < B.cal_base + CAL_LEN) m[nm++] = p - B.cal_base; }
    double cands[2][12][4];
    for (int src = 0; src < 2; src++) {
        cal_bandpass(src);
        double C[16] = {0};
        for (int t = CAL_WARM; t < CAL_LEN; t++) for (int a = 0; a < 4; a++) for (int b = 0; b < 4; b++) C[a * 4 + b] += (double)B.Yc[t][a] * B.Yc[t][b];
        for (int a = 0; a < 16; a++) C[a] /= (double)(CAL_LEN - CAL_WARM);
        double A[16], ev[4], V[16], C2[16];
        memcpy(A, C, sizeof(A)); jacobi(A, 4, ev, V);
        double tr_ = C[0] + C[5] + C[10] + C[15];
        memcpy(C2, C, sizeof(C2));
        for (int i = 0; i < 4; i++) C2[i * 4 + i] += 1e-6 * tr_ / 4.0;
        int nc = 0;
        for (int i = 0; i < 4; i++) { for (int j = 0; j < 4; j++) cands[src][nc][j] = (i == j); nc++; }
        for (int j = 0; j < 4; j++) { for (int i = 0; i < 4; i++) cands[src][nc][i] = V[i * 4 + j]; nc++; }
        for (int j = 0; j < 4; j++) { double v0[4]; for (int i = 0; i < 4; i++) v0[i] = V[i * 4 + j]; refine(C2, v0, m, nm, cands[src][nc]); nc++; }
        if (RECAL_KEEP && B.ncal > 0)                   /* recalibration: keep the old filter if it is at least as good here */
            for (int j = 0; j < 4; j++) {
                int k = src ? 8 + j : 4 + j;
                if (cal_quality(B.wsent[k], m, nm) >= cal_quality(cands[src][8 + j], m, nm)) memcpy(cands[src][8 + j], B.wsent[k], sizeof(double) * 4);
            }
    }
    /* 16 tracks: Z leads + Z GEVD (tracker, blanked), Xf GEVD tracker, Xf GEVD detector */
    static const int csrc[16] = {0,0,0,0, 0,0,0,0, 1,1,1,1, 1,1,1,1};
    static const int ccand[16] = {0,1,2,3, 8,9,10,11, 8,9,10,11, 8,9,10,11};
    uint8_t o[1 + 16 * 11]; int off = 1;
    B.ntr = 16; o[0] = 16;
    for (int k = 0; k < 16; k++) {
        double *w = cands[csrc[k]][ccand[k]], n = 0.0;
        for (int i = 0; i < 4; i++) n += w[i] * w[i];
        n = sqrt(n);
        o[off] = (uint8_t)(k >= 12); o[off + 1] = (uint8_t)csrc[k]; o[off + 2] = (uint8_t)(csrc[k] == 0); off += 3;
        for (int i = 0; i < 4; i++) { put16(o + off, q14(n > 0 ? w[i] / n : (i == 0))); off += 2; }
        for (int i = 0; i < 4; i++) B.wsent[k][i] = n > 0 ? w[i] / n : (i == 0);
    }
    if (B.ncal == 0) memset(B.tr, 0, sizeof(B.tr));    /* recalibration keeps the tracks' history */
    B.ncal++; B.cal_open = 0;
    SEND(C_RSP_CAL, o, off);
}

/* ─────────── 5. selection ─────────── */
#ifndef SEL_WIN
#define SEL_WIN 5000            /* selection window (samples) */
#endif
#ifndef SEL_REGP
#define SEL_REGP 2              /* exponent of the RR-regularity factor */
#endif
#ifndef SEL_AGR0
#define SEL_AGR0 0.5f           /* quality x (SEL_AGR0 + agreement) */
#endif
static float mylogf(float x)
{
    if (!(x > 0.0f)) return -1e30f;
    int e; float m = frexpf(x, &e);
    if (m < 0.70710678f) { m *= 2.0f; e -= 1; }
    float z = (m - 1.0f) / (m + 1.0f), z2 = z * z;
    float s = z * (2.0f + z2 * (0.6666667f + z2 * (0.4f + z2 * (0.2857143f + z2 * 0.2222222f))));
    return s + (float)e * 0.69314718f;
}
static float FEAT_[MAXTR][6];         /* last window features per track (c, acc, log prom, reg, rate, n) */
static float window_quality(int k, int t0, int t1, float *rate_out)
{
    for (int j = 0; j < 6; j++) FEAT_[k][j] = 0.0f;
    int idx[PKRING], n = 0, first = B.tr[k].npk > PKRING ? B.tr[k].npk - PKRING : 0;
    *rate_out = 0.0f;
    for (int i = first; i < B.tr[k].npk; i++) { int q = B.tr[k].pk[i % PKRING]; if (q >= t0 + 16 && q < t1 - 16 && i < B.tr[k].nfeat) idx[n++] = i; }
    if (n < 4) return 0.0f;
    int rr[PKRING];
    for (int i = 0; i < n - 1; i++) rr[i] = B.tr[k].pk[idx[i + 1] % PKRING] - B.tr[k].pk[idx[i] % PKRING];
    float R = imedian(rr, n - 1);
    float rate = 60.0f * FS / R;
    *rate_out = rate;
    if (rate < 80.0f || rate > 220.0f) return 0.0f;
    float expct = (float)(t1 - t0) / R; if (expct < 1.0f) expct = 1.0f;
    float acc = (float)n / expct; if (acc > 1.0f) acc = 1.0f;
    float T[31], col[PKRING];
    for (int j = 0; j < 31; j++) { for (int i = 0; i < n; i++) col[i] = (float)B.tr[k].pcc[idx[i] % PKRING][j]; T[j] = fmedian(col, n); }
    float tm = 0.0f; for (int j = 0; j < 31; j++) tm += T[j]; tm /= 31.0f;
    float tn = 0.0f; for (int j = 0; j < 31; j++) { T[j] -= tm; tn += T[j] * T[j]; }
    tn = sqrtf(tn);
    float cc[PKRING], em[PKRING];
    for (int i = 0; i < n; i++) {
        const int8_t *w = B.tr[k].pcc[idx[i] % PKRING];
        float wm = 0.0f; for (int j = 0; j < 31; j++) wm += (float)w[j]; wm /= 31.0f;
        float d = 0.0f, wn = 0.0f;
        for (int j = 0; j < 31; j++) { float a = (float)w[j] - wm; d += a * T[j]; wn += a * a; }
        cc[i] = d / (sqrtf(wn) * tn + 1e-12f);
        em[i] = B.tr[k].pem[idx[i] % PKRING];
    }
    float c = fmedian(cc, n), pe = fmedian(em, n);
    float bm[64]; int nb = 0, nbk = B.tr[k].nb < 64 ? B.tr[k].nb : 64;
    for (int i = 0; i < nbk && i < (t1 - t0) / 125; i++) bm[nb++] = B.tr[k].bmed[(B.tr[k].nb - 1 - i) & 63];
    float med = nb ? fmedian(bm, nb) : 0.0f;
    float prom = pe / (med + 1e-12f);
    if (c < 0.0f) c = 0.0f;
    float q = c * acc * mylogf(1.0f + prom);
    if (rate < 120.0f) { float pr = (rate - 80.0f) / 40.0f; if (pr < 0.2f) pr = 0.2f; q *= pr; }   /* FHR prior */
    int ok = 0;
    for (int i = 0; i < n - 1; i++) if (fabsf((float)rr[i] - R) <= 0.15f * R) ok++;
    float reg = (float)ok / (float)(n - 1);
    float rg = reg; for (int i = 1; i < SEL_REGP; i++) rg *= reg;
    FEAT_[k][0] = c; FEAT_[k][1] = acc; FEAT_[k][2] = mylogf(1.0f + prom); FEAT_[k][3] = reg; FEAT_[k][4] = rate; FEAT_[k][5] = (float)n;
    return q * rg;
}
static float coincidence_penalty(int k, int t0, int t1)
{
    int m[64], nm = 0, first = B.nmpk > 512 ? B.nmpk - 512 : 0;
    for (int i = first; i < B.nmpk && nm < 64; i++) { int p = B.mpk[i & 511]; if (p >= t0 - 20 && p < t1 + 20) m[nm++] = p; }
    if (nm <= 3 || B.mk < 0 || B.pcfrac[B.mk] < 0.1f) return 1.0f;   /* no / untrusted maternal reference */
    int n = 0, hit = 0, f = B.tr[k].npk > PKRING ? B.tr[k].npk - PKRING : 0;
    for (int i = f; i < B.tr[k].npk; i++) {
        int q = B.tr[k].pk[i % PKRING];
        if (q < t0 || q >= t1) continue;
        n++;
        for (int j = 0; j < nm; j++) if (abs(m[j] - q) <= 12) { hit++; break; }
    }
    float c = n ? (float)hit / (float)n : 0.0f;
    float pen = (0.6f - c) / 0.3f;
    return pen < 0.0f ? 0.0f : pen > 1.0f ? 1.0f : pen;
}
static float agreement(int k, int t0, int t1)
{
    int fk = B.tr[k].npk > PKRING ? B.tr[k].npk - PKRING : 0, nb = 0, hits = 0;
    for (int i = fk; i < B.tr[k].npk; i++) {
        int q = B.tr[k].pk[i % PKRING];
        if (q < t0 || q >= t1) continue;
        nb++;
        for (int j = 0; j < B.ntr; j++) {
            if (j == k) continue;
            int fj = B.tr[j].npk > PKRING ? B.tr[j].npk - PKRING : 0;
            for (int mm = B.tr[j].npk - 1; mm >= fj; mm--) {
                int d = B.tr[j].pk[mm % PKRING] - q;
                if (d < -8) break;
                if (d <= 8) { hits++; break; }
            }
        }
    }
    if (nb == 0 || B.ntr < 2) return 0.0f;
    return (float)hits / ((float)nb * (float)(B.ntr - 1));
}
#ifndef SEL_MATRATE
#define SEL_MATRATE 0.0f        /* >0: quality x (1 - SEL_MATRATE) for tracks at the maternal rate (+-8%) */
#endif
#ifndef SEL_CLUSTER
#define SEL_CLUSTER 0           /* 1: pick the rate cluster with the largest summed quality, then its best track */
#endif
#ifndef SEL_CONT
#define SEL_CONT 0.0f           /* >0: continuity with the previous output rate, scale in bpm */
#endif
static float maternal_rate(int t0, int t1)
{
    int m[64], nm = 0, first = B.nmpk > 512 ? B.nmpk - 512 : 0;
    for (int i = first; i < B.nmpk && nm < 64; i++) { int p = B.mpk[i & 511]; if (p >= t0 && p < t1) m[nm++] = p; }
    if (nm < 4) return 0.0f;
    int rr[64];
    for (int i = 0; i < nm - 1; i++) rr[i] = m[i + 1] - m[i];
    float med = imedian(rr, nm - 1);
    int ok = 0;
    for (int i = 0; i < nm - 1; i++) if (fabsf((float)rr[i] - med) <= 0.15f * med) ok++;
    if ((float)ok < 0.6f * (float)(nm - 1)) return 0.0f;           /* irregular: not a usable maternal rate */
    return 60.0f * FS / med;
}
static void on_req_sel(int t)
{
    int best = 0; float bq = -1.0f;
    float q[MAXTR], rate[MAXTR];
    float mrate = maternal_rate(t - SEL_WIN, t);
    for (int k = 0; k < B.ntr; k++) {
        q[k] = window_quality(k, t - SEL_WIN, t, &rate[k]) * coincidence_penalty(k, t - SEL_WIN, t);
        if (q[k] > 0.0f) q[k] *= SEL_AGR0 + agreement(k, t - SEL_WIN, t);
        if (SEL_MATRATE > 0.0f && mrate > 0.0f && fabsf(rate[k] - mrate) <= 0.08f * mrate) q[k] *= 1.0f - SEL_MATRATE;
        if (SEL_CONT > 0.0f && B.prev_rate > 0.0f && q[k] > 0.0f) q[k] *= 0.5f + 0.5f * expf(-fabsf(rate[k] - B.prev_rate) / SEL_CONT);
        if (q[k] > bq) { bq = q[k]; best = k; }
    }
    if (SEL_CLUSTER && bq > 0.0f) {
        int c = best; float bs = -1.0f;
        for (int k = 0; k < B.ntr; k++) {
            if (q[k] <= 0.0f) continue;
            float s = 0.0f;
            for (int j = 0; j < B.ntr; j++) if (q[j] > 0.0f && fabsf(rate[j] - rate[k]) <= 0.05f * rate[k]) s += q[j];
            if (s > bs) { bs = s; c = k; }
        }
        bq = -1.0f;
        for (int k = 0; k < B.ntr; k++) if (q[k] > 0.0f && fabsf(rate[k] - rate[c]) <= 0.05f * rate[c] && q[k] > bq) { bq = q[k]; best = k; }
    }
    if (bq > 0.0f) B.prev_rate = rate[best];
    {   /* development dump: features of every track at every selection (env BR_DUMP=file) */
        static FILE *df = 0; static int tried = 0;
        if (!tried) { const char *fn = getenv("BR_DUMP"); tried = 1; if (fn) df = fopen(fn, "w"); }
        if (df) {
            for (int k = 0; k < B.ntr; k++)
                fprintf(df, "%d %d %.4f %.4f %.4f %.4f %.3f %.0f %.4f %.4f %.5g %.1f\n", t, k, FEAT_[k][0], FEAT_[k][1], FEAT_[k][2], FEAT_[k][3],
                        FEAT_[k][4], FEAT_[k][5], coincidence_penalty(k, t - SEL_WIN, t), agreement(k, t - SEL_WIN, t), q[k], mrate);
            fflush(df);
        }
    }
    uint8_t o = (uint8_t)best;
    SEND(C_RSP_SEL, &o, 1);
}

/* ─────────── message dispatch ─────────── */
void br_reset(br_send_fn send)
{
    SEND = send;
    memset(&B, 0, sizeof(B));
    B.mk = -1;
}

void br_rx(int cmd, const uint8_t *p, int len)
{
    (void)len;
    switch (cmd) {
    case C_COV: on_cov(p); break;
    case C_MDET: { int k = p[0]; B.mtr[k][B.nmtr[k] % PKRING] = (int)get32(p + 1); B.nmtr[k]++; break; }
    case C_REQ_MK: { uint8_t o = (uint8_t)mat_choose((int)get32(p), B.mk); B.mk = o; SEND(C_RSP_MK, &o, 1); break; }
    case C_MPK: B.mpk[B.nmpk & 511] = (int)get32(p); B.nmpk++; break;
    case C_SEG: on_seg(p); break;
    case C_CALDATA: {
        int s0 = (int)get32(p), n = (int)get16u(p + 4);
        if (!B.cal_open) { B.cal_base = s0; B.cal_open = 1; }
        for (int i = 0; i < n; i++) for (int l = 0; l < NL; l++) {
            B.Zc[s0 + i - B.cal_base][l] = (int16_t)get16s(p + 6 + 16 * i + 2 * l);
            B.Xc[s0 + i - B.cal_base][l] = (int16_t)get16s(p + 6 + 16 * i + 8 + 2 * l);
        }
        break;
    }
    case C_REQ_CAL: on_req_cal(); break;
    case C_BEAT: { int k = p[0]; B.tr[k].pk[B.tr[k].npk % PKRING] = (int)get32(p + 1); B.tr[k].npk++; break; }
    case C_FEAT: {
        int k = p[0], i = B.tr[k].nfeat % PKRING;
        int32_t bp[31]; int32_t mx = 0;
        for (int j = 0; j < 31; j++) { bp[j] = (int32_t)get32(p + 5 + 4 * j); int32_t a = bp[j] < 0 ? -bp[j] : bp[j]; if (a > mx) mx = a; }
        float sc = mx > 0 ? 127.0f / (float)mx : 0.0f;
        for (int j = 0; j < 31; j++) B.tr[k].pcc[i][j] = (int8_t)floorf((float)bp[j] * sc + 0.5f);
        B.tr[k].pem[i] = (float)dec_e((uint16_t)get16u(p + 5 + 124));
        B.tr[k].nfeat++;
        break;
    }
    case C_BMED: { int k = p[0]; B.tr[k].bmed[B.tr[k].nb & 63] = (float)dec_e((uint16_t)get16u(p + 1)); B.tr[k].nb++; break; }
    case C_REQ_SEL: on_req_sel((int)get32(p)); break;
    default: break;
    }
}
