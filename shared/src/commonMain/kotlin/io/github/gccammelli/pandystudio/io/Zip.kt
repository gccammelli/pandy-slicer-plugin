package io.github.gccammelli.pandystudio.io

/** Platform ZIP archive support. */
expect object Zip {
    fun read(bytes: ByteArray): Map<String, ByteArray>
    fun write(entries: List<Pair<String, ByteArray>>, deflate: Boolean = true): ByteArray
}
