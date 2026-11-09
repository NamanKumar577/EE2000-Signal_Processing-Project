/* FECG v5 algorithm: configuration (defaults = the deployed design). */
#ifndef FECG_V5_H
#define FECG_V5_H
#include "fecg_algo.h"

typedef struct {
    int mat_refr;            /* maternal detector refractory / fusion (samples) */
    float mat_lo, mat_hi;    /* plausible maternal rate range (bpm) */
    float gate;              /* apply the coincidence penalty when maternal rate < gate */
    float c0, c1, floor;     /* penalty ramp (coincidence c0 -> 1, c1 -> 0), lower bound */
    int use_canc, use_rawT, use_rawD;
} fecg_cfg_t;

extern fecg_cfg_t fecg_cfg;
#endif
