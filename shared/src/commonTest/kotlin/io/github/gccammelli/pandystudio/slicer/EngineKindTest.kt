package io.github.gccammelli.pandystudio.slicer

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class EngineKindTest {
    @Test fun oldClientsKeepBambuAndExplicitOrcaSelectsOrca() {
        assertEquals(EngineKind.BAMBU, EngineKind.parse(null))
        assertEquals(EngineKind.BAMBU, EngineKind.parse("bambu"))
        assertEquals(EngineKind.ORCA, EngineKind.parse("orca"))
    }

    @Test fun jobsCannotUseStaleOrOtherEngineResources() {
        EngineKind.BAMBU.checkResourceVersion(null, "bambu-version")
        EngineKind.ORCA.checkResourceVersion("orca-version", "orca-version")
        assertFailsWith<IllegalArgumentException> { EngineKind.ORCA.checkResourceVersion(null, "orca-version") }
        assertFailsWith<IllegalArgumentException> { EngineKind.ORCA.checkResourceVersion("bambu-version", "orca-version") }
        assertFailsWith<IllegalArgumentException> { EngineKind.BAMBU.checkResourceVersion("stale-version", "bambu-version") }
    }

    @Test fun invalidSelectionNeverFallsBackToAnotherSlicer() {
        listOf("", "Orca", "unknown", "../bambu", "orca\u0000").forEach {
            assertFailsWith<IllegalStateException> { EngineKind.parse(it) }
        }
    }

    @Test fun engineResourcesCannotCollideAndServerModeIsBambuOnly() {
        assertEquals(EngineKind.entries.size, EngineKind.entries.map { it.id }.toSet().size)
        assertEquals(EngineKind.entries.size, EngineKind.entries.map { it.executable }.toSet().size)
        assertEquals(EngineKind.entries.size, EngineKind.entries.map { it.resourceAsset }.toSet().size)
        assertTrue(EngineKind.BAMBU.supportsServer)
        assertFalse(EngineKind.ORCA.supportsServer)
    }
}
