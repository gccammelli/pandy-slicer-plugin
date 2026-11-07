package io.github.gccammelli.pandystudio.slicer

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** Reads files of the engine's resources directory (resources/profiles/...), relative paths. */
fun interface ProfileSource {
    fun read(path: String): String?
}

/** A system preset as Bambu Studio lists it. */
data class Preset(val name: String, val type: String, val values: Map<String, Setting>) {
    operator fun get(key: String): Setting? = values[key]
    fun string(key: String) = values[key]?.first
}

/** A printer the app can slice for: its 0.2-0.8 mm nozzle presets share one model. */
data class PrinterModel(val model: String, val nozzles: List<Preset>) {
    val displayName get() = model.removePrefix("Bambu Lab ")
}

/**
 * Bambu's system presets (resources/profiles/BBL), read the way Bambu Studio reads them: the vendor index BBL.json
 * lists every preset file; a preset's "inherits" parent is applied first, then its "include" templates, then its own
 * keys. The engine resolves presets itself when slicing; this is for choosing them and showing their values.
 */
class PresetLibrary(private val source: ProfileSource, vendor: String = "BBL") {
    private val json = Json { ignoreUnknownKeys = true }
    private val raw = mutableMapOf<String, JsonObject>()
    private val resolved = mutableMapOf<String, Preset>()
    private val paths = mutableMapOf<String, String>()
    private val index: Map<String, List<String>>

    init {
        val idx = json.parseToJsonElement(source.read("profiles/$vendor.json") ?: error("No $vendor profiles")).jsonObject
        index = listOf("machine_list", "process_list", "filament_list").associateWith { list ->
            idx[list]?.jsonArray?.mapNotNull { e ->
                val o = e.jsonObject
                val name = o["name"]?.jsonPrimitive?.content ?: return@mapNotNull null
                val path = o["sub_path"]?.jsonPrimitive?.content ?: return@mapNotNull null
                paths[name] = "profiles/$vendor/$path"
                name
            } ?: emptyList()
        }
    }

    private fun rawOf(name: String): JsonObject? = raw.getOrPut(name) {
        val text = paths[name]?.let(source::read) ?: return null
        json.parseToJsonElement(text).jsonObject
    }

    /** The preset [name] with inheritance applied, or null when Bambu has no such preset. */
    fun preset(name: String): Preset? = resolved[name] ?: run {
        val own = rawOf(name) ?: return null
        val values = linkedMapOf<String, Setting>()
        own["inherits"]?.jsonPrimitive?.content?.takeIf { it.isNotEmpty() }?.let { parent -> preset(parent)?.values?.let(values::putAll) }
        own["include"]?.let { inc -> (inc as? JsonArray)?.forEach { i -> preset(i.jsonPrimitive.content)?.values?.let(values::putAll) } }
        for ((k, v) in own) if (k !in META) values[k] = v.toSetting()
        Preset(name, own["type"]?.jsonPrimitive?.content ?: "", values).also { resolved[name] = it }
    }

    private fun instantiable(list: String) = index[list].orEmpty().filter { rawOf(it)?.get("instantiation")?.jsonPrimitive?.content == "true" }

    /** Bambu Lab printers, grouped by model, nozzles sorted by size. */
    fun printers(): List<PrinterModel> = instantiable("machine_list").mapNotNull(::preset)
        .groupBy { it.string("printer_model") ?: it.name.substringBefore(" 0.") }
        .map { (model, presets) -> PrinterModel(model, presets.sortedBy { it.string("nozzle_diameter")?.toDoubleOrNull() ?: 0.0 }) }
        .sortedBy { it.model }

    /** Process presets made for [printer] (a printer preset name), in Bambu's order (layer height). */
    fun processes(printer: String) = instantiable("process_list").filter { compatible(it, printer) }.mapNotNull(::preset)
        .sortedBy { it.string("layer_height")?.toDoubleOrNull() ?: 0.0 }

    /** Filament presets made for [printer]. */
    fun filaments(printer: String) = instantiable("filament_list").filter { compatible(it, printer) }.mapNotNull(::preset)

    private fun compatible(name: String, printer: String): Boolean {
        val list = rawOf(name)?.get("compatible_printers") as? JsonArray ?: return false
        return list.any { it.jsonPrimitive.content == printer }
    }

    companion object {
        private val META = setOf("name", "inherits", "from", "instantiation", "setting_id", "type", "include", "renamed_from")

        private fun JsonElement.toSetting(): Setting = when (this) {
            is JsonArray -> Setting.Many(map { (it as? JsonPrimitive)?.content ?: it.toString() })
            is JsonPrimitive -> Setting.One(content)
            else -> Setting.One(toString())
        }
    }
}
