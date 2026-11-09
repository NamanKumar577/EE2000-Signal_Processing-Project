/* PC reference runner: host_main <in.i16> [key=value ...]
   in.i16 = N x 4 int16 little-endian; prints "t fhr_x10 src" per output beat.
   With -DFECG_DEBUG and FECG_DUMP set, also prints "# k q" for every track beat. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <xmmintrin.h>
#include "fecg_v5.h"

static void setcfg(const char *kv)
{
    char k[64]; double v;
    if (sscanf(kv, "%63[^=]=%lf", k, &v) != 2) return;
    if (!strcmp(k, "mat_refr")) fecg_cfg.mat_refr = (int)v;
    else if (!strcmp(k, "mat_lo")) fecg_cfg.mat_lo = (float)v;
    else if (!strcmp(k, "mat_hi")) fecg_cfg.mat_hi = (float)v;
    else if (!strcmp(k, "gate")) fecg_cfg.gate = (float)v;
    else if (!strcmp(k, "c0")) fecg_cfg.c0 = (float)v;
    else if (!strcmp(k, "c1")) fecg_cfg.c1 = (float)v;
    else if (!strcmp(k, "floor")) fecg_cfg.floor = (float)v;
    else if (!strcmp(k, "use_canc")) fecg_cfg.use_canc = (int)v;
    else if (!strcmp(k, "use_rawT")) fecg_cfg.use_rawT = (int)v;
    else if (!strcmp(k, "use_rawD")) fecg_cfg.use_rawD = (int)v;
    else if (!strcmp(k, "mat_minfrac")) fecg_cfg.mat_minfrac = (float)v;
    else if (!strcmp(k, "pen_minfrac")) fecg_cfg.pen_minfrac = (float)v;
    else if (!strcmp(k, "cand_mask")) fecg_cfg.cand_mask = (int)v;
    else if (!strcmp(k, "sel_look")) fecg_cfg.sel_look = (int)v;
    else if (!strcmp(k, "hyst")) fecg_cfg.hyst = (float)v;
    else if (!strcmp(k, "reg_pow")) fecg_cfg.reg_pow = (float)v;
    else if (!strcmp(k, "sel_hop")) fecg_cfg.sel_hop = (int)v;
    else if (!strcmp(k, "agr_w")) fecg_cfg.agr_w = (float)v;
    else if (!strcmp(k, "agr_a0")) fecg_cfg.agr_a0 = (float)v;
    else if (!strcmp(k, "pen_rate_ok")) fecg_cfg.pen_rate_ok = (float)v;
    else if (!strcmp(k, "rate_full")) fecg_cfg.rate_full = (float)v;
    else if (!strcmp(k, "rate_floor")) fecg_cfg.rate_floor = (float)v;
    else if (!strcmp(k, "trk_lo")) fecg_cfg.trk_lo = (int)v;
    else if (!strcmp(k, "trk_hi")) fecg_cfg.trk_hi = (int)v;
    else if (!strcmp(k, "trk_thr")) fecg_cfg.trk_thr = (float)v;
    else { fprintf(stderr, "unknown cfg %s\n", k); exit(2); }
}

#ifdef FECG_DEBUG
extern void (*fecg_dbg_beat)(int k, int q);
static void dbg(int k, int q) { printf("# %d %d\n", k, q); }
extern void (*fecg_dbg_sel)(int t, int k, float wq, float pen, float q);
static void dbgs(int t, int k, float wq, float pen, float q) { printf("@ %d %d %g %g %g\n", t, k, wq, pen, q); }
#endif

int main(int argc, char **argv)
{
    _mm_setcsr(_mm_getcsr() | 0x8040);   /* FTZ + DAZ: match the MicroBlaze FPU */
#ifdef FECG_DEBUG
    if (getenv("FECG_DUMP")) { fecg_dbg_beat = dbg; fecg_dbg_sel = dbgs; }
#endif
    if (argc < 2) return 1;
    for (int i = 2; i < argc; i++) setcfg(argv[i]);
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 1;
    fecg_reset();
    int16_t x[4]; fecg_beat_t b[16];
    while (fread(x, sizeof(int16_t), 4, f) == 4) {
        int n = fecg_push(x, b, 16);
        for (int i = 0; i < n; i++) printf("%u %u %u\n", b[i].t, b[i].fhr_x10, b[i].src);
    }
    fclose(f);
    return 0;
}
