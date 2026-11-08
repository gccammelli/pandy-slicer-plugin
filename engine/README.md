# The slicing engine

Pandy Studio slices with **Bambu Studio's own command-line slicer**, `src/BambuStudio.cpp` of Bambu Studio
02.08.02.61 (tag `v02.08.02.61`, commit `926a7192574bcb9b3a732e1ec59a46d79cb45466`), the release Pandy Slicer runs.
Nothing in upstream's source is changed. What differs from Bambu's own Linux build is listed here in full.

## How it is built

| | Official Linux build | Pandy Studio engine |
|---|---|---|
| Source | tag v02.08.02.61 | same tree, unmodified (`third_party/bambustudio`) |
| Compiler | GCC 13.3.0 (Ubuntu 24.04) | same: `gcc-13` / `aarch64-linux-gnu-gcc-13` 13.3.0-6ubuntu2~24.04.1 (`docker/Dockerfile`) |
| Dependencies | `deps/` recipes, versions pinned there | same recipes, same versions (`build-deps.sh`) |
| CMake | `BuildLinux.sh -s`: `-DSLIC3R_STATIC=1 -DSLIC3R_GTK=3 -DBBL_RELEASE_TO_PUBLIC=1 -DBBL_INTERNAL_TESTING=0` | same options, upstream's own `CMakeLists.txt` (`build-engine.sh`) |
| Program | `BambuStudio` target: `BambuStudio.cpp` + all of `libslic3r_gui` | `pandy-engine` target (`engine.cmake`): `BambuStudio.cpp` + the GUI sources the CLI uses (`PANDY_GUI_SOURCES`) |
| Resources | `resources/` in the AppImage | the AppImage's own `resources/`, byte for byte (taken from the pinned image, not git: see below) |
| Display | none on a server: `glfwInit()` fails, no thumbnails | `headless.c` makes `glfwInit()` fail with the same error |

The CLI's code path never needs the desktop interface, but its source includes GUI headers and uses the GUI's plate
code (`slic3r/GUI/PartPlate.cpp`, `PartPlateList`). Those sources are compiled exactly as upstream compiles them
(`pandy_mirror` copies `libslic3r_gui`'s flags, and its precompiled header is force-included as upstream does).
Every other GUI function they reference (windows, OpenGL drawing, cloud) is replaced by a **trap**
(`tools/gen_traps.py`, generated at link time, listed in `build/<arch>/engine/pandy-traps.c`): calling one prints its
name and aborts. A missing GUI function can stop a slice; it can never change one.

wxWidgets is linked for real (Bambu's fork, as the official build links it: static, GTK 3): the GUI headers construct
wx objects at start-up. On arm64 there is no GTK: its functions are traps too.

### Phones

Android runs the arm64 build as a static Linux executable (glibc and libstdc++ linked in, so the C and C++ libraries
are the same code as on Linux, not Android's). It is compiled with `-ffp-contract=off`: GCC fuses `a*b+c` into one
FMA instruction on ARM by default, which x86-64 (no FMA in its baseline instruction set) never does, and fused results
round differently. With it off, every floating-point operation is the same IEEE operation on both.

### Maths library

The C maths functions (`sin`, `atan2`, `pow`, ...) come from glibc 2.39, the version the official build runs on
(Ubuntu 24.04). arm64 glibc gives bit-identical results to x86-64 glibc for all of them except eight, found with
`tests/libm-parity.c` (2 million inputs per function, run on a phone against x86-64): `hypot`, `cbrt`, `pow` and
the single-precision `tanf`, `asinf`, `acosf`, `atanf`, `atan2f`. For those the engine links glibc 2.39's own C
source compiled the way x86-64 compiles it (`x86-libm/`, about 40 KB): no x86 code and no emulation, the same source
with the same floating-point choices. All 29 tested functions are then bit-identical, except that an invalid
operation's NaN is `-nan` on x86-64 and `nan` on ARM (each processor's default NaN).

The glibc source download is pinned by SHA-256 (`build-engine.sh`). When the official build moves to another
glibc, rebuild `x86-libm` from that version and rerun the parity test.

### Android's sandbox

Android runs apps under a seccomp filter that refuses some system calls glibc makes (`set_robust_list`, `rseq`,
`clone3`, ...). On a kernel without them glibc gets `ENOSYS` and carries on; the filter kills the process instead.
`android-start.c` (the entry point, before glibc starts) answers them with `ENOSYS`; `android-location.c` logs any
refused call, makes `clone3` report `ENOSYS` (glibc then uses `clone`), and lets `PANDY_ENGINE_HOME` say where
`resources/` is (Android installs the executable read-only, with no room beside it). None of this touches slicing.

### Why the resources come from the AppImage

The official release's `resources/` is not git's: `profiles/BBL.json` lists presets in a different order and
`cli_config.json` differs in its trailing newline. The engine ships the release's files so that every profile byte
the slicer reads is the release's.

## Equivalence

`docs/equivalence/README.md` is the report: every reference model under every printer and setting tested, sliced on
a phone and by the official build, with the result of each.

## Build

```
sudo docker build -t pandy-studio-build engine/docker
engine/build-deps.sh x86_64 && engine/build-engine.sh x86_64      # desktop build, to test against the AppImage
engine/build-deps.sh aarch64 && engine/build-engine.sh aarch64    # phone build
engine/package-android.sh                                          # build/android-engine/ for the app
```
