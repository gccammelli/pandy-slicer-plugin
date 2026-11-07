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
 * The executable ships in the APK as lib/arm64-v8a/libpandy_engine.so and its resources (Bambu's profiles) as
 * assets/engine-resources.zip. Both are copied once per version into the app's files in the layout the CLI expects:
 * it finds its resources from its own real path (bin/pandy-engine -> ../resources), so it must run from a copy there
 * rather than from the read-only library folder (the app targets API 28, which still lets it run that copy). Each slice runs in a fresh directory with a fresh HOME, LC_ALL=C and one CPU,
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
                    require(f.path.startsWith(root.canonicalPath)) { "Bad resource path ${e.name}" }
                    if (e.isDirectory) f.mkdirs() else { f.parentFile?.mkdirs(); f.outputStream().use { z.copyTo(it) } }
                }
            }
            done.writeText(version)
            File(context.filesDir, "engine").listFiles()?.filter { it.name != version }?.forEach { it.deleteRecursively() }
        }
        val bin = File(root, "bin/pandy-engine")
        if (!bin.exists() || bin.length() != exe.length()) {
            exe.copyTo(bin, overwrite = true)
            bin.setExecutable(true, true)
        }
        return root
    }

    /** The fastest CPU, by its maximum frequency (big.LITTLE phones list little cores first). */
    private fun fastestCpu(): Int = (0 until Runtime.getRuntime().availableProcessors()).maxByOrNull { cpu ->
        runCatching { File("/sys/devices/system/cpu/cpu$cpu/cpufreq/cpuinfo_max_freq").readText().trim().toLong() }.getOrDefault(0L)
    } ?: 0

    /** Slices [job]; [onLog] gets the slicer's log lines as they come. Returns the result and the output directory. */
    suspend fun slice(job: SliceJob, onLog: (String) -> Unit = {}): EngineRun = withContext(Dispatchers.IO) {
        val dir = File(context.cacheDir, "slice-${System.nanoTime()}").apply { mkdirs() }
        val out = File(dir, "out").apply { mkdirs() }
        File(dir, "home").mkdirs()
        job.files().forEach { (name, bytes) -> File(dir, name).writeBytes(bytes) }
        val cmd = listOf("/system/bin/taskset", Integer.toHexString(1 shl fastestCpu()), File(home, "bin/pandy-engine").path) +
            job.arguments() + listOf("--outputdir", out.path)
        val pb = ProcessBuilder(cmd).directory(dir).redirectErrorStream(true)
        pb.environment().apply { clear(); put("HOME", File(dir, "home").path); put("LC_ALL", "C"); put("TMPDIR", dir.path); put("PATH", "/system/bin") }
        val started = System.currentTimeMillis()
        val p = pb.start()
        try {
            p.inputStream.bufferedReader().useLines { lines ->
                for (l in lines) { currentCoroutineContext().ensureActive(); onLog(l) }
            }
            val rc = p.waitFor()
            val outcome = SliceOutcome.parse(File(out, "result.json").takeIf { it.exists() }?.readText())
            EngineRun(rc, outcome, File(out, SliceJob.OUTPUT).takeIf { it.exists() }, dir, System.currentTimeMillis() - started)
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
    val ok get() = exitCode == 0 && outcome?.ok == true && output != null
}
