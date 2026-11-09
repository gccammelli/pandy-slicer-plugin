# Equivalence tests: is the phone's G-code Bambu Studio's G-code?

> **Historical results are invalid for the named presets.** Before input format 3, the CLI received
> inherit-only presets and silently used fallback values. Format 3 resolves profiles explicitly, validates
> effective output settings, and invalidates the old caches. Only results regenerated with format 3 apply.

The claim Pandy Studio makes, and these tests check: **for the same plate and settings, the engine writes the same
G-code as the official Bambu Studio 02.08.02.61, byte for byte**, on every Bambu printer and for every print setting.

## What is compared

* **Reference**: the official Bambu Studio AppImage, in Pandy Slicer's Docker image (its Dockerfile pins the
  download's SHA-256), run as Pandy Slicer runs it.
* **Candidates**: the engine built for x86-64 (checks the build method against the AppImage), the arm64 engine under
  QEMU, and the arm64 engine on real phones over adb (`run.py check --candidate device:SERIAL`), the same file the app
  ships (`engine/package-android.sh`).
* **Inputs**: every case is a plain 3MF of generated models or the reference's bundled Benchy (`pandy_equiv/models.py`),
  plus complete system presets resolved through their inheritance and includes, with the case's changes applied, and the command line
  `--load-settings machine.json;process.json --load-filaments … --slice 0 --export-3mf out.gcode.3mf model.3mf`.
  The app builds slice jobs the same way (`shared/…/slicer/Job.kt`).
* **Verdict**: every `Metadata/plate_N.gcode` must be byte-identical for a byte-identical pass. Nothing in the G-code is normalised. A case
  where the reference refuses the settings passes only if the candidate refuses them with the same return code.
  Other files of the 3MF are compared too and reported; only their creation dates are normalised (`compare.py`).
  Successful outputs must also confirm their effective printer, process, filament and requested override settings.
  The matrix distinguishes byte matches, approximate geometry within observed reference variation, matching refusals,
  support differences, and failures; geometric similarity is not byte equality.
  The checks deliberately fail a successful slice when a requested override was silently changed or clamped, even if
  both engines make the same change; that outcome does not prove the requested settings were applied.

### Benchy provenance

The `benchy` case uses `resources/model/3DBenchy.stl` from the pinned official reference image. Its SHA-256 is
`bda2c80f10195078cbca11753584087341ec13d530ac9282482bcebf6de9c59b`; a different or missing file fails the test.
The original 3DBenchy was designed by Daniel Norée for Creative Tools; the current [3DBenchy license](https://www.3dbenchy.com/license/)
is CC0 1.0. The test imports the mesh at its original size and centres it on the plate.

## Suites

| Suite | Cases | What |
|---|---|---|
| `smoke` | 26 | every Bambu printer model with its default process and PLA; supports (tree, normal), vase mode, sequential printing, ironing, fuzzy skin, Arachne/classic walls, two filaments, H2D two nozzles |
| `benchy` | 1 | the reference's hash-verified 3DBenchy on X1 Carbon, standard PLA settings |
| `sweep` | 897 | every process and filament option of `schema.json` (extracted from upstream `PrintConfig.cpp`), one at a time, at each interesting value: both booleans, every enum choice, min, max, values around the default |
| `random:SEED:N` | N | N seeded combinations of 12 changed settings on 1-3 random models and a random printer; a seed re-runs exactly |

## Determinism (read this before reading a report)

**The official Bambu Studio is not deterministic.** Slicing the same input twice gives different G-code: in the
first run of the smoke suite, 18 of 26 cases differed between two runs of the official build itself, in
toolpath order, loop start points, fan speeds and estimates. It stays nondeterministic pinned to one CPU, with
address-space randomisation off, a frozen clock (libfaketime) and fixed `getrandom()` output (the last two only make
it rarer). So "byte-identical to Bambu Studio" can only mean: identical to *an* output Bambu Studio produces for that
input. The tests therefore:

1. pin every run (reference and candidates) to one CPU, where variation is smallest;
2. record the reference's own variation: `run.py check --candidate reference` slices every case again with the
   official build and reports which cases it fails to reproduce;
3. for those cases, accept a candidate output only if it equals one of the reference outputs seen (`--ref-runs N`
   collects N reference outputs per case).

The engine runs Bambu Studio's code unchanged, so it inherits this variation rather than adding to it: a case the
reference reproduces must be reproduced by the engine exactly.

`distribution.py` makes the comparison directly: it slices one case N times with each and compares the sets of
outputs. **Historical fallback-profile result, not evidence for the named presets:** the first result (A1 mini, feature plate, N = 20, x86-64 engine) was that the official build gave 11 distinct outputs,
the engine 8; 7 are shared, the most frequent one is the same on both (5 runs each), and 17 of the engine's 20 runs
are byte-identical to an output of the official build.

On a phone (Sony Xperia 10 IV, arm64, X1 Carbon feature plate, N = 20): with the first arm64 build no phone output
matched any official one: Eigen's ARM code used fused multiply-add instructions, which round differently from x86-64.
Built without them (`engine/toolchains/aarch64-linux-gnu.cmake`), 19 of the phone's 20 slices are byte-identical to
an output of the official build, sharing 5 variants with it.

### What we know about the cause

Slicing is single-threaded when pinned to one CPU (the only other thread starts at exit), and the variation stays
with the clock frozen, `getrandom` and `std::random_device` fixed, ASLR off, a fixed hostname and fixed file dates.
Valgrind finds uninitialised reads in upstream's G-code generation, a sign the remaining randomness comes from
memory contents (the kernel seeds every process's stack with random bytes):

* `GCodeWriter::m_last_bed_temperature` is never initialised (its initialiser is commented out in
  `GCodeWriter.hpp`). The first-layer bed temperature command is skipped when the garbage equals the temperature.
* `RetractWhenCrossingPerimeters::m_layer` is never initialised before its first comparison.
* `PartPlateList` fields are printed into the 3MF's plate metadata uninitialised.

These are upstream bugs; the engine keeps them, so it behaves as the official build does.

## Run

```
sudo docker build -t pandy-studio-reference:02.08.02.61 ../pandy-slicer/pandy_slicer
python3 run.py profiles
python3 run.py check --suite smoke --candidate x86_64
python3 run.py check --suite benchy --candidate device:SERIAL --package ../build/aarch64/package --ref-runs 5
python3 run.py check --suite sweep --candidate device:SERIAL --package ../build/aarch64/package
```

Reports land in `build/equiv/<run>/report.md` (one row per case: status, G-code SHA-256 of both sides, timings) with
`results.jsonl` holding every detail, including the first differing line of any failure.
