package io.github.gccammelli.pandystudio.slicer

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipInputStream

/**
 * Runs the engine (Bambu Studio's CLI, built for arm64; engine/README.md) on the phone.
 *
 * The executable ships in the APK as lib/arm64-v8a/libpandy_engine.so and runs from there (the only place Android
 * lets an app run files from). Its resources (Bambu's profiles) ship as assets/engine-resources.zip, unpacked once
 * per version into the app's files. The CLI looks for resources/ next to itself; PANDY_ENGINE_HOME points it at the
 * unpacked copy instead (engine/android-location.c), where bin/pandy-engine is an empty placeholder. Each slice runs in a fresh directory with a fresh HOME, LC_ALL=C and one CPU,
 * which is exactly how the equivalence tests run the official Bambu Studio and the engine.
 */
class AndroidEngine(private val context: Context) {
    private val exe get() = File(context.applicationInfo.nativeLibraryDir, "libpandy_engine.so")

    /** SHA-256 of the installed engine executable, shown in About and matched against the equivalence report. */
    val engineSha256: String by lazy { sha256(exe) }

    /** The unpacked engine package: bin/pandy-engine (a link to the installed executable) and resources/. */
    val home: File by lazy { install() }

    private fun install(): File {
        val version = context.assets.open("engine-resources.sha256").bufferedReader().readText().trim()
        val root = File(context.filesDir, "engine/$version")
        val done = File(root, ".complete")
        if (!done.exists()) {
            root.deleteRecursively()
            File(root, "bin").mkdirs()
            ZipInputStream(context.assets.open("engine-resources.zip").buffered()).use { z ->
                generateSequence { z.nextEntry }.forEach { e ->
                    val f = File(root, e.name).canonicalFile
                    require(f.path.startsWith(root.canonicalPath + File.separator)) { "Bad resource path ${e.name}" }
                    if (e.isDirectory) f.mkdirs() else { f.parentFile?.mkdirs(); f.outputStream().use { z.copyTo(it) } }
                }
            }
            done.writeText(version)
            File(context.filesDir, "engine").listFiles()?.filter { it.name != version }?.forEach { it.deleteRecursively() }
        }
        File(root, "bin/pandy-engine").apply { if (!exists()) createNewFile() }
        return root
    }

    /** The fastest CPU, by its maximum frequency (big.LITTLE phones list little cores first). */
    private fun fastestCpu(): Int = (0 until Runtime.getRuntime().availableProcessors()).maxByOrNull { cpu ->
        runCatching { File("/sys/devices/system/cpu/cpu$cpu/cpufreq/cpuinfo_max_freq").readText().trim().toLong() }.getOrDefault(0L)
    } ?: 0

    /** Slices [job]; [onLog] gets the slicer's log lines as they come. Returns the result and the output directory. */
    suspend fun slice(job: SliceJob, onLog: (String) -> Unit = {}): EngineRun = run(job.files(), job.arguments(), SliceJob.OUTPUT, onLog)

    /** Runs a prepared server-style job in a fresh directory without mutating engine resources. */
    suspend fun sliceServer(job: ServerJob, onLog: (String) -> Unit = {}): EngineRun = run(job.files, job.arguments, "sliced.gcode.3mf", onLog)

    private suspend fun run(files: Map<String, ByteArray>, arguments: List<String>, output: String, onLog: (String) -> Unit): EngineRun = withContext(Dispatchers.IO) {
        val dir = File(context.cacheDir, "slice-${System.nanoTime()}").apply { mkdirs() }
        val out = File(dir, "out").apply { mkdirs() }
        File(dir, "home").mkdirs()
        files.forEach { (name, bytes) -> File(dir, name).writeBytes(bytes) }
        val cmd = listOf("/system/bin/taskset", Integer.toHexString(1 shl fastestCpu()), exe.path) +
            arguments + listOf("--outputdir", out.path)
        val pb = ProcessBuilder(cmd).directory(dir).redirectErrorStream(true)
        pb.environment().apply { clear(); put("HOME", File(dir, "home").path); put("LC_ALL", "C"); put("PANDY_ENGINE_HOME", home.path)
            // glibc registers rseq at start-up, before any handler exists; Android's sandbox may not allow it.
            put("GLIBC_TUNABLES", "glibc.pthread.rseq=0"); put("TMPDIR", dir.path); put("PATH", "/system/bin") }
        val started = System.currentTimeMillis()
        val p = pb.start()
        // The log is read on its own thread, so cancelling kills the slicer at once even when it prints nothing.
        // The last slice's log is kept in the app's cache (last-slice.log), for diagnosing a failed slice.
        val logFile = File(context.cacheDir, "last-slice.log").bufferedWriter()
        val reader = Thread {
            runCatching { p.inputStream.bufferedReader().forEachLine { logFile.write(it); logFile.newLine(); onLog(it) } }
            runCatching { logFile.close() }
        }.apply { isDaemon = true; start() }
        try {
            while (!p.waitFor(100, java.util.concurrent.TimeUnit.MILLISECONDS)) currentCoroutineContext().ensureActive()
            reader.join(2000)
            val rc = p.exitValue()
            val outcome = SliceOutcome.parse(File(out, "result.json").takeIf { it.exists() }?.readText())
            EngineRun(rc, outcome, File(out, output).takeIf { it.exists() }, dir, System.currentTimeMillis() - started)
        } catch (e: Exception) {
            if (p.isAlive) p.destroyForcibly()
            dir.deleteRecursively()
            throw e
        } finally {
            if (p.isAlive) p.destroyForcibly()
        }
    }

    private fun sha256(f: File): String = MessageDigest.getInstance("SHA-256").let { md ->
        f.inputStream().use { s -> val b = ByteArray(1 shl 16); while (true) { val n = s.read(b); if (n < 0) break; md.update(b, 0, n) } }
        md.digest().joinToString("") { "%02x".format(it) }
    }
}

/** One engine run: its exit code, what it reported, the sliced file (when it sliced) and the job directory. */
data class EngineRun(val exitCode: Int, val outcome: SliceOutcome?, val output: File?, val dir: File, val millis: Long) {
    /**
     * Sliced and complete. The slicer writes result.json only after the 3MF is finished; Android's sandbox can still
     * stop it later, while it exits (signal 31). Such a run counts only when the file opens and every plate's G-code
     * matches the MD5 the slicer stored next to it.
     */
    val ok get() = outcome?.ok == true && output != null && (exitCode == 0 || (exitCode == 128 + 31 && verified(output)))

    private fun verified(f: File): Boolean = runCatching {
        java.util.zip.ZipFile(f).use { z ->
            val plates = z.entries().asSequence().map { it.name }.filter { Regex("Metadata/plate_\\d+\\.gcode").matches(it) }.toList()
            plates.isNotEmpty() && plates.all { name ->
                val md5 = java.security.MessageDigest.getInstance("MD5").digest(z.getInputStream(z.getEntry(name)).readBytes())
                    .joinToString("") { "%02X".format(it) }
                z.getEntry("$name.md5")?.let { e -> z.getInputStream(e).bufferedReader().readText().trim().equals(md5, ignoreCase = true) } == true
            }
        }
    }.getOrDefault(false)
}
