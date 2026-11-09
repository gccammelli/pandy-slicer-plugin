package io.github.gccammelli.pandystudio.slicer

import io.github.gccammelli.pandystudio.io.Zip
import kotlinx.serialization.json.*

/** Inputs for a server-style CLI run. Generated presets live in the job directory, never the shared resources. */
data class ServerJob(val files: Map<String, ByteArray>, val arguments: List<String>, val source: ByteArray)

/** Prepares the original 3MF using the container slicer's printer, plate and process selection rules. */
object ServerPort {
    private val json = Json { prettyPrint = true }
    private const val SETTINGS = "Metadata/project_settings.config"
    private const val MODEL = "Metadata/model_settings.config"
    private val gcodes = setOf("machine_start_gcode", "machine_end_gcode", "change_filament_gcode", "layer_change_gcode", "time_lapse_gcode")
    private val beds = mapOf("cool_plate" to "Cool Plate", "eng_plate" to "Engineering Plate", "hot_plate" to "High Temp Plate", "textured_plate" to "Textured PEI Plate", "supertack_plate" to "Supertack Plate")

    private fun readObject(bytes: ByteArray): JsonObject = Json.parseToJsonElement(bytes.decodeToString()).jsonObject
    private fun encoded(o: JsonObject) = json.encodeToString(JsonObject.serializer(), o).encodeToByteArray()

    /** Resolve externally loaded process presets before the CLI, which otherwise falls back to generic values. */
    fun resolveProcess(job: ServerJob, profiles: ProfileSource): ServerJob {
        val file = job.files["process.json"] ?: return job
        val requested = readObject(file)
        val name = requested.string("inherits")
        require(name.isNotEmpty()) { "Missing process preset." }
        val preset = requireNotNull(PresetLibrary(profiles).preset(name)) { "Missing process preset: $name" }
        val values = preset.values.filterKeys { it !in BLOCKED_OPTIONS }.mapValues { it.value.json }
        val merged = JsonObject(values + requested.filterKeys { it !in BLOCKED_OPTIONS })
        return job.copy(files = job.files + ("process.json" to encoded(merged)))
    }
    private fun JsonObject.string(key: String) = (this[key] as? JsonPrimitive)?.contentOrNull.orEmpty()
    private fun JsonObject.strings(key: String) = (this[key] as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }.orEmpty()
    private fun safeName(name: String) = name.isNotEmpty() && !name.startsWith('.') && name.none { it == '/' || it == '\\' || it == '\u0000' }
    private fun raw(source: ProfileSource, folder: String, name: String): JsonObject? {
        if (!safeName(name)) return null
        return source.read("profiles/BBL/$folder/$name.json")?.let { Json.parseToJsonElement(it).jsonObject }
    }
    private fun flatten(source: ProfileSource, folder: String, name: String, depth: Int = 0): JsonObject {
        if (depth > 6) return JsonObject(emptyMap())
        val own = raw(source, folder, name) ?: return JsonObject(emptyMap())
        return JsonObject(flatten(source, folder, own.string("inherits"), depth + 1) + own.filterKeys { it != "inherits" })
    }
    private fun systemGcodes(source: ProfileSource, machine: String): Map<String, JsonElement> {
        val preset = raw(source, "machine", machine) ?: return emptyMap()
        val out = linkedMapOf<String, JsonElement>()
        preset.strings("include").forEach { name -> raw(source, "machine", name)?.filterKeys { it in gcodes }?.let(out::putAll) }
        preset.filter { (k, v) -> k in gcodes && v.toString() != "\"\"" }.let(out::putAll)
        return out
    }
    private fun bedSource(data: MutableMap<String, ByteArray>, plate: Int, bed: String) {
        val label = beds[bed] ?: return
        val xml = data[MODEL]?.decodeToString() ?: return
        val block = Regex("<plate\\b[^>]*>.*?</plate>", setOf(RegexOption.DOT_MATCHES_ALL))
        val metadata = Regex("<metadata\\b(?=[^>]*\\bkey=[\"']plater_id[\"'])(?=[^>]*\\bvalue=[\"'](\\d+)[\"'])[^>]*/>")
        val updated = block.replace(xml) { match ->
            if (metadata.find(match.value)?.groupValues?.get(1)?.toIntOrNull() != plate) match.value else {
                var text = match.value; var changed = false
                for (key in listOf("curr_bed_type", "bed_type")) {
                    val pat = Regex("<metadata\\b(?=[^>]*\\bkey=[\"']$key[\"'])(?=[^>]*\\bvalue=[\"'][^\"']*[\"'])[^>]*/>")
                    if (pat.containsMatchIn(text)) { text = pat.replaceFirst(text, "<metadata key=\"$key\" value=\"$label\"/>"); changed = true }
                }
                if (!changed) text = text.replaceFirst("</plate>", "<metadata key=\"bed_type\" value=\"$label\"/>\n</plate>")
                text
            }
        }
        if (updated != xml) {
            data[MODEL] = updated.encodeToByteArray()
            data[SETTINGS]?.let { data[SETTINGS] = encoded(JsonObject(readObject(it) + ("curr_bed_type" to JsonPrimitive(label)))) }
        }
    }

    fun prepare(request: PhoneRequest, original: ByteArray, profiles: ProfileSource, profileBase: String): ServerJob {
        require(original.isNotEmpty() && original.size <= PhoneProtocol.MAX_MODEL) { "Invalid model size." }
        val data = Zip.read(original).toMutableMap()
        require(data.size <= 5000 && data.keys.any { it.endsWith(".model", ignoreCase = true) }) { "Invalid 3MF project." }
        require(raw(profiles, "machine", request.printer) != null) { "Unknown printer preset." }
        val bare = SETTINGS !in data
        if (bare) {
            val base = mutableMapOf<String, JsonElement>("printer_settings_id" to JsonPrimitive(""), "print_settings_id" to JsonPrimitive(""), "filament_settings_id" to JsonArray(emptyList()))
            beds[request.bed]?.let { base["curr_bed_type"] = JsonPrimitive(it) }
            data[SETTINGS] = encoded(JsonObject(base))
        }
        bedSource(data, request.plate, request.bed)
        var cfg = readObject(data.getValue(SETTINGS))
        // Untrusted project scripts cannot be passed to the executable, even if the UI does not expose them.
        fun hasValue(value: JsonElement?): Boolean = when (value) {
            null, JsonNull -> false
            is JsonPrimitive -> value.contentOrNull?.isNotBlank() == true
            is JsonArray -> value.any { hasValue(it) }
            else -> true
        }
        require(!hasValue(cfg["post_process"]) && !hasValue(cfg["gcode_substitutions"])) { "The project contains blocked slicer options." }
        cfg = JsonObject(cfg.filterKeys { it !in BLOCKED_OPTIONS })
        val modelXml = data[MODEL]?.decodeToString().orEmpty()
        require(BLOCKED_OPTIONS.none { key -> Regex("\\bkey=[\"']${Regex.escape(key)}[\"']").containsMatchIn(modelXml) }) { "The project contains blocked object settings." }
        if (request.settings.isNotEmpty()) {
            require(data.keys.none { it.equals("Metadata/Slic3r_PE_model.config", true) || it.equals("Metadata/layer_config_ranges.xml", true) || it.equals("Metadata/layer_heights_profile.txt", true) }) { "The project has settings that require editing in Studio." }
            require(request.settings.keys.none { key -> Regex("\\bkey=[\"']${Regex.escape(key)}[\"']").containsMatchIn(modelXml) }) { "The project has object-specific settings." }
            val layerKeys = request.settings.keys.intersect(setOf("layer_height", "initial_layer_print_height"))
            if (layerKeys.isNotEmpty()) {
                val machine = flatten(profiles, "machine", request.printer).toMutableMap()
                (machine["include"] as? JsonArray)?.forEach { inc ->
                    raw(profiles, "machine", inc.jsonPrimitive.content)?.filterKeys { it in setOf("nozzle_diameter", "min_layer_height", "max_layer_height") }?.let(machine::putAll)
                }
                if (request.printer == cfg.string("printer_settings_id")) for (key in listOf("nozzle_diameter", "min_layer_height", "max_layer_height")) if (machine[key] == null) cfg[key]?.let { machine[key] = it }
                fun numbers(key: String): List<Double> {
                    val value = machine[key] ?: return emptyList()
                    return (if (value is JsonArray) value.toList() else listOf(value)).mapNotNull { (it as? JsonPrimitive)?.contentOrNull?.toDoubleOrNull()?.takeIf { n -> n.isFinite() && n > 0 } }
                }
                val nozzle = numbers("nozzle_diameter").minOrNull() ?: throw IllegalArgumentException("Cannot determine the nozzle size for the selected layer height.")
                val min = numbers("min_layer_height").maxOrNull() ?: 0.0
                val max = (numbers("max_layer_height") + nozzle * 0.8).minOrNull()!!
                require(layerKeys.all { request.settings.getValue(it).toDouble() in (min - 1e-9)..(max + 1e-9) }) { "Layer height is outside the printer nozzle's limits." }
            }
        }
        data[SETTINGS] = encoded(JsonObject(cfg + systemGcodes(profiles, cfg.string("printer_settings_id"))))
        val src = Zip.write(data.toList(), true)
        val files = linkedMapOf("model.3mf" to src)
        val args = mutableListOf<String>()
        val from = cfg.string("printer_settings_id")
        if (request.printer != from) {
            require(raw(profiles, "machine", request.printer) != null) { "Unknown printer preset." }
            val machine = flatten(profiles, "machine", request.printer).toMutableMap()
            (machine.remove("include") as? JsonArray)?.forEach { inc ->
                raw(profiles, "machine", inc.jsonPrimitive.content)?.filterKeys { it !in setOf("name", "instantiation") }?.let(machine::putAll)
            }
            val defaultProcess = (machine["default_print_profile"] as? JsonPrimitive)?.contentOrNull.orEmpty()
            val suffix = defaultProcess.substringAfter(" @", "")
            val base = cfg.string("print_settings_id").substringBefore(" @")
            val target = "$base @$suffix".takeIf { raw(profiles, "process", it) != null } ?: defaultProcess
            require(target.isNotEmpty()) { "The printer has no process preset." }
            val process = mutableMapOf<String, JsonElement>("type" to JsonPrimitive("process"), "from" to JsonPrimitive("User"), "name" to JsonPrimitive("pandy process"), "inherits" to JsonPrimitive(target), "print_settings_id" to JsonPrimitive("pandy process"), "compatible_printers" to JsonArray(listOf(JsonPrimitive(request.printer))))
            cfg.strings("different_settings_to_system").firstOrNull().orEmpty().split(';').filter { it.isNotEmpty() && it !in BLOCKED_OPTIONS }.forEach { k -> cfg[k]?.let { process[k] = it } }
            if (from.isEmpty()) cfg["curr_bed_type"]?.let { process["curr_bed_type"] = it }
            files["machine.json"] = encoded(JsonObject(machine)); files["process.json"] = encoded(JsonObject(process))
            args += listOf("--load-settings", "machine.json;process.json")
            val filaments = cfg.strings("filament_settings_id").map { it.substringBefore(" @") + " @$suffix" }
            if (filaments.isEmpty()) {
                val kind = request.filamentType.orEmpty().replace(Regex("[^A-Za-z0-9+\\- ]"), "").trim()
                val candidates = listOf("Bambu $kind Basic @$suffix", "Bambu $kind @$suffix", "Generic $kind @$suffix")
                val name = candidates.firstOrNull { kind.isNotEmpty() && raw(profiles, "filament", it) != null } ?: "Bambu PLA Basic @$suffix"
                val filament = flatten(profiles, "filament", name).toMutableMap()
                require(filament.isNotEmpty()) { "The printer has no filament preset." }
                filament["name"] = JsonPrimitive("pandy filament"); filament["from"] = JsonPrimitive("User"); filament["setting_id"] = JsonPrimitive("")
                request.filamentColor?.let { filament["filament_colour"] = JsonArray(listOf(JsonPrimitive(it.uppercase()))) }
                files["filament.json"] = encoded(JsonObject(filament)); args += listOf("--load-filaments", "filament.json")
            } else if (filaments.all { raw(profiles, "filament", it) != null }) {
                args += listOf("--load-filaments", filaments.joinToString(";") { "$profileBase/profiles/BBL/filament/$it.json" })
            }
        }
        request.settings.forEach { (key, value) -> args += "--${key.replace('_', '-')}=$value${if (key == "sparse_infill_density") "%" else ""}" }
        if (bare) args += listOf("--arrange", "1")
        args += listOf("--slice", request.plate.toString(), "--export-3mf", "sliced.gcode.3mf", "--uptodate", "model.3mf")
        return ServerJob(files, args, src)
    }
}
