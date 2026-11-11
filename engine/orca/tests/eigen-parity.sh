#!/usr/bin/env bash
# Builds eigen-parity.cpp for x86-64 and arm64 with the engine's compilers, flags and Eigen copies,
# runs both (arm64 under qemu-aarch64-static) and fails unless every hash line is the same.
# Run from /repo in a container that has the build image plus qemu-user-static (see ../README.md).
set -euo pipefail
cd "$(dirname "$0")/../../.."
OUT=build/orca/probe
mkdir -p $OUT
SRC=engine/orca/tests/eigen-parity.cpp
clang++-18 -O3 -DNDEBUG -std=gnu++17 -Ibuild/orca/x86_64/deps/destdir/usr/local/include/eigen3 $SRC -o $OUT/eigen-x86
engine/orca/cxx-aarch64 -O3 -DNDEBUG -std=gnu++17 -ffp-contract=off -include engine/orca/no-fma.h -static \
  -Ibuild/orca/aarch64/deps/destdir/usr/local/include/eigen3 $SRC -o $OUT/eigen-arm
$OUT/eigen-x86 > $OUT/eigen-x86.txt
qemu-aarch64-static $OUT/eigen-arm > $OUT/eigen-arm.txt
[ -s $OUT/eigen-x86.txt ] || { echo 'The probe printed nothing' >&2; exit 1; }
diff $OUT/eigen-x86.txt $OUT/eigen-arm.txt || { echo 'Eigen results differ between x86-64 and arm64' >&2; exit 1; }
echo "Eigen parity: $(wc -l < $OUT/eigen-x86.txt) hash groups identical"
