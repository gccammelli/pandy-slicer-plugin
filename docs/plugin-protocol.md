# Pandy slicer plugin protocol, version 1

The Android plugin is `io.github.gccammelli.pandy.slicer` (append `.testbed` for testbed builds). Bind explicitly to its `io.github.gccammelli.pandy.slicer.BIND_V1` service. Its `<applicationId>.permission.SLICE` permission has signature protection; Pandy must request that permission and be signed by the same key. Neither the editor nor printer credentials are part of the service.

Messages use Android `Messenger`. Each request must have `replyTo` and a `request_id` string (1–256 characters, no control characters). The same ID is returned in every response. Only one operation is active at a time. The codes are:

| Request | Code | Data |
| --- | --- | --- |
| Capabilities | 1 | none; returns supported server settings, engine SHA-256, and resource version |
| Slice | 2 | `mode`, `request_json`, `input` and `output` |
| Cancel | 3 | ID of the operation to cancel |
| Resources | 4 | `output` |

`input` and `output` are read- and write-capable `ParcelFileDescriptor`s supplied by the caller. The caller owns the files. Model and result files are limited to 100 MB; requests are limited to 128,000 characters. The service closes its descriptors and removes engine scratch files. Progress (100), success (101), and error (102) replies contain a `text` string; a cancelled operation reports an error. The caller must reject mismatched IDs and verify results before printing.

For `mode=server`, `request_json` is the version-1 original-project request documented in Pandy's integration notes. The service validates the request and the project, prepares it with the server-compatible rules, verifies the generated plate and applied settings, and replies with the version-1 plate metadata.

When conversion creates an external process preset, the plugin resolves its full trusted system profile before invoking the CLI. The CLI can otherwise silently use generic process defaults for an inherit-only preset; this correction intentionally goes beyond the older server's input preparation.

For `mode=editor`, the JSON contains `version`, `printer`, `process`, `filaments`, `process_overrides`, `filament_overrides`, and `printer_includes`. Overrides and includes map setting keys to strings or arrays of strings. Preset names refer to the plugin's profiles. The includes must match the plugin's printer profile, so its start/end G-code cannot be substituted by an IPC caller. The generated job uses `SliceJob.resolvedFiles()` and `SliceJob.arguments()`; complete trusted machine, process and filament profiles are resolved before overrides are applied. The success text is `{"version":1}`; the 3MF is written to the output descriptor.

Resources writes the plugin's engine resource ZIP to the output descriptor and replies with `{"version":1,"sha256":"..."}`, the SHA-256 of those exact ZIP bytes. The caller should check the digest, bound extraction, and reject unsafe paths before using the profiles. The archive is provided by the AGPL plugin at runtime and is not linked into Pandy.
