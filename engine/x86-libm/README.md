# x86-64's hypot, cbrt and pow, for the arm64 engine

The official Bambu Studio runs on x86-64 and calls glibc's maths functions there. On arm64 most of them give
bit-identical results (`engine/tests/libm-parity.c`: 2 million inputs per function), but `hypot`, `cbrt`, and in
single precision `tanf`, `asinf`, `acosf`, `atanf` and `atan2f` do not:
GCC fuses multiply-adds differently on arm64, and glibc's arm64 build takes other code paths. Tree supports and some
printers' plates showed toolpath differences from it.

`build.sh` compiles glibc 2.39's own sources for these functions (`sysdeps/ieee754/dbl-64`: `e_hypot.c`, `s_cbrt.c`,
`e_pow.c` with its tables) for arm64 the way x86-64 compiles them:

* `hypot`, `cbrt`, `tanf`, `asinf`, `acosf`, `atanf`, `atan2f`: no fused multiply-add (`-ffp-contract=off`, `__FP_FAST_FMA` undefined), x86-64's generic code.
* `pow`: x86-64 glibc picks its FMA variant at run time on every FMA-capable CPU (the official build's), compiled
  with `-mfma` and GCC's default contraction; built here the same way. (`pow` matched already except for NaN signs.)

`include/` holds minimal stand-ins for glibc's internal headers. Internal names are renamed (`pandy_*`) so they never
clash with arm64's libm, which the rest of the engine keeps.

Result, checked on a phone against x86-64: all 29 functions the parity test covers (16 double, 13 float)
bit-identical on all inputs, except that an invalid
operation's NaN is `-nan` on x86-64 and `nan` on arm64. That is the processors' default NaN, not glibc's, and only
shows if a NaN were printed.
