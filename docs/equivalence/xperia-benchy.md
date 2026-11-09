# Xperia Benchy cross-check

The 40 Benchy configurations were sliced on the Xperia XQ-CC54 (Android SDK 34, arm64) using the same pinned engine and profiles as the main matrix. The baseline was also sliced on the OnePlus 3. Neither phone's baseline G-code matched any of 20 official Bambu Studio runs byte for byte.

A geometry analysis error was corrected: extruder-only unretractions do not deposit points. In a corrected baseline comparison against one official run, both phones had identical sampled outer, inner and overhang wall paths, top and bottom surfaces, and infill paths. Floating vertical shell paths differed by at most 0.093 mm in sampled nearest-point distance; similar differences occurred between two official runs. These distances are not measurements of printed-part dimensions.

The baseline is **yellow** on the Xperia and **yellow** on the OnePlus under the current tiers. Both have small floating vertical shell path differences. Ten official runs were used for their geometry classifications.

| Configuration | Result |
|---|---|
| baseline | Small model differences |
| A1 | Small model differences |
| A1 mini | Small model differences |
| A2L | Small model differences |
| H2C | Small model differences |
| H2D | Small model differences |
| H2D Pro | Within observed variation; bytes differ |
| H2S | Small model differences |
| P1P | Small model differences |
| P1S | Small model differences |
| P2S | Small model differences |
| X1 | Within observed variation; bytes differ |
| X1E | Within observed variation; bytes differ |
| X2D | Small model differences |
| nozzle 0.2 mm | Small model differences |
| nozzle 0.6 mm | Small model differences |
| nozzle 0.8 mm | Small model differences |
| layer 0.08 mm | Small model differences |
| layer 0.12 mm | Small model differences |
| layer 0.16 mm | Small model differences |
| layer 0.24 mm | Within observed variation; bytes differ |
| layer 0.28 mm | Within observed variation; bytes differ |
| infill 0% | Within observed variation; bytes differ |
| infill 40% | Within observed variation; bytes differ |
| infill 100% | Both refused |
| pattern gyroid | Small model differences |
| pattern grid | Small model differences |
| pattern honeycomb | Small model differences |
| pattern lightning | Small model differences |
| pattern adaptivecubic | Small model differences |
| walls 1 | Small model differences |
| walls 4 | Within observed variation; bytes differ |
| classic walls | Small model differences |
| normal supports | Within observed variation; bytes differ |
| tree supports | Small model differences |
| no brim | Small model differences |
| outer brim | Small model differences |
| ironing | Within observed variation; bytes differ |
| seam back | Small model differences |
| fuzzy skin | Significant difference or failed check |

All other rows use five official reference runs. The classification uses sampled per-layer extrusion paths; sampling can itself affect small distances. See the [main equivalence report](README.md) and [test documentation](../../equivalence/README.md) for the comparison method and limits.
