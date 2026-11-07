/*
 * GTK functions the arm64 engine really reaches, with display-less behaviour. The phone has no GTK; every other GTK
 * function is a trap (aborts). Each function here is reached at start-up by wxWidgets constructing GUI constants
 * (theme colours) that the slicer never uses, and each behaves as GTK does when it cannot help.
 */
typedef struct { double red, green, blue, alpha; } GdkRGBA;

/* wxColour::FromString asks GTK first, then parses the string itself (wxColourBase::FromString). */
int gdk_rgba_parse(GdkRGBA *rgba, const char *spec) { (void)rgba; (void)spec; return 0; }

/* The CLI calls XInitThreads() first thing on Linux (BambuStudio.cpp). It only sets up Xlib's locking, needs no
 * display, and succeeds (non-zero) on a headless machine. */
int XInitThreads(void) { return 1; }
