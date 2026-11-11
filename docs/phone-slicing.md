# Slicing for Pandy

The plugin receives a model from Pandy, slices it on the phone, and returns the sliced file and filament details to Pandy. Pandy remains responsible for connecting to the printer and starting the print. No printer access code is sent to the plugin.

Pandy supplies the selected plate, printer, build plate, filament and any changed slicer settings. The plugin checks the request, prepares the original 3MF for the selected printer, slices it, checks the output and returns it to Pandy. If the plugin cannot apply or confirm the requested settings, it refuses the result.

The plate editor is Pandy's Studio tab; the plugin has no screen of its own. The earlier standalone Pandy Studio app and its **Open in Pandy Studio** action are gone.

Phone slicing is Android-only. The phone checks in `engine/orca/README.md` compare OrcaSlicer G-code with the desktop build and check Bambu Studio output for safety and integrity; they do not establish printer compatibility or full fidelity for every project.
