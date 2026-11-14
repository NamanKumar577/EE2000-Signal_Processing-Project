/* FECG v7-DL look-ahead unit: API of the bit-accurate model (v7_post.c) */
#ifndef V7_POST_H
#define V7_POST_H
#include <stdint.h>
typedef void (*v7_emit_fn)(int cmd, const uint8_t *payload, int len);
void v7_reset(v7_emit_fn emit);
void v7_up(int cmd, const uint8_t *payload, int len);    /* tap: uplink frame from the v6.1 units */
void v7_rsp(int cmd, const uint8_t *payload, int len);   /* tap: RSP_V / RSP_MK */
void v7_sample(int T);                                   /* after sample T was processed */
void v7_flush(int n);                                    /* FLUSH: n samples were processed */
#endif
