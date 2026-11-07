package io.github.gccammelli.pandystudio

import androidx.compose.runtime.staticCompositionLocalOf
import io.github.gccammelli.pandystudio.slicer.EngineInfo
import io.github.gccammelli.pandystudio.slicer.ProfileSource
import io.github.gccammelli.pandystudio.slicer.SliceJob
import io.github.gccammelli.pandystudio.slicer.SliceRun

/** What the shared UI needs from the phone. */
interface Platform {
    fun setDarkBars(dark: Boolean)
    fun openUrl(url: String)
    /** Lets the user pick STL or 3MF files; returns (file name, contents) for each. */
    suspend fun pickModels(): List<Pair<String, ByteArray>>
    /** The engine's resources (profiles), once unpacked. */
    suspend fun profiles(): ProfileSource
    val engine: EngineInfo
    suspend fun slice(job: SliceJob, onLog: (String) -> Unit): SliceRun
    /** Offers a sliced file to other apps (Pandy, Files, ...). */
    fun share(run: SliceRun, fileName: String)
    /** Saves a sliced file where the user chooses. */
    suspend fun save(run: SliceRun, fileName: String): Boolean
    /** Hands the sliced file to Pandy, which uploads it to the printer; false when Pandy is not installed. */
    fun sendToPandy(run: SliceRun, fileName: String): Boolean
    fun loadSetting(key: String): String?
    fun saveSetting(key: String, value: String)
}

val LocalPlatform = staticCompositionLocalOf<Platform> { error("No platform") }

fun guide(path: String) = "https://github.com/gccammelli/pandy-studio/blob/main/$path"
