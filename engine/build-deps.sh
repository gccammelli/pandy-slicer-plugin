#!/usr/bin/env bash
# Builds the engine's third-party libraries with Bambu Studio's own pinned dependency recipes (deps/), in the build
# container. Usage: engine/build-deps.sh x86_64|aarch64. Output: build/<arch>/deps/destdir/usr/local
set -euo pipefail
ARCH=${1:?x86_64 or aarch64}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
JOBS=${JOBS:-10}
# What the command-line slicer links. wxWidgets is built as the official build has it (static, GTK3): the CLI's
# sources run some of its code at startup. No GLFW, GLEW, OpenCSG, FFmpeg or libharu (GUI only).
TARGETS="dep_Boost dep_TBB dep_Cereal dep_NLopt dep_libnoise dep_OpenVDB dep_OpenCV dep_CGAL dep_Qhull dep_OCCT dep_Assimp dep_GMP dep_MPFR dep_PNG dep_ZLIB dep_EXPAT dep_FREETYPE dep_OpenSSL dep_CURL dep_wxWidgets"
# OpenGL is only looked up by GUI recipes the arm64 build never links; the x86-64 entries satisfy the lookup.
TOOLCHAIN=""
[ "$ARCH" = aarch64 ] && TARGETS=${TARGETS/dep_OpenSSL dep_CURL /} && TOOLCHAIN="-DCMAKE_TOOLCHAIN_FILE=/repo/engine/toolchains/aarch64-linux-gnu.cmake -DOPENGL_opengl_LIBRARY=/usr/lib/x86_64-linux-gnu/libOpenGL.so -DOPENGL_glx_LIBRARY=/usr/lib/x86_64-linux-gnu/libGLX.so -DOPENGL_gl_LIBRARY=/usr/lib/x86_64-linux-gnu/libGL.so -DOPENGL_egl_LIBRARY=/usr/lib/x86_64-linux-gnu/libEGL.so"
sudo -n docker run --rm -u "$(id -u):$(id -g)" -e CMAKE_BUILD_PARALLEL_LEVEL="$JOBS" \
  -v "$ROOT:/repo" -w /repo pandy-studio-build bash -c "
    set -e
    export CC=$ARCH-linux-gnu-gcc-13 CXX=$ARCH-linux-gnu-g++-13
    cmake -S third_party/bambustudio/deps -B build/$ARCH/deps -G Ninja -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
      -DDESTDIR=/repo/build/$ARCH/deps/destdir -DDEP_DOWNLOAD_DIR=/repo/build/downloads \
      -DDEP_BUILD_WXWIDGETS=ON -DDEP_WX_GTK3=ON -DDEP_BUILD_GLFW=OFF -DDEP_BUILD_FFMPEG=OFF -DDEP_BUILD_LIBHARU=OFF -DDEP_BUILD_TIFF=OFF $TOOLCHAIN
    # Libraries the recipes take from the system (when found) have no dep_ target: build the ones that exist.
    have=\$(ninja -C build/$ARCH/deps -t targets all | cut -d: -f1)
    want=''; for t in $TARGETS; do echo \"\$have\" | grep -qx \$t && want=\"\$want \$t\"; done
    echo \"Building:\$want\"
    cmake --build build/$ARCH/deps --target \$want"
