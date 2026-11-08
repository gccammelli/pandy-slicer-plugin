package io.github.gccammelli.pandystudio.slicer

import kotlinx.serialization.json.*

/** Version 1 request from Pandy; the file itself is transferred separately by a temporary URI grant. */
data class PhoneRequest(val id: String, val plate: Int, val name: String, val printer: String, val bed: String,
                        val filamentType: String?, val filamentColor: String?, val settings: Map<String, String>)

/** Validates the public app-to-app contract before any engine invocation. */
object PhoneProtocol {
    const val MAX_JSON = 128_000
    const val MAX_MODEL = 100_000_000
    private val json = Json { ignoreUnknownKeys = false }
    private val catalogue = json.parseToJsonElement(SERVER_SETTINGS_JSON).jsonObject
    private val settings = catalogue.getValue("settings").jsonArray.map { it.jsonObject }.associateBy { it.getValue("key").jsonPrimitive.content }

    /** The current editor imports only geometry; do not silently discard a project's plates or profile. */
    fun validateEditorModel(request: PhoneRequest, model: ByteArray) {
        val entries = io.github.gccammelli.pandystudio.io.Zip.read(model)
        require(request.plate == 1 && entries.keys.none { it.equals("Metadata/project_settings.config", true) || it.equals("Metadata/model_settings.config", true) }) {
            "This project contains plate or profile settings that the editor cannot preserve yet."
        }
        require(entries.keys.any { it.endsWith(".model", true) }) { "This file has no 3MF model." }
    }

    /** Server-compatible settings, restricted to safe options available in the installed schema. */
    fun capabilities(schema: Schema): String = buildJsonObject {
        put("version", 1)
        put("settings", JsonArray(settings.values.filter { spec ->
            val key = spec.getValue("key").jsonPrimitive.content
            key !in BLOCKED_OPTIONS && schema[key] != null
        }))
    }.toString()

    fun parse(id: String?, text: String?, needsModel: Boolean, schema: Schema): PhoneRequest {
        require(!id.isNullOrBlank() && id.length <= 256 && id.none { it.isISOControl() }) { "Invalid request ID." }
        require(text != null && text.length <= MAX_JSON) { "Invalid request details." }
        val root = try { json.parseToJsonElement(text).jsonObject } catch (_: Exception) { throw IllegalArgumentException("Invalid request details.") }
        val version = root["version"] as? JsonPrimitive
        require(version != null && !version.isString && version.intOrNull == 1) { "Unsupported protocol version." }
        if (!needsModel) {
            require(root.keys == setOf("version")) { "Invalid capabilities request." }
            return PhoneRequest(id, 0, "", "", "", null, null, emptyMap())
        }
        val allowed = setOf("version", "plate", "name", "printer", "bed_type", "filament_type", "filament_color", "settings")
        require(root.keys.all { it in allowed }) { "Unsupported request field." }
        fun string(key: String, max: Int, required: Boolean = true): String? {
            val value = root[key] ?: run { require(!required) { "Missing $key." }; return null }
            require(value is JsonPrimitive && value.isString && value.content.length <= max && value.content.none { it.isISOControl() }) { "Invalid $key." }
            return value.content
        }
        val plateValue = root["plate"] as? JsonPrimitive
        val plate = plateValue?.takeIf { !it.isString }?.intOrNull
        require(plate != null && plate in 1..1000) { "Invalid plate." }
        val name = string("name", 200)!!
        val printer = string("printer", 200)!!
        require(printer.isNotBlank() && !printer.startsWith('.') && printer.none { it == '/' || it == '\\' }) { "Invalid printer preset." }
        val bed = string("bed_type", 32)!!
        require(bed in setOf("auto", "cool_plate", "eng_plate", "hot_plate", "textured_plate", "supertack_plate")) { "Invalid build plate." }
        val type = string("filament_type", 80, false)
        val color = string("filament_color", 9, false)
        require(color == null || color.matches(Regex("#[0-9a-fA-F]{6}"))) { "Invalid filament colour." }
        val values = root["settings"] as? JsonObject ?: throw IllegalArgumentException("Invalid slicer settings.")
        require(values.toString().length <= 4096) { "Slicer settings are too large." }
        val overrides = values.mapValues { (key, value) ->
            val spec = settings[key]
            require(spec != null && key !in BLOCKED_OPTIONS && schema[key] != null && value is JsonPrimitive && value.isString && value.content.length <= 32) { "Unsupported slicer setting." }
            val content = value.content
            when (spec.getValue("type").jsonPrimitive.content) {
                "choice" -> require(spec.getValue("options").jsonArray.any { it.jsonObject.getValue("value").jsonPrimitive.content == content }) { "Invalid slicer setting." }
                else -> {
                    val integer = spec.getValue("type").jsonPrimitive.content == "integer"
                    val pattern = if (integer) Regex("[0-9]+") else Regex("(?:[0-9]+(?:\\.[0-9]{1,3})?|\\.[0-9]{1,3})")
                    val number = content.toDoubleOrNull()
                    require(pattern.matches(content) && number != null && number in spec.getValue("min").jsonPrimitive.double..spec.getValue("max").jsonPrimitive.double) { "Invalid slicer setting." }
                }
            }
            content
        }
        return PhoneRequest(id, plate, name, printer, bed, type, color, overrides)
    }
}
