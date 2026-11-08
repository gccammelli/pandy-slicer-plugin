package io.github.gccammelli.pandystudio.slicer

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.*

class PhoneProtocolTest {
    private val schema = Schema(mapOf("wall_loops" to OptionDef("coInt"), "layer_height" to OptionDef("coFloat"), "post_process" to OptionDef("coStrings")), Layout(emptyList(), emptyList()))
    private val request = """{"version":1,"plate":2,"name":"demo","printer":"Bambu Lab X1 Carbon 0.4 nozzle","bed_type":"textured_plate","settings":{"wall_loops":"3"}}"""

    @Test fun acceptsAndPreservesSelectedSettings() {
        val parsed = PhoneProtocol.parse("id-1", request, true, schema)
        assertEquals(2, parsed.plate); assertEquals("3", parsed.settings["wall_loops"])
        assertEquals("id-1", PhoneProtocol.parse("id-1", """{"version":1}""", false, schema).id)
    }

    @Test fun advertisesOnlySupportedAndUnblockedOptions() {
        val root = Json.parseToJsonElement(PhoneProtocol.capabilities(schema)).jsonObject
        val keys = root.getValue("settings").jsonArray.map { it.jsonObject.getValue("key").jsonPrimitive.content }
        assertEquals(listOf("layer_height", "wall_loops"), keys)
    }

    @Test fun rejectsInvalidRequestsAndOverrides() {
        fun reject(id: String?, text: String?) = assertFailsWith<IllegalArgumentException> { PhoneProtocol.parse(id, text, true, schema) }
        reject(null, request); reject("x", null); reject("x", "x".repeat(PhoneProtocol.MAX_JSON + 1))
        reject("x", request.replace("\"version\":1", "\"version\":2"))
        reject("x", request.replace("\"plate\":2", "\"plate\":0"))
        reject("x", request.replace("Bambu Lab X1 Carbon 0.4 nozzle", "../printer"))
        reject("x", request.replace("textured_plate", "unknown"))
        reject("x", request.replace("\"wall_loops\":\"3\"", "\"post_process\":\"script\""))
        reject("x", request.replace("\"wall_loops\":\"3\"", "\"wall_loops\":\"30\""))
        reject("x", request.replace("\"wall_loops\":\"3\"", "\"wall_loops\":3"))
        reject("x", request.replace("\"wall_loops\":\"3\"", "\"layer_height\":\"0.1234\""))
        assertFailsWith<IllegalArgumentException> { PhoneProtocol.parse("x", request, false, schema) }
    }
}
