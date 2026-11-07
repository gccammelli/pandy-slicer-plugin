package io.github.gccammelli.pandystudio.ui

import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer

fun Modifier.graphicsLayerRotate(degrees: Float) = graphicsLayer { rotationZ = degrees }
