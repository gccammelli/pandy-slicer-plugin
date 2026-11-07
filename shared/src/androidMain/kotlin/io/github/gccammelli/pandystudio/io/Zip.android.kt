package io.github.gccammelli.pandystudio.io

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.util.zip.CRC32
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

actual object Zip {
    actual fun read(bytes: ByteArray): Map<String, ByteArray> {
        val validSignature = bytes.size >= 4 && bytes[0] == 0x50.toByte() && bytes[1] == 0x4b.toByte() &&
            ((bytes[2] == 0x03.toByte() && bytes[3] == 0x04.toByte()) || (bytes[2] == 0x05.toByte() && bytes[3] == 0x06.toByte()) || (bytes[2] == 0x07.toByte() && bytes[3] == 0x08.toByte()))
        require(validSignature) { "Malformed ZIP archive: missing ZIP signature" }
        val entries=LinkedHashMap<String,ByteArray>()
        try {
            ZipInputStream(ByteArrayInputStream(bytes)).use { input ->
                while(true) { val entry=input.nextEntry ?: break; entries[entry.name]=input.readBytes();input.closeEntry() }
            }
        } catch(e: Exception) { throw IllegalArgumentException("Malformed ZIP archive: ${e.message ?: "invalid data"}",e) }
        return entries
    }

    actual fun write(entries: List<Pair<String, ByteArray>>, deflate: Boolean): ByteArray {
        val output=ByteArrayOutputStream()
        try {
            ZipOutputStream(output).use { zip ->
                for((name,data) in entries) {
                    require(name.isNotEmpty() && !name.startsWith("/")) { "ZIP entry name must be a non-empty relative path" }
                    val entry=ZipEntry(name);entry.time=315532800000L
                    if(!deflate) { val crc=CRC32();crc.update(data);entry.method=ZipEntry.STORED;entry.size=data.size.toLong();entry.compressedSize=data.size.toLong();entry.crc=crc.value }
                    zip.putNextEntry(entry);zip.write(data);zip.closeEntry()
                }
            }
        } catch(e: IllegalArgumentException) { throw e } catch(e: Exception) { throw IllegalArgumentException("Could not write ZIP archive: ${e.message ?: "invalid data"}",e) }
        return output.toByteArray()
    }
}
