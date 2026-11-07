# Equivalence tests: is the phone's G-code Bambu Studio's G-code?

The claim Pandy Studio makes, and these tests check: **for the same plate and settings, the engine writes the same
G-code as the official Bambu Studio 02.08.02.61, byte for byte**, on every Bambu printer and for every print setting.

## What is compared

* **Reference**: the official Bambu Studio AppImage, in Pandy Slicer's Docker image (its Dockerfile pins the
  download's SHA-256), run as Pandy Slicer runs it.
* **Candidates**: the engine built for x86-64 (checks the build method against the AppImage), the arm64 engine under
  QEMU, and the arm64 engine on real phones over adb (`run.py check --candidate device:SERIAL`), the same file the app
  ships (`engine/package-android.sh`).
* **Inputs**: every case is a plain 3MF of generated models (`pandy_equiv/models.py`) plus user presets that
  inherit Bambu's system presets with the case's changes, and the command line
  `--load-settings machine.json;process.json --load-filaments … --slice 0 --export-3mf out.gcode.3mf model.3mf`.
  The app builds slice jobs the same way (`shared/…/slicer/Job.kt`).
* **Verdict**: every `Metadata/plate_N.gcode` must be byte-identical. Nothing in the G-code is normalised. A case
  where the reference refuses the settings passes only if the candidate refuses them with the same return code.
  Other files of the 3MF are compared too and reported; only their creation dates are normalised (`compare.py`).

## Suites

| Suite | Cases | What |
|---|---|---|
| `smoke` | 26 | every Bambu printer model with its default process and PLA; supports (tree, normal), vase mode, sequential printing, ironing, fuzzy skin, Arachne/classic walls, two filaments, H2D two nozzles |
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

## Run

```
sudo docker build -t pandy-studio-reference:02.08.02.61 ../pandy-slicer/pandy_slicer
python3 run.py profiles
python3 run.py check --suite smoke --candidate x86_64
python3 run.py check --suite sweep --candidate device:SERIAL --package ../build/aarch64/package
```

Reports land in `build/equiv/<run>/report.md` (one row per case: status, G-code SHA-256 of both sides, timings) with
`results.jsonl` holding every detail, including the first differing line of any failure.
