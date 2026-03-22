package com.mira.watch.theme

import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.wear.compose.material3.ColorScheme
import androidx.wear.compose.material3.MaterialTheme
import androidx.wear.compose.material3.Typography

// Mira brand purple palette
val MiraPurple = Color(0xFF9B59B6)
val MiraPurpleLight = Color(0xFFBB8FCE)
val MiraPurpleDark = Color(0xFF6C3483)
val MiraSurface = Color(0xFF1A1A2E)
val MiraSurfaceDim = Color(0xFF0F0F1A)
val MiraOnSurface = Color(0xFFE8E0F0)
val MiraOnSurfaceVariant = Color(0xFFA89BB5)
val MiraError = Color(0xFFE74C3C)
val MiraSuccess = Color(0xFF2ECC71)

private val MiraColorScheme = ColorScheme(
    primary = MiraPurple,
    onPrimary = Color.White,
    primaryContainer = MiraPurpleDark,
    onPrimaryContainer = MiraPurpleLight,
    secondary = MiraPurpleLight,
    onSecondary = Color.Black,
    background = MiraSurfaceDim,
    onBackground = MiraOnSurface,
    surface = MiraSurface,
    onSurface = MiraOnSurface,
    onSurfaceVariant = MiraOnSurfaceVariant,
    error = MiraError,
    onError = Color.White,
)

@Composable
fun MiraWatchTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = MiraColorScheme,
        typography = Typography(),
        content = content
    )
}
