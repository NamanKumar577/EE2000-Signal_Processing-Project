/* FECG v6 bit-accurate RTL model: API */
#ifndef V6_FPGA_MODEL_H
#define V6_FPGA_MODEL_H
#include <stdint.h>

typedef void (*fm_emit_fn)(int cmd, const uint8_t *payload, int len);  /* uplink frame */
typedef void (*fm_need_fn)(void);     /* called when a response is needed: deliver pending frames */

void fm_reset(fm_emit_fn emit, fm_need_fn need);
void fm_rx(int cmd, const uint8_t *payload, int len);                    /* downlink response */
void fm_push(const int16_t x[4]);
void fm_done(void);                   /* end of a SAMPLES frame -> DONE */
extern int fm_overflow;

#endif
