package casa.leo.cancha.net

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

object Api {
    // Recipient backend, selected with -PcanchaBaseUrl at build time.
    val BASE = casa.leo.cancha.BuildConfig.SERVER_URL.trimEnd('/')

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        coerceInputValues = true
    }

    suspend fun fetchStatus(): StatusResponse = withContext(Dispatchers.IO) {
        val req = Request.Builder().url("$BASE/v1/status").build()
        client.newCall(req).execute().use { resp ->
            val body = resp.body?.string() ?: throw Exception("empty body")
            json.decodeFromString(StatusResponse.serializer(), body)
        }
    }

    suspend fun swapMirror(channelId: String) = withContext(Dispatchers.IO) {
        val req = Request.Builder().url("$BASE/v1/$channelId/swap").post(okhttp3.RequestBody.create(null, ByteArray(0))).build()
        runCatching { client.newCall(req).execute().close() }
    }

    // Start the DVR recorder so the channel is buffered + instant before the user tunes in.
    suspend fun warm(channelId: String) = withContext(Dispatchers.IO) {
        val req = Request.Builder().url("$BASE/v1/$channelId/warm").post(okhttp3.RequestBody.create(null, ByteArray(0))).build()
        runCatching { client.newCall(req).execute().close() }
    }

    suspend fun fetchLatestVersion(): AppVersion? = withContext(Dispatchers.IO) {
        runCatching {
            val req = Request.Builder().url("$BASE/v1/app/latest").build()
            client.newCall(req).execute().use { resp ->
                val body = resp.body?.string() ?: return@use null
                json.decodeFromString(AppVersion.serializer(), body)
            }
        }.getOrNull()
    }

    fun masterUrl(channelId: String) = "$BASE/v1/$channelId/master.m3u8"
    // DVR ring-buffer playlist: instant tune + 15-min rewind + stall-smoothing.
    fun dvrUrl(channelId: String) = "$BASE/v1/$channelId/dvr.m3u8"
    fun apkUrl() = "$BASE/apk/latest"
    fun flagUrl(cc: String) = "$BASE/flag/${cc.lowercase()}.svg"
    fun logoUrl(channelId: String) = "$BASE/logo/$channelId"
    fun thumbUrl(channelId: String) = "$BASE/thumb/$channelId.jpg"
    // bucket changes every 15 min → Coil re-fetches a fresh frame
    fun thumbUrl(channelId: String, bucket: Long) = "$BASE/thumb/$channelId.jpg?t=$bucket"
}
