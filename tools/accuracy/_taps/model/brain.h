/* FECG v6 PC brain: API */
#ifndef V6_BRAIN_H
#define V6_BRAIN_H
#include <stdint.h>

typedef void (*br_send_fn)(int cmd, const uint8_t *payload, int len);   /* downlink frame */
void br_reset(br_send_fn send);
void br_rx(int cmd, const uint8_t *payload, int len);                   /* uplink frame */

#endif
