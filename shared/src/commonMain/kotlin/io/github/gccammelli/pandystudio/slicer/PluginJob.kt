package io.github.gccammelli.pandystudio.slicer

import kotlinx.serialization.json.*

/** Validates the small editor job description; model bytes are transported separately. */
object PluginJob {
    fun parse(text: String?, model: ByteArray, schema: Schema): SliceJob {
        require(text != null && text.length <= PhoneProtocol.MAX_JSON) { "Invalid editor job." }
        val root = Json.parseToJsonElement(text).jsonObject
        require(root.keys.all { it in setOf("version", "printer", "process", "filaments", "process_overrides", "filament_overrides", "printer_includes") }) { "Unsupported editor job field." }
        require(root["version"]?.jsonPrimitive?.intOrNull == 1) { "Unsupported protocol version." }
        fun name(value: JsonElement?): String {
            val s = (value as? JsonPrimitive)?.takeIf { it.isString }?.content ?: error("Missing preset.")
            require(s.isNotBlank() && s.length <= 200 && !s.startsWith('.') && s.none { it == '/' || it == '\\' || it.isISOControl() }) { "Invalid preset." }
            return s
        }
        val printer = name(root["printer"]); val process = name(root["process"])
        val filaments = (root["filaments"] as? JsonArray)?.map(::name) ?: error("Missing filaments.")
        require(filaments.size in 1..16) { "Invalid filaments." }
        fun settings(field: String, includes: Boolean = false): Map<String, Setting> {
            val entries = root[field] as? JsonObject ?: if (root[field] == null) return emptyMap() else error("Invalid settings.")
            require(entries.size <= 1000) { "Too many settings." }
            return entries.mapValues { (key, value) ->
                require(key !in BLOCKED_OPTIONS && (includes || schema[key] != null)) { "Unsupported setting." }
                require(key.length <= 128 && key.all { it.isLetterOrDigit() || it == '_' }) { "Invalid setting name." }
                fun str(v: JsonElement): String = (v as? JsonPrimitive)?.takeIf { it.isString && it.content.length <= 32_000 }?.content ?: error("Invalid setting value.")
                when (value) {
                    is JsonArray -> { require(value.size <= 16); Setting.Many(value.map(::str)) }
                    else -> Setting.One(str(value))
                }
            }
        }
        require(model.isNotEmpty() && model.size <= PhoneProtocol.MAX_MODEL) { "Invalid model size." }
        return SliceJob(model, printer, process, filaments, settings("process_overrides"), settings("filament_overrides"), settings("printer_includes", true))
    }
}
