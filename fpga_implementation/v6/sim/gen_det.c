#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
typedef int64_t i64;
typedef struct { i64 r[40]; int w, i; i64 sum; } mwi_t;
static i64 mwi_q(mwi_t *m, i64 sq) { m->sum += sq - m->r[m->i]; m->r[m->i] = sq; if (++m->i == m->w) m->i = 0; return m->sum; }
typedef struct { int det_start, warmup, refr, loc, rr_min; i64 peak, noise, wmax, wsum; int enabled, last; i64 e1, e2; i64 ab[32]; int pend; i64 pend_v; } det_t;
static void det_init(det_t *d, int ds, int w, int refr, int loc, int rr) { memset(d, 0, sizeof(*d)); d->det_start = ds; d->warmup = w; d->refr = refr; d->loc = loc; d->rr_min = rr; d->last = -1000000000; d->pend = -1; }
static int det_step(det_t *d, int t, i64 e, i64 ab)
{
    int out = -1; d->ab[t & 31] = ab;
    if (t >= d->det_start) {
        if (t < d->det_start + d->warmup) { if (e > d->wmax) d->wmax = e; d->wsum += e;
            if (t == d->det_start + d->warmup - 1) { d->peak = d->wmax; d->noise = d->wsum >> 9; d->enabled = d->peak > d->noise; } }
        else if (d->enabled && t >= 2) { int m = t - 1; i64 v = d->e1, vp = d->e2;
            if (vp < v && v >= e) { i64 thr = (d->peak + 3 * d->noise) >> 2;
                if (v > thr && m - d->last >= d->refr) { int lo = t - (d->loc - 1); if (lo < 0) lo = 0;
                    int best = lo; i64 bv = d->ab[lo & 31];
                    for (int i = lo + 1; i <= t; i++) if (d->ab[i & 31] > bv) { bv = d->ab[i & 31]; best = i; }
                    if (d->pend >= 0 && best - d->pend < d->rr_min) { if (bv > d->pend_v) { d->pend = best; d->pend_v = bv; } }
                    else { out = d->pend; d->pend = best; d->pend_v = bv; }
                    d->last = m; d->peak += (v - d->peak) >> 3; }
                else if (v <= thr) d->noise += (v - d->noise) >> 3; } } }
    d->e2 = d->e1; d->e1 = e;
    if (out < 0 && d->pend >= 0 && t - (d->loc - 1) - d->pend >= d->rr_min) { out = d->pend; d->pend = -1; }
    return out;
}
int main(void)
{
    mwi_t m0 = {{0}, 38, 0, 0}, m1 = {{0}, 30, 0, 0}; det_t d0, d1;
    det_init(&d0, 0, 512, 75, 30, 75); det_init(&d1, 1000, 512, 50, 26, 50);
    srand(7); int next = 50, next2 = 80;
    for (int t = 0; t < 20000; t++) {
        int y = (rand() % 2001) - 1000;
        if (t == next) { y += 30000; next += 170 + rand() % 40; }
        if (t == next2) { y += 12000 + rand() % 9000; next2 += 100 + rand() % 25; }
        if (t > 9000 && t < 9400) y *= 5;
        i64 yq = (i64)y << 8;
        i64 e0 = mwi_q(&m0, yq * yq), e1 = mwi_q(&m1, yq * yq);
        int p0 = det_step(&d0, t, e0, yq < 0 ? -yq : yq);
        int p1 = det_step(&d1, t, e1, yq < 0 ? -yq : yq);
        printf("%d %d %d %d\n", y, (int)(e0 >> 32), p0, p1);
    }
}
