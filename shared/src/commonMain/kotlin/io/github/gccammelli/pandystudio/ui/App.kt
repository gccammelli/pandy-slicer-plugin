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
import io.github.gccammelli.pandystudio.LocalPlatform
import io.github.gccammelli.pandystudio.studio.Studio

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
