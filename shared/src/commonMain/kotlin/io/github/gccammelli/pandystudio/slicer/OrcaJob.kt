package io.github.gccammelli.pandystudio.slicer

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject

/** Orca resolves inherited CLI presets through its user-preset registry. */
object OrcaJob {
    fun files(job: SliceJob, library: PresetLibrary): Map<String, ByteArray> = job.resolvedFiles(library).mapValues { (name, bytes) ->
        if (!name.endsWith(".json")) bytes else {
            val preset = Json.parseToJsonElement(bytes.decodeToString()).jsonObject
            JsonObject(preset + ("version" to JsonPrimitive(EngineKind.ORCA.version))).toString().encodeToByteArray()
        }
    }

    /** --strict alone does not reject config substitutions; inspect the structured warnings too. */
    fun outcome(text: String?): SliceOutcome? {
        val result = SliceOutcome.parse(text) ?: return null
        if (!result.ok) return result
        val warnings = runCatching { Json.parseToJsonElement(text!!).jsonObject["warnings"] as? JsonArray }.getOrNull()
        return if (warnings != null && warnings.isEmpty()) result else
            SliceOutcome(-1, "Orca reported warnings or could not confirm the requested settings. Check the slice log.")
    }

    /** Registry paths -> job input paths. Names match the names in SliceJob.files(). */
    fun presetLinks(filaments: Int): Map<String, String> {
        require(filaments in 1..16)
        return buildMap {
            put("user/default/machine/case printer.json", "machine.json")
            put("user/default/process/case process.json", "process.json")
            repeat(filaments) { i -> put("user/default/filament/case filament ${i + 1}.json", "filament${i + 1}.json") }
        }
    }
}
