/* asinf, acosf, atan2f over glibc's implementations (tanf and atanf get their names from their own sources). glibc's own wrappers only add errno
 * handling for domain errors, which leaves the results unchanged. */
float pandy_asinf(float), pandy_acosf(float), pandy_atan2f(float, float);
float asinf(float x) { return pandy_asinf(x); }
float acosf(float x) { return pandy_acosf(x); }
float atan2f(float y, float x) { return pandy_atan2f(y, x); }
