#!/usr/bin/env bash
# Builds the Pandy Studio engine (OrcaSlicer's CLI without its GUI) in the build container.
# Usage: engine/orca/build-engine.sh x86_64|aarch64   Output: build/orca/<arch>/engine/pandy-engine
# Configures upstream exactly as BuildLinux.sh does for a release (-DSLIC3R_STATIC=1 -DSLIC3R_GTK=3
# -DBBL_RELEASE_TO_PUBLIC=1 -DBBL_INTERNAL_TESTING=0 -DSLIC3R_CAD=OFF -DORCA_BUILD_PYTHON_STUBGEN_MODULE=OFF -DORCA_BUNDLED_UV_EXECUTABLE=/bin/false, default Release build type) plus the engine overlay.
set -euo pipefail
ARCH=${1:?x86_64 or aarch64}
case "$ARCH" in x86_64|aarch64) ;; *) echo "Unsupported architecture: $ARCH" >&2; exit 2 ;; esac
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
JOBS=${JOBS:-2}
case "$JOBS" in ''|*[!0-9]*|0) echo "JOBS must be a positive integer: $JOBS" >&2; exit 2 ;; esac
EXTRA=""
[ "$ARCH" = aarch64 ] && EXTRA="-DCMAKE_TOOLCHAIN_FILE=/repo/engine/orca/toolchain-aarch64.cmake -DPKG_CONFIG_EXECUTABLE=/repo/engine/tools/pkg-config-arm64 -DOPENGL_opengl_LIBRARY=/usr/lib/x86_64-linux-gnu/libOpenGL.so -DOPENGL_glx_LIBRARY=/usr/lib/x86_64-linux-gnu/libGLX.so -DOPENGL_gl_LIBRARY=/usr/lib/x86_64-linux-gnu/libGL.so -DOPENGL_egl_LIBRARY=/usr/lib/x86_64-linux-gnu/libEGL.so -DPANDY_STATIC_EXE=ON -DPANDY_STUB_LIBDIR=/repo/build/orca/aarch64/engine/stub-libs -DwxWidgets_CONFIG_EXECUTABLE=/repo/build/orca/aarch64/deps/destdir/usr/local/bin/wx-config -DOPENSSL_ROOT_DIR=/opt/arm64-glib/usr -DOPENSSL_INCLUDE_DIR=/opt/arm64-glib/usr/include -DPANDY_EXTRA_INCLUDES=/opt/arm64-glib/usr/include,/opt/arm64-glib/usr/include/aarch64-linux-gnu -DOPENSSL_CRYPTO_LIBRARY=/opt/arm64-glib/usr/lib/aarch64-linux-gnu/libcrypto.a -DOPENSSL_SSL_LIBRARY=/opt/arm64-glib/usr/lib/aarch64-linux-gnu/libssl.a -DCURL_LIBRARY=/opt/arm64-glib/usr/lib/aarch64-linux-gnu/libcurl.a -DCURL_INCLUDE_DIR=/opt/arm64-glib/usr/include -DEXPAT_LIBRARY=/opt/arm64-glib/usr/lib/aarch64-linux-gnu/libexpat.a -DEXPAT_INCLUDE_DIR=/opt/arm64-glib/usr/include"
python3 "$ROOT/engine/orca/checkout.py"
python3 "$ROOT/engine/orca/headers.py"
sudo -n docker run --rm -e GIT_CEILING_DIRECTORIES=/repo/build -u "$(id -u):$(id -g)" -v "$ROOT:/repo" -w /repo pandy-orca-build bash -c "
  set -e
  [ $ARCH = aarch64 ] && export PKG_CONFIG=/repo/engine/tools/pkg-config-arm64
  export CC=clang-18 CXX=clang++-18
  [ $ARCH = aarch64 ] && export CC=/repo/engine/orca/cc-aarch64 CXX=/repo/engine/orca/cxx-aarch64
  B=build/orca/$ARCH/engine
  # Upstream's configure copies the GUI's FFmpeg libraries next to the binary; the engine never links them, so
  # empty placeholders stand in (the desktop app's video player is the only user).
  L=/repo/build/orca/$ARCH/deps/destdir/usr/local/lib
  for f in libavformat.so libavformat.so.61 libavformat.so.61.1.100 libavcodec.so libavcodec.so.61 libavcodec.so.61.3.100 libavutil.so libavutil.so.59 libavutil.so.59.8.100 \
    libswscale.so libswscale.so.8 libswscale.so.8.1.100 libswresample.so libswresample.so.5 libswresample.so.5.1.100; do
    [ -e \$L/\$f ] || : > \$L/\$f
  done
  # arm64 has no fontconfig (system font lookup, used by the GUI's text tool) and no X11 (named by OCCT's display
  # library, which STEP import pulls in): empty archives stand in for them, so their functions become traps.
  if [ $ARCH = aarch64 ]; then mkdir -p \$B/stub-libs; for l in fontconfig X11; do [ -f \$B/stub-libs/lib\$l.a ] || aarch64-linux-gnu-ar rc \$B/stub-libs/lib\$l.a; done; fi
  # arm64: glibc 2.39's hypot, cbrt and pow compiled as x86-64 compiles them (engine/x86-libm/README.md).
  if [ $ARCH = aarch64 ] && [ ! -f /repo/build/glibc/libpandy-x86libm.a ]; then
    mkdir -p /repo/build/glibc && cd /repo/build/glibc
    [ -f glibc-2.39.tar.xz ] || curl -sL -o glibc-2.39.tar.xz https://ftp.gnu.org/gnu/glibc/glibc-2.39.tar.xz
    echo 'f77bd47cf8170c57365ae7bf86696c118adb3b120d3259c64c502d3dc1e2d926  glibc-2.39.tar.xz' | sha256sum -c -
    [ -d glibc-2.39 ] || tar xf glibc-2.39.tar.xz
    GLIBC_SRC=/repo/build/glibc/glibc-2.39 bash /repo/engine/x86-libm/build.sh
    cd /repo
  fi
  # arm64: Eigen 5 gives NEON a two-float half packet, which x86-64 has not. With it a three-float vector is
  # summed (a0+a1)+a2 instead of a0+(a1+a2). Name the full packet as its own half, as SSE does (README.md).
  if [ $ARCH = aarch64 ]; then
    H=/repo/build/orca/aarch64/deps/destdir/usr/local/include/eigen3/Eigen/src/Core/arch/NEON/PacketMath.h
    sed -i 's/typedef Packet2f half;/typedef Packet4f half;/; s/using half = Packet2f;/using half = Packet4f;/' \$H
    [ \$(grep -c 'typedef Packet4f half;\|using half = Packet4f;' \$H) = 2 ] || { echo 'Eigen NEON half-packet change did not apply' >&2; exit 1; }
  fi
  if [ ! -f \$B/build.ninja ]; then
    cmake -S third_party/orcaslicer -B \$B -G Ninja -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
      -DCMAKE_PREFIX_PATH=/repo/build/orca/$ARCH/deps/destdir/usr/local -DSLIC3R_STATIC=1 -DSLIC3R_GTK=3 \
      -DBBL_RELEASE_TO_PUBLIC=1 -DBBL_INTERNAL_TESTING=0 -DSLIC3R_CAD=OFF -DORCA_BUILD_PYTHON_STUBGEN_MODULE=OFF -DORCA_BUNDLED_UV_EXECUTABLE=/bin/false \
      -DCMAKE_PROJECT_INCLUDE=/repo/engine/orca/overlay.cmake -DHPDF_LIBRARY=pandy-gui-only-unused '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-18 -Wl,--no-demangle,--error-limit=0' $EXTRA
  fi
  # First link: collect the GUI symbols the CLI sources reference, turn them into traps, link again.
  for attempt in 1 2 3 4 5 6; do
    if cmake --build \$B --target pandy-engine -j $JOBS > \$B/link.log 2>&1; then break; fi
    grep -q -E 'undefined reference|multiple definition|undefined symbol|duplicate symbol' \$B/link.log || { tail -60 \$B/link.log; exit 1; }
    python3 engine/orca/gen_traps.py \$B/link.log \$B/pandy-traps.c
    [ \$attempt = 6 ] && { tail -30 \$B/link.log; exit 1; }
  done
  ls -l \$B/pandy-engine"
