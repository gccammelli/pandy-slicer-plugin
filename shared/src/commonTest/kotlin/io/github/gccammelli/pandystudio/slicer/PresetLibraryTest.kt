package io.github.gccammelli.pandystudio.slicer

import kotlin.test.Test
import kotlin.test.assertEquals

class PresetLibraryTest {
    private val files = mapOf(
        "profiles/BBL.json" to """{"machine_list":[{"name":"base","sub_path":"machine/base.json"},{"name":"start tpl","sub_path":"machine/start.json"},
            {"name":"P 0.4 nozzle","sub_path":"machine/p.json"}],"process_list":[],"filament_list":[]}""",
        "profiles/BBL/machine/base.json" to """{"type":"machine","name":"base","nozzle_diameter":["0.4"]}""",
        "profiles/BBL/machine/start.json" to """{"type":"machine","name":"start tpl","machine_start_gcode":"G28\nG29"}""",
        "profiles/BBL/machine/p.json" to """{"type":"machine","name":"P 0.4 nozzle","inherits":"base","instantiation":"true","include":["start tpl"],"printable_height":"250"}""",
    )
    private val lib = PresetLibrary(ProfileSource { files[it] })

    @Test fun inheritanceAndIncludesResolve() {
        val p = lib.preset("P 0.4 nozzle")!!
        assertEquals("250", p.string("printable_height"))
        assertEquals("0.4", p.string("nozzle_diameter"))
        assertEquals("G28\nG29", p.string("machine_start_gcode"))
    }

    @Test fun includesAreReportedForTheJob() = assertEquals(mapOf("machine_start_gcode" to Setting.One("G28\nG29")), lib.includes("P 0.4 nozzle"))
}
