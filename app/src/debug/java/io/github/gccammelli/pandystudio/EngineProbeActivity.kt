package io.github.gccammelli.pandystudio

import android.app.Activity
import android.content.ComponentName
import android.content.Intent
import android.content.ServiceConnection
import android.os.*
import org.json.JSONObject
import java.io.File
import java.util.UUID

/** Testbed-only IPC probe. Reads fixed cache fixtures and never contacts a printer. */
class EngineProbeActivity : Activity() {
    private val id = UUID.randomUUID().toString()
    private var bound = false
    private var remote: Messenger? = null
    private var stage = 1
    private var testCase = "cube"
    private lateinit var folder: File
    private val descriptors = mutableListOf<ParcelFileDescriptor>()
    private val timeout = Handler(Looper.getMainLooper())
    private val deadline = Runnable { complete(false, "Probe timed out.") }
    private val listener = Messenger(Handler(Looper.getMainLooper()) { message ->
        if (message.data.getString("request_id") != id) return@Handler true
        val text = message.data.getString("text").orEmpty()
        when (message.what) {
            102 -> complete(false, text)
            101 -> runCatching {
                val reply = JSONObject(text)
                if (stage == 1) {
                    File(folder, "capabilities.json").writeText(text)
                    val check = intent.getStringExtra("check") ?: "slice"
                    if (check == "capabilities") complete(true, text)
                    else if (check == "resources") {
                        stage = 4
                        send(4, Bundle().apply { putParcelable("output", output("resources.zip")) })
                    } else {
                        stage = 2
                        val input = File(cacheDir, "probe/input/${testCase}")
                        send(2, Bundle().apply {
                            putString("mode", if (check == "server-refusal") "server" else "editor")
                            putString("resource_version", if (check == "stale-resources") "stale" else reply.getString("resource_version"))
                            putString("request_json", File(input, "request.json").readText())
                            putParcelable("input", ParcelFileDescriptor.open(File(input, "model.3mf"), ParcelFileDescriptor.MODE_READ_ONLY).also(descriptors::add))
                            putParcelable("output", output("out.gcode.3mf"))
                        })
                    }
                } else complete(true, text)
            }.onFailure { complete(false, it.message ?: it.toString()) }
        }
        true
    })
    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
            remote = Messenger(binder)
            send(1, Bundle())
        }
        override fun onServiceDisconnected(name: ComponentName?) { complete(false, "Service disconnected.") }
    }

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        if (!BuildConfig.APPLICATION_ID.endsWith(".testbed")) { finish(); return }
        val case = intent.getStringExtra("case") ?: "cube"
        if (!case.matches(Regex("[a-z0-9-]{1,40}"))) { finish(); return }
        testCase = case
        val token = intent.getStringExtra("token") ?: "latest"
        if (!token.matches(Regex("[a-zA-Z0-9_-]{1,80}"))) { finish(); return }
        folder = File(cacheDir, "probe/output/$token").apply { mkdirs() }
        File(folder, "result.json").delete()
        timeout.postDelayed(deadline, 16 * 60 * 1000L)
        bound = bindService(Intent(this, SlicerService::class.java), connection, BIND_AUTO_CREATE)
        if (!bound) complete(false, "Could not bind plugin service.")
    }

    private fun output(name: String) = ParcelFileDescriptor.open(File(folder, name),
        ParcelFileDescriptor.MODE_CREATE or ParcelFileDescriptor.MODE_TRUNCATE or ParcelFileDescriptor.MODE_READ_WRITE).also(descriptors::add)

    private fun send(action: Int, bundle: Bundle) {
        bundle.putString("request_id", id)
        intent.getStringExtra("engine_id")?.let { bundle.putString("engine_id", it) }
        remote!!.send(Message.obtain(null, action).apply { data = bundle; replyTo = listener })
    }

    private fun complete(ok: Boolean, text: String) {
        if (!::folder.isInitialized || isFinishing) return
        File(folder, "result.json").writeText(JSONObject().put("ok", ok).put("stage", stage).put("text", text).toString())
        finish()
    }

    override fun onDestroy() {
        timeout.removeCallbacks(deadline)
        if (stage in 1..4) runCatching {
            remote?.send(Message.obtain(null, 3).apply { data = Bundle().apply { putString("request_id", id) }; replyTo = listener })
        }
        if (bound) { unbindService(connection); bound = false }
        descriptors.forEach { runCatching { it.close() } }
        super.onDestroy()
    }
}
