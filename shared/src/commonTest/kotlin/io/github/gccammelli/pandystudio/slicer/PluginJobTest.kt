package io.github.gccammelli.pandystudio.slicer

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails

class PluginJobTest {
    private val schema = Schema(mapOf("wall_loops" to OptionDef("coInt"), "post_process" to OptionDef("coStrings")), Layout(emptyList(), emptyList()))
    private val job = """{"version":1,"printer":"A1 mini","process":"0.20 Standard","filaments":["PLA"],"process_overrides":{"wall_loops":"3"}}"""
    @Test fun editorJobPreservesInputs() {
        val model = byteArrayOf(1, 2, 3)
        val parsed = PluginJob.parse(job, model, schema)
        assertEquals(SliceJob(model, "A1 mini", "0.20 Standard", listOf("PLA"), mapOf("wall_loops" to Setting.One("3"))).files().keys, parsed.files().keys)
        assertEquals(Setting.One("3"), parsed.processOverrides["wall_loops"])
    }
    @Test fun rejectsBlockedSettingsAndPathPresets() {
        assertFails { PluginJob.parse(job.replace("wall_loops", "post_process"), byteArrayOf(1), schema) }
        assertFails { PluginJob.parse(job.replace("A1 mini", "../machine"), byteArrayOf(1), schema) }
        assertFails { PluginJob.parse(job.replace("\"version\":1", "\"version\":2"), byteArrayOf(1), schema) }
    }
}
