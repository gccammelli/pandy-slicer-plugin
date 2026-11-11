package io.github.gccammelli.pandystudio.slicer

/** Stable IPC identities. Each engine owns its executable, presets and option schema. */
enum class EngineKind(
    val id: String,
    val displayName: String,
    val version: String,
    val executable: String,
    val resourceAsset: String,
    val supportsServer: Boolean,
) {
    BAMBU("bambu", "Bambu Studio", "02.08.02.61", "libpandy_engine.so", "engine-resources", true),
    ORCA("orca", "OrcaSlicer", "2.5.0", "libpandy_orca.so", "orca-resources", false);

    val profileRoot: String get() = if (this == ORCA) "pandy/editor" else "resources"

    /** Orca clients must bind their job to the exact schema/profile package they used. */
    fun checkResourceVersion(requested: String?, installed: String) {
        require((this == BAMBU && requested == null) || requested == installed) {
            "Engine resources changed or were not selected. Reload ${displayName} profiles."
        }
    }

    companion object {
        /** Omission preserves protocol v1's Bambu behavior; invalid IDs never fall back. */
        fun parse(id: String?): EngineKind = if (id == null) BAMBU else
            entries.singleOrNull { it.id == id } ?: error("Unsupported slicing engine: $id")
    }
}
