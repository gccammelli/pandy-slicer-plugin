package io.github.gccammelli.pandystudio

import android.app.Service
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Message
import android.os.Messenger
import android.os.ParcelFileDescriptor
import io.github.gccammelli.pandystudio.slicer.*
import kotlinx.coroutines.*
import java.io.ByteArrayOutputStream
import java.io.File

/** Signature-protected, versioned IPC. Large files travel through descriptors, never Binder transactions. */
class SlicerService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val engines = mutableMapOf<EngineKind, AndroidEngine>()
    private var running: Job? = null
    private var runningId: String? = null
    private val incoming = Messenger(Handler(Looper.getMainLooper()) { message -> handle(message); true })

    override fun onBind(intent: Intent?): IBinder = incoming.binder
    override fun onDestroy() { scope.cancel(); super.onDestroy() }

    private fun reply(to: Messenger?, what: Int, id: String?, text: String) {
        if (to == null) return
        runCatching { to.send(Message.obtain(null, what).apply { data = Bundle().apply { putString("request_id", id); putString("text", text.take(128_000)) } }) }
    }

    private fun handle(message: Message) {
        val b = message.data
        val id = b.getString("request_id")
        val target = message.replyTo
        val action = message.what
        if (id.isNullOrBlank() || id.length > 256 || id.any { it.isISOControl() } || target == null) { closeDescriptors(b); return }
        when (action) {
            CANCEL -> { closeDescriptors(b); if (runningId == id) running?.cancel() }
            CAPABILITIES, SLICE, RESOURCES -> {
                if (running != null) { closeDescriptors(b); reply(target, ERROR, id, "Another slice request is already running."); return }
                runningId = id
                running = scope.launch(start = CoroutineStart.LAZY) {
                    try {
                        val text = withContext(Dispatchers.IO) { execute(action, id, b, target) }
                        reply(target, RESULT, id, text)
                    } catch (e: CancellationException) {
                        reply(target, ERROR, id, "Cancelled.")
                    } catch (e: Exception) {
                        reply(target, ERROR, id, e.message ?: "The slicer could not complete the request.")
                    } finally { closeDescriptors(b); running = null; runningId = null }
                }.also { it.start() }
            }
            else -> { closeDescriptors(b); reply(target, ERROR, id, "Unsupported operation.") }
        }
    }

    @Suppress("DEPRECATION")
    private fun closeDescriptors(bundle: Bundle) {
        for (key in listOf("input", "output")) runCatching { bundle.getParcelable<ParcelFileDescriptor>(key)?.close() }
    }

    @Suppress("DEPRECATION")
    private suspend fun execute(action: Int, id: String, b: Bundle, target: Messenger): String {
        val kind = EngineKind.parse(b.getString("engine_id"))
        val available = AndroidEngine.available(applicationContext)
        require(kind in available) { "${kind.displayName} is not installed." }
        val engine = engines.getOrPut(kind) { AndroidEngine(applicationContext, kind) }
        val resourceVersion = assets.open("${kind.resourceAsset}.sha256").bufferedReader().use { it.readText().trim() }
        require(Regex("[a-f0-9]{64}").matches(resourceVersion)) { "Invalid engine resource version." }
        if (action == SLICE) kind.checkResourceVersion(b.getString("resource_version"), resourceVersion)
        if (action == SLICE && b.getString("mode") == "server") {
            require(kind.supportsServer) { "${kind.displayName} does not support server mode." }
        }
        if (action == RESOURCES) {
            val output = b.getParcelable<ParcelFileDescriptor>("output") ?: error("Missing output file.")
            val digest = java.security.MessageDigest.getInstance("SHA-256")
            ParcelFileDescriptor.AutoCloseOutputStream(output).use { out ->
                java.security.DigestInputStream(assets.open("${kind.resourceAsset}.zip"), digest).use { it.copyTo(out) }
            }
            val sha = digest.digest().joinToString("") { "%02x".format(it) }
            // Bambu retains its existing resource-tree digest; Orca versions the archive itself.
            require(kind == EngineKind.BAMBU || sha == resourceVersion) { "Engine resources failed their integrity check." }
            return org.json.JSONObject().put("version", 1).put("engine_id", kind.id).put("profile_root", kind.profileRoot).put("sha256", sha).put("resource_version", resourceVersion).toString()
        }
        val home = engine.home
        val profiles = engine.profiles()
        val schema = Schema.load(profiles)
        if (action == CAPABILITIES) return org.json.JSONObject(
            if (kind.supportsServer) PhoneProtocol.capabilities(schema) else """{"version":1,"settings":[]}"""
        )
            .put("engine_id", kind.id)
            .put("engine_version", kind.version)
            .put("profile_root", kind.profileRoot)
            .put("supported_modes", org.json.JSONArray(if (kind.supportsServer) listOf("editor", "server") else listOf("editor")))
            .put("engines", org.json.JSONArray(available.map { installed ->
                org.json.JSONObject().put("id", installed.id).put("name", installed.displayName).put("version", installed.version)
                    .put("supported_modes", org.json.JSONArray(if (installed.supportsServer) listOf("editor", "server") else listOf("editor")))
            }))
            .put("engine_sha256", engine.engineSha256)
            .put("resource_version", resourceVersion)
            .toString()
        val input = b.getParcelable<ParcelFileDescriptor>("input") ?: error("Missing model file.")
        val output = b.getParcelable<ParcelFileDescriptor>("output") ?: run { input.close(); error("Missing output file.") }
        try {
            val original = ParcelFileDescriptor.AutoCloseInputStream(input).use { stream ->
                val result = ByteArrayOutputStream(); val buffer = ByteArray(65536)
                while (true) { currentCoroutineContext().ensureActive(); val n = stream.read(buffer); if (n < 0) break; require(result.size() + n <= PhoneProtocol.MAX_MODEL) { "Model is too large." }; result.write(buffer, 0, n) }
                result.toByteArray().also { require(it.isNotEmpty()) { "Model is empty." } }
            }
            val editor = b.getString("mode") == "editor"
            require(editor || b.getString("mode") == "server") { "Unsupported slice mode." }
            val request = if (editor) null else PhoneProtocol.parse(id, b.getString("request_json"), true, schema)
            val run = withTimeout(15 * 60 * 1000L) {
                if (editor) {
                    val job = PluginJob.parse(b.getString("request_json"), original, schema)
                    require(job.printerIncludes == PresetLibrary(profiles).includes(job.printer)) { "Printer profiles do not match the plugin." }
                    engine.slice(job) { line -> reply(target, PROGRESS, id, line.take(1024)) }
                } else {
                    PhoneScope.check(original, request!!.settings)
                    val prepared = ServerPort.prepare(request, original, profiles, File(home, "resources").path)
                    engine.sliceServer(ServerPort.resolveProcess(prepared, profiles)) { line -> reply(target, PROGRESS, id, line.take(1024)) }
                }
            }
            try {
                check(run.ok) { run.outcome?.message ?: "The slicer could not finish." }
                val sliced = run.output ?: error("No sliced file was produced.")
                require(sliced.length() in 1..PhoneProtocol.MAX_MODEL.toLong()) { "Sliced file is too large." }
                val bytes = sliced.readBytes()
                val result = if (request != null) PhoneResults.create(request, original, bytes) else {
                    val entries = io.github.gccammelli.pandystudio.io.Zip.read(bytes)
                    val gcodes = entries.filterKeys { Regex("Metadata/plate_\\d+\\.gcode").matches(it) }
                    require(gcodes.isNotEmpty() && gcodes.values.all { Safety.problems(it.decodeToString()).isEmpty() }) { "The sliced file failed its printer safety check." }
                    PhoneResult(bytes, "{\"version\":1}")
                }
                ParcelFileDescriptor.AutoCloseOutputStream(output).use { it.write(result.file) }
                return org.json.JSONObject(result.metadata).put("engine_id", kind.id).put("engine_version", kind.version).toString()
            } finally { run.dir.deleteRecursively() }
        } finally { runCatching { input.close() }; runCatching { output.close() } }
    }

    companion object {
        const val CAPABILITIES = 1; const val SLICE = 2; const val CANCEL = 3; const val RESOURCES = 4
        const val PROGRESS = 100; const val RESULT = 101; const val ERROR = 102
    }
}
