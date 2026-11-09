# Investigation of remaining differences

The following checks use the pinned Bambu Studio reference and the packaged engines identified in the matrix report. They do not establish physical print quality.

The current 440-cell matrix has 253 byte matches, 80 within observed reference variation, three support-only
differences, 93 small model differences, eleven matching refusals and no red cells. Eleven fuzzy-skin cases are
excluded because their surface texture is intentionally random. None of the retained cases triggered the bounded
start-sequence/heater safety checks. No print was started.

| Case | Evidence | Interpretation |
|---|---|---|
| Tube, A1 | Desktop builds matched an official G-code output in all three diagnostic runs. The ARM inner-wall paths differed by about 0.032 mm near configured 0.06 mm seam gaps; dimension bounds were unchanged. Completing only those gaps gave a contour distance of about 0.011 mm. | A localized seam-path difference, eligible for yellow under the documented contour and material checks. |
| Torus, X2D | The continuous comparison found about 0.018 mm at the affected wall, versus 0.055 mm from the former point-sampling comparison. Bounds and deposited material agreed to the documented tolerances. | The old measurement overstated the path difference. The remaining difference is small. |
| Tower, 0.08 mm layers | A desktop diagnostic run reproduced the phone's internal-shell variant. Expanding the official reference sample from five to twenty produced a G-code file byte-identical to the phone output. | Observed reference nondeterminism; this candidate is a byte match. |

Disabling arc fitting for diagnostic slices did not remove the tube or torus discrepancies on the Xperia. The desktop build continued to agree with the official path at the affected features. This rules out arc fitting as the sole cause; it does not locate the exact floating-point or seam-placement operation responsible. The production engine and its upstream sources were not changed.

The 100% grid configuration was rejected by both engines because that pattern does not support 100% density. A new successful solid-fill column uses the actual Bambu enum value `zig-zag` (rectilinear), tested on all eleven models with five official reference runs each.

The continuous pass also identified three Benchy configurations (0.08 mm layers, 0.16 mm layers, and one wall)
that the previous classifier rejected because any gap-infill difference was treated as an unknown-role failure.
The inspected gap paths differed by about 0.0011–0.0015 mm, with matching deposited material and bound changes
below 0.0005 mm. Gap infill now receives the existing strict surface limits, rather than the looser internal-infill
limits; missing material or a larger thin-feature displacement still fails. These cases must not be described as
large changes to the model.

## Yellow-case investigation

The initial 98 yellow cells fell into a few repeated groups: 60 reported only floating vertical shell paths,
12 combined those with outer walls, 19 reported only outer walls, six only inner walls, and one both wall roles.
All 32 cells reporting outer walls were torus cases; all six inner-wall-only cases were tubes. Ten cells had
recognized wall seam relocations. These are reported feature groups, not a complete list of every sub-micron
or within-reference variation in their outputs.

### Repeated reference runs

Six configurations were investigated with eight additional official runs each. Three also received three new
runs of our desktop x86-64 build. The same saved phone output and resolved inputs were used throughout.

| Configuration | New official outputs byte-identical to phone | New desktop outputs byte-identical to phone |
|---|---:|---:|
| Cube, 0.24 mm layers | 3 / 8 | 1 / 3 |
| Cube, grid infill | 6 / 8 | Not run |
| Cube, normal supports | 2 / 8 | Not run |
| Cube, ironing | 4 / 8 | Not run |
| Gear, four walls | 0 / 8 | 0 / 3 |
| Benchy, baseline | 0 / 8 | 0 / 3 |

The result is four yellow-to-green changes for the cubes and one yellow-to-dark-green change for baseline
Benchy: 93 yellow cases remain, with 55 reporting only floating-shell differences and 38 reporting wall
differences (including mixed cases).

All four cube differences are therefore confirmed official nondeterminism, including the extrusion-width
change; their complete G-code, rather than just the affected contour, was reproduced by the official binary.
The new reference outputs are retained with the matrix evidence. No acceptance tolerance was changed.

For baseline Benchy, one new official run reproduced the phone's affected floating-shell geometry and
extrusion amount at zero-based layer 76, despite the whole G-code still differing. This confirms official
variation at that location. Reclassification against 28 validated official runs places the whole candidate
within observed official variation, while the G-code bytes still differ. This includes ten previously cached
reference runs beyond the original ten recorded for this cell, plus the eight new runs.
For gear, all three desktop runs and eight new official runs retained the original reference geometry at
zero-based layer 34, about 0.03181 mm from the phone's path. This remains evidence of a platform-dependent
path choice at that location, not proof of a specific floating-point instruction causing it.

### Loop endings account for much of the distance

Upstream `Fill/Fill.cpp` sets internal loop clipping to 0.15 times nozzle diameter, and
`Fill/FillFloatingConcentric.cpp` clips each loop's end to avoid extruding back onto its beginning.
For a 0.4 mm nozzle that is 0.06 mm. Moving that small gap to another corner can produce a roughly
0.03 mm path distance while leaving the underlying loop and its outer bounds effectively unchanged.
The floating-shell generator itself uses Arachne variable-width toolpaths, so selecting classic walls does
not by itself remove Arachne from this internal-path calculation.

The following diagnostics compare the phone with recorded official run 0. Only gaps near the expected
0.06 mm length were completed, solely to inspect the underlying contours. These completed paths are
never substituted into the matrix verdict.

| Configuration and zero-based layer | Raw path distance | Completed contour distance | Filament difference | Surface/path bounds difference |
|---|---:|---:|---:|---:|
| Cube, 0.24 mm, layer 78 | 0.03036 mm | 0.00084 mm | -3.4002% | 0 mm |
| Gear, four walls, layer 34 | 0.03181 mm | 0.01136 mm | -0.5820% | 0 mm |
| Benchy, baseline, layer 76 | 0.03083 mm | 0.00876 mm | +0.00062% | 0.00039 mm |

There is still real material variation in some internal paths. For the cube, the affected loop's emitted
line width was 0.391672 mm on the phone versus 0.403653 mm in original reference run 0, with 2.40040 versus
2.48489 mm of filament. Its loop direction/end gap also changed. The official binary reproduced the phone's
entire output, so this difference cannot be attributed exclusively to ARM arithmetic. Gear's remaining
0.58% material difference likewise should not be dismissed as merely reordering identical paths.

Reproduce the inventory and the gear contour diagnostic from the saved matrix with:

```sh
build/venv/bin/python equivalence/yellow_diagnostics.py
build/venv/bin/python equivalence/yellow_diagnostics.py --case 'gear|walls 4' --layer 34
```

The diagnostic reports both raw and completed distances, gap lengths, filament changes and bounds. A regression
test verifies that completing identical underlying contours still reports a material difference.

The next engine-level trace should compare Arachne loop orientation/start selection and variable-width extrusion
conversion for gear before G-code arc fitting. For torus and tube, trace seam selection before fitting; earlier
no-arc tests already showed fitting alone does not cause their discrepancy. The existing data does not yet
identify a single computation responsible for all yellow cases.

## Fuzzy skin

Fuzzy skin deliberately displaces surfaces using random numbers in upstream's `FuzzySkin.cpp` and `PerimeterGenerator.cpp`. Independent textures can therefore exceed the ordinary 0.02 mm surface-match rule even when generated by the same official build.

A diagnostic on the cube compared the phone and five official fuzzy outputs against the smooth official outer-wall rectangle, sampling by path length. The phone's signed mean displacement was -0.00154 mm and standard deviation was 0.14087 mm. Official signed means ranged from -0.00453 to +0.00419 mm and standard deviations from 0.13972 to 0.14151 mm. Those aggregate texture statistics are consistent with the official samples.

Fuzzy skin is excluded from the main matrix because its texture is intentionally random. These measurements
remain an optional historical diagnostic of the cube's texture distribution; they do not establish exact toolpath
equivalence or local geometry and strength for every model.

Reproduce this diagnostic with `build/venv/bin/python equivalence/fuzzy_stats.py`. It deliberately rejects a
non-rectangular baseline rather than treating its bounding box as the actual surface, and never awards a pass.

## Numerical comparison

The matrix's current implementation uses analytic point-to-line and point-to-arc distances. An adaptive interval bound limits the remaining numerical Hausdorff error to 0.0005 mm. Exact line and circle coverage is independent of segmentation and direction. Tests cover missing path intervals, changed hole sizes, opposite arcs with common endpoints, modal coordinates, rounded arc endpoints and misleading nearest spatial-index centres.
