package io.github.gccammelli.pandystudio.slicer

import io.github.gccammelli.pandystudio.io.Zip
import org.w3c.dom.Element
import java.io.StringReader
import javax.xml.parsers.DocumentBuilderFactory
import org.xml.sax.InputSource
import org.xml.sax.SAXException

/** Rejects unsafe per-object or per-layer overrides before invoking the engine. */
object PhoneScope {
    fun check(model: ByteArray, settings: Map<String, String>) {
        val entries = Zip.read(model)
        val names = entries.keys.associateBy { it.lowercase() }
        require("metadata/slic3r_pe_model.config" !in names) { "This project has unsupported third-party object settings." }
        fun document(name: String): org.w3c.dom.Document? {
            val path = names[name] ?: return null
            return try {
                // Android's XML parser does not implement Xerces' disallow-doctype-decl flag. Decode as UTF-8
                // ourselves and reject declarations before the parser sees them; an entity resolver is a second
                // boundary. A StringReader also prevents an XML encoding declaration bypassing this check.
                val xml = entries.getValue(path).decodeToString(throwOnInvalidSequence = true)
                require('\u0000' !in xml && !Regex("<!\\s*DOCTYPE", RegexOption.IGNORE_CASE).containsMatchIn(xml))
                val builder = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }.newDocumentBuilder()
                builder.setEntityResolver { _, _ -> throw SAXException("External entities are not permitted") }
                builder.parse(InputSource(StringReader(xml)))
            }
            catch (_: Exception) { throw IllegalArgumentException("The project's object settings could not be checked.") }
        }
        document("metadata/model_settings.config")?.let { doc ->
            val nodes = doc.getElementsByTagName("*")
            for (i in 0 until nodes.length) {
                val item = nodes.item(i) as? Element ?: continue
                if (item.localName != "metadata" && item.tagName.substringAfterLast(':') != "metadata") continue
                val key = item.getAttribute("key")
                require(key !in BLOCKED_OPTIONS) { "This project contains blocked object settings." }
                var parent = item.parentNode
                while (parent is Element) {
                    if (parent.tagName.substringAfterLast(':') in setOf("object", "part", "volume")) {
                        require(key !in settings) { "This project has conflicting object settings." }
                    }
                    parent = parent.parentNode
                }
            }
        }
        if ("layer_height" in settings) require("metadata/layer_heights_profile.txt" !in names) { "This project has a variable layer-height profile." }
        document("metadata/layer_config_ranges.xml")?.let { doc ->
            val nodes = doc.getElementsByTagName("*")
            for (i in 0 until nodes.length) {
                val node = nodes.item(i) as? Element ?: continue
                val key = node.getAttribute("opt_key")
                require(key !in BLOCKED_OPTIONS && key !in settings) { "This project has conflicting layer settings." }
            }
        }
    }
}
