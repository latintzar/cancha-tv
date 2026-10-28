package casa.leo.cancha.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import casa.leo.cancha.BuildConfig
import casa.leo.cancha.net.Api
import casa.leo.cancha.net.AppVersion
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Self-update for the sideloaded TV app (no Play Store).
 * Flow: check backend manifest → if newer, download the APK → launch the system installer
 * (one "Install" tap). A non-privileged app cannot install fully silently — that's the ceiling
 * without device-owner provisioning.
 */
object Updater {

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    /** Returns a newer version if the backend advertises one, else null. */
    suspend fun checkForUpdate(): AppVersion? {
        val latest = Api.fetchLatestVersion() ?: return null
        return if (latest.versionCode > BuildConfig.VERSION_CODE) latest else null
    }

    /** Downloads the APK to the external cache dir. Returns the file or null on failure. */
    suspend fun download(context: Context, url: String): File? = withContext(Dispatchers.IO) {
        runCatching {
            val out = File(context.externalCacheDir, "cancha-update.apk")
            if (out.exists()) out.delete()
            val req = Request.Builder().url(url).header("User-Agent", "Cancha-Updater").build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return@withContext null
                val body = resp.body ?: return@withContext null
                out.outputStream().use { fos -> body.byteStream().copyTo(fos) }
            }
            if (out.length() > 1_000_000) out else null  // sanity: a real APK is multi-MB
        }.getOrNull()
    }

    /** True if we're allowed to launch the package installer. */
    fun canInstall(context: Context): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            context.packageManager.canRequestPackageInstalls()
        else true

    /** Sends the user to the one-time "allow installs from Cancha" settings screen. */
    fun requestInstallPermission(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            runCatching {
                val i = Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:${context.packageName}"),
                ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(i)
            }
        }
    }

    /** Launches the system package installer for the downloaded APK. */
    fun install(context: Context, apk: File) {
        runCatching {
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", apk)
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "application/vnd.android.package-archive")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                putExtra(Intent.EXTRA_NOT_UNKNOWN_SOURCE, true)
            }
            context.startActivity(intent)
        }
    }
}
