# Equivalence report

Does the Pandy Slicer plugin write the same G-code as the official Bambu Studio? Each cell below is one
plate sliced on a phone and by the official Bambu Studio, compared as described in
[equivalence/README.md](../../equivalence/README.md). Regenerate with `equivalence/matrix.py run` and `report`.

*Generated 2026-11-09 23:41 UTC.*

| | |
|---|---|
| 🟩 **Byte-identical** | the phone's G-code is byte-identical to an observed official output |
| **Dark green — Within observed variation** | bytes differ; continuous paths are within the observed official variation |
| **Light green — Support differences** | support paths or extrusion differ; model paths and extrusion stay within observed variation |
| 🟨 **Small model differences** | bounded internal or surface changes with similar material and outline |
| 🟥 **Significant difference or failed safety check** | model differences exceed the bounds, a safety check fails, or slicing outcomes differ |
| 🟩 **Matching refusal** | both returned the same nonzero CLI error without slicing; expected rejection passes |
| ⬜ **Not verified** | not run or insufficient reference evidence |

**253 byte-identical · 80 within observed variation · 3 support differences · 93 small model differences · 0 significant differences or failed checks · 11 both refused · 0 not verified** (of 440: 11 models × 40 configurations)

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
| Phone | ONEPLUS A3003 (Android SDK 28, arm64-v8a, CPU 2), XQ-CC54 (Android SDK 34, arm64-v8a, CPU 6) |
| Runs | Each recorded cell has one phone run and the number of official runs recorded in its result; all are pinned to one CPU. |

Models are generated (`equivalence/pandy_equiv/models.py`): cube 20 mm, cylinder, tube (hole), sphere, torus, gear,
bridge (32 mm span), overhangs (45°/60°/75°), thin walls (0.4–2 mm), tower 80 mm; Benchy uses the verified model bundled with the reference.

A separate [Xperia Benchy cross-check](xperia-benchy.md) covers 39 configurations on a second phone; solid rectilinear was tested on OnePlus only.

Fuzzy skin is excluded: its intentionally random surface texture is outside this matrix's equivalence comparison.

The [difference investigation](difference-investigation.md) records the seam, curve, tower and fuzzy-skin diagnostics.

## Cells that are not green

| | Model | Configuration | Largest difference | Features | Layers |
|---|---|---|---|---|---|
| Light green | overhangs | tree supports | 5.306 mm | Support | 0–72 |
| Light green | sphere | tree supports | 1.205 mm | Support | 0–9 |
| Light green | torus | tree supports | 0.74 mm | Support | 0–1 |
| 🟨 | benchy | A2L | 0.061 mm | Floating vertical shell | 5–22 |
| 🟨 | benchy | H2C | 0.031 mm | Floating vertical shell | 46–46 |
| 🟨 | benchy | H2S | 0.032 mm | Floating vertical shell | 80–86 |
| 🟨 | benchy | P1P | 0.032 mm | Floating vertical shell | 6–85 |
| 🟨 | benchy | P1S | 0.031 mm | Floating vertical shell | 43–77 |
| 🟨 | benchy | P2S | 0.03 mm | Floating vertical shell | 49–49 |
| 🟨 | benchy | classic walls | 0.032 mm | Floating vertical shell | 49–85 |
| 🟨 | benchy | layer 0.08 mm | 0.032 mm | Floating vertical shell | 47–473 |
| 🟨 | benchy | layer 0.12 mm | 0.061 mm | Floating vertical shell | 59–126 |
| 🟨 | benchy | layer 0.16 mm | 0.032 mm | Floating vertical shell | 86–107 |
| 🟨 | benchy | no brim | 0.061 mm | Floating vertical shell | 22–22 |
| 🟨 | benchy | nozzle 0.2 mm | 0.016 mm | Floating vertical shell | 84–84 |
| 🟨 | benchy | nozzle 0.6 mm | 0.045 mm | Floating vertical shell | 48–65 |
| 🟨 | benchy | nozzle 0.8 mm | 0 mm | Floating vertical shell | 34–34 |
| 🟨 | benchy | outer brim | 0.061 mm | Floating vertical shell | 22–22 |
| 🟨 | benchy | pattern grid | 0.061 mm | Floating vertical shell | 68–68 |
| 🟨 | benchy | pattern gyroid | 0.032 mm | Floating vertical shell | 46–88 |
| 🟨 | benchy | pattern honeycomb | 0.031 mm | Floating vertical shell | 46–99 |
| 🟨 | benchy | pattern lightning | 0.061 mm | Floating vertical shell | 22–68 |
| 🟨 | benchy | seam back | 0.032 mm | Floating vertical shell | 49–186 |
| 🟨 | benchy | solid rectilinear | 0 mm | Floating vertical shell | 69–69 |
| 🟨 | benchy | tree supports | 0 mm | Floating vertical shell | 43–43 |
| 🟨 | benchy | walls 1 | 0.031 mm | Floating vertical shell | 26–235 |
| 🟨 | cylinder | layer 0.08 mm | 0.031 mm | Floating vertical shell | 300–300 |
| 🟨 | gear | A1 | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | A1 mini | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | A2L | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | H2C | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | H2D Pro | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | X1 | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | X1E | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | classic walls | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | infill 0% | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | layer 0.12 mm | 0.031 mm | Floating vertical shell | 60–60 |
| 🟨 | gear | layer 0.24 mm | 0.031 mm | Floating vertical shell | 27–27 |
| 🟨 | gear | no brim | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | normal supports | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | outer brim | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | pattern grid | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | pattern lightning | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | tree supports | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | walls 1 | 0.03 mm | Floating vertical shell | 34–34 |
| 🟨 | gear | walls 4 | 0.032 mm | Floating vertical shell | 34–34 |
| 🟨 | overhangs | H2C | 0.03 mm | Floating vertical shell | 4–70 |
| 🟨 | overhangs | P2S | 0.03 mm | Floating vertical shell | 4–70 |
| 🟨 | overhangs | X2D | 0.03 mm | Floating vertical shell | 4–70 |
| 🟨 | overhangs | classic walls | 0.03 mm | Floating vertical shell | 4–70 |
| 🟨 | overhangs | layer 0.16 mm | 0.03 mm | Floating vertical shell | 5–86 |
| 🟨 | sphere | pattern honeycomb | 0.03 mm | Floating vertical shell | 119–119 |
| 🟨 | torus | A1 | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | A1 mini | 0.017 mm | Outer wall | 10–10 |
| 🟨 | torus | A2L | 0.031 mm | Outer wall | 9–40 |
| 🟨 | torus | H2C | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | H2D | 0.031 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟨 | torus | H2D Pro | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | H2S | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | P1P | 0.031 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟨 | torus | P1S | 0.031 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟨 | torus | P2S | 0.031 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟨 | torus | X1 | 0.031 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟨 | torus | X1E | 0.031 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟨 | torus | X2D | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | baseline | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | classic walls | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | infill 0% | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | infill 40% | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | ironing | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | layer 0.08 mm | 0.031 mm | Inner wall, Outer wall | 2–99 |
| 🟨 | torus | layer 0.16 mm | 0.026 mm | Outer wall | 14–14 |
| 🟨 | torus | layer 0.28 mm | 0.03 mm | Outer wall | 15–15 |
| 🟨 | torus | no brim | 0.031 mm | Floating vertical shell, Outer wall | 10–44 |
| 🟨 | torus | normal supports | 0.026 mm | Outer wall | 44–44 |
| 🟨 | torus | outer brim | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | pattern adaptivecubic | 0.026 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟨 | torus | pattern grid | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | pattern gyroid | 0.03 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟨 | torus | pattern honeycomb | 0.031 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟨 | torus | pattern lightning | 0.026 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟨 | torus | seam back | 0.031 mm | Floating vertical shell | 42–42 |
| 🟨 | torus | solid rectilinear | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | walls 1 | 0.018 mm | Outer wall | 10–10 |
| 🟨 | torus | walls 4 | 0.031 mm | Floating vertical shell, Outer wall | 10–43 |
| 🟨 | tower | A2L | 0.03 mm | Floating vertical shell | 394–394 |
| 🟨 | tower | H2S | 0.03 mm | Floating vertical shell | 394–394 |
| 🟨 | tower | layer 0.28 mm | 0.031 mm | Floating vertical shell | 281–281 |
| 🟨 | tower | nozzle 0.8 mm | 0.06 mm | Floating vertical shell | 197–197 |
| 🟨 | tower | pattern honeycomb | 0.03 mm | Floating vertical shell | 394–394 |
| 🟨 | tube | A1 | 0.032 mm | Inner wall | 7–58 |
| 🟨 | tube | layer 0.12 mm | 0.03 mm | Inner wall | 64–64 |
| 🟨 | tube | layer 0.24 mm | 0.03 mm | Inner wall | 24–24 |
| 🟨 | tube | layer 0.28 mm | 0.03 mm | Inner wall | 54–57 |
| 🟨 | tube | nozzle 0.2 mm | 0.016 mm | Inner wall | 2–144 |
| 🟨 | tube | nozzle 0.8 mm | 0.06 mm | Inner wall | 10–23 |

## Interpretation

Geometric similarity is not byte equality. Unrun cells and results from older input formats or different engine, profile, or reference image identities are not counted.
A matching refusal is recorded separately from a successful slice. A successful slice must also pass effective-settings checks.
Reported distances compare continuous per-layer extrusion paths with a 0.0005 mm numerical error bound; they are not measurements of printed-part dimensional error.
The safety check covers the start sequence and heater limits; it does not prove the absence of collisions or other hazards.
