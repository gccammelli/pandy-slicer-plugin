# Xperia Benchy cross-check

The 39 non-fuzzy Benchy configurations were sliced on the Xperia XQ-CC54 (Android SDK 34, arm64). The baseline was also sliced on the OnePlus 3. Neither phone's baseline G-code matched any of 20 observed official Bambu Studio runs byte for byte. The additional solid-rectilinear column in the main matrix was tested on the OnePlus only.

The table below has been reclassified with the continuous line/arc comparator. With the original ten baseline reference runs, the baseline was **yellow on both phones**. The [expanded yellow investigation](difference-investigation.md#yellow-case-investigation) now places the OnePlus baseline within observed official variation (dark green) using 28 validated official runs. This Xperia table retains its original reference sample; the Xperia baseline has not been reclassified against those additional runs. The remaining baseline differences are small floating vertical shell paths; outer, inner and overhang walls, top and bottom surfaces, and infill matched the checked official path geometry. The numerical error bound is 0.0005 mm. These are toolpath comparisons, not measurements of a printed part.

| Configuration | Result |
|---|---|
| baseline | Small model differences |
| A1 | Within observed variation; bytes differ |
| A1 mini | Within observed variation; bytes differ |
| A2L | Small model differences |
| H2C | Small model differences |
| H2D | Within observed variation; bytes differ |
| H2D Pro | Within observed variation; bytes differ |
| H2S | Small model differences |
| P1P | Small model differences |
| P1S | Small model differences |
| P2S | Small model differences |
| X1 | Within observed variation; bytes differ |
| X1E | Within observed variation; bytes differ |
| X2D | Within observed variation; bytes differ |
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
| pattern adaptivecubic | Within observed variation; bytes differ |
| walls 1 | Small model differences |
| walls 4 | Within observed variation; bytes differ |
| classic walls | Small model differences |
| normal supports | Within observed variation; bytes differ |
| tree supports | Small model differences |
| no brim | Small model differences |
| outer brim | Small model differences |
| ironing | Within observed variation; bytes differ |
| seam back | Small model differences |

Ten official runs were used for the baseline geometry classification; other rows use five. See the [main report](README.md), [comparison method](../../equivalence/README.md), and [difference investigation](difference-investigation.md) for seam, gap-infill and fuzzy-skin evidence.
