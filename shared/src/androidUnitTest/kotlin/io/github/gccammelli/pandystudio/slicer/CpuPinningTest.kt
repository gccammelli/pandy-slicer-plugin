package io.github.gccammelli.pandystudio.slicer

import kotlin.test.Test
import kotlin.test.assertEquals

class CpuPinningTest {
    @Test fun cpuListsAreExpandedAndMalformedPartsIgnored() {
        assertEquals(listOf(0, 1, 2, 3, 4, 5, 6, 7, 8), parseCpuList("0-8\n"))
        assertEquals(listOf(0, 1, 2, 3, 5), parseCpuList("0-3,5"))
        assertEquals(listOf(4), parseCpuList(" 4 "))
        assertEquals(listOf(1, 2), parseCpuList("1-2,x,7-3,1-2-3,"))
        assertEquals(emptyList(), parseCpuList(""))
    }

    /** A Pixel 8: cores 0-3 at 1.7 GHz, 4-7 at 2.37 GHz, 8 at 2.91 GHz, which only the foreground app may use. */
    private val pixel8 = { cpu: Int -> when (cpu) { in 0..3 -> 1_704_000L; in 4..7 -> 2_367_000L; else -> 2_914_000L } }

    @Test fun theFastestCoreIsChosenAmongThoseTheProcessMayUse() {
        assertEquals(8, fastestCpu(parseCpuList("0-8"), pixel8))
        assertEquals(4, fastestCpu(parseCpuList("0-7"), pixel8))
        assertEquals(0, fastestCpu(parseCpuList("0-3"), pixel8))
        assertEquals(0, fastestCpu(emptyList(), pixel8))
    }

    @Test fun theMaskSelectsOneCoreAndTiesGoToTheFirst() {
        assertEquals("100", cpuMask(8)); assertEquals("1", cpuMask(0)); assertEquals("80000000", cpuMask(31)); assertEquals("100000000", cpuMask(32))
        assertEquals(4, fastestCpu(listOf(4, 5, 6, 7)) { 2_367_000L })
    }
}
