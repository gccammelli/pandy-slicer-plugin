# Pandy Slicer plugin

**Bambu Studio's and OrcaSlicer's slicers, on your phone, for [Pandy](https://github.com/gccammelli/pandy).**
The plugin has no screen of its own. Pandy's Studio tab is the editor: it opens the model, arranges the plate, chooses
printer, filaments and settings, and asks this plugin to slice. The plugin runs the slicer on the phone, offline, checks
the result and hands the sliced `.gcode.3mf` back. Pandy talks to the printer; the plugin never does.

The plugin does not imitate the desktop slicers: it runs them.

| Engine | Source | Notes |
|---|---|---|
| Bambu Studio 02.08.02.61 (default) | Bambu Lab's published source | [engine/README.md](engine/README.md) |
| OrcaSlicer 2.5.0 | pinned upstream commit, unmodified | [engine/orca/README.md](engine/orca/README.md) |

Each engine is its command-line slicer built with the same compiler and libraries as the official Linux build, with
its own profiles and resources. The G-code is compared with the official desktop build: Bambu Studio over a matrix of
printers and settings ([equivalence/README.md](equivalence/README.md)), OrcaSlicer over a smaller set of cases, byte
for byte apart from the timestamp comment, on a PC and on phones
([engine/orca/README.md](engine/orca/README.md#validation)).

## What it does

- Slices 3MF plates for Bambu Lab printers with either engine, with that engine's own presets and settings
- Serves each engine's profile catalog, settings schema and page layout to Pandy
- Safety check before returning a file: the printer's start sequence must be there and temperatures within limits
- Refuses a request it cannot honour exactly rather than changing engine or dropping settings

Pandy reaches it through a bound service protected by a signature permission: only an app signed with the same key can
use it ([docs/plugin-protocol.md](docs/plugin-protocol.md), [docs/phone-slicing.md](docs/phone-slicing.md)).

## Install

The plugin is sideloaded next to Pandy (arm64 phones, Android 8 or newer).

## Build

    engine/build-deps.sh aarch64 && engine/build-engine.sh aarch64 && engine/package-android.sh
    engine/orca/build-deps.sh aarch64 && engine/orca/build-engine.sh aarch64 && python3 engine/orca/package.py
    ./gradlew -Ppandy.testbed assembleDebug     (test installs; release builds drop the flag)

## Licence

AGPL-3.0, like Bambu Studio, OrcaSlicer, PrusaSlicer and Slic3r it is built on. Pandy is a separate MIT app and links
none of this code.
