package io.github.gccammelli.pandystudio.slicer

import io.github.gccammelli.pandystudio.io.Zip
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.*

class PhoneResultTest {
    private val request = PhoneRequest("demo", 2, "model", "Demo Printer", "textured_plate", null, null, mapOf("wall_loops" to "3"))
    private val original = Zip.write(listOf("Metadata/plate_1.png" to byteArrayOf(1)), true)
    private fun output(gcode: String = "G28\nG29\n; CHANGE_LAYER\n", settings: String = "3", filament: String = "<filament id=\"1\" type=\"PLA\" color=\"#FFFFFF\"/>") = Zip.write(listOf(
        "Metadata/plate_1.gcode" to gcode.encodeToByteArray(),
        "Metadata/project_settings.config" to """{"wall_loops":"$settings"}""".encodeToByteArray(),
        "Metadata/slice_info.config" to """<config><plate><metadata key="index" value="1"/>$filament</plate></config>""".encodeToByteArray(),
    ), true)

    @Test fun acceptsConfirmedSafeOutputAndRestoresPictures() {
        val result = PhoneResults.create(request, original, output())
        val metadata = Json.parseToJsonElement(result.metadata).jsonObject
        assertEquals("2", metadata.getValue("source_plate").jsonPrimitive.content)
        assertEquals("1", metadata.getValue("output_plate").jsonPrimitive.content)
        assertContentEquals(byteArrayOf(1), Zip.read(result.file).getValue("Metadata/plate_1.png"))
    }

    @Test fun rejectsUnsafeUnconfirmedOrUnmappedOutput() {
        assertFailsWith<IllegalArgumentException> { PhoneResults.create(request, original, output(gcode = "G1 X1")) }
        assertFailsWith<IllegalArgumentException> { PhoneResults.create(request, original, output(settings = "4")) }
        assertFailsWith<IllegalArgumentException> { PhoneResults.create(request, original, output(filament = "")) }
        assertFailsWith<IllegalArgumentException> { PhoneResults.create(request, original, output(filament = "<filament id=\"99\" type=\"PLA\" color=\"#FFFFFF\"/>")) }
    }
}
