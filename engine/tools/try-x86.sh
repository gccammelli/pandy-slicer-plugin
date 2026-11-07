#!/usr/bin/env bash
# Slices one equivalence case with the x86-64 engine build and prints the outcome (development helper).
# Usage: engine/tools/try-x86.sh <case inputs dir>
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
IN=$(realpath "$1"); W=$(mktemp -d); cp -r "$IN" "$W/in"; mkdir -p "$W/out" "$W/home"; chmod -R 777 "$W"
cp "$ROOT/build/x86_64/engine/pandy-engine" "$ROOT/build/x86_64/package/bin/"
sudo -n docker run --rm --network none --cpuset-cpus 8 -u 10001:10001 -v "$W:/work" -v "$ROOT/build/x86_64/package:/pkg:ro" -w /work/in \
  -e HOME=/work/home -e LC_ALL=C pandy-studio-build /pkg/bin/pandy-engine --load-settings "machine.json;process.json" \
  --load-filaments "$(cd "$IN" && ls filament*.json | tr '\n' ';' | sed 's/;$//')" --slice 0 --export-3mf out.gcode.3mf --outputdir /work/out model.3mf > "$W/log.txt" 2>&1
echo "rc=$?"; grep -m3 "unsupported GUI" "$W/log.txt"; head -3 "$W/out/result.json" 2>/dev/null
unzip -p "$W/out/out.gcode.3mf" Metadata/plate_1.gcode 2>/dev/null | sha256sum; echo "work: $W"
