#!/usr/bin/env bash
# Orca's pinned dependency recipes; separate prefix from the Bambu engine.
set -euo pipefail
ARCH=${1:?x86_64 or aarch64}
case "$ARCH" in x86_64|aarch64) ;; *) echo 'Unsupported architecture' >&2; exit 2 ;; esac
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
python3 "$ROOT/engine/orca/checkout.py"
sudo -n docker run --rm -u "$(id -u):$(id -g)" \
  -e CMAKE_BUILD_PARALLEL_LEVEL="${JOBS:-2}" -e ARCH="$ARCH" -e GIT_CEILING_DIRECTORIES=/repo/build \
  -v "$ROOT:/repo" -w /repo pandy-orca-build bash -euc '
    export PATH=/repo/engine/orca:$PATH
    export CC=clang-18 CXX=clang++-18
    extra=()
    if [[ $ARCH == aarch64 ]]; then
      export CC=/repo/engine/orca/cc-aarch64 CXX=/repo/engine/orca/cxx-aarch64
      export PKG_CONFIG=/repo/engine/tools/pkg-config-arm64
      extra+=(-DCMAKE_TOOLCHAIN_FILE=/repo/engine/orca/toolchain-aarch64.cmake
        -DPKG_CONFIG_EXECUTABLE=/repo/engine/tools/pkg-config-arm64)
    fi
    B=build/orca/$ARCH/deps
    cmake -S third_party/orcaslicer/deps -B "$B" -G Ninja \
      -DDESTDIR=/repo/$B/destdir -DDEP_DOWNLOAD_DIR=/repo/build/orca/downloads \
      -DSLIC3R_CAD=OFF "${extra[@]}"
    targets=$(ninja -C "$B" -t targets all | cut -d: -f1 | grep -E "^dep_(Boost|TBB|Cereal|Draco|NLopt|libnoise|OpenVDB|OpenCV|Eigen|CGAL|Qhull|OCCT|Assimp|GMP|MPFR|PNG|ZLIB|FREETYPE|OpenSSL|CURL|JPEG|wxWidgets)$")
    if [[ $ARCH == aarch64 ]]; then
      targets=$(printf "%s\n" "$targets" | grep -Ev "^dep_(OpenSSL|CURL)$")
    fi
    cmake --build "$B" -j 1 --target $targets
  '
