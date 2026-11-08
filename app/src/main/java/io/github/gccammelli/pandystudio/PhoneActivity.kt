package io.github.gccammelli.pandystudio

import android.app.Activity
import android.content.ClipData
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.*
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import androidx.core.view.WindowCompat
import io.github.gccammelli.pandystudio.slicer.AndroidEngine
import io.github.gccammelli.pandystudio.slicer.PhoneProtocol
import io.github.gccammelli.pandystudio.slicer.PhoneResults
import io.github.gccammelli.pandystudio.slicer.ProfileSource
import io.github.gccammelli.pandystudio.slicer.Schema
import io.github.gccammelli.pandystudio.slicer.ServerPort
import io.github.gccammelli.pandystudio.ui.C
import io.github.gccammelli.pandystudio.ui.OutlineButton
import io.github.gccammelli.pandystudio.ui.T
import io.github.gccammelli.pandystudio.ui.ThemeMode
import kotlinx.coroutines.*
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.UUID

/** A bounded, cancelable activity for versioned requests from Pandy. */
class PhoneActivity : ComponentActivity() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private val engine by lazy { AndroidEngine(applicationContext) }
    private var message by mutableStateOf("Preparing Pandy Studio…")
    private var failed by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setResult(Activity.RESULT_CANCELED)
        setContent {
            ThemeMode.dark = isSystemInDarkTheme()
            SideEffect {
                @Suppress("DEPRECATION")
                window.statusBarColor = if (ThemeMode.dark) android.graphics.Color.rgb(17, 17, 17) else android.graphics.Color.rgb(244, 244, 244)
                @Suppress("DEPRECATION")
                window.navigationBarColor = if (ThemeMode.dark) android.graphics.Color.rgb(17, 17, 17) else android.graphics.Color.rgb(244, 244, 244)
                WindowCompat.getInsetsController(window, window.decorView).apply {
                    isAppearanceLightStatusBars = !ThemeMode.dark; isAppearanceLightNavigationBars = !ThemeMode.dark
                }
            }
            MaterialTheme {
                Column(Modifier.fillMaxSize().background(C.Bg).statusBarsPadding().navigationBarsPadding().padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                    if (!failed) { CircularProgressIndicator(color = C.Accent); Spacer(Modifier.height(24.dp)) }
                    T(if (failed) "Couldn’t prepare the model" else "Pandy Studio", 22.sp, weight = FontWeight.Bold)
                    Spacer(Modifier.height(10.dp))
                    T(message, 15.sp, C.Text, lh = 21.sp)
                    Spacer(Modifier.height(28.dp))
                    OutlineButton(if (failed) "Close" else "Cancel", C.Accent) { finish() }
                }
            }
        }
        scope.launch {
            try {
                val action = intent.action ?: error("Missing request action.")
                val capabilities = action == "io.github.gccammelli.pandystudio.CAPABILITIES_V1"
                val edit = action == "io.github.gccammelli.pandystudio.EDIT_V1"
                require(capabilities || edit || action == "io.github.gccammelli.pandystudio.SLICE_V1") { "Unsupported request." }
                val home = withContext(Dispatchers.IO) { engine.home }
                val profiles = ProfileSource { path -> File(home, if (path.startsWith("pandy/")) path else "resources/$path").takeIf { it.isFile }?.readText() }
                val schema = withContext(Dispatchers.IO) { Schema.load(profiles) }
                val request = PhoneProtocol.parse(intent.getStringExtra("request_id"), intent.getStringExtra("request_json"), !capabilities, schema)
                if (capabilities) {
                    setResult(Activity.RESULT_OK, Intent().putExtra("request_id", request.id).putExtra("result_json", PhoneProtocol.capabilities(schema)))
                    finish(); return@launch
                }
                val uri = intent.data ?: error("No model was provided.")
                require(uri.scheme == "content" && intent.flags and Intent.FLAG_GRANT_READ_URI_PERMISSION != 0) { "The model must have a temporary read grant." }
                message = "Reading model…"
                val original = withContext(Dispatchers.IO) {
                    contentResolver.openInputStream(uri)?.use { input ->
                        val out = ByteArrayOutputStream(); val buffer = ByteArray(65536)
                        while (true) { val n = input.read(buffer); if (n < 0) break; require(out.size() + n <= PhoneProtocol.MAX_MODEL) { "The model is too large." }; out.write(buffer, 0, n) }
                        out.toByteArray().also { require(it.isNotEmpty()) { "The model is empty." } }
                    } ?: error("Unable to read the model.")
                }
                if (edit) {
                    // The editor currently imports geometry only. Do not silently discard a project's settings or plates.
                    withContext(Dispatchers.Default) { PhoneProtocol.validateEditorModel(request, original) }
                    val staged = withContext(Dispatchers.IO) {
                        File(cacheDir, "sliced").apply { mkdirs() }.let { File(it, "edit-${UUID.randomUUID()}.3mf").apply { writeBytes(original) } }
                    }
                    val model = FileProvider.getUriForFile(this@PhoneActivity, "$packageName.files", staged)
                    val editor = Intent(this@PhoneActivity, MainActivity::class.java).setAction("io.github.gccammelli.pandystudio.EDIT_PROJECT")
                        .setDataAndType(model, "model/3mf").putExtra("request_id", request.id).putExtra("request_json", intent.getStringExtra("request_json"))
                        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    startActivity(editor)
                    setResult(Activity.RESULT_OK, Intent().putExtra("request_id", request.id).putExtra("result_json", "{}"))
                    finish(); return@launch
                }
                message = "Preparing model…"
                val job = withContext(Dispatchers.Default) {
                    io.github.gccammelli.pandystudio.slicer.PhoneScope.check(original, request.settings)
                    ServerPort.prepare(request, original, profiles, File(home, "resources").path)
                }
                message = "Slicing on this phone…"
                val run = withTimeoutOrNull(15 * 60 * 1000L) { engine.sliceServer(job) } ?: error("Slicing took too long.")
                val result = withContext(Dispatchers.IO) {
                    try {
                        check(run.ok) { run.outcome?.message ?: "The slicer could not finish." }
                        val output = run.output ?: error("The slicer returned no file.")
                        require(output.length() in 1..PhoneProtocol.MAX_MODEL.toLong()) { "The sliced file is too large." }
                        PhoneResults.create(request, original, output.readBytes())
                    } finally { run.dir.deleteRecursively() }
                }
                val file = withContext(Dispatchers.IO) {
                    File(cacheDir, "sliced").apply { mkdirs() }.let { File(it, "${UUID.randomUUID()}.gcode.3mf").apply { writeBytes(result.file) } }
                }
                val output = FileProvider.getUriForFile(this@PhoneActivity, "$packageName.files", file)
                val reply = Intent().setDataAndType(output, "model/3mf").putExtra("request_id", request.id).putExtra("result_json", result.metadata)
                reply.clipData = ClipData.newRawUri("sliced file", output)
                reply.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                setResult(Activity.RESULT_OK, reply); finish()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                failed = true
                message = when (e.message) {
                    "Unsupported protocol version." -> "Update Pandy and Pandy Studio, then try again."
                    else -> e.message ?: "Pandy Studio could not complete this request."
                }
            }
        }
    }

    override fun onDestroy() { scope.cancel(); super.onDestroy() }
}
