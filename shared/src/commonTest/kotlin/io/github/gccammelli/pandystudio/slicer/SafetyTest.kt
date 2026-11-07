package io.github.gccammelli.pandystudio.slicer

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class SafetyTest {
    private val start = "G28\nM1002 gcode_claim_action : 2\nG29\n"

    @Test fun completeFilePasses() = assertEquals(emptyList(), Safety.problems(start + "M104 S220\n; CHANGE_LAYER\nG1 X1 E1\n"))

    @Test fun missingStartSequenceIsRefused() =
        assertTrue(Safety.problems("M104 S220\n; CHANGE_LAYER\nG28\nG29\n").single().contains("start sequence"))

    @Test fun hotNozzleIsRefused() = assertTrue(Safety.problems(start + "; CHANGE_LAYER\nM109 S400 ; too hot\n").single().contains("M109"))

    @Test fun limitsAreInclusive() = assertEquals(emptyList(), Safety.problems(start + "; CHANGE_LAYER\nM104 S350\nM140 S120\nM141 S65\n"))

    @Test fun commentedCommandsAreIgnored() = assertEquals(emptyList(), Safety.problems(start + "; CHANGE_LAYER\n; M104 S999\n"))

    @Test fun outcomeParses() {
        assertEquals(SliceOutcome(0, "Success."), SliceOutcome.parse("""{"return_code": 0, "error_string": "Success."}"""))
        assertEquals(-17, SliceOutcome.parse("""{"return_code": -17, "error_string": "x"}""")?.returnCode)
        assertEquals(null, SliceOutcome.parse("not json"))
    }
}
