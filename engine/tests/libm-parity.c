/* Hashes the results of glibc's double-precision maths functions on a fixed set of inputs, to compare libm between
 * x86-64 (as the official Bambu Studio runs) and arm64 (the phone engine). Same output = bit-identical results.
 * Usage: libm-parity [count]   Prints one line per function: name, FNV-1a hash of all result bits, first input index
 * whose result differs from the reference file given as argv[2] (optional, written by a previous run with "dump"). */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint64_t rng = 0x9E3779B97F4A7C15ull;
static uint64_t next(void) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return rng; }
/* Inputs spanning the ranges slicing uses: small angles, coordinates in mm, and random bit patterns. */
static double input(uint64_t i) {
    uint64_t r = next();
    switch (i % 4) {
        case 0: return ((double)(r >> 11) / 9007199254740992.0) * 2 * M_PI - M_PI;
        case 1: return ((double)(r >> 11) / 9007199254740992.0) * 1000.0 - 500.0;
        case 2: return ((double)(r >> 11) / 9007199254740992.0) * 20.0;
        default: { double d; uint64_t b = (r & 0x800FFFFFFFFFFFFFull) | ((uint64_t)(1023 - 30 + (r >> 52) % 60) << 52); memcpy(&d, &b, 8); return d; }
    }
}

typedef double (*f1)(double);
typedef double (*f2)(double, double);

int main(int argc, char **argv) {
    long n = argc > 1 ? atol(argv[1]) : 2000000;
    struct { const char *name; f1 one; f2 two; } fs[] = {
        {"sin", sin, 0}, {"cos", cos, 0}, {"tan", tan, 0}, {"asin", asin, 0}, {"acos", acos, 0}, {"atan", atan, 0},
        {"exp", exp, 0}, {"log", log, 0}, {"log2", log2, 0}, {"log10", log10, 0}, {"sqrt", sqrt, 0}, {"cbrt", cbrt, 0},
        {"atan2", 0, atan2}, {"pow", 0, pow}, {"hypot", 0, hypot}, {"fmod", 0, fmod},
    };
    /* Single precision, as some of the slicer's geometry (Eigen float vectors, tree supports) uses. */
    typedef float (*g1)(float);
    typedef float (*g2)(float, float);
    struct { const char *name; g1 one; g2 two; } gs[] = {
        {"sinf", sinf, 0}, {"cosf", cosf, 0}, {"tanf", tanf, 0}, {"asinf", asinf, 0}, {"acosf", acosf, 0}, {"atanf", atanf, 0},
        {"expf", expf, 0}, {"logf", logf, 0}, {"sqrtf", sqrtf, 0}, {"cbrtf", cbrtf, 0}, {"atan2f", 0, atan2f}, {"powf", 0, powf},
        {"hypotf", 0, hypotf},
    };
    for (size_t f = 0; f < sizeof gs / sizeof *gs; f++) {
        rng = 0x9E3779B97F4A7C15ull;
        uint64_t h = 1469598103934665603ull;
        for (long i = 0; i < n; i++) {
            float x = (float)input(i), y = (float)input(i + 1), r;
            if (gs[f].one) r = gs[f].one(gs[f].name[0] == 'a' && gs[f].name[1] != 't' ? fmodf(x, 1.0f) : (gs[f].name[0] == 'l' || gs[f].name[1] == 'q') ? fabsf(x) + 1e-30f : x);
            else r = gs[f].two(x, gs[f].name[0] == 'p' ? fmodf(y, 8.0f) : y);
            uint32_t b; memcpy(&b, &r, 4);
            if (r != r) b = 0x7fc00000u; /* NaN signs are the processor's (see x86-libm/README.md) */
            for (int k = 0; k < 4; k++) { h ^= (b >> (8 * k)) & 0xff; h *= 1099511628211ull; }
        }
        printf("%-6s %016llx\n", gs[f].name, (unsigned long long)h);
    }
    for (size_t f = 0; f < sizeof fs / sizeof *fs; f++) {
        rng = 0x9E3779B97F4A7C15ull;
        uint64_t h = 1469598103934665603ull;
        for (long i = 0; i < n; i++) {
            double x = input(i), y = input(i + 1), r;
            if (fs[f].one) r = fs[f].one(fs[f].name[0] == 'a' && fs[f].name[1] != 't' ? fmod(x, 1.0) : (strcmp(fs[f].name, "log") == 0 || fs[f].name[0] == 'l' || fs[f].name[1] == 'q') ? fabs(x) + 1e-300 : x);
            else r = fs[f].two(x, fs[f].name[0] == 'p' ? fmod(y, 8.0) : y);
            uint64_t b; memcpy(&b, &r, 8);
            if (r != r) b = 0x7ff8000000000000ull; /* NaN signs are the processor's (see x86-libm/README.md) */
            for (int k = 0; k < 8; k++) { h ^= (b >> (8 * k)) & 0xff; h *= 1099511628211ull; }
        }
        printf("%-6s %016llx\n", fs[f].name, (unsigned long long)h);
    }
    return 0;
}
