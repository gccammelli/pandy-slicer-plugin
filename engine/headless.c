/*
 * GLFW for a machine without a display. Bambu Studio's CLI only uses GLFW to open an off-screen OpenGL context for
 * plate thumbnails. On a headless Linux machine (the reference: Pandy Slicer's container) the official build's
 * glfwInit() fails, the CLI logs it and slices without thumbnails. These functions reproduce exactly that: glfwInit()
 * fails with GLFW_PLATFORM_ERROR and nothing else is ever reached. Thumbnails are drawn by the app instead.
 */
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

#define GLFW_FALSE 0
#define GLFW_PLATFORM_ERROR 0x00010008
#define NO_DISPLAY "Wayland: Failed to connect to display"

typedef void (*GLFWerrorfun)(int, const char *);
static GLFWerrorfun error_callback;

int glfwInit(void) {
    if (error_callback) error_callback(GLFW_PLATFORM_ERROR, NO_DISPLAY);
    return GLFW_FALSE;
}
int glfwGetError(const char **description) {
    if (description) *description = NO_DISPLAY;
    return GLFW_PLATFORM_ERROR;
}
GLFWerrorfun glfwSetErrorCallback(GLFWerrorfun callback) {
    GLFWerrorfun previous = error_callback;
    error_callback = callback;
    return previous;
}
void glfwGetVersion(int *major, int *minor, int *rev) {
    if (major) *major = 3;
    if (minor) *minor = 3;
    if (rev) *rev = 7;
}
void glfwTerminate(void) {}

/* Only reachable after a successful glfwInit(), which never happens. */
static void unreachable(const char *name) {
    fprintf(stderr, "pandy-engine: %s called without a display\n", name);
    abort();
}
void glfwWindowHint(int hint, int value) { (void)hint; (void)value; unreachable("glfwWindowHint"); }
void *glfwCreateWindow(int w, int h, const char *t, void *m, void *s) { (void)w; (void)h; (void)t; (void)m; (void)s; unreachable("glfwCreateWindow"); return NULL; }
void glfwMakeContextCurrent(void *window) { (void)window; unreachable("glfwMakeContextCurrent"); }
