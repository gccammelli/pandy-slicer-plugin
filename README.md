# Pandy Studio

**Bambu Studio's slicer, on your phone.** Open an STL or 3MF, arrange it on the plate, choose printer, filaments and
settings, slice on the phone, look through the layers, and send the file to your printer with
[Pandy](https://github.com/gccammelli/pandy).

Pandy Studio does not imitate Bambu Studio's slicing: it runs it. The engine is Bambu Studio 02.08.02.61's own
command-line slicer, built from Bambu Lab's published source with the same compiler and libraries as the official
Linux build ([engine/README.md](engine/README.md)). Every release is tested against the official Bambu Studio on
every Bambu printer and every print setting, and the G-code must match byte for byte
([equivalence/README.md](equivalence/README.md)).

## Features

- Plate editor: orbit, zoom and pan; tap to select, drag to move; rotate, tip over, scale, duplicate, arrange
- All Bambu Lab printers and nozzles, Bambu's system process and filament presets
- Up to 16 filaments with colours, assigned per object
- Every print setting, on Bambu Studio's own pages and groups, with its names, limits and tooltips
- Slicing on the phone, offline, with a layer-by-layer preview coloured by feature, time and filament estimates
- Safety check before sending: the printer's start sequence must be there and temperatures within limits
- Print with Pandy, share, or save the sliced `.gcode.3mf`

Android first (arm64); the app is Kotlin Multiplatform and Compose, so iOS shares all but the 3D view and the engine
runner.

## Install

Pandy Studio is sideloaded. It targets Android API 28 so it can run the engine from its own files, which Google Play
does not allow.

## Build

    engine/build-deps.sh aarch64 && engine/build-engine.sh aarch64 && engine/package-android.sh
    ./gradlew -Ppandy.testbed assembleDebug     (test installs; release builds drop the flag)

## Licence

AGPL-3.0, like Bambu Studio, PrusaSlicer and Slic3r it is built on.
