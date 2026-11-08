package io.github.gccammelli.pandystudio.slicer

import io.github.gccammelli.pandystudio.io.Zip
import kotlinx.serialization.json.*

/** A verified sliced file and its versioned Pandy response. */
data class PhoneResult(val file: ByteArray, val metadata: String)

/** Rejects incomplete, unsafe, or unconfirmed output before it leaves Studio. */
object PhoneResults {
    fun create(request: PhoneRequest, original: ByteArray, sliced: ByteArray): PhoneResult {
        val entries = Zip.read(sliced).toMutableMap()
        val plates = entries.keys.mapNotNull { Regex("Metadata/plate_(\\d+)\\.gcode").matchEntire(it)?.groupValues?.get(1)?.toIntOrNull() }
        require(plates.size == 1) { "The sliced file must contain exactly one plate." }
        val outputPlate = plates.single()
        require(Safety.problems(entries.getValue("Metadata/plate_$outputPlate.gcode").decodeToString()).isEmpty()) { "The sliced file failed its printer safety check." }
        if (request.settings.isNotEmpty()) {
            val cfg = Json.parseToJsonElement(entries["Metadata/project_settings.config"]?.decodeToString() ?: error("Missing sliced settings.")).jsonObject
            val specs = Json.parseToJsonElement(SERVER_SETTINGS_JSON).jsonObject.getValue("settings").jsonArray.associate { it.jsonObject.getValue("key").jsonPrimitive.content to it.jsonObject }
            request.settings.forEach { (key, expected) ->
                val actual = cfg[key] ?: error("The slicer did not confirm $key.")
                val values = if (actual is JsonArray) actual.toList() else listOf(actual)
                val choice = specs.getValue(key).getValue("type").jsonPrimitive.content == "choice"
                require(values.isNotEmpty() && values.all { element ->
                    val value = (element as? JsonPrimitive)?.contentOrNull ?: return@all false
                    if (choice) value == expected else value.removeSuffix("%").toDoubleOrNull()?.let { kotlin.math.abs(it - (expected.toDoubleOrNull() ?: return@let false)) <= 0.000001 } == true
                }) { "The slicer did not confirm $key." }
            }
        }
        val xml = entries["Metadata/slice_info.config"]?.decodeToString() ?: error("The slicer returned no filament information.")
        val block = xml.substringAfter("<plate>", "").substringBefore("</plate>")
        val meta = Regex("<metadata\\s+key=\"([^\"]+)\"\\s+value=\"([^\"]*)\"").findAll(block).associate { it.groupValues[1] to it.groupValues[2] }
        require(meta["index"]?.toIntOrNull() == outputPlate) { "The slicer returned the wrong plate information." }
        val filaments = Regex("<filament\\s+([^>]*)/?>").findAll(block).map { match ->
            val attrs = Regex("(\\w+)=\"([^\"]*)\"").findAll(match.groupValues[1]).associate { it.groupValues[1] to it.groupValues[2] }
            val id = attrs["id"]?.toIntOrNull(); val type = attrs["type"]; val color = attrs["color"]
            require(id != null && id in 1..16 && !type.isNullOrBlank() && color != null && color.matches(Regex("#?[0-9a-fA-F]{6}([0-9a-fA-F]{2})?"))) { "The slicer returned invalid filament information." }
            buildJsonObject { put("id", id); put("type", type); put("color", color) }
        }.toList()
        require(filaments.isNotEmpty() && filaments.map { it.getValue("id").jsonPrimitive.int }.distinct().size == filaments.size) { "The slicer returned invalid filament information." }
        val pictures = Regex("Metadata/(plate|plate_no_light|top|pick)_\\d+(_small)?\\.png")
        Zip.read(original).filterKeys { pictures.matches(it) && it !in entries }.forEach { (name, bytes) -> entries[name] = bytes }
        val output = Zip.write(entries.toList(), true)
        require(output.size <= PhoneProtocol.MAX_MODEL) { "The sliced file is too large." }
        val result = buildJsonObject {
            put("version", 1); put("source_plate", request.plate); put("printer", request.printer); put("bed_type", request.bed)
            put("project_preserved", true); put("output_plate", outputPlate); put("filaments", JsonArray(filaments))
            put("applied_settings", JsonObject(request.settings.mapValues { JsonPrimitive(it.value) }))
        }
        return PhoneResult(output, result.toString())
    }
}
