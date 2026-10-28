package casa.leo.cancha.ui

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.darkColorScheme

object CanchaColors {
    val BgBase = Color(0xFF0A0D12)
    val BgElev1 = Color(0xFF11161E)
    val BgElev2 = Color(0xFF181F2A)
    val BgElev3 = Color(0xFF232B39)
    val OnBg = Color(0xFFF0EEE8)
    val OnBgDim = Color(0xFF9AA2B0)
    val OnBgMute = Color(0xFF5A6376)
    val AccentWarm = Color(0xFFD97757)
    val AccentWarmStrong = Color(0xFFFFA07A)
    val AccentCool = Color(0xFF5D7FF5)
    val LiveRed = Color(0xFFEF4444)
    val OkGreen = Color(0xFF34D399)

    val MxGrad = Brush.linearGradient(listOf(Color(0xFFD97757), Color(0xFF5D2818)))
    val PeGrad = Brush.linearGradient(listOf(Color(0xFFF97316), Color(0xFF7C2D12)))
    val CoGrad = Brush.linearGradient(listOf(Color(0xFFFACC15), Color(0xFF713F12)))
    val ArGrad = Brush.linearGradient(listOf(Color(0xFF60A5FA), Color(0xFF1E3A8A)))
    val EsGrad = Brush.linearGradient(listOf(Color(0xFFEF4444), Color(0xFF7F1D1D)))
    val FrGrad = Brush.linearGradient(listOf(Color(0xFF3B5BBF), Color(0xFF1A2748)))
    val SnGrad = Brush.linearGradient(listOf(Color(0xFF2A9D5C), Color(0xFF123A24)))
    val CiGrad = Brush.linearGradient(listOf(Color(0xFFD98A3D), Color(0xFF5A3414)))
    val DeGrad = Brush.linearGradient(listOf(Color(0xFF5A5A5A), Color(0xFF1C1C1C)))
    val GbGrad = Brush.linearGradient(listOf(Color(0xFF3A4A8F), Color(0xFF171D38)))
    val UsGrad = Brush.linearGradient(listOf(Color(0xFF3556A8), Color(0xFF16203F)))
    val AfrGrad = Brush.linearGradient(listOf(Color(0xFF1B6B43), Color(0xFF0D3322)))

    fun gradFor(country: String): Brush = when (country) {
        "MX" -> MxGrad
        "PE" -> PeGrad
        "CO" -> CoGrad
        "AR" -> ArGrad
        "ES" -> EsGrad
        "FR" -> FrGrad
        "SN" -> SnGrad
        "CI" -> CiGrad
        "DE" -> DeGrad
        "GB" -> GbGrad
        "US" -> UsGrad
        "AFR" -> AfrGrad
        else -> Brush.linearGradient(listOf(BgElev2, BgBase))
    }
}

// Inter for body, Instrument Serif for display — bundled at runtime via Google Fonts emulated locally.
// For first cut we use sans-serif default + serif for display.
val DisplayFont = FontFamily.Serif
val BodyFont = FontFamily.SansSerif

object CanchaType {
    val hero = TextStyle(fontFamily = DisplayFont, fontSize = 64.sp, fontWeight = FontWeight.Normal, letterSpacing = (-1.5).sp, lineHeight = 64.sp)
    val title1 = TextStyle(fontFamily = DisplayFont, fontSize = 40.sp, fontWeight = FontWeight.Normal, letterSpacing = (-0.5).sp)
    val title2 = TextStyle(fontFamily = BodyFont, fontSize = 24.sp, fontWeight = FontWeight.SemiBold)
    val body = TextStyle(fontFamily = BodyFont, fontSize = 16.sp, fontWeight = FontWeight.Normal)
    val bodyDim = TextStyle(fontFamily = BodyFont, fontSize = 14.sp, fontWeight = FontWeight.Normal, color = CanchaColors.OnBgDim)
    val caption = TextStyle(fontFamily = BodyFont, fontSize = 12.sp, fontWeight = FontWeight.Medium, color = CanchaColors.OnBgMute, letterSpacing = 0.4.sp)
    val tilename = TextStyle(fontFamily = BodyFont, fontSize = 15.sp, fontWeight = FontWeight.Medium)
    val fallbackLogo = TextStyle(fontFamily = DisplayFont, fontSize = 28.sp, fontWeight = FontWeight.Normal, color = CanchaColors.OnBg, letterSpacing = (-0.5).sp)
}

object CanchaShapes {
    val tile = RoundedCornerShape(14.dp)
    val chip = RoundedCornerShape(999.dp)
    val card = RoundedCornerShape(20.dp)
}

@Composable
fun CanchaTheme(content: @Composable () -> Unit) {
    val cs = darkColorScheme(
        primary = CanchaColors.AccentWarm,
        onPrimary = CanchaColors.BgBase,
        background = CanchaColors.BgBase,
        onBackground = CanchaColors.OnBg,
        surface = CanchaColors.BgElev1,
        onSurface = CanchaColors.OnBg,
    )
    MaterialTheme(colorScheme = cs, content = content)
}
