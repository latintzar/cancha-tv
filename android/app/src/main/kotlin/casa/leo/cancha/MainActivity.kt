package casa.leo.cancha

import android.os.Bundle
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.tv.material3.Text
import casa.leo.cancha.net.Api
import casa.leo.cancha.net.ChannelStatus
import casa.leo.cancha.player.PlayerScreen
import casa.leo.cancha.ui.CanchaTheme
import casa.leo.cancha.ui.HomeScreen
import casa.leo.cancha.update.Updater
import java.io.File

class MainActivity : ComponentActivity() {

    private var onBackOverride: (() -> Boolean)? = null

    @androidx.media3.common.util.UnstableApi
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            CanchaTheme {
                val context = LocalContext.current
                var updateMsg by remember { mutableStateOf<String?>(null) }
                var pendingApk by remember { mutableStateOf<File?>(null) }

                // Check for a newer APK on launch; download + offer install.
                // Offer each build at most ONCE — if you dismiss it (you're watching, not
                // updating), we don't re-nag the installer every launch. A newer build re-offers.
                LaunchedEffect(Unit) {
                    val v = Updater.checkForUpdate() ?: return@LaunchedEffect
                    if (casa.leo.cancha.data.RecentStore.lastUpdatePrompt(context) >= v.versionCode)
                        return@LaunchedEffect
                    casa.leo.cancha.data.RecentStore.setUpdatePrompted(context, v.versionCode)
                    updateMsg = "Descargando actualización ${v.versionName}…"
                    val apk = Updater.download(context, if (v.url.isNotBlank()) v.url else Api.apkUrl())
                    if (apk == null) { updateMsg = null; return@LaunchedEffect }
                    if (Updater.canInstall(context)) {
                        updateMsg = "Instalando ${v.versionName}…"
                        Updater.install(context, apk)
                    } else {
                        updateMsg = "Permite instalar para actualizar Cancha"
                        pendingApk = apk
                        Updater.requestInstallPermission(context)
                    }
                }

                // The system installer owns the flow once launched — never let our banner stick.
                // Auto-dismiss any update message so "Instalando…" can't linger after the
                // install finished, was cancelled, or failed.
                LaunchedEffect(updateMsg) {
                    if (updateMsg != null) {
                        kotlinx.coroutines.delay(7000)
                        updateMsg = null
                    }
                }

                // After the user grants the install permission and returns, finish the install.
                val lifecycleOwner = LocalLifecycleOwner.current
                DisposableEffect(lifecycleOwner, pendingApk) {
                    val obs = LifecycleEventObserver { _, event ->
                        if (event == Lifecycle.Event.ON_RESUME) {
                            val apk = pendingApk
                            if (apk != null && Updater.canInstall(context)) {
                                updateMsg = "Instalando…"
                                pendingApk = null
                                Updater.install(context, apk)
                            }
                        }
                    }
                    lifecycleOwner.lifecycle.addObserver(obs)
                    onDispose { lifecycleOwner.lifecycle.removeObserver(obs) }
                }

                Box(Modifier.fillMaxSize()) {
                    var navList by remember { mutableStateOf<List<ChannelStatus>>(emptyList()) }
                    var index by remember { mutableStateOf(-1) }
                    val current = navList.getOrNull(index)

                    // Record a tune-in for the "Seguir viendo" rail
                    fun tune(i: Int) {
                        if (navList.isEmpty()) return
                        val ni = ((i % navList.size) + navList.size) % navList.size
                        index = ni
                        casa.leo.cancha.data.RecentStore.add(context, navList[ni].id)
                    }

                    if (current == null) {
                        onBackOverride = null
                        HomeScreen(onChannelClick = { ch, list ->
                            navList = list
                            tune(list.indexOfFirst { it.id == ch.id }.coerceAtLeast(0))
                        })
                    } else {
                        onBackOverride = { index = -1; true }
                        PlayerScreen(
                            channel = current,
                            navList = navList,
                            index = index,
                            onClose = { index = -1 },
                            onTune = { i -> tune(i) },
                        )
                    }

                    UpdateBanner(updateMsg)
                }
            }
        }
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            onBackOverride?.let { if (it()) return true }
        }
        return super.onKeyDown(keyCode, event)
    }

    @androidx.media3.common.util.UnstableApi
    override fun onDestroy() {
        casa.leo.cancha.player.PlayerHolder.release()
        super.onDestroy()
    }
}

@androidx.compose.runtime.Composable
private fun androidx.compose.foundation.layout.BoxScope.UpdateBanner(msg: String?) {
    if (msg == null) return
    Box(
        Modifier
            .align(Alignment.TopCenter)
            .padding(top = 18.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(Color(0xFFE50914))
            .padding(horizontal = 18.dp, vertical = 8.dp),
    ) {
        Text(msg, style = casa.leo.cancha.ui.CanchaType.caption.copy(color = Color.White))
    }
}
