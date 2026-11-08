package io.github.gccammelli.pandystudio

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import androidx.core.view.WindowCompat
import io.github.gccammelli.pandystudio.slicer.AndroidEngine
import io.github.gccammelli.pandystudio.slicer.EngineInfo
import io.github.gccammelli.pandystudio.slicer.ProfileSource
import io.github.gccammelli.pandystudio.slicer.SliceJob
import io.github.gccammelli.pandystudio.slicer.SliceRun
import io.github.gccammelli.pandystudio.ui.App
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

class MainActivity : ComponentActivity(), Platform {
    companion object { const val MAX_MODEL = 512L shl 20 }
    private val engineRunner by lazy { AndroidEngine(applicationContext) }
    private var picked: CompletableDeferred<List<Uri>>? = null
    private var saved: CompletableDeferred<Uri?>? = null
    private val pick = registerForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { picked?.complete(it) }
    private val create = registerForActivityResult(ActivityResultContracts.CreateDocument("model/3mf")) { saved?.complete(it) }
    private val prefs by lazy { getSharedPreferences("studio", MODE_PRIVATE) }
    /** Files other apps opened with Pandy Studio, read once the UI asks for models. */
    private val incoming = mutableListOf<Uri>()
    private var pendingEdit by mutableStateOf<Intent?>(null)
    override val phoneEditPending get() = pendingEdit != null

    override suspend fun takePhoneEdit(): PhoneEdit? {
        val edit = pendingEdit ?: return null
        try {
            val source = profiles()
            val schema = io.github.gccammelli.pandystudio.slicer.Schema.load(source)
            val request = io.github.gccammelli.pandystudio.slicer.PhoneProtocol.parse(edit.getStringExtra("request_id"), edit.getStringExtra("request_json"), true, schema)
            val data = edit.data?.let { withContext(Dispatchers.IO) { readCapped(it) } } ?: error("The model was not available.")
            return PhoneEdit(request, data)
        } finally { if (pendingEdit === edit) pendingEdit = null }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        intentUris(intent)
        setContent {
            CompositionLocalProvider(LocalPlatform provides this) {
                App { enabled, onBack -> BackHandler(enabled, onBack) }
            }
        }
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); intentUris(intent) }

    private fun intentUris(i: Intent?) {
        i ?: return
        when (i.action) {
            "io.github.gccammelli.pandystudio.EDIT_PROJECT" -> if (i.data != null) pendingEdit = i
            Intent.ACTION_VIEW -> i.data?.let(incoming::add)
            Intent.ACTION_SEND -> (if (android.os.Build.VERSION.SDK_INT >= 33) i.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                else @Suppress("DEPRECATION") i.getParcelableExtra(Intent.EXTRA_STREAM))?.let(incoming::add)
        }
    }

    override fun setDarkBars(dark: Boolean) {
        WindowCompat.getInsetsController(window, window.decorView).apply { isAppearanceLightStatusBars = !dark; isAppearanceLightNavigationBars = !dark }
    }

    override fun openUrl(url: String) { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }

    override suspend fun pickModels(): List<Pair<String, ByteArray>> {
        val uris = if (incoming.isNotEmpty()) incoming.toList().also { incoming.clear() } else {
            picked = CompletableDeferred(); pick.launch(arrayOf("*/*")); picked!!.await()
        }
        return withContext(Dispatchers.IO) {
            uris.map { u -> nameOf(u) to u }.filter { (n, _) -> n.lowercase().let { it.endsWith(".stl") || it.endsWith(".3mf") } }
                .map { (n, u) -> n to readCapped(u) }
                .also { if (it.isEmpty() && uris.isNotEmpty()) error("Pandy Studio opens STL and 3MF files.") }
        }
    }

    /** Reads a picked file, refusing ones too big to load on a phone. */
    private fun readCapped(u: Uri): ByteArray = contentResolver.openInputStream(u)?.use { s ->
        val out = java.io.ByteArrayOutputStream(); val buf = ByteArray(1 shl 16); var total = 0L
        while (true) { val n = s.read(buf); if (n < 0) break; total += n; require(total <= MAX_MODEL) { "That file is over ${MAX_MODEL shr 20} MB." }; out.write(buf, 0, n) }
        out.toByteArray()
    } ?: ByteArray(0)

    private fun nameOf(u: Uri): String = contentResolver.query(u, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
        if (c.moveToFirst()) c.getString(0) else null
    } ?: u.lastPathSegment ?: "model.stl"

    override suspend fun profiles(): ProfileSource = withContext(Dispatchers.IO) {
        val home = engineRunner.home
        ProfileSource { path -> File(home, if (path.startsWith("pandy/")) path else "resources/$path").takeIf { it.isFile }?.readText() }
    }

    override val engine: EngineInfo by lazy {
        EngineInfo("02.08.02.61", runCatching { engineRunner.engineSha256 }.getOrDefault("not installed"),
            runCatching { assets.open("engine-resources.sha256").bufferedReader().readText().trim() }.getOrDefault("not installed"))
    }

    override suspend fun slice(job: SliceJob, onLog: (String) -> Unit): SliceRun {
        val log = ArrayList<String>()
        val r = engineRunner.slice(job) { line -> synchronized(log) { log += line }; onLog(line) }
        return withContext(Dispatchers.IO) {
            try { SliceRun(r.outcome, if (r.ok) 0 else r.exitCode, r.output?.takeIf { r.ok }?.readBytes(), r.millis, synchronized(log) { log.toList() }, null) }
            finally { r.dir.deleteRecursively() }
        }
    }

    private fun stage(run: SliceRun, name: String): Uri {
        // One staged file at a time: earlier ones are removed so sliced files don't pile up in the cache.
        val dir = File(cacheDir, "sliced").apply { mkdirs(); listFiles()?.forEach { it.delete() } }
        val f = File(dir, name.replace(Regex("[^A-Za-z0-9._ -]"), "_")).apply { writeBytes(run.sliced!!) }
        return FileProvider.getUriForFile(this, "$packageName.files", f)
    }

    override fun share(run: SliceRun, fileName: String) {
        val uri = stage(run, fileName)
        startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("model/3mf").putExtra(Intent.EXTRA_STREAM, uri)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION), "Send sliced file"))
    }

    override suspend fun save(run: SliceRun, fileName: String): Boolean {
        saved = CompletableDeferred(); create.launch(fileName)
        val uri = saved!!.await() ?: return false
        withContext(Dispatchers.IO) { contentResolver.openOutputStream(uri)?.use { it.write(run.sliced!!) } }
        return true
    }

    override fun sendToPandy(run: SliceRun, fileName: String): Boolean {
        val uri = stage(run, fileName)
        for (pkg in listOf("io.github.gccammelli.pandy", "io.github.gccammelli.pandy.testbed")) {
            val i = Intent(Intent.ACTION_SEND).setType("model/3mf").setPackage(pkg).putExtra(Intent.EXTRA_STREAM, uri)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            if (i.resolveActivity(packageManager) != null) { grantUriPermission(pkg, uri, Intent.FLAG_GRANT_READ_URI_PERMISSION); startActivity(i); return true }
        }
        return false
    }

    override fun loadSetting(key: String): String? = prefs.getString(key, null)
    override fun saveSetting(key: String, value: String) { prefs.edit().putString(key, value).apply() }
}
