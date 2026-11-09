# Equivalence report

Does Pandy Studio's phone slicer write the same G-code as the official Bambu Studio? Each cell below is one
plate sliced on a phone and by the official Bambu Studio, compared as described in
[equivalence/README.md](../../equivalence/README.md). Regenerate with `equivalence/matrix.py run` and `report`.

*Generated 2026-11-09 00:18 UTC.*

| | |
|---|---|
| 🟩 **Byte-identical** | the phone's G-code is byte-identical to an observed official output |
| 🟪 **Within observed variation** | bytes differ; sampled geometry is within the observed official variation |
| 🟦 **Both refused** | both returned the same nonzero CLI error without slicing |
| 🟨 **Support differences** | sampled walls stay within observed variation; support-related features differ |
| 🟥 **Differs** | sampled paths differ beyond variation observed in the official runs |
| ⬜ **Not verified** | not run or insufficient reference evidence |

**1 byte-identical · 0 within observed variation · 0 both refused · 0 support differences · 1 differ · 438 not verified** (of 440: 11 models × 40 configurations)

![Equivalence matrix](matrix.svg)

Hover a cell (open the SVG) for its details. Columns change one thing from the baseline: X1 Carbon, 0.4 mm nozzle,
0.20mm Standard @BBL X1C, Bambu PLA Basic; printer columns use that printer's own default process and PLA.

## What was compared

| | |
|---|---|
| Official build | Bambu Studio 02.08.02.61 Linux AppImage (SHA-256 pinned in Pandy Slicer's Dockerfile), x86-64, Docker image `sha256:b9e97e25dc56` |
| Phone engine | `pandy-engine` arm64, SHA-256 `729b7ad33821c458bc60b3db6822663ad6ffc58b17501c86641aefb38760af00` |
| Profiles | the retained CLI resource subset of the official release, tree SHA-256 `208e794164f68830cf50f27711d0ae91c7371d64f96c984bdb6daea732a2b175` (3889 files) |
| Compiler | GCC 13.3.0 (Ubuntu 24.04), both builds |
| C library | glibc 2.39 (Ubuntu 24.04), static on the phone |
| Maths functions | arm64 glibc, except `hypot`, `cbrt`, `pow`, `tanf`, `asinf`, `acosf`, `atanf`, `atan2f`: glibc 2.39's source compiled as x86-64 compiles it ([engine/x86-libm](../../engine/x86-libm/README.md)); bit-identical to x86-64 on 2M inputs each |
| Phone | ONEPLUS A3003 (Android SDK 28, arm64-v8a, CPU 2) |
| Runs | Each recorded cell has one phone run and the number of official runs recorded in its result; all are pinned to one CPU. |

Models are generated (`equivalence/pandy_equiv/models.py`): cube 20 mm, cylinder, tube (hole), sphere, torus, gear,
bridge (32 mm span), overhangs (45°/60°/75°), thin walls (0.4–2 mm), tower 80 mm; Benchy uses the verified model bundled with the reference.

## Cells that are not green

| | Model | Configuration | Largest difference | Features | Layers |
|---|---|---|---|---|---|
| 🟥 | benchy | baseline | 13.862 mm | Floating vertical shell, Internal solid infill, Sparse infill | 40–83 |

## Interpretation

Geometric similarity is not byte equality. Unrun cells and results from older input formats or different engine, profile, or reference image identities are not counted.
A matching refusal is recorded separately from a successful slice. A successful slice must also pass effective-settings checks.
Reported distances compare sampled per-layer extrusion paths; they are not measurements of printed-part dimensional error.
