# Floating-shell memory-lifetime investigation

The four-wall gear exposes a use-after-free in the pinned upstream floating-shell implementation.
This is stronger evidence than the earlier inference of an ARM-specific numerical difference. The same
OnePlus engine can produce both the original phone output and a byte-identical official output. The
production engine, upstream source tree and matrix acceptance limits have not been changed.

## Evidence

All normal and allocator-probe slices used the saved, resolved gear inputs. Successful outputs passed
the effective-setting checks. Allocator probes are separate diagnostics, not additional ordinary matrix references.

| Experiment | Result |
|---|---|
| 32 more ordinary official runs, after the 13 already recorded | All retained the original reference geometry at zero-based layer 34; none matched the original phone G-code. |
| Five OnePlus repeats | Three matched an official output byte for byte; two matched the original phone output byte for byte. |
| Five Xperia repeats | All reproduced the original phone geometry and extrusion amount on layer 34; four matched its complete G-code. |
| Official binary with `MALLOC_PERTURB_=85`, three runs | All reproduced the phone geometry and extrusion amount; two matched its complete G-code. |
| Official binary with `MALLOC_PERTURB_=170`, three runs | Same result: three geometry/material matches, two complete byte matches. |
| Official binary with malloc tcache disabled, three runs | All retained the original reference geometry and material amount. |
| Floating-shell detection disabled, three runs each on official, desktop, OnePlus and Xperia | All twelve outputs were byte-identical to each other. This is a diagnostic setting change, not a proposed production workaround. |

The main heap probes reproduced the phone's 3.38235 mm of filament on layer 34 instead of the original
reference's 3.40215 mm, together with its loop geometry. An additional run of the committed reproducer
also matched the phone's complete G-code. This makes heap-sensitive control flow a concrete explanation
for the gear difference; a fixed architecture-dependent rounding error is not sufficient to explain it.

## Exact lifetime error

Valgrind Memcheck, run with origin tracking on the packaged x86-64 engine and the original gear input,
reported reads from freed memory in this call chain:

```text
EdgeGrid::Grid::has_intersecting_edges()
FillFloatingConcentric::resplit_order_loops(...)
FillFloatingConcentric::_fill_surface_single(...)
FillFloatingConcentric::fill_surface_extrusion(...)
```

The allocation and deletion stacks both point back to `resplit_order_loops`. For one reported read,
the address was 384 bytes inside an already freed 1,232-byte point buffer. A second Memcheck run
with floating-shell detection disabled completed successfully and contained no `has_intersecting_edges`
or `resplit_order_loops` error contexts. Other unrelated memory-error contexts remained; this was not
a clean bill of health for the entire slicer.

The relevant upstream code is in `src/libslic3r/Fill/FillFloatingConcentric.cpp`, around lines 697–700:

```cpp
grid.create({ polyline.points }, scaled<coord_t>(10.), !all_extrusions[idx]->is_closed);
if (grid.has_intersecting_edges())
    is_self_intersect = true;
```

The initializer constructs a temporary `std::vector<Points>` containing a copy of the points.
`EdgeGrid::Grid::create(const std::vector<Points>&, ...)`, in `EdgeGrid.cpp`, stores pointers to those
points in its `Contour` objects. It does not take ownership. The temporary and its point buffer are
freed at the end of the `grid.create(...)` statement. The next statement dereferences those pointers.

The resulting `is_self_intersect` value enters `detect_floating_line` as a reason to skip detection.
The skipped path retains the original widths and point order; the detected path intersects and merges
segments against floating areas before selecting starts and producing extrusion paths. Thus the invalid
read lies directly upstream of the observed loop and material changes.

## Repair to validate next

Keep the copied points alive through the intersection query:

```cpp
const std::vector<Points> grid_contours{polyline.points};
grid.create(grid_contours, scaled<coord_t>(10.), !all_extrusions[idx]->is_closed);
if (grid.has_intersecting_edges())
    is_self_intersect = true;
```

This describes the local lifetime repair; it has not been applied to the production engine. It should
be tested in an isolated build, with Memcheck and both architectures, followed by the affected matrix
cases. Disabling floating-shell detection would change requested slicing behavior and is not the repair.
A repaired engine may consistently choose one valid output while the unmodified official binary retains
its memory-dependent variants; that distinction must remain explicit in equivalence reporting.

## Limits and remaining wall cases

The same heap-fill probe did not remove the tube A1 inner-wall difference (about 0.03173 mm at layer 7)
or the baseline torus outer-wall difference (about 0.01803 mm at layer 10), in three runs each.
Those wall cases still need their own seam-selection trace. This finding does not establish that all
55 internal-only yellow cases share this cause, although they use the affected floating-shell machinery.
The matrix remains at 93 yellow cases; the altered-environment outputs have not been used to turn them green.

## Reproduction

With the pinned reference image and saved matrix inputs available:

```sh
build/venv/bin/python equivalence/heap_probe.py --case 'gear|walls 4' --mode fill85 --runs 3 --layer 34
```

Other modes are `normal`, `fill170`, and `no-tcache`. The tool records image identity, environment,
G-code hashes, setting validation and optional layer measurements under `build/heap-probes/`. It creates
fresh output directories and never updates matrix grades. The raw phone-repeat and Memcheck evidence
is retained locally under `build/yellow-phone-repeats/` and `build/yellow-memcheck/`.
