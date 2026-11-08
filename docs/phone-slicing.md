# Slicing for Pandy

Pandy Studio can receive a model from Pandy, slice it on the phone, and return the sliced file and filament details to Pandy. Pandy remains responsible for connecting to the printer and starting the print. No printer access code is sent to Studio.

Pandy supplies the selected plate, printer, build plate, filament and any changed slicer settings. Studio checks the request, prepares the original 3MF for the selected printer, slices it, checks the output and returns it to Pandy. If Studio cannot apply or confirm the requested settings, it refuses the result.

The separate **Open in Pandy Studio** action opens a plain single-plate model in Studio's editor. The editor currently imports geometry rather than complete project metadata, so it refuses 3MF projects containing plate or profile settings instead of discarding them silently. Editor changes do not return to the original print in Pandy yet.

Phone slicing and the editor handoff are Android-only. This integration still requires testing both apps together; the standalone phone checks do not establish printer compatibility or full fidelity for every project.
