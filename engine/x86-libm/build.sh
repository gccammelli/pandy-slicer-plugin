#!/usr/bin/env bash
# Builds libpandy-x86libm.a: glibc 2.39's pow, hypot and cbrt for arm64, compiled the way x86-64 compiles them
# (no fused multiply-add: __FP_FAST_FMA undefined, -ffp-contract=off). Their internal tables and helpers are renamed
# so they never clash with the arm64 libm the rest of the engine links. Run in the build container.
set -euo pipefail
G=${GLIBC_SRC:?glibc-2.39 source}; D=$G/sysdeps/ieee754/dbl-64; OUT=${OUT:-.}
CC=aarch64-linux-gnu-gcc-13
RENAME="-D__exp_data=pandy_exp_data -D__pow_log_data=pandy_pow_log_data -D__math_oflow=pandy_math_oflow -D__math_uflow=pandy_math_uflow
  -D__math_may_uflow=pandy_math_may_uflow -D__math_divzero=pandy_math_divzero -D__math_invalid=pandy_math_invalid
  -D__math_check_uflow=pandy_math_check_uflow -D__math_check_oflow=pandy_math_check_oflow -D__math_edom=pandy_math_edom
  -D__math_erange=pandy_math_erange -D__pow=pandy_pow -D__hypot=pandy_hypot -D__cbrt=pandy_cbrt -D__ieee754_hypot=pandy_ieee754_hypot"
FLAGS="-Werror=implicit-function-declaration -O2 -ffp-contract=off -U__FP_FAST_FMA -fno-builtin -fno-math-errno -I$(dirname "$0")/include -I$D -include glibc-shim.h $RENAME"
# pow: x86-64 glibc picks __pow_fma at run time on CPUs with FMA (every x86-64 CPU since 2013, and the reference
# machine), which takes e_pow.c's explicit-fma paths. POW_FMA=1 builds it that way.
POWFLAGS=$FLAGS; [ "${POW_FMA:-1}" = 1 ] && POWFLAGS="${FLAGS/-U__FP_FAST_FMA/} -ffp-contract=fast"
$CC $POWFLAGS -c $D/e_pow.c -o $OUT/e_pow.o
for f in e_pow_log_data.c e_exp_data.c e_hypot.c s_cbrt.c math_err.c; do $CC $FLAGS -c $D/$f -o $OUT/${f%.c}.o; done
$CC -O2 -c "$(dirname "$0")/pow-alias.c" -o $OUT/pow-alias.o
# Single precision: tanf, asinf, acosf, atanf and atan2f differ on arm64 too; x86-64 uses glibc's generic C for them.
F=$G/sysdeps/ieee754/flt-32
FRENAME="-D__tanf=pandy_tanf -D__atanf=pandy_atanf -D__ieee754_asinf=pandy_asinf -D__ieee754_acosf=pandy_acosf
  -D__ieee754_atan2f=pandy_atan2f -D__kernel_tanf=pandy_kernel_tanf -D__ieee754_rem_pio2f=pandy_rem_pio2f
  -D__kernel_rem_pio2f=pandy_kernel_rem_pio2f -D__sincosf_table=pandy_sincosf_table -D__inv_pio4=pandy_inv_pio4
  -D__math_invalidf=pandy_math_invalidf"
FFLAGS="-Werror=implicit-function-declaration -O2 -ffp-contract=off -U__FP_FAST_FMA -fno-builtin -fno-math-errno -I$(dirname "$0")/include -I$F -I$D -include glibc-shim.h $FRENAME"
for f in s_tanf.c k_tanf.c s_sincosf_data.c e_asinf.c e_acosf.c s_atanf.c e_atan2f.c; do $CC $FFLAGS -c $F/$f -o $OUT/${f%.c}.o; done
$CC -O2 -c "$(dirname "$0")/float-alias.c" -o $OUT/float-alias.o
FLOAT_OBJS="$OUT/s_tanf.o $OUT/k_tanf.o $OUT/s_sincosf_data.o $OUT/e_asinf.o $OUT/e_acosf.o $OUT/s_atanf.o $OUT/e_atan2f.o $OUT/float-alias.o"
aarch64-linux-gnu-ar rcs $OUT/libpandy-x86libm.a $OUT/e_pow.o $OUT/e_pow_log_data.o $OUT/e_exp_data.o $OUT/e_hypot.o $OUT/s_cbrt.o $OUT/math_err.o $OUT/pow-alias.o $FLOAT_OBJS
