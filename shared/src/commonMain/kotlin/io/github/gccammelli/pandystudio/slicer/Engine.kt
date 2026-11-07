package io.github.gccammelli.pandystudio.slicer

/** The engine build the app carries, as the equivalence report identifies it. */
data class EngineInfo(val version: String, val engineSha256: String, val resourcesSha256: String)

/** A finished engine run, platform-neutral: what it reported, the sliced 3MF's bytes and the time it took. */
class SliceRun(val outcome: SliceOutcome?, val exitCode: Int, val sliced: ByteArray?, val millis: Long, val log: List<String>, val handle: Any?) {
    val ok get() = exitCode == 0 && outcome?.ok == true && sliced != null
}
