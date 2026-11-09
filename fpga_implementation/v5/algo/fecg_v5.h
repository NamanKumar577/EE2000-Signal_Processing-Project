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
    float mat_minfrac, pen_minfrac;   /* min PC energy fraction for a maternal train / for the penalty */
    int cand_mask;                    /* cancelled candidates: bits 0-3 leads, 4-7 PCA, 8-11 GEVD */
    int sel_look;                     /* quality window (samples) */
    float hyst, reg_pow;              /* selection hysteresis; RR-regularity exponent (0 = off) */
    int sel_hop;                      /* selection period (samples) */
    float agr_w, agr_a0;
    float pen_rate_ok;
    int trk_lo, trk_hi; float trk_thr;   /* tracker search window (% of RR) and acceptance threshold */
    float rate_full, rate_floor;      /* quality prior ramps from rate_floor at 80 bpm to 1 at rate_full (0: off) */                /* penalty also trusted when maternal rate < this (bpm) */              /* quality *= a0 + w * cross-track agreement (w = 0: off) */
} fecg_cfg_t;

extern fecg_cfg_t fecg_cfg;
#endif
