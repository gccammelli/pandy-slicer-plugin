# OrcaSlicer engine

OrcaSlicer **2.5.0**, commit `40ecc66f78ed72dc368e0c1ebe40d77f00cc8a19`, is
pinned in `source.json`. The checkout helper refuses a different or modified
source tree. The upstream slicing sources are not edited.

This engine uses its own dependency prefix, executable, resource archive,
option schema and profile catalog. Bambu remains the default and its build
scripts and artifacts are independent. Both engines are **AGPL-3.0**;
adding Orca does not permit relicensing either engine under MIT or a different
non-AGPL license. The existing separately distributed Pandy client continues to
communicate through the signature-protected plugin protocol.

## Build

The official Ubuntu 24.04 Orca AppImage reports Clang/LLD 18.1.3 and GCC 14.2.0
in its ELF `.comment` section. Orca's upstream Linux release workflow uses
`build_linux.sh -istrlL`; its dependency build uses `-drlL`. The separate Orca
container adds those compilers to the existing Bambu build environment, without
changing the Bambu image. ARM uses the same Clang and libstdc++ major version,
with the Android syscall and floating-point adaptations documented in
`../README.md`.

```sh
sudo docker build -t pandy-studio-build engine/docker
sudo docker build -t pandy-orca-build engine/orca/docker
engine/orca/build-deps.sh x86_64
engine/orca/build-engine.sh x86_64
engine/orca/build-deps.sh aarch64
engine/orca/build-engine.sh aarch64
python3 engine/orca/package.py
./gradlew -Ppandy.testbed :app:assembleDebug
```

Builds default to two concurrent compiler processes. `make` recipes that request
unbounded parallelism are capped by the wrapper in this directory. Override
`JOBS` when appropriate for available memory.

The headless target compiles upstream `OrcaSlicer.cpp` and the required plate/GUI
sources. It reuses the Bambu port's Android startup/resource-location shims.
Unused desktop symbols become explicit aborting traps, with LLD diagnostics
adapted to the existing trap generator. Python, WebRTC, the widget inspector and
FFmpeg are desktop-only configure dependencies; the overlay supplies declaration
targets for them, never executable replacements. CAD is disabled. Reaching an
omitted function must fail the slice.

Besides the plate sources shared with the Bambu port, four upstream sources are
compiled as they are because Orca's CLI reaches them: `IMSlider.cpp` (a header
constant is initialised from it at start-up), `Utils/FileHelp.cpp` (texture path
normalisation), `Utils/BBLPrinterAgent.cpp` (the CLI translates filament ids
into Bambu's catalog ids for `slice_info.config`; it reads
`resources/printers/bambu_filament_ids.json`) and `Utils/ColorSpaceConvert.cpp`
(flush volumes between two filaments are computed from their colours). Each was
found by the trap it replaced.

Orca links Ubuntu's libexpat on Linux. The ARM engine links the same Ubuntu
package version built for arm64 (see `docker/Dockerfile`), next to OpenSSL and
curl. OCCT's display library names X11 and the GUI names fontconfig; the static
ARM engine has neither, so empty archives stand in and their functions become
traps.

### Same arithmetic as x86-64

The phone build must give the official build's G-code, so every floating-point
operation has to be the same IEEE operation in the same order. On top of the
Bambu port's measures (`-ffp-contract=off`, glibc 2.39, `../x86-libm`), Orca's
Eigen 5 needs three more, because its NEON code differs from its SSE2 code:

* Its matrix-product kernel calls the fused multiply-add intrinsics directly.
  `no-fma.h`, included ahead of every source, turns them into a multiply and an
  add.
* It sums a four-float packet pairwise, (a0+a1)+(a2+a3); SSE2 adds the high half
  onto the low one, (a0+a2)+(a1+a3). `no-fma.h` gives NEON the SSE2 order.
* It gives NEON a two-float half packet, which SSE2 has not. Three-float vectors
  (`Vec3f`: normals, ray directions) were then summed (a0+a1)+a2 instead of
  a0+(a1+a2). `build-engine.sh` names the full packet as its own half in the
  arm64 dependency tree's installed copy of
  `Eigen/src/Core/arch/NEON/PacketMath.h`, as SSE2 does, and fails if those two
  lines are not found. The pinned Orca source is not changed.

The last one moved seams on Benchy (the seam placer's visibility rays) while
cubes and gears were unaffected. `tests/eigen-parity.cpp` hashes small-vector and
matrix results, and `tests/eigen-parity.sh` builds it for both architectures,
runs the arm64 one under qemu and fails on any difference (a few seconds, in the
qemu image described under Validation). Run it after every dependency build and
before anything else after an Eigen update.

## Presets and protocol

The official release prunes JSON presets after generating `.opc` caches. The
engine keeps the release's caches. The editor reads a separate `pandy/editor`
JSON catalog from the matching pinned source. `pandy/schema.json` and
`pandy/layout.json` are extracted from Orca's own PrintConfig.cpp and Tab.cpp.
Only BBL printers are offered by the current editor adapter and printer safety
checks; including other vendors' official caches does not advertise them as
supported printers.

Orca's CLI resolves inherited input files by their identity in its user-preset
registry. Each job therefore includes a preset version, a fresh `--datadir`,
private copies of the official cache files under `system`, and registered user-preset file
links. Directory links into the resource package are prohibited: recursive job
cleanup must not traverse installed resources. Complete resolved settings and
user overrides are retained.

The service selects `engine_id=orca`; see `docs/plugin-protocol.md`. Orca jobs
must carry their `resource_version`, use editor mode, and pass both `--strict`
and a structured-warning check. The Bambu server adapter is not enabled for
Orca. No request silently switches engines.

## Validation

`reference.py` downloads the official AppImage and verifies GitHub's release
asset SHA-256. `smoke.py` prepares identical jobs for reference and candidate.
Without options it runs four quick cases: X1 Carbon cube, Benchy and gear, plus
an A1 cube. `--all` runs every case in its `CASES` table: also mixed feature
plates on X1 Carbon, P1S, A1 mini and H2D, tree and normal supports, classic
walls, gyroid infill, ironing, vase mode, by-object printing and a plate with
two filaments. `--case NAME` (repeatable) picks cases. Benchy uses the existing
pinned model at `build/reference/resources/model/3DBenchy.stl`.

```sh
python3 engine/orca/reference.py
sudo docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/repo" -w /repo \
  pandy-orca-build python3 engine/orca/smoke.py reference
sudo docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/repo" -w /repo \
  pandy-orca-build python3 engine/orca/smoke.py engine --all
```

The runner `arm64` slices with the phone build under `qemu-aarch64-static`, for
looking into an ARM difference without a phone. The build image does not carry
qemu; derive a local one that adds the `qemu-user-static` package and run
`smoke.py arm64` in it. It is slow (Benchy takes many minutes) and does not
replace the phone checks below. Jobs are pinned to one CPU so that timings are
comparable; `--unpinned` uses all of them, and the G-code must not change.

Reports preserve raw G-code hashes and normalize only Orca's generated timestamp
comment for comparison. Toolpaths, settings and remaining comments are compared
byte for byte. The smoke check also checks plate MD5 sidecars, structured
warnings, and the harness's bounded start-sequence/heater checks. These are not
comprehensive motion/collision checks or a full Orca equivalence matrix.

For Android sandbox checks, build the testbed APK with both packages present,
install it on the selected phone, then use the debug-only probe:

```sh
adb -s SERIAL install -r app/build/outputs/apk/debug/app-debug.apk
python3 engine/orca/phone-smoke.py --serial SERIAL --engine orca --case benchy
python3 engine/orca/phone-smoke.py --serial SERIAL --engine bambu --case cube
python3 engine/orca/phone-smoke.py --serial SERIAL --check resources
python3 engine/orca/phone-smoke.py --serial SERIAL --check stale-resources
python3 engine/orca/phone-smoke.py --serial SERIAL --check server-refusal
python3 engine/orca/phone-smoke.py --serial SERIAL --check unknown-engine
```

The probe is guarded by Android's DUMP permission and accepts only testbed
package IDs. It exercises the production Messenger service and never sends a
file to a printer. Phone evidence is saved under `build/orca/phones/<serial>`.
Cross-architecture G-code differences are reported explicitly; successful
slicing and MD5 checks alone do not establish equivalence.

The widget inspector's pinned upstream headers are fetched with their upstream
SHA-256 by `headers.py`. Its GUI implementation is omitted. Its notice and the
wxWidgets license are included with the engine resource package.
