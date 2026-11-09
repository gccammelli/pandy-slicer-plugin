# Xperia Benchy cross-check

The 40 Benchy configurations were sliced on the Xperia XQ-CC54 (Android SDK 34, arm64) using the same pinned engine and profiles as the main matrix. Each was compared against at least five official Bambu Studio runs. The baseline was also checked on the OnePlus 3.

No Xperia output was byte-identical: 29 differed beyond observed official variation, 10 had sampled geometry within that variation, and one configuration was refused by both slicers. Geometric similarity does not establish byte equality.

For the baseline, neither phone matched any of 20 official G-code outputs. A geometry recheck against ten official runs still classified both phone outputs as differing beyond the observed variation.

| Configuration | Result |
|---|---|
| baseline | Differs |
| A1 | Differs |
| A1 mini | Differs |
| A2L | Differs |
| H2C | Differs |
| H2D | Differs |
| H2D Pro | Differs |
| H2S | Differs |
| P1P | Differs |
| P1S | Differs |
| P2S | Differs |
| X1 | Within observed variation; bytes differ |
| X1E | Within observed variation; bytes differ |
| X2D | Differs |
| nozzle 0.2 mm | Differs |
| nozzle 0.6 mm | Differs |
| nozzle 0.8 mm | Within observed variation; bytes differ |
| layer 0.08 mm | Differs |
| layer 0.12 mm | Differs |
| layer 0.16 mm | Differs |
| layer 0.24 mm | Within observed variation; bytes differ |
| layer 0.28 mm | Within observed variation; bytes differ |
| infill 0% | Within observed variation; bytes differ |
| infill 40% | Within observed variation; bytes differ |
| infill 100% | Both refused |
| pattern gyroid | Differs |
| pattern grid | Differs |
| pattern honeycomb | Differs |
| pattern lightning | Differs |
| pattern adaptivecubic | Differs |
| walls 1 | Differs |
| walls 4 | Within observed variation; bytes differ |
| classic walls | Differs |
| normal supports | Within observed variation; bytes differ |
| tree supports | Differs |
| no brim | Differs |
| outer brim | Differs |
| ironing | Within observed variation; bytes differ |
| seam back | Differs |
| fuzzy skin | Differs |

The classification uses sampled per-layer extrusion paths. See the [main equivalence report](README.md) and [test documentation](../../equivalence/README.md) for the comparison method and limits.
