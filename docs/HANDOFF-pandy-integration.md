# Handoff: Pandy ↔ Pandy Studio phone slicing

> **Superseded (2026-11-08).** The plan changed: Pandy gets a Studio tab with the plate editor (MIT, moved into
> Pandy) and the engine becomes a separately installed plugin APK that Pandy calls through a signature-protected
> service. The two-app request/result contract below is no longer the target.

Goal: Pandy can use Pandy Studio (on the same phone) instead of the Pandy Slicer container to slice a model, with the
same result. The contract is `~/projects/pandy-studio-integration/docs/phone-slicer-integration.md` (Android v1:
`CAPABILITIES_V1`, `SLICE_V1`, `EDIT_V1`; request/result JSON; URI grants; limits). Read it first; it is the spec.

## Work in two separate runs, one repository each

Run 1 implements the Studio side and must pass before Run 2 starts. Never edit both repositories in one run.

### Run 1: Pandy Studio (`~/projects/pandy-studio`)

1. Exported activity (or one activity with three intent filters, default category) for the three actions; return
   `RESULT_OK` with `request_id` + `result_json`, or `RESULT_CANCELED`. Reject unknown `version`, missing or
   oversized input (100 MB file, 128,000-character JSON), and any request not matching the contract.
2. `CAPABILITIES_V1`: the settings schema in the same version-1 format as Pandy Slicer's `/settings`
   (`~/projects/pandy-slicer/pandy_slicer/server.py`), built from `equivalence/schema.json` + the presets, minus
   `BLOCKED_OPTIONS` (`slicer/Job.kt`).
3. `SLICE_V1`: port Pandy Slicer's server logic to Kotlin so the phone runs the **same CLI arguments on the original
   3MF** as the container: `conversion()`, `heal()`, `set_bed_type()`, `as_project()`, `bare_model()`, `keep_pictures()`
   and `check_safe()` from `server.py`, then `AndroidEngine` with those arguments. Do NOT rebuild the 3MF through the
   plate editor (that loses plates, per-object filaments, modifiers). Reject what cannot be preserved. Return the
   sliced file through a `FileProvider` URI owned by Studio, and the result JSON (`source_plate`, `printer`,
   `bed_type` echoed; `project_preserved`; `output_plate`; filaments 1–16 with type and colour from the sliced 3MF;
   `applied_settings` exactly equal to the requested overrides).
4. `EDIT_V1`: open the plate editor with the model (one-way handoff; no automatic print).
5. Tests (required, `./gradlew :shared:testDebugUnitTest`): request parsing and rejection cases; result JSON; a parity
   test proving the Kotlin port produces the same files and arguments as `server.py` for representative inputs
   (MakerWorld-style project with 2 plates and 2 filaments, plain STL, bed-type change, printer conversion). Generate
   the expected values by running the Python functions, as `JobParityTest` does.
6. Device check: install with `./gradlew -Ppandy.testbed assembleDebug` (package `io.github.gccammelli.pandystudio.testbed`)
   on the test phone (`adb devices`), drive a `SLICE_V1` request with `adb shell am start` and a test file, and confirm
   the returned 3MF passes `check_safe`.

### Run 2: Pandy (`~/projects/pandy-studio-integration`, branch `integration/pandy-studio`)

Finish the Pandy side already started there (`PhoneSlicer.kt`, manifest queries, `AdvancedSlicerSettings`). Keep the
container path unchanged and the default. Test against the real Studio build from Run 1 on the test phone; never start a
real print (the owner must be asked first).

## Rules (both runs)

* Do not touch `engine/`, `equivalence/`, `third_party/`, signing, release or CI files, or the Pandy Slicer repository.
* Do not commit, push, merge or open pull requests: leave the work uncommitted for review.
* Testbed package ids only; never uninstall or overwrite the real `io.github.gccammelli.pandy` app.
* Privacy: demo names only; no real names, cats, devices, accounts or LAN addresses (use 10.20.x.x) in code or tests.
* Every behaviour change gets a test; never weaken an existing test.
* Report what was actually run (tests, device checks) and what was not, honestly.
