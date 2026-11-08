package io.github.gccammelli.pandystudio.ui

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.snapshotFlow
import io.github.gccammelli.pandystudio.LocalPlatform
import io.github.gccammelli.pandystudio.studio.Studio
import io.github.gccammelli.pandystudio.slicer.Setting
import kotlinx.coroutines.flow.first

/** Screens, as a back stack. */
sealed class Screen {
    data object Home : Screen()
    data object Plate : Screen()
    data class Settings(val page: Int = 0) : Screen()
    data object About : Screen()
}

class Nav {
    val stack = mutableStateListOf<Screen>(Screen.Home)
    val current get() = stack.last()
    fun go(s: Screen) { stack.add(s) }
    fun back(): Boolean = if (stack.size > 1) { stack.removeAt(stack.lastIndex); true } else false
}

@Composable
fun App(onBackHandler: @Composable (enabled: Boolean, onBack: () -> Unit) -> Unit) {
    val platform = LocalPlatform.current
    val scope = rememberCoroutineScope()
    val studio = remember { Studio(platform, scope) }
    val nav = remember { Nav() }
    LaunchedEffect(Unit) { studio.load() }
    LaunchedEffect(platform.phoneEditPending) {
        if (platform.phoneEditPending) {
            snapshotFlow { studio.library != null || studio.loadError != null }.first { it }
            try {
                val edit = platform.takePhoneEdit() ?: return@LaunchedEffect
                val printer = studio.printers.flatMap { it.nozzles }.firstOrNull { it.name == edit.request.printer }
                    ?: error("Pandy's printer preset is not available in Studio.")
                studio.choosePrinter(printer)
                val bed = mapOf("cool_plate" to "Cool Plate", "eng_plate" to "Engineering Plate", "hot_plate" to "High Temp Plate", "textured_plate" to "Textured PEI Plate", "supertack_plate" to "Supertack Plate")[edit.request.bed]
                if (bed != null) studio.set("curr_bed_type", Setting.One(bed))
                edit.request.filamentType?.takeIf { it.isNotBlank() }?.let { kind ->
                    val filament = studio.filamentChoices.firstOrNull { it.name.startsWith("Bambu $kind Basic @") }
                        ?: studio.filamentChoices.firstOrNull { it.name.startsWith("Bambu $kind @") }
                        ?: studio.filamentChoices.firstOrNull { it.name.startsWith("Generic $kind @") }
                        ?: error("The selected filament is not available for this printer.")
                    studio.setFilament(0, filament, edit.request.filamentColor ?: filament.string("default_filament_colour") ?: "#FFFFFF")
                }
                edit.request.settings.forEach { (key, value) -> studio.set(key, Setting.One(value)) }
                studio.addFile(edit.request.name + ".3mf", edit.model)
                nav.go(Screen.Plate)
            } catch (e: Exception) { studio.loadError = e.message ?: "Couldn't open the model from Pandy." }
        }
    }
    AppTheme {
        onBackHandler(nav.stack.size > 1) { nav.back() }
        AnimatedContent(nav.current, transitionSpec = { fadeIn() togetherWith fadeOut() }, label = "screen") { s ->
            when (s) {
                Screen.Home -> Home(studio, nav)
                Screen.Plate -> PlateScreen(studio, nav)
                is Screen.Settings -> SettingsScreen(studio, nav, s.page)
                Screen.About -> AboutScreen(studio, nav)
            }
        }
    }
}
