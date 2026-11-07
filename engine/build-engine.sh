#!/usr/bin/env bash
# Builds the Pandy Studio engine (Bambu Studio's CLI without its GUI) in the build container.
# Usage: engine/build-engine.sh x86_64|aarch64   Output: build/<arch>/engine/pandy-engine
# Configures upstream exactly as BuildLinux.sh does for a release (-DSLIC3R_STATIC=1 -DSLIC3R_GTK=3
# -DBBL_RELEASE_TO_PUBLIC=1 -DBBL_INTERNAL_TESTING=0, default Release build type) plus the engine overlay.
set -euo pipefail
ARCH=${1:?x86_64 or aarch64}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
JOBS=${JOBS:-10}
EXTRA=""
[ "$ARCH" = aarch64 ] && EXTRA="-DCMAKE_TOOLCHAIN_FILE=/repo/engine/toolchains/aarch64-linux-gnu.cmake -DOPENGL_opengl_LIBRARY=/usr/lib/x86_64-linux-gnu/libOpenGL.so -DOPENGL_glx_LIBRARY=/usr/lib/x86_64-linux-gnu/libGLX.so -DOPENGL_gl_LIBRARY=/usr/lib/x86_64-linux-gnu/libGL.so -DOPENGL_egl_LIBRARY=/usr/lib/x86_64-linux-gnu/libEGL.so -DPANDY_STATIC_EXE=ON -DOPENSSL_ROOT_DIR=/opt/arm64-glib/usr -DOPENSSL_INCLUDE_DIR=/opt/arm64-glib/usr/include -DOPENSSL_CRYPTO_LIBRARY=/opt/arm64-glib/usr/lib/aarch64-linux-gnu/libcrypto.a -DOPENSSL_SSL_LIBRARY=/opt/arm64-glib/usr/lib/aarch64-linux-gnu/libssl.a -DCURL_LIBRARY=/opt/arm64-glib/usr/lib/aarch64-linux-gnu/libcurl.a -DCURL_INCLUDE_DIR=/opt/arm64-glib/usr/include"
sudo -n docker run --rm -u "$(id -u):$(id -g)" -v "$ROOT:/repo" -w /repo pandy-studio-build bash -c "
  set -e
  export CC=$ARCH-linux-gnu-gcc-13 CXX=$ARCH-linux-gnu-g++-13
  B=build/$ARCH/engine
  # Upstream's configure copies the GUI's FFmpeg libraries next to the binary; the engine never links them, so
  # empty placeholders stand in (the desktop app's video player is the only user).
  L=/repo/build/$ARCH/deps/destdir/usr/local/lib
  for f in libavcodec.so libavcodec.so.61 libavcodec.so.61.3.100 libavutil.so libavutil.so.59 libavutil.so.59.8.100 \
    libswscale.so libswscale.so.8 libswscale.so.8.1.100 libswresample.so libswresample.so.5 libswresample.so.5.1.100; do
    [ -e \$L/\$f ] || : > \$L/\$f
  done
  if [ ! -f \$B/build.ninja ]; then
    cmake -S third_party/bambustudio -B \$B -G Ninja -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
      -DCMAKE_PREFIX_PATH=/repo/build/$ARCH/deps/destdir/usr/local -DSLIC3R_STATIC=1 -DSLIC3R_GTK=3 \
      -DBBL_RELEASE_TO_PUBLIC=1 -DBBL_INTERNAL_TESTING=0 \
      -DCMAKE_PROJECT_INCLUDE=/repo/engine/overlay.cmake -DHPDF_LIBRARY=pandy-gui-only-unused -DCMAKE_EXE_LINKER_FLAGS=-Wl,--no-demangle $EXTRA
  fi
  # First link: collect the GUI symbols the CLI sources reference, turn them into traps, link again.
  if ! cmake --build \$B --target pandy-engine -j $JOBS > \$B/link.log 2>&1; then
    grep -q 'undefined reference' \$B/link.log || { tail -60 \$B/link.log; exit 1; }
    python3 engine/tools/gen_traps.py \$B/link.log \$B/pandy-traps.c
    cmake --build \$B --target pandy-engine -j $JOBS
  fi
  ls -l \$B/pandy-engine"
