package org.flow.reader.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.RowScope
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

val FlowBlue = Color(0xFF0B5CAD)
val FlowBlueDark = Color(0xFF083D77)
val FlowSky = Color(0xFFE6F0FB)
val FlowSuccess = Color(0xFF15803D)
val FlowWarning = Color(0xFFB45309)
val FlowDanger = Color(0xFFB91C1C)
private val Ink = Color(0xFF0F172A)

val FlowGradient = Brush.verticalGradient(listOf(FlowBlueDark, FlowBlue))

private val LightColors = lightColorScheme(
    primary = FlowBlue,
    onPrimary = Color.White,
    primaryContainer = FlowSky,
    onPrimaryContainer = FlowBlueDark,
    surface = Color.White,
    onSurface = Ink,
    surfaceVariant = Color(0xFFEFF3F8),
    onSurfaceVariant = Color(0xFF526077),
    background = Color(0xFFF3F6FB),
    onBackground = Ink,
    outline = Color(0xFFCBD5E1),
    outlineVariant = Color(0xFFE2E8F0),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF7DB8F2),
    onPrimary = Ink,
)

// Field-readable: larger body and numeric input than the Material defaults.
private val FieldTypography = Typography().let { base ->
    base.copy(
        bodyLarge = base.bodyLarge.copy(fontSize = 18.sp, lineHeight = 26.sp),
        bodyMedium = base.bodyMedium.copy(fontSize = 16.sp, lineHeight = 22.sp),
        titleLarge = base.titleLarge.copy(fontSize = 24.sp, fontWeight = FontWeight.SemiBold),
        labelLarge = TextStyle(fontSize = 17.sp, fontWeight = FontWeight.Medium),
    )
}

@Composable
fun FlowTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        typography = FieldTypography,
        content = content,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FlowTopBar(
    title: String,
    navigationIcon: @Composable () -> Unit = {},
    actions: @Composable RowScope.() -> Unit = {},
) {
    TopAppBar(
        title = { Text(title, fontWeight = FontWeight.SemiBold) },
        navigationIcon = navigationIcon,
        actions = actions,
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = FlowBlueDark,
            titleContentColor = Color.White,
            navigationIconContentColor = Color.White,
            actionIconContentColor = Color.White,
        ),
    )
}
