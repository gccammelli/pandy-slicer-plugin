package io.github.gccammelli.pandystudio.slicer

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class OrcaJobTest {
    @Test fun matchesInputsAcceptedByOfficialOrcaWithStrictMode() {
        val fixture = Json.parseToJsonElement(javaClass.classLoader!!.getResourceAsStream("orca-job-parity.json")!!
            .bufferedReader().use { it.readText() }).jsonObject
        val profiles = fixture.getValue("profiles").jsonObject
        val library = PresetLibrary(ProfileSource { profiles[it]?.jsonPrimitive?.content })
        val model = byteArrayOf(1, 2, 3)
        val job = SliceJob(model, "Bambu Lab X1 Carbon 0.4 nozzle", "0.20mm Standard @BBL X1C",
            listOf("Bambu PLA Basic @BBL X1C"), printerIncludes = library.includes("Bambu Lab X1 Carbon 0.4 nozzle"))
        val actual = OrcaJob.files(job, library)
        assertContentEquals(model, actual.getValue("model.3mf"))
        fixture.getValue("expected").jsonObject.forEach { (name, expected) ->
            assertEquals(expected, Json.parseToJsonElement(actual.getValue(name).decodeToString()), name)
        }
        // Orca's user-registry version requirement must not alter the Bambu input format.
        assertFalse("version" in Json.parseToJsonElement(job.resolvedFiles(library).getValue("machine.json").decodeToString()).jsonObject)
    }

    @Test fun substitutedSettingsCannotBeAcceptedAsSuccessfulSlices() {
        assertTrue(OrcaJob.outcome("""{"return_code":0,"warnings":[]}""")!!.ok)
        assertFalse(OrcaJob.outcome("""{"return_code":0,"warnings":[{"class":"config_value_substituted"}]}""")!!.ok)
        assertFalse(OrcaJob.outcome("""{"return_code":0}""")!!.ok)
        assertFalse(OrcaJob.outcome("""{"return_code":-5,"warnings":[]}""")!!.ok)
    }

    @Test fun registryNamesMatchGeneratedPresetsForMultipleFilaments() {
        assertEquals(mapOf(
            "user/default/machine/case printer.json" to "machine.json",
            "user/default/process/case process.json" to "process.json",
            "user/default/filament/case filament 1.json" to "filament1.json",
            "user/default/filament/case filament 2.json" to "filament2.json",
        ), OrcaJob.presetLinks(2))
    }
}
