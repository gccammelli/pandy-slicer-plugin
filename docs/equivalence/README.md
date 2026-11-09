# Equivalence report

Does Pandy Studio's phone slicer write the same G-code as the official Bambu Studio? Each cell below is one
plate sliced on a phone and by the official Bambu Studio, compared as described in
[equivalence/README.md](../../equivalence/README.md). Regenerate with `equivalence/matrix.py run` and `report`.

*Generated 2026-11-09 10:49 UTC.*

| | |
|---|---|
| 🟩 **Byte-identical** | the phone's G-code is byte-identical to an observed official output |
| 🟪 **Within observed variation** | bytes differ; sampled geometry is within the observed official variation |
| 🟦 **Both refused** | both returned the same nonzero CLI error without slicing |
| 🟨 **Support differences** | sampled walls stay within observed variation; support-related features differ |
| 🟥 **Differs** | sampled paths differ beyond variation observed in the official runs |
| ⬜ **Not verified** | not run or insufficient reference evidence |

**240 byte-identical · 71 within observed variation · 11 both refused · 3 support differences · 115 differ · 0 not verified** (of 440: 11 models × 40 configurations)

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

A separate [Xperia Benchy cross-check](xperia-benchy.md) covers all 40 configurations on a second phone.

## Cells that are not green

| | Model | Configuration | Largest difference | Features | Layers |
|---|---|---|---|---|---|
| 🟥 | benchy | A1 | 0.03 mm | Floating vertical shell | 40–40 |
| 🟥 | benchy | A1 mini | 0.055 mm | Floating vertical shell | 19–87 |
| 🟥 | benchy | A2L | 0.064 mm | Floating vertical shell | 5–23 |
| 🟥 | benchy | H2C | 0.088 mm | Floating vertical shell | 46–46 |
| 🟥 | benchy | H2D | 0.03 mm | Floating vertical shell | 40–40 |
| 🟥 | benchy | H2S | 0.067 mm | Floating vertical shell | 80–86 |
| 🟥 | benchy | P1P | 0.074 mm | Floating vertical shell | 6–85 |
| 🟥 | benchy | P1S | 0.085 mm | Floating vertical shell | 43–186 |
| 🟥 | benchy | P2S | 0.066 mm | Floating vertical shell | 49–49 |
| 🟥 | benchy | X2D | 0.093 mm | Floating vertical shell | 19–44 |
| 🟥 | benchy | baseline | 0.067 mm | Floating vertical shell | 40–76 |
| 🟥 | benchy | classic walls | 0.075 mm | Floating vertical shell | 49–85 |
| 🟥 | benchy | fuzzy skin | inf mm | Gap infill, Inner wall, Outer wall, Overhang wall | 8–214 |
| 🟥 | benchy | layer 0.08 mm | 0.094 mm | Floating vertical shell | 47–473 |
| 🟥 | benchy | layer 0.12 mm | 0.073 mm | Floating vertical shell | 59–126 |
| 🟥 | benchy | layer 0.16 mm | 0.093 mm | Floating vertical shell | 85–107 |
| 🟥 | benchy | no brim | 0.067 mm | Floating vertical shell | 22–22 |
| 🟥 | benchy | nozzle 0.2 mm | 0.088 mm | Floating vertical shell | 84–354 |
| 🟥 | benchy | nozzle 0.6 mm | 0.078 mm | Floating vertical shell | 48–65 |
| 🟥 | benchy | outer brim | 0.072 mm | Floating vertical shell | 22–186 |
| 🟥 | benchy | pattern adaptivecubic | 0.093 mm | Floating vertical shell | 44–44 |
| 🟥 | benchy | pattern grid | 0.075 mm | Floating vertical shell | 68–68 |
| 🟥 | benchy | pattern gyroid | 0.088 mm | Floating vertical shell | 46–88 |
| 🟥 | benchy | pattern honeycomb | 0.099 mm | Floating vertical shell | 46–99 |
| 🟥 | benchy | pattern lightning | 0.072 mm | Floating vertical shell | 22–186 |
| 🟥 | benchy | seam back | 0.093 mm | Floating vertical shell | 40–186 |
| 🟥 | benchy | tree supports | 0.03 mm | Floating vertical shell | 40–40 |
| 🟥 | benchy | walls 1 | 0.095 mm | Floating vertical shell | 26–235 |
| 🟥 | bridge | fuzzy skin | 0.667 mm | Inner wall, Outer wall | 5–58 |
| 🟥 | cube | fuzzy skin | 0.619 mm | Outer wall | 43–43 |
| 🟥 | cube | ironing | 0.06 mm | Floating vertical shell | 94–94 |
| 🟥 | cube | layer 0.24 mm | 0.06 mm | Floating vertical shell | 78–78 |
| 🟥 | cube | normal supports | 0.06 mm | Floating vertical shell | 94–94 |
| 🟥 | cube | pattern grid | 0.06 mm | Floating vertical shell | 94–94 |
| 🟥 | cylinder | fuzzy skin | 0.586 mm | Inner wall, Outer wall | 2–121 |
| 🟥 | cylinder | layer 0.08 mm | 0.053 mm | Floating vertical shell | 300–300 |
| 🟥 | gear | A1 | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | A1 mini | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | A2L | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | H2C | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | H2D Pro | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | X1 | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | X1E | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | classic walls | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | fuzzy skin | 0.058 mm | Floating vertical shell, Inner wall | 27–34 |
| 🟥 | gear | infill 0% | 0.06 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | layer 0.12 mm | 0.051 mm | Floating vertical shell | 60–60 |
| 🟥 | gear | layer 0.24 mm | 0.051 mm | Floating vertical shell | 27–27 |
| 🟥 | gear | no brim | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | normal supports | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | outer brim | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | pattern grid | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | pattern lightning | 0.06 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | tree supports | 0.051 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | walls 1 | 0.043 mm | Floating vertical shell | 34–34 |
| 🟥 | gear | walls 4 | 0.095 mm | Floating vertical shell | 34–34 |
| 🟥 | overhangs | H2C | 0.06 mm | Floating vertical shell | 4–70 |
| 🟥 | overhangs | P2S | 0.06 mm | Floating vertical shell | 4–70 |
| 🟥 | overhangs | X2D | 0.06 mm | Floating vertical shell | 4–70 |
| 🟥 | overhangs | classic walls | 0.06 mm | Floating vertical shell | 4–70 |
| 🟥 | overhangs | fuzzy skin | 17.139 mm | Inner wall, Outer wall, Overhang wall | 2–74 |
| 🟥 | overhangs | infill 0% | 0.096 mm | Floating vertical shell | 69–69 |
| 🟥 | overhangs | layer 0.16 mm | 0.053 mm | Floating vertical shell | 5–86 |
| 🟥 | overhangs | layer 0.28 mm | 0.083 mm | Floating vertical shell | 49–49 |
| 🟥 | overhangs | pattern lightning | 0.096 mm | Floating vertical shell | 69–69 |
| 🟥 | sphere | fuzzy skin | inf mm | Inner wall, Outer wall, Overhang wall | 16–119 |
| 🟥 | sphere | pattern honeycomb | 0.042 mm | Floating vertical shell | 119–119 |
| 🟥 | thin | fuzzy skin | 0.607 mm | Outer wall | 22–59 |
| 🟥 | torus | A1 | 0.018 mm | Outer wall | 10–10 |
| 🟥 | torus | A1 mini | 0.017 mm | Outer wall | 10–10 |
| 🟥 | torus | A2L | 0.035 mm | Outer wall | 9–40 |
| 🟥 | torus | H2C | 0.018 mm | Outer wall | 10–10 |
| 🟥 | torus | H2D | 0.051 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟥 | torus | H2D Pro | 0.018 mm | Outer wall | 10–10 |
| 🟥 | torus | H2S | 0.018 mm | Outer wall | 10–10 |
| 🟥 | torus | P1P | 0.051 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟥 | torus | P1S | 0.051 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟥 | torus | P2S | 0.055 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟥 | torus | X1 | 0.051 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟥 | torus | X1E | 0.051 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟥 | torus | X2D | 0.055 mm | Outer wall | 10–10 |
| 🟥 | torus | baseline | 0.018 mm | Outer wall | 10–10 |
| 🟥 | torus | classic walls | 0.018 mm | Outer wall | 10–10 |
| 🟥 | torus | fuzzy skin | 0.099 mm | Inner wall | 29–38 |
| 🟥 | torus | infill 0% | 0.018 mm | Outer wall | 10–10 |
| 🟥 | torus | infill 40% | 0.018 mm | Outer wall | 10–10 |
| 🟥 | torus | ironing | 0.018 mm | Outer wall | 10–10 |
| 🟥 | torus | layer 0.08 mm | 0.043 mm | Inner wall, Outer wall | 2–99 |
| 🟥 | torus | layer 0.16 mm | 0.053 mm | Outer wall | 14–14 |
| 🟥 | torus | layer 0.28 mm | 0.058 mm | Outer wall | 11–15 |
| 🟥 | torus | no brim | 0.054 mm | Floating vertical shell, Outer wall | 10–44 |
| 🟥 | torus | normal supports | 0.052 mm | Outer wall | 44–44 |
| 🟥 | torus | outer brim | 0.018 mm | Outer wall | 10–10 |
| 🟥 | torus | pattern adaptivecubic | 0.052 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟥 | torus | pattern grid | 0.018 mm | Outer wall | 10–10 |
| 🟥 | torus | pattern gyroid | 0.05 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟥 | torus | pattern honeycomb | 0.051 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟥 | torus | pattern lightning | 0.052 mm | Floating vertical shell, Outer wall | 10–42 |
| 🟥 | torus | seam back | 0.051 mm | Floating vertical shell | 42–42 |
| 🟥 | torus | walls 1 | 0.018 mm | Outer wall | 10–10 |
| 🟥 | torus | walls 4 | 0.054 mm | Floating vertical shell, Outer wall | 10–43 |
| 🟥 | tower | A2L | 0.06 mm | Floating vertical shell | 394–394 |
| 🟥 | tower | H2S | 0.06 mm | Floating vertical shell | 394–394 |
| 🟥 | tower | fuzzy skin | 0.627 mm | Inner wall, Outer wall | 3–395 |
| 🟥 | tower | layer 0.08 mm | 0.072 mm | Floating vertical shell | 988–988 |
| 🟥 | tower | layer 0.28 mm | 0.06 mm | Floating vertical shell | 281–281 |
| 🟥 | tower | nozzle 0.8 mm | 0.056 mm | Floating vertical shell | 197–197 |
| 🟥 | tower | pattern honeycomb | 0.041 mm | Floating vertical shell | 394–394 |
| 🟥 | tube | A1 | 0.053 mm | Inner wall | 7–58 |
| 🟥 | tube | fuzzy skin | 0.58 mm | Inner wall, Outer wall | 8–81 |
| 🟥 | tube | layer 0.12 mm | 0.052 mm | Inner wall | 64–64 |
| 🟥 | tube | layer 0.24 mm | 0.054 mm | Inner wall, Outer wall | 24–24 |
| 🟥 | tube | layer 0.28 mm | 0.053 mm | Inner wall | 54–57 |
| 🟥 | tube | nozzle 0.2 mm | 0.053 mm | Inner wall | 2–144 |
| 🟥 | tube | nozzle 0.8 mm | 0.048 mm | Inner wall | 10–23 |
| 🟨 | overhangs | tree supports | 5.305 mm | Support | 0–72 |
| 🟨 | sphere | tree supports | 1.205 mm | Support | 0–9 |
| 🟨 | torus | tree supports | 0.734 mm | Support | 0–1 |

## Interpretation

Geometric similarity is not byte equality. Unrun cells and results from older input formats or different engine, profile, or reference image identities are not counted.
A matching refusal is recorded separately from a successful slice. A successful slice must also pass effective-settings checks.
Reported distances compare sampled per-layer extrusion paths; they are not measurements of printed-part dimensional error.
