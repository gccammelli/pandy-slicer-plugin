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
 * Runs the selected upstream CLI as an ARM64 executable installed in the APK's native library directory.
 * Each engine has independent assets and storage. PANDY_ENGINE_HOME redirects executable discovery to its
 * unpacked resources (engine/android-location.c). Every slice gets a fresh HOME, job directory and one CPU.
 */
class AndroidEngine(private val context: Context, val kind: EngineKind = EngineKind.BAMBU) {
    private val exe get() = File(context.applicationInfo.nativeLibraryDir, kind.executable)

    /** SHA-256 of the installed engine executable, shown in About and matched against the equivalence report. */
    val engineSha256: String by lazy { sha256(exe) }

    /** The unpacked engine package: bin/pandy-engine (a link to the installed executable) and resources/. */
    val home: File by lazy { install() }

    fun profiles(): ProfileSource = ProfileSource { path ->
        File(home, if (path.startsWith("pandy/")) path else "${kind.profileRoot}/$path").takeIf { it.isFile }?.readText()
    }

    private fun install(): File {
        val version = context.assets.open("${kind.resourceAsset}.sha256").bufferedReader().use { it.readText().trim() }
        require(Regex("[a-f0-9]{64}").matches(version)) { "Invalid engine resource version." }
        val root = File(context.filesDir, "engine/${kind.id}/$version")
        val done = File(root, ".complete")
        if (!done.exists()) {
            root.deleteRecursively()
            File(root, "bin").mkdirs()
            ZipInputStream(context.assets.open("${kind.resourceAsset}.zip").buffered()).use { z ->
                generateSequence { z.nextEntry }.forEach { e ->
                    val f = File(root, e.name).canonicalFile
                    require(f.path.startsWith(root.canonicalPath + File.separator)) { "Bad resource path ${e.name}" }
                    if (e.isDirectory) f.mkdirs() else { f.parentFile?.mkdirs(); f.outputStream().use { z.copyTo(it) } }
                }
            }
            done.writeText(version)
            File(context.filesDir, "engine/${kind.id}").listFiles()?.filter { it.name != version }?.forEach { it.deleteRecursively() }
        }
        // Legacy Bambu installations predate engine namespacing. Never remove another engine's directory.
        File(context.filesDir, "engine").listFiles()?.filter { Regex("[a-f0-9]{64}").matches(it.name) }
            ?.forEach { it.deleteRecursively() }
        File(root, "bin/pandy-engine").apply { if (!exists()) createNewFile() }
        return root
    }

    /**
     * The fastest CPU this process may run on, by its maximum frequency (big.LITTLE phones list little cores first).
     * Android's cpusets leave out cores for background and bound-service processes (a Pixel 8's fastest core is for
     * the foreground app only), and `taskset` fails on a core outside the set, so only allowed cores are candidates.
     */
    private fun fastestCpu(): Int {
        val allowed = runCatching {
            File("/proc/self/status").readLines().firstOrNull { it.startsWith("Cpus_allowed_list:") }?.substringAfter(':')?.let(::parseCpuList)
        }.getOrNull().orEmpty().ifEmpty { (0 until Runtime.getRuntime().availableProcessors()).toList() }
        return fastestCpu(allowed) { cpu -> runCatching { File("/sys/devices/system/cpu/cpu$cpu/cpufreq/cpuinfo_max_freq").readText().trim().toLong() }.getOrDefault(0L) }
    }

    /** Slices [job]; [onLog] gets the slicer's log lines as they come. Returns the result and the output directory. */
    suspend fun slice(job: SliceJob, onLog: (String) -> Unit = {}): EngineRun = withContext(Dispatchers.IO) {
        val library = PresetLibrary(profiles())
        val files = if (kind == EngineKind.ORCA) OrcaJob.files(job, library) else job.resolvedFiles(library)
        run(files, job.arguments() + if (kind == EngineKind.ORCA) listOf("--strict") else emptyList(), SliceJob.OUTPUT, onLog)
    }

    /** Runs a prepared server-style job in a fresh directory without mutating engine resources. */
    suspend fun sliceServer(job: ServerJob, onLog: (String) -> Unit = {}): EngineRun {
        require(kind.supportsServer) { "${kind.displayName} does not support server mode." }
        return run(job.files, job.arguments, "sliced.gcode.3mf", onLog)
    }

    private suspend fun run(files: Map<String, ByteArray>, arguments: List<String>, output: String, onLog: (String) -> Unit): EngineRun = withContext(Dispatchers.IO) {
        val dir = File(context.cacheDir, "slice-${kind.id}-${System.nanoTime()}").apply { mkdirs() }
        var process: Process? = null
        var reader: Thread? = null
        var logFile: java.io.BufferedWriter? = null
        fun stop() {
            process?.let { p -> if (p.isAlive) { p.destroyForcibly(); p.waitFor(2, java.util.concurrent.TimeUnit.SECONDS) } }
            reader?.join(2000)
            runCatching { logFile?.close() }
        }
        try {
            val out = File(dir, "out").apply { mkdirs() }
            File(dir, "home").mkdirs()
            files.forEach { (name, bytes) -> File(dir, name).writeBytes(bytes) }
            val engineArgs = if (kind == EngineKind.ORCA) {
                val data = File(dir, "data").apply { mkdirs() }
                val system = File(data, "system").apply { mkdirs() }
                val caches = File(home, "resources/profiles").listFiles().orEmpty().filter { it.isFile && it.extension == "opc" }
                require(caches.isNotEmpty()) { "Orca system presets are missing." }
                // Private cache copies prevent upstream cache refreshes from modifying installed resources.
                caches.forEach { it.copyTo(File(system, it.name)) }
                val count = files.keys.count { Regex("filament\\d+\\.json").matches(it) }
                OrcaJob.presetLinks(count).forEach { (alias, name) ->
                    val link = File(data, alias); link.parentFile!!.mkdirs()
                    android.system.Os.symlink(File(dir, name).path, link.path)
                }
                listOf("--datadir", data.path)
            } else emptyList()
            val cmd = listOf("/system/bin/taskset", cpuMask(fastestCpu()), exe.path) +
                arguments + engineArgs + listOf("--outputdir", out.path)
            val pb = ProcessBuilder(cmd).directory(dir).redirectErrorStream(true)
            pb.environment().apply { clear(); put("HOME", File(dir, "home").path); put("LC_ALL", "C"); put("PANDY_ENGINE_HOME", home.path)
                // glibc registers rseq at start-up, before any handler exists; Android's sandbox may not allow it.
                put("GLIBC_TUNABLES", "glibc.pthread.rseq=0"); put("TMPDIR", dir.path); put("PATH", "/system/bin") }
            val started = System.currentTimeMillis()
            val p = pb.start().also { process = it }
            // The log is read on its own thread, so cancelling kills the slicer at once even when it prints nothing.
            // The last slice's log is kept in the app's cache (last-slice.log), for diagnosing a failed slice.
            val writer = File(context.cacheDir, if (kind == EngineKind.BAMBU) "last-slice.log" else "last-slice-${kind.id}.log").bufferedWriter().also { logFile = it }
            val logReader = Thread {
                runCatching { p.inputStream.bufferedReader().forEachLine { writer.write(it); writer.newLine(); onLog(it) } }
                runCatching { writer.close() }
            }.apply { isDaemon = true; reader = this; start() }
            try {
                while (!p.waitFor(100, java.util.concurrent.TimeUnit.MILLISECONDS)) currentCoroutineContext().ensureActive()
                logReader.join(2000)
                val rc = p.exitValue()
                val resultText = File(out, "result.json").takeIf { it.exists() }?.readText()
                val outcome = if (kind == EngineKind.ORCA) OrcaJob.outcome(resultText) else SliceOutcome.parse(resultText)
                EngineRun(rc, outcome, File(out, output).takeIf { it.exists() }, dir, System.currentTimeMillis() - started)
            } catch (e: Exception) {
                if (p.isAlive) p.destroyForcibly()
                throw e
            } finally {
                if (p.isAlive) p.destroyForcibly()
            }
        } catch (e: Exception) {
            stop()
            dir.deleteRecursively()
            throw e
        } finally {
            stop()
        }
    }

    companion object {
        fun available(context: Context): List<EngineKind> {
            val assets = context.assets.list("")?.toSet().orEmpty()
            return EngineKind.entries.filter { kind ->
                File(context.applicationInfo.nativeLibraryDir, kind.executable).isFile &&
                    "${kind.resourceAsset}.zip" in assets && "${kind.resourceAsset}.sha256" in assets
            }
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

/** The CPUs of a `Cpus_allowed_list` value such as "0-3,5"; malformed parts are ignored. */
internal fun parseCpuList(list: String): List<Int> = list.trim().split(',').flatMap { part ->
    val ends = part.trim().split('-')
    val first = ends.firstOrNull()?.toIntOrNull(); val last = (if (ends.size == 2) ends[1] else ends[0]).toIntOrNull()
    if (ends.size > 2 || first == null || last == null || last < first) emptyList() else (first..last).toList()
}.distinct()

/** The CPU with the highest [maxFrequency] among [allowed] (the first on a tie); 0 when none is allowed. */
internal fun fastestCpu(allowed: List<Int>, maxFrequency: (Int) -> Long): Int = allowed.maxByOrNull(maxFrequency) ?: 0

/** The `taskset` mask (hexadecimal) that selects only [cpu]. */
internal fun cpuMask(cpu: Int): String = java.lang.Long.toHexString(1L shl cpu)
