# Cross-compiling for 64-bit ARM (Android phones run the engine as a static Linux executable) with Ubuntu 24.04's
# aarch64 GCC 13.3, the same compiler version and C++ library the official x86-64 build uses.
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)
# Bambu Studio's autotools recipes (GMP, MPFR, OpenSSL) cross-compile with this prefix.
set(TOOLCHAIN_PREFIX aarch64-linux-gnu)
set(CMAKE_C_COMPILER aarch64-linux-gnu-gcc-13)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++-13)
set(CMAKE_FIND_ROOT_PATH /usr/aarch64-linux-gnu)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY BOTH)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE BOTH)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
# glibconfig.h is the one architecture-specific GTK header (see docker/Dockerfile); it must win over the x86-64 one.
# x86-64 has no fused multiply-add in its baseline instruction set, so the official build never fuses a*b+c; GCC on
# ARM fuses by default, which rounds differently. Off, so every floating-point operation rounds as on x86-64.
set(PANDY_ARM64_GLIB "-I/opt/arm64-glib/usr/lib/aarch64-linux-gnu/glib-2.0/include")
set(CMAKE_C_FLAGS_INIT "-ffp-contract=off ${PANDY_ARM64_GLIB}")
set(CMAKE_CXX_FLAGS_INIT "-ffp-contract=off ${PANDY_ARM64_GLIB}")

# Desktop libraries that GUI recipes look up (wxWidgets' GTK port, OpenGL) but the static arm64 engine never links:
# the lookups are satisfied with the x86-64 files so configuration succeeds; nothing is linked against them.
foreach (_lib X11:libX11 Xxf86vm:libXxf86vm Xext:libXext Xtst:libXtst SM:libSM ICE:libICE)
    string(REPLACE ":" ";" _p ${_lib})
    list(GET _p 0 _name)
    list(GET _p 1 _file)
    set(X11_${_name}_LIB /usr/lib/x86_64-linux-gnu/${_file}.so CACHE FILEPATH "")
endforeach ()
set(OPENGL_opengl_LIBRARY /usr/lib/x86_64-linux-gnu/libOpenGL.so CACHE FILEPATH "")
set(OPENGL_glx_LIBRARY /usr/lib/x86_64-linux-gnu/libGLX.so CACHE FILEPATH "")
set(OPENGL_gl_LIBRARY /usr/lib/x86_64-linux-gnu/libGL.so CACHE FILEPATH "")
set(OPENGL_egl_LIBRARY /usr/lib/x86_64-linux-gnu/libEGL.so CACHE FILEPATH "")
set(OPENGL_glu_LIBRARY /usr/lib/x86_64-linux-gnu/libGLU.so CACHE FILEPATH "")

# wxWidgets' resource compiler (wxrc, built only with XRC) links against GTK, which arm64 does not have; the engine uses no XRC.
set(wxUSE_XRC OFF CACHE BOOL "")
# GLEW and GLFW: looked up by upstream's top level for the GUI; the engine's GLFW is headless.c and it uses no GLEW.
set(GLEW_SHARED_LIBRARY_RELEASE /usr/lib/x86_64-linux-gnu/libGLEW.so CACHE FILEPATH "")
set(GLEW_STATIC_LIBRARY_RELEASE /usr/lib/x86_64-linux-gnu/libGLEW.so CACHE FILEPATH "")
set(glfw3_DIR /usr/lib/x86_64-linux-gnu/cmake/glfw3 CACHE PATH "")
# Wayland, looked up for the GUI library (libslic3r_gui), which the engine does not build.
set(WAYLAND_CLIENT_LIBRARIES /usr/lib/x86_64-linux-gnu/libwayland-client.so CACHE FILEPATH "")
set(WAYLAND_EGL_LIBRARIES /usr/lib/x86_64-linux-gnu/libwayland-egl.so CACHE FILEPATH "")
set(WAYLAND_SERVER_LIBRARIES /usr/lib/x86_64-linux-gnu/libwayland-server.so CACHE FILEPATH "")
