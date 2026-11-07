#!/usr/bin/env bash
# Packages the arm64 engine for the app: build/android-engine/
#   jniLibs/arm64-v8a/libpandy_engine.so   the engine executable (Android installs native libraries runnable)
#   assets/engine-resources.zip            resources/ (the official release's, minus desktop-only folders) + pandy/
#   assets/engine-resources.sha256         the resources tree hash, as equivalence/pandy_equiv/runners.package_identity
# Also refreshes build/aarch64/package (bin/ + the same resources/) that the equivalence tests run on phones, so the
# tested package and the shipped one are the same files.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PKG=$ROOT/build/aarch64/package
OUT=$ROOT/build/android-engine
# Folders the command-line slicer never reads: the desktop app's web pages, printer error help, pictures, 3D printer
# models for the GUI, tooltips, translations and shaders. (The equivalence tests run with this same set.)
DESKTOP_ONLY="web hms images model tooltip i18n shaders"
rm -rf "$PKG" "$OUT"; mkdir -p "$PKG/bin" "$PKG/resources" "$OUT/jniLibs/arm64-v8a" "$OUT/assets"
if [ -f "$ROOT/build/aarch64/engine/pandy-engine" ]; then cp "$ROOT/build/aarch64/engine/pandy-engine" "$PKG/bin/pandy-engine"
else
  # UI work before the engine is built: ALLOW_NO_ENGINE=1 packages a stand-in that refuses to slice.
  [ "${ALLOW_NO_ENGINE:-}" = 1 ] || { echo "No arm64 engine: run engine/build-engine.sh aarch64"; exit 1; }
  printf '#!/system/bin/sh\necho "engine not built"; exit 1\n' > "$PKG/bin/pandy-engine"
fi
for d in "$ROOT"/build/reference/resources/*; do
  n=$(basename "$d"); case " $DESKTOP_ONLY " in *" $n "*) continue ;; esac
  cp -al "$d" "$PKG/resources/$n"
done
cp "$PKG/bin/pandy-engine" "$OUT/jniLibs/arm64-v8a/libpandy_engine.so"
STAGE=$ROOT/build/android-stage; rm -rf "$STAGE"; mkdir -p "$STAGE/pandy"
cp -rL "$PKG/resources" "$STAGE/resources"   # a copy: the zip dates set below must not touch shared files
cp "$ROOT/equivalence/schema.json" "$ROOT/equivalence/layout.json" "$STAGE/pandy/"
(cd "$STAGE" && TZ=UTC find resources pandy -exec touch -d 1980-01-02T00:00:00 {} + 2>/dev/null; zip -qrX -9 "$OUT/assets/engine-resources.zip" resources pandy)
python3 -c "import sys; sys.path.insert(0, '$ROOT/equivalence'); from pandy_equiv.runners import package_identity; i = package_identity('$PKG'); print(i['resources_sha256'])" > "$OUT/assets/engine-resources.sha256"
rm -rf "$STAGE"
echo "engine $(sha256sum "$PKG/bin/pandy-engine" | cut -c1-16)…  resources $(cut -c1-16 "$OUT/assets/engine-resources.sha256")…  zip $(du -h "$OUT/assets/engine-resources.zip" | cut -f1)"
