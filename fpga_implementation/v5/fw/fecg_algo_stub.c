/* Stub algorithm: a fake beat every 100 samples, so the data path is testable. */
#include "fecg_algo.h"

static uint32_t n;

void fecg_reset(void) { n = 0; }

int fecg_push(const int16_t x[4], fecg_beat_t *out, int max_out)
{
    uint32_t t = n++;
    if (max_out < 1 || t % 100 != 99) return 0;
    out[0].t = t;
    out[0].fhr_x10 = 1500;
    out[0].src = 0;
    out[0].flags = (uint8_t)(x[0] & 0xFF);
    return 1;
}
