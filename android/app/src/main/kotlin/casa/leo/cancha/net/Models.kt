package casa.leo.cancha.net

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class StatusResponse(
    val at: Double = 0.0,
    val channels: List<ChannelStatus> = emptyList(),
)

@Serializable
data class AppVersion(
    @SerialName("version_code") val versionCode: Int = 0,
    @SerialName("version_name") val versionName: String = "",
    val url: String = "",
    val notes: String = "",
)

@Serializable
data class ChannelStatus(
    val id: String,
    val name: String,
    val country: String,
    val type: String = "Entretenimiento",
    val kind: String = "hls",
    val yt: String = "",
    val number: Int = 0,
    val priority: Int = 5,
    @SerialName("logo_url") val logoUrl: String = "",
    val tags: List<String> = emptyList(),
    @SerialName("best_mirror_score") val bestMirrorScore: Double? = null,
    @SerialName("best_mirror_summary") val bestMirrorSummary: MirrorSummary? = null,
    val mirrors: List<MirrorDetail> = emptyList(),
) {
    val isLive: Boolean get() = (bestMirrorScore ?: 0.0) > 0.0
}

@Serializable
data class MirrorSummary(
    val fps: Double? = null,
    val codec: String? = null,
    val res: String? = null,
    @SerialName("bitrate_mbps") val bitrateMbps: Double? = null,
    val field: String? = null,
    @SerialName("jitter_ms") val jitterMs: Int? = null,
) {
    val height: Int get() = (res ?: "").split("x").getOrNull(1)?.toIntOrNull() ?: 0
    val qualityLabel: String get() = when {
        height >= 1080 && (fps ?: 0.0) >= 50 -> "60fps HD"
        height >= 1080 -> "1080p"
        height >= 720 -> "720p"
        height > 0 -> "${height}p"
        else -> "live"
    }
    val isGoldTier: Boolean get() = height >= 1080 && (fps ?: 0.0) >= 50
}

@Serializable
data class MirrorDetail(
    val id: String,
    val url: String,
    val score: Double = -1.0,
    val fps: Double = 0.0,
    val codec: String = "",
    val res: String = "",
    @SerialName("bitrate_mbps") val bitrateMbps: Double = 0.0,
    val field: String = "",
    @SerialName("jitter_ms") val jitterMs: Int = 0,
    val fails: Int = 0,
    val sick: Boolean = false,
    val error: String = "",
    @SerialName("proxy_country") val proxyCountry: String? = null,
)
