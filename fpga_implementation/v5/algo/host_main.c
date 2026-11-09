/* PC reference runner: host_main <in.i16> [key=value ...]
   in.i16 = N x 4 int16 little-endian; prints "t fhr_x10 src" per output beat. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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
    else { fprintf(stderr, "unknown cfg %s\n", k); exit(2); }
}

int main(int argc, char **argv)
{
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
