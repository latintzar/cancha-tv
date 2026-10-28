package casa.leo.cancha.player

import android.content.Context
import androidx.media3.common.MediaItem
import androidx.media3.common.TrackSelectionParameters
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.hls.HlsMediaSource
import casa.leo.cancha.net.Api

/**
 * Two ExoPlayers so channels are buffered BEFORE you open them — instant, like a real TV.
 *
 * - `active` renders on screen.
 * - `spare` silently pre-buffers the channel you're most likely to hit next (the focused grid
 *   tile, or the next channel in the surf direction). When you go there, we just swap which
 *   player is active — the picture is already decoded, so it's instant.
 *
 * PlayerScreen renders whatever `active()` returns and re-attaches its PlayerView whenever the
 * active instance changes. If a channel wasn't pre-buffered, `activate()` loads it into the
 * active player the normal (cold) way — so the fallback is always correct.
 */
@UnstableApi
object PlayerHolder {
    private var active: ExoPlayer? = null
    private var spare: ExoPlayer? = null
    var activeId: String? = null; private set
    var spareId: String? = null; private set

    private fun build(context: Context): ExoPlayer {
        val dataSourceFactory = DefaultHttpDataSource.Factory()
            .setUserAgent("Cancha/0.4 (Android TV)")
            .setConnectTimeoutMs(15_000)
            .setReadTimeoutMs(20_000)
        val mediaSourceFactory = HlsMediaSource.Factory(dataSourceFactory)
            .setAllowChunklessPreparation(true)
        val loadControl = DefaultLoadControl.Builder()
            .setBackBuffer(90_000, true)
            .setBufferDurationsMs(15_000, 50_000, 1_000, 2_000)
            .build()
        return ExoPlayer.Builder(context.applicationContext)
            .setMediaSourceFactory(mediaSourceFactory)
            .setLoadControl(loadControl)
            .setSeekBackIncrementMs(30_000)
            .setSeekForwardIncrementMs(30_000)
            .build()
            .apply {
                trackSelectionParameters = TrackSelectionParameters.Builder(context)
                    .setForceHighestSupportedBitrate(true)
                    .build()
            }
    }

    fun obtain(context: Context): ExoPlayer = active ?: build(context).also { active = it }
    fun active(): ExoPlayer? = active

    private fun load(p: ExoPlayer, channelId: String) {
        val item = MediaItem.Builder()
            .setUri(Api.dvrUrl(channelId))
            // ~18s behind live: feels like "now" but still smooths a brief hiccup (< 1-min cap).
            .setLiveConfiguration(
                MediaItem.LiveConfiguration.Builder()
                    .setTargetOffsetMs(18_000).setMaxOffsetMs(36_000).build()
            )
            .build()
        p.setMediaItem(item)
        p.prepare()
    }

    /** Grid: we're NOT watching → pre-buffer straight into the active player. */
    fun preroll(context: Context, channelId: String) {
        if (activeId == channelId) return
        val p = obtain(context)
        p.volume = 0f
        load(p, channelId)
        p.playWhenReady = true
        activeId = channelId
    }

    /** Pre-buffer a likely-next channel into the spare so a flip to it is instant. */
    fun bufferSpare(context: Context, channelId: String?) {
        if (channelId == null || channelId == activeId || channelId == spareId) return
        val s = spare ?: build(context).also { spare = it }
        s.volume = 0f
        load(s, channelId)
        s.playWhenReady = true
        spareId = channelId
    }

    /** Make `channelId` the active, audible stream. Instant if it was the spare. Returns the
     *  player to render. */
    fun activate(context: Context, channelId: String): ExoPlayer {
        active?.let { a ->
            if (activeId == channelId) { a.volume = 1f; a.playWhenReady = true; return a }
        }
        if (channelId == spareId && spare != null) {
            // Swap: the buffered spare becomes active; the old active becomes the spare.
            val newActive = spare!!
            val oldActive = active
            spare = oldActive
            spareId = activeId
            oldActive?.volume = 0f          // keep it silently buffered as the new spare
            active = newActive
            activeId = channelId
            newActive.volume = 1f
            newActive.playWhenReady = true
            return newActive
        }
        // Cold: load into the active player.
        val p = obtain(context)
        load(p, channelId)
        activeId = channelId
        p.volume = 1f
        p.playWhenReady = true
        return p
    }

    /** Auto-repair: rebuild + re-prepare the active stream from scratch — the programmatic
     *  equivalent of flipping a channel forward+back. Clears a stuck/garbled/doubled decode. */
    fun reload(context: Context, channelId: String) {
        val p = active ?: obtain(context)
        load(p, channelId)
        activeId = channelId
        p.playWhenReady = true
    }

    /** Silence everything when leaving the player (keep buffered for an instant re-open). */
    fun mute() { active?.volume = 0f; spare?.volume = 0f }

    fun release() {
        active?.release(); spare?.release()
        active = null; spare = null; activeId = null; spareId = null
    }
}
