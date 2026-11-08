package io.github.gccammelli.pandystudio.slicer

import io.github.gccammelli.pandystudio.io.Zip
import kotlin.test.*

class PhoneScopeTest {
    private fun model(xml: String, extra: List<Pair<String, ByteArray>> = emptyList()) = Zip.write(listOf("Metadata/model_settings.config" to xml.encodeToByteArray()) + extra, true)

    @Test fun allowsUnrelatedMetadataAndRejectsConflictingObjectSettings() {
        PhoneScope.check(model("""<config><object><metadata key="other" value="2"/></object></config>"""), mapOf("wall_loops" to "3"))
        val conflict = model("""<config><object><metadata key="wall_&#108;oops" value="2"/></object></config>""")
        assertFailsWith<IllegalArgumentException> { PhoneScope.check(conflict, mapOf("wall_loops" to "3")) }
        val blocked = model("""<config><object><metadata key="post_process" value="script"/></object></config>""")
        assertFailsWith<IllegalArgumentException> { PhoneScope.check(blocked, emptyMap()) }
    }

    @Test fun refusesMalformedXmlAndExternalEntities() {
        assertFailsWith<IllegalArgumentException> { PhoneScope.check(model("<config><object>"), emptyMap()) }
        assertFailsWith<IllegalArgumentException> { PhoneScope.check(model("""<!DOCTYPE config [<!ENTITY e SYSTEM "file:///etc/passwd">]><config>&e;</config>"""), emptyMap()) }
        val invalid = Zip.write(listOf("Metadata/model_settings.config" to byteArrayOf(0xff.toByte(), 0xfe.toByte(), 0)), true)
        assertFailsWith<IllegalArgumentException> { PhoneScope.check(invalid, emptyMap()) }
    }
}
