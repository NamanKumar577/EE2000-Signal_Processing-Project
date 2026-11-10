/* golden vectors for v6_sos: inst 0 = LP, inst 1 = MAT, inst 2 = BP, 3000 samples */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "../model/coef_q28.h"
typedef int64_t i64;
static i64 rnd(i64 a, int s) { return (a + ((i64)1 << (s - 1))) >> s; }
typedef struct { i64 z1[4], z2[4]; } sos_t;
static int32_t sos_q(const int32_t (*c)[5], int ns, sos_t *s, int32_t x)
{ i64 xv = x; for (int i = 0; i < ns; i++) { i64 y = rnd((i64)c[i][0] * xv + s->z1[i], 28);
  s->z1[i] = (i64)c[i][1] * xv - (i64)c[i][3] * y + s->z2[i]; s->z2[i] = (i64)c[i][2] * xv - (i64)c[i][4] * y; xv = y; } return (int32_t)xv; }
int main(void) {
  sos_t a = {0}, b = {0}, c = {0}; srand(1);
  for (int n = 0; n < 3000; n++) {
    int32_t x = (int32_t)(((rand() << 15) ^ rand()) % 8000000) - 4000000;
    if (n % 500 < 3) x = (n & 1) ? 8000000 : -8000000;
    printf("%08x %08x %08x %08x\n", (uint32_t)x, (uint32_t)sos_q(LP_Q, LP_NS, &a, x), (uint32_t)sos_q(MAT_Q, MAT_NS, &b, x), (uint32_t)sos_q(BP_Q, BP_NS, &c, x));
  }
}
