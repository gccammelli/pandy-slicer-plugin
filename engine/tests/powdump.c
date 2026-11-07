#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static uint64_t rng = 0x9E3779B97F4A7C15ull;
static uint64_t next(void) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return rng; }
static double input(uint64_t i) {
    uint64_t r = next();
    switch (i % 4) {
        case 0: return ((double)(r >> 11) / 9007199254740992.0) * 2 * M_PI - M_PI;
        case 1: return ((double)(r >> 11) / 9007199254740992.0) * 1000.0 - 500.0;
        case 2: return ((double)(r >> 11) / 9007199254740992.0) * 20.0;
        default: { double d; uint64_t b = (r & 0x800FFFFFFFFFFFFFull) | ((uint64_t)(1023 - 30 + (r >> 52) % 60) << 52); memcpy(&d, &b, 8); return d; }
    }
}
double (*volatile fp)(double, double) = pow;
int main(void) { for (long i = 0; i < 200000; i++) { double x = input(i), y = input(i + 1); y = fmod(y, 8.0); double r = fp(x, y); printf("%ld %a %a %a\n", i, x, y, r); } }
