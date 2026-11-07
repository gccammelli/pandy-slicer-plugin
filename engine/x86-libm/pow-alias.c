/* e_pow.c only exports pow when __pow is not renamed; the engine's pow is glibc's, called through this. */
double pandy_pow(double x, double y);
double pow(double x, double y) { return pandy_pow(x, y); }
