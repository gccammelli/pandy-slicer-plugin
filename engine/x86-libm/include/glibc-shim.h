/* Minimal stand-ins for glibc's internal headers, enough to compile glibc 2.39's pow, hypot and cbrt
 * (sysdeps/ieee754/dbl-64) outside glibc. See README.md. */
#pragma once
#include <stdint.h>
#include <errno.h>
#include <stdbool.h>
#define attribute_hidden
#define __glibc_likely(x) __builtin_expect((x), 1)
#define __glibc_unlikely(x) __builtin_expect((x), 0)
#define strong_alias(name, aliasname) pandy_strong_alias(name, aliasname)
#define pandy_strong_alias(name, aliasname) extern __typeof(name) aliasname __attribute__((alias(#name)));
#define libm_alias_double(from, to) strong_alias(from, to)
#define libm_alias_finite(from, to)
#define declare_mgen_alias(from, to)
#define math_narrow_eval(x) (x)
#define math_check_force_underflow_nonneg(x) ((void)0)
#define math_opt_barrier(x) ({ __typeof(x) __x = (x); __asm__("" : "+w"(__x)); __x; })
#define math_force_eval(x) ({ __typeof(x) __x = (x); __asm__ __volatile__("" : : "w"(__x)); })
#define USE_FMA_BUILTIN 0
/* x86-64 has no fmax/fmin instruction: glibc uses the C code there, so the same here. */
#define USE_FMAX_BUILTIN 0
#define USE_FMIN_BUILTIN 0
#define HIGH_ORDER_BIT_IS_SET_FOR_SNAN 0
#define _LIB_VERSION _IEEE_
#define _IEEE_ 0
#define NOINLINE __attribute__((noinline))
#define __set_errno(e) (errno = (e))
/* Float word access, as glibc's math_private.h defines it. */
#define GET_FLOAT_WORD(i, d) do { union { float f; uint32_t w; } __u; __u.f = (d); (i) = __u.w; } while (0)
#define SET_FLOAT_WORD(d, i) do { union { float f; uint32_t w; } __u; __u.w = (i); (d) = __u.f; } while (0)
#define libm_alias_float(from, to) strong_alias(from ## f, to ## f)
#define math_check_force_underflow(x) ((void)0)
/* Prototypes glibc's math_private.h provides for the internal functions used here. */
float __kernel_tanf(float x, float y, int iy);
float __atanf(float x);
float __ieee754_atan2f(float y, float x);
