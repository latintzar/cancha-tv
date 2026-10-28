package casa.leo.cancha.player

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.FastForward
import androidx.compose.material.icons.filled.FastRewind
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.filled.VolumeOff
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material.icons.filled.Warning
import androidx.tv.material3.Icon
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.focusable
import androidx.compose.foundation.lazy.items
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.TrackSelectionParameters
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.hls.HlsMediaSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.ui.PlayerView
import androidx.tv.material3.Text
import casa.leo.cancha.net.Api
import casa.leo.cancha.net.ChannelStatus
import casa.leo.cancha.ui.CanchaColors
import casa.leo.cancha.ui.CanchaType
import coil.compose.AsyncImage
import kotlinx.coroutines.delay

private const val SEEK_STEP_MS = 30_000L
private const val LIVE_THRESHOLD_MS = 15_000L
private const val SURF_COMMIT_MS = 1300L

@androidx.media3.common.util.UnstableApi
@Composable
fun PlayerScreen(
    channel: ChannelStatus,
    navList: List<ChannelStatus>,
    index: Int,
    onClose: () -> Unit,
    onTune: (Int) -> Unit,
) {
    // On-demand YouTube "channel" → a WebView playlist embed, not the live HLS player.
    if (channel.kind == "youtube" && channel.yt.isNotBlank()) {
        YouTubeChannelScreen(channel, navList.size, index, onClose, onTune)
        return
    }
    val context = LocalContext.current
    var showChrome by remember { mutableStateOf(false) }
    var lastChromeShownAt by remember { mutableStateOf(System.currentTimeMillis()) }
    var muted by remember { mutableStateOf(false) }
    var liveOffsetMs by remember { mutableStateOf(0L) }
    var firstFrame by remember { mutableStateOf(false) }
    var isFav by remember(channel.id) { mutableStateOf(casa.leo.cancha.data.RecentStore.isFav(context, channel.id)) }
    var showList by remember { mutableStateOf(false) }   // Netflix-style channel list panel
    var surfDir by remember { mutableStateOf(1) }         // last flip direction → which neighbor to pre-buffer
    var flipOsd by remember { mutableStateOf(false) }     // brief channel banner (number · name · country)
    val focusRequester = remember { FocusRequester() }
    val n = navList.size

    // The on-screen player. Swaps to a pre-buffered spare on an instant flip, so up/down is
    // instant (the next channel is already decoding in the background).
    var activePlayer by remember { mutableStateOf(PlayerHolder.obtain(context)) }
    val player = activePlayer

    // Hide the cover overlay once playback actually starts. Re-keyed on activePlayer so the
    // listener follows the active instance across a swap.
    DisposableEffect(activePlayer) {
        val l = object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) { if (isPlaying) firstFrame = true }
            // Auto-repair: a playback error → rebuild the stream (the forward+back fix, automatic).
            override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
                runCatching { PlayerHolder.reload(context, channel.id) }
            }
        }
        activePlayer.addListener(l)
        if (activePlayer.isPlaying) firstFrame = true   // already-buffered swap → reveal at once
        onDispose { activePlayer.removeListener(l) }
    }

    LaunchedEffect(activePlayer, muted) { activePlayer.volume = if (muted) 0f else 1f }

    // Activate the tuned channel — instant if it was pre-rolled (grid) or pre-buffered (neighbor).
    // Every channel change flashes the compact OSD (number · name · country), then fades.
    LaunchedEffect(channel.id) {
        firstFrame = false
        activePlayer = PlayerHolder.activate(context, channel.id)
        firstFrame = activePlayer.isPlaying
        flipOsd = true
        delay(2600)
        flipOsd = false
    }

    // After landing, silently pre-buffer the next channel in the surf direction so the next
    // flip is instant.
    LaunchedEffect(index, surfDir, n) {
        if (n > 0) {
            delay(350)
            val nextIdx = ((index + surfDir) % n + n) % n
            navList.getOrNull(nextIdx)?.let { PlayerHolder.bufferSpare(context, it.id) }
        }
    }

    // Auto-hide chrome (~4s) + track live offset for the badge + stall watchdog.
    // Stall watchdog (auto-repair): if a channel is "playing" but the playhead is frozen for
    // ~6s, it's wedged — re-tune the SAME channel (the forward+back fix, automatic).
    LaunchedEffect(Unit) {
        var lastPos = -1L
        var stuckTicks = 0
        while (true) {
            delay(400)
            val ap = activePlayer
            liveOffsetMs = ap.currentLiveOffset.let { if (it == C.TIME_UNSET) 0L else it }
            if (ap.playWhenReady && ap.playbackState == Player.STATE_READY) {
                val pos = ap.currentPosition
                if (pos == lastPos) stuckTicks++ else { stuckTicks = 0; lastPos = pos }
                if (stuckTicks >= 15) {   // ~6s frozen while it claims to be playing → wedged
                    stuckTicks = 0; lastPos = -1L
                    runCatching { PlayerHolder.reload(context, channel.id) }
                }
            } else { lastPos = -1L; stuckTicks = 0 }
            if (showChrome && !showList && firstFrame && System.currentTimeMillis() - lastChromeShownAt > 4_000) {
                showChrome = false
            }
        }
    }

    // Don't release the shared players on close — keep them buffered for an instant re-open;
    // just silence them. Released when the app is destroyed.
    DisposableEffect(Unit) { onDispose { PlayerHolder.mute() } }
    LaunchedEffect(showList) { if (!showList) focusRequester.requestFocus() }

    val showChromeNow: () -> Unit = {
        showChrome = true
        lastChromeShownAt = System.currentTimeMillis()
    }
    val seekRelative: (Long) -> Unit = { delta ->
        val dur = player.duration
        val target = (player.currentPosition + delta).coerceAtLeast(0)
        player.seekTo(if (dur > 0) target.coerceAtMost(dur) else target)
        showChromeNow()
    }
    val goLive: () -> Unit = { player.seekToDefaultPosition(); player.play(); showChromeNow() }
    // Instant channel flip: jump straight to the prev/next channel in the alphabetical order;
    // the spare player has usually already buffered it, so the picture is immediate.
    val flip: (Int) -> Unit = { dir ->
        if (n > 0) { surfDir = dir; onTune(((index + dir) % n + n) % n) }  // OSD shows via channel.id effect
    }

    val behindLive = liveOffsetMs > LIVE_THRESHOLD_MS

    Box(
        Modifier
            .fillMaxSize()
            .background(Color.Black)
            .focusRequester(focusRequester)
            .focusable()
            .onPreviewKeyEvent { ev ->
                if (ev.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                // While the channel list is open it owns the keys; only Back (handled there) closes it.
                if (showList) return@onPreviewKeyEvent false
                when (ev.key) {
                    Key.DirectionCenter, Key.Enter, Key.NumPadEnter -> {
                        when {
                            !showChrome -> showChromeNow()      // first OK reveals the overlay
                            behindLive -> goLive()              // behind live → snap back to live
                            else -> { showList = true }         // overlay up + at live → channel list
                        }
                        true
                    }
                    Key.DirectionLeft, Key.MediaRewind -> { seekRelative(-SEEK_STEP_MS); true }
                    Key.DirectionRight, Key.MediaFastForward -> { seekRelative(SEEK_STEP_MS); true }
                    Key.DirectionUp, Key.ChannelUp -> { flip(1); true }
                    Key.DirectionDown, Key.ChannelDown -> { flip(-1); true }
                    Key.MediaPlay, Key.MediaPlayPause -> { goLive(); true }
                    else -> false
                }
            }
            .pointerInput(Unit) {
                awaitPointerEventScope { while (true) { awaitPointerEvent(); showChromeNow() } }
            }
    ) {
        AndroidView(
            factory = {
                PlayerView(it).apply {
                    this.player = activePlayer
                    useController = false
                    isFocusable = false
                    isFocusableInTouchMode = false
                    setShowBuffering(PlayerView.SHOW_BUFFERING_NEVER)  // no native spinner
                    setShutterBackgroundColor(android.graphics.Color.BLACK)
                    // Don't hold a stale frame across a player reset/swap — a held old surface is
                    // the classic source of the "doubled / garbled" frame after an instant flip.
                    setKeepContentOnPlayerReset(false)
                }
            },
            // Re-attach ONLY when the active instance actually changed (an instant flip swap).
            // Clear first (null) so the old surface is released cleanly, then bind the new one —
            // re-binding the same player every recomposition is what garbles the frame.
            update = { pv ->
                if (pv.player !== activePlayer) {
                    pv.player = null
                    pv.player = activePlayer
                }
            },
            modifier = Modifier.fillMaxSize(),
        )

        // Cover overlay: channel identity until the first frame renders → no black/spinner zap
        if (!firstFrame) {
            Box(Modifier.fillMaxSize().background(Color.Black)) {
                AsyncImage(
                    model = Api.thumbUrl(channel.id),
                    contentDescription = null,
                    modifier = Modifier.fillMaxSize(),
                    contentScale = ContentScale.Crop,
                )
                Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.45f)))
                Column(
                    Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(channel.name, style = CanchaType.title1.copy(color = CanchaColors.OnBg))
                    Spacer(Modifier.height(8.dp))
                    Text("sintonizando…", style = CanchaType.caption.copy(color = CanchaColors.OnBgMute))
                }
            }
        }

        // Compact channel-flip OSD: number · name · country, top-left, auto-fades.
        AnimatedVisibility(
            visible = flipOsd && !showChrome && !showList,
            enter = fadeIn(tween(120)),
            exit = fadeOut(tween(260)),
            modifier = Modifier.align(Alignment.TopStart),
        ) {
            Row(
                Modifier
                    .padding(40.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(Color.Black.copy(alpha = 0.66f))
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (channel.number > 0) {
                    Text(
                        "${channel.number}",
                        style = CanchaType.title1.copy(color = CanchaColors.OnBg),
                    )
                    Spacer(Modifier.width(14.dp))
                }
                Column {
                    Text(channel.name, style = CanchaType.body.copy(color = CanchaColors.OnBg), maxLines = 1)
                    Text(
                        casa.leo.cancha.ui.countryLabelOf(channel.country),
                        style = CanchaType.caption.copy(color = CanchaColors.OnBgMute),
                    )
                }
            }
        }

        AnimatedVisibility(
            visible = showChrome && !showList,
            enter = fadeIn(tween(300)),
            exit = fadeOut(tween(300)),
            modifier = Modifier.matchParentSize(),
        ) {
            Box(Modifier.fillMaxSize()) {
                TopChrome(
                    onClose = onClose,
                    isFav = isFav,
                    onToggleFav = { isFav = casa.leo.cancha.data.RecentStore.toggleFav(context, channel.id); showChromeNow() },
                )
                BottomChrome(
                    ch = channel,
                    muted = muted,
                    behindLive = behindLive,
                    liveOffsetMs = liveOffsetMs,
                    onPrev = { onTune(index - 1) },
                    onNext = { onTune(index + 1) },
                    onRewind = { seekRelative(-SEEK_STEP_MS) },
                    onForward = { seekRelative(SEEK_STEP_MS) },
                    onGoLive = goLive,
                    onMuteToggle = { muted = !muted; showChromeNow() },
                )
            }
        }

        // Netflix-style channel list — slides in top-right, sticky country headers, country filter.
        AnimatedVisibility(
            visible = showList,
            enter = fadeIn(tween(160)),
            exit = fadeOut(tween(160)),
            modifier = Modifier.matchParentSize(),
        ) {
            ChannelListPanel(
                navList = navList,
                currentId = channel.id,
                onPick = { picked ->
                    val i = navList.indexOfFirst { it.id == picked.id }
                    showList = false
                    if (i >= 0 && i != index) onTune(i)
                },
                onClose = { showList = false },
            )
        }
    }
}

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
private fun BoxScope.ChannelListPanel(
    navList: List<ChannelStatus>,
    currentId: String,
    onPick: (ChannelStatus) -> Unit,
    onClose: () -> Unit,
) {
    var filterCC by remember { mutableStateOf<String?>(null) }   // null = todos
    val countries = remember(navList) { navList.map { it.country }.distinct() }  // already alpha-ordered
    val shown = remember(navList, filterCC) {
        if (filterCC == null) navList else navList.filter { it.country == filterCC }
    }
    val grouped = remember(shown) { shown.groupBy { it.country } }
    val panelFocus = remember { FocusRequester() }
    LaunchedEffect(Unit) { runCatching { panelFocus.requestFocus() } }

    // Dim scrim + right-aligned panel
    Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.35f)))
    Column(
        Modifier
            .align(Alignment.TopEnd)
            .fillMaxHeight()
            .fillMaxWidth(0.42f)
            .background(Color(0xFF0E0E0E))
            .focusRequester(panelFocus)
            .focusable()
            .onPreviewKeyEvent { ev ->
                if (ev.type == KeyEventType.KeyDown && ev.key == Key.Back) { onClose(); true } else false
            }
            .padding(horizontal = 22.dp, vertical = 20.dp),
    ) {
        Text("Canales", style = CanchaType.title1.copy(color = CanchaColors.OnBg))
        Spacer(Modifier.height(14.dp))
        // Country filter chips
        androidx.compose.foundation.lazy.LazyRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            item {
                FilterChip("Todos", filterCC == null) { filterCC = null }
            }
            items(countries, key = { it }) { cc ->
                FilterChip(casa.leo.cancha.ui.countryLabelOf(cc), filterCC == cc) { filterCC = cc }
            }
        }
        Spacer(Modifier.height(14.dp))
        val listState = androidx.compose.foundation.lazy.rememberLazyListState()
        androidx.compose.foundation.lazy.LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            grouped.forEach { (cc, chans) ->
                stickyHeader(key = "h_$cc") {
                    Box(
                        Modifier.fillMaxWidth().background(Color(0xFF0E0E0E)).padding(vertical = 8.dp),
                    ) {
                        Text(
                            casa.leo.cancha.ui.countryLabelOf(cc).uppercase(),
                            style = CanchaType.caption.copy(color = CanchaColors.OnBgMute),
                        )
                    }
                }
                items(chans, key = { it.id }) { ch ->
                    ChannelRow(ch, ch.id == currentId) { onPick(ch) }
                }
            }
        }
    }
}

@Composable
private fun FilterChip(label: String, selected: Boolean, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Box(
        Modifier
            .clip(RoundedCornerShape(999.dp))
            .background(if (selected || focused) CanchaColors.OnBg else Color.White.copy(alpha = 0.08f))
            .onFocusChanged { focused = it.isFocused }
            .focusable()
            .clickable { onClick() }
            .padding(horizontal = 14.dp, vertical = 7.dp),
    ) {
        Text(
            label,
            style = CanchaType.caption.copy(color = if (selected || focused) Color.Black else CanchaColors.OnBg),
        )
    }
}

@Composable
private fun ChannelRow(ch: ChannelStatus, isCurrent: Boolean, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(if (focused) CanchaColors.OnBg.copy(alpha = 0.16f) else Color.Transparent)
            .onFocusChanged { focused = it.isFocused }
            .focusable()
            .clickable { onClick() }
            .padding(horizontal = 12.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (isCurrent) {
            Box(Modifier.size(7.dp).clip(CircleShape).background(Color(0xFFFF3B5C)))
            Spacer(Modifier.width(10.dp))
        }
        Text(
            ch.name,
            style = CanchaType.body.copy(color = if (focused) CanchaColors.OnBg else CanchaColors.OnBgDim),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun BoxScope.SurfStrip(navList: List<ChannelStatus>, sel: Int) {
    val n = navList.size
    // window of 5 around the selection
    val window = (-2..2).map { off -> ((sel + off) % n + n) % n }
    Box(
        Modifier
            .align(Alignment.BottomCenter)
            .fillMaxWidth()
            .background(Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(alpha = 0.92f))))
            .padding(horizontal = 40.dp, vertical = 28.dp),
    ) {
        Column {
            Text("Cambiar canal  ·  ▲ ▼", style = CanchaType.caption.copy(color = CanchaColors.OnBgMute))
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
                window.forEachIndexed { i, ci ->
                    val ch = navList[ci]
                    val isSel = i == 2
                    Column(
                        Modifier.width(if (isSel) 210.dp else 150.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Box(
                            Modifier
                                .fillMaxWidth()
                                .aspectRatio(16f / 9f)
                                .clip(RoundedCornerShape(8.dp))
                                .background(CanchaColors.BgElev1)
                                .then(
                                    if (isSel) Modifier.background(Color.Transparent) else Modifier
                                ),
                        ) {
                            AsyncImage(
                                model = Api.thumbUrl(ch.id),
                                contentDescription = ch.name,
                                modifier = Modifier.fillMaxSize().clip(RoundedCornerShape(8.dp)),
                                contentScale = ContentScale.Crop,
                            )
                            if (ch.number > 0) {
                                Box(
                                    Modifier.align(Alignment.TopStart).padding(6.dp)
                                        .clip(RoundedCornerShape(5.dp))
                                        .background(Color.Black.copy(alpha = 0.72f))
                                        .padding(horizontal = 6.dp, vertical = 2.dp),
                                ) {
                                    Text("Ch ${ch.number}", style = CanchaType.caption.copy(color = CanchaColors.OnBg))
                                }
                            }
                        }
                        Spacer(Modifier.height(6.dp))
                        Text(
                            ch.name,
                            style = CanchaType.caption.copy(
                                color = if (isSel) CanchaColors.OnBg else CanchaColors.OnBgMute,
                            ),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun BoxScope.TopChrome(onClose: () -> Unit, isFav: Boolean, onToggleFav: () -> Unit) {
    Row(
        Modifier
            .align(Alignment.TopCenter)
            .fillMaxWidth()
            .background(Brush.verticalGradient(listOf(Color.Black.copy(alpha = 0.75f), Color.Transparent)))
            .padding(horizontal = 40.dp, vertical = 24.dp),
        verticalAlignment = Alignment.Top,
    ) {
        IconBtn(icon = Icons.Filled.ArrowBack, contentDescription = "Atrás", onClick = onClose)
        Spacer(Modifier.weight(1f))
        // Favorite heart (top-right)
        Box(
            Modifier.size(48.dp).clip(CircleShape).background(Color.Black.copy(alpha = 0.35f))
                .clickable { onToggleFav() },
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = if (isFav) Icons.Filled.Favorite else Icons.Filled.FavoriteBorder,
                contentDescription = if (isFav) "Quitar de favoritos" else "Añadir a favoritos",
                tint = if (isFav) Color(0xFFFF3B5C) else CanchaColors.OnBg,
                modifier = Modifier.size(26.dp),
            )
        }
    }
}

@Composable
private fun BoxScope.BottomChrome(
    ch: ChannelStatus,
    muted: Boolean,
    behindLive: Boolean,
    liveOffsetMs: Long,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    onRewind: () -> Unit,
    onForward: () -> Unit,
    onGoLive: () -> Unit,
    onMuteToggle: () -> Unit,
) {
    Box(
        Modifier
            .align(Alignment.BottomCenter)
            .fillMaxWidth()
            .background(Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(alpha = 0.85f))))
            .padding(horizontal = 40.dp, vertical = 24.dp)
    ) {
        Column(Modifier.fillMaxWidth()) {
            Text(
                if (behindLive) "OK · volver a vivo    ▲▼ cambiar canal"
                else "OK · lista de canales    ▲▼ cambiar canal",
                style = CanchaType.caption.copy(color = CanchaColors.OnBgMute),
            )
            Spacer(Modifier.height(10.dp))
            LiveBadge(behindLive, liveOffsetMs, onGoLive)
            Spacer(Modifier.height(14.dp))
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconBtn(Icons.Filled.SkipPrevious, "Canal anterior", onPrev)
                    Spacer(Modifier.width(8.dp))
                    IconBtn(Icons.Filled.FastRewind, "Retroceder 30s", onRewind)
                    Spacer(Modifier.width(8.dp))
                    IconBtn(Icons.Filled.FastForward, "Avanzar 30s", onForward)
                    Spacer(Modifier.width(8.dp))
                    IconBtn(Icons.Filled.SkipNext, "Canal siguiente", onNext)
                    Spacer(Modifier.width(8.dp))
                    IconBtn(
                        if (muted) Icons.Filled.VolumeOff else Icons.Filled.VolumeUp,
                        if (muted) "Activar audio" else "Silenciar",
                        onMuteToggle,
                    )
                }
                Spacer(Modifier.weight(1f))
                CenterLabel(ch)
                Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun LiveBadge(behindLive: Boolean, liveOffsetMs: Long, onGoLive: () -> Unit) {
    Box(
        Modifier
            .clip(RoundedCornerShape(6.dp))
            .background(if (behindLive) Color(0xFFF59E0B).copy(alpha = 0.18f) else Color(0xFFE50914).copy(alpha = 0.22f))
            .clickable { onGoLive() }
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        if (behindLive) {
            val s = (liveOffsetMs / 1000)
            val label = if (s < 60) "-${s}s" else "-${s / 60}:${(s % 60).toString().padStart(2, '0')}"
            Text("⏪ $label · OK→vivo", style = CanchaType.caption.copy(color = Color(0xFFF59E0B)))
        } else {
            Text("● EN VIVO", style = CanchaType.caption.copy(color = Color(0xFFE50914)))
        }
    }
}

// On-demand YouTube channel: a WebView playing the playlist embed (autoplay + auto-advance).
// D-pad: Back closes, Up/Down flip channel; YouTube's own controls handle play/seek.
@Composable
private fun YouTubeChannelScreen(
    channel: ChannelStatus,
    n: Int,
    index: Int,
    onClose: () -> Unit,
    onTune: (Int) -> Unit,
) {
    // Our always-on player page (IFrame API: random clean start, auto-advance, loop, skip-on-error).
    // muted=0 → sound on the TV. Pre-seed YouTube's consent cookie so a fresh WebView doesn't stall
    // on the EU consent page (undismissable with a D-pad).
    val url = "${Api.BASE}/yt/${channel.id}?name=${java.net.URLEncoder.encode(channel.name, "UTF-8")}&muted=0"
    LaunchedEffect(Unit) {
        runCatching {
            val cm = android.webkit.CookieManager.getInstance()
            cm.setAcceptCookie(true)
            cm.setCookie("https://www.youtube.com", "SOCS=CAI; Path=/; Domain=.youtube.com; Max-Age=31536000")
            cm.setCookie("https://www.youtube.com", "CONSENT=YES+; Path=/; Domain=.youtube.com; Max-Age=31536000")
        }
    }
    val focusRequester = remember { FocusRequester() }
    LaunchedEffect(Unit) { focusRequester.requestFocus() }
    var loaded by remember { mutableStateOf("") }
    Box(
        Modifier
            .fillMaxSize()
            .background(Color.Black)
            .focusRequester(focusRequester)
            .focusable()
            .onPreviewKeyEvent { ev ->
                if (ev.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                when (ev.key) {
                    Key.Back -> { onClose(); true }
                    Key.DirectionUp, Key.ChannelUp -> { if (n > 0) onTune(((index + 1) % n + n) % n); true }
                    Key.DirectionDown, Key.ChannelDown -> { if (n > 0) onTune(((index - 1) % n + n) % n); true }
                    else -> false
                }
            },
    ) {
        AndroidView(
            factory = { ctx ->
                android.webkit.WebView(ctx).apply {
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    settings.mediaPlaybackRequiresUserGesture = false
                    webChromeClient = android.webkit.WebChromeClient()
                    setBackgroundColor(android.graphics.Color.BLACK)
                    isFocusable = false
                }
            },
            update = { wv -> if (loaded != url) { wv.loadUrl(url); loaded = url } },
            onRelease = { it.destroy() },
            modifier = Modifier.fillMaxSize(),
        )
        Row(
            Modifier
                .fillMaxWidth()
                .align(Alignment.TopStart)
                .background(Brush.verticalGradient(listOf(Color.Black.copy(alpha = 0.7f), Color.Transparent)))
                .padding(horizontal = 40.dp, vertical = 20.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconBtn(icon = Icons.Filled.ArrowBack, contentDescription = "Atrás", onClick = onClose)
            Spacer(Modifier.width(16.dp))
            Text(channel.name, style = CanchaType.body.copy(color = CanchaColors.OnBg))
            Spacer(Modifier.width(10.dp))
            Text(
                "· ${casa.leo.cancha.ui.countryLabelOf(channel.country)}",
                style = CanchaType.caption.copy(color = CanchaColors.OnBgMute),
            )
        }
    }
}

@Composable
private fun CenterLabel(ch: ChannelStatus) {
    val sum = ch.bestMirrorSummary
    val good = (sum?.jitterMs ?: 9999) < 400 && (sum?.bitrateMbps ?: 0.0) > 1.5 && (sum?.height ?: 0) >= 480
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier.clip(RoundedCornerShape(6.dp)).background(Color.Black.copy(alpha = 0.55f))
                .padding(horizontal = 10.dp, vertical = 4.dp)
        ) {
            Text(if (ch.number > 0) "Ch ${ch.number}" else ch.name, style = CanchaType.caption.copy(color = CanchaColors.OnBg))
        }
        Spacer(Modifier.width(10.dp))
        Text(ch.name, style = CanchaType.body.copy(color = CanchaColors.OnBg))
        Spacer(Modifier.width(8.dp))
        Text("· ${casa.leo.cancha.ui.countryLabelOf(ch.country)}", style = CanchaType.caption.copy(color = CanchaColors.OnBgMute))
        // only flag a PROBLEM — a green "all good" tick is just noise when it's playing
        if (!good) {
            Spacer(Modifier.width(8.dp))
            Icon(
                imageVector = Icons.Filled.Warning,
                contentDescription = "Señal inestable",
                tint = Color(0xFFF59E0B),
                modifier = Modifier.size(18.dp),
            )
        }
    }
}

@Composable
private fun IconBtn(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    contentDescription: String,
    onClick: () -> Unit,
) {
    Box(
        Modifier.size(44.dp).clip(CircleShape).background(Color.White.copy(alpha = 0.08f)).clickable { onClick() },
        contentAlignment = Alignment.Center,
    ) {
        Icon(imageVector = icon, contentDescription = contentDescription, tint = CanchaColors.OnBg, modifier = Modifier.size(22.dp))
    }
}
