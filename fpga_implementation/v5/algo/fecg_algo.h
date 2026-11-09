/* FECG v5 streaming algorithm API (runs on the MicroBlaze, also builds on the PC). */
#ifndef FECG_ALGO_H
#define FECG_ALGO_H
#include <stdint.h>

typedef struct {
    uint32_t t;        /* sample index of the beat (0 = first sample after reset) */
    uint16_t fhr_x10;  /* fetal heart rate x10 (bpm) */
    uint8_t  src;      /* candidate / source id */
    uint8_t  flags;
} fecg_beat_t;

void fecg_reset(void);
/* Push one 4-lead sample; writes up to max_out beats decided at this sample, returns count. */
int  fecg_push(const int16_t x[4], fecg_beat_t *out, int max_out);

#endif
