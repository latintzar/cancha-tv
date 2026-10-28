@file:androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)

package casa.leo.cancha.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.activity.compose.BackHandler
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.launch
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Star
import android.content.Context
import androidx.compose.ui.layout.ContentScale
import casa.leo.cancha.net.Api
import casa.leo.cancha.net.ChannelStatus
import casa.leo.cancha.net.StatusResponse
import coil.ImageLoader
import coil.compose.AsyncImage
import coil.decode.SvgDecoder
import kotlinx.coroutines.delay

// Netflix-grade design: #141414 base, no EN VIVO pill, no quality badge, 16:9 thumbs.
private val BgPure = Color(0xFF141414)

// Overscan-safe side margin (~5% of a 1080p TV; older Philips/Saphi panels clip below this).
private val EDGE = 64.dp

// Shared 15-min thumbnail cache-bucket (updated by HomeScreen); tiles re-fetch when it changes.
private val gThumbBucket = mutableStateOf(System.currentTimeMillis() / 900_000L)

private val COUNTRY_ORDER = listOf("MX", "PE", "CO", "AR", "ES", "FR", "SN", "CI", "DE", "GB", "US", "AFR")
val COUNTRY_LABEL = mapOf(
    "MX" to "México", "PE" to "Perú", "CO" to "Colombia", "AR" to "Argentina", "ES" to "España",
    "FR" to "Francia", "SN" to "Senegal", "CI" to "C. Marfil", "DE" to "Alemania",
    "GB" to "Reino Unido", "US" to "USA", "AFR" to "África",
)

// Spanish-aware collator (Á≈A, case-insensitive) so "África" sorts under A, not after Z.
private val ES_COLLATOR = java.text.Collator.getInstance(java.util.Locale("es"))
    .apply { strength = java.text.Collator.PRIMARY }
fun countryLabelOf(cc: String) = COUNTRY_LABEL[cc] ?: cc
// Channel-flip / list order: countries alphabetical, channels alphabetical within each country.
val NAV_COMPARATOR = Comparator<ChannelStatus> { a, b ->
    val c = ES_COLLATOR.compare(countryLabelOf(a.country), countryLabelOf(b.country))
    if (c != 0) c else ES_COLLATOR.compare(a.name, b.name)
}
// Rounded flag SVGs served by the backend (/flag/<cc>.svg) — reliable on TV unlike emoji flags
private val FLAG_CC = mapOf(
    "MX" to "mx", "PE" to "pe", "CO" to "co", "AR" to "ar", "ES" to "es",
    "FR" to "fr", "SN" to "sn", "CI" to "ci", "DE" to "de", "GB" to "gb", "US" to "us", "AFR" to "afr",
)

private data class Tab(val key: String, val label: String, val flag: String? = null)

// Top nav is by TYPE (country is a sub-filter). Preferred order; tabs are built from the
// types actually present in the catalog, so new categories appear server-side with no rebuild.
val TYPE_ORDER = listOf(
    "Noticias", "Entretenimiento", "Películas y Series", "Documentales",
    "Ciencia", "Cultura", "Cocina y Viajes", "Debate", "Deportes", "Música",
)
private fun tabsFor(catalog: StatusResponse?): List<Tab> {
    val present = catalog?.channels?.map { it.type }?.toSet().orEmpty()
    val ordered = TYPE_ORDER.filter { it in present } + present.filter { it !in TYPE_ORDER }.sorted()
    return listOf(Tab("inicio", "Inicio")) + ordered.map { Tab(it, it) }
}

// Coil needs an SVG decoder for the flag SVGs; cache a single loader.
private var _flagLoader: ImageLoader? = null
private fun flagLoader(context: Context): ImageLoader =
    _flagLoader ?: ImageLoader.Builder(context)
        .components { add(SvgDecoder.Factory()) }
        .build().also { _flagLoader = it }

@Composable
private fun FlagChip(cc: String, width: androidx.compose.ui.unit.Dp = 26.dp) {
    val ctx = LocalContext.current
    AsyncImage(
        model = Api.flagUrl(cc),
        contentDescription = null,
        imageLoader = flagLoader(ctx),
        modifier = Modifier.width(width).aspectRatio(4f / 3f).clip(RoundedCornerShape(3.dp)),
        contentScale = ContentScale.Crop,
    )
}

// dead channels sink to the bottom of any rail
private fun liveFirst(a: ChannelStatus, b: ChannelStatus): Int =
    (if (b.isLive) 1 else 0) - (if (a.isLive) 1 else 0)

@Composable
fun HomeScreen(onChannelClick: (ChannelStatus, List<ChannelStatus>) -> Unit) {
    var catalog by remember { mutableStateOf<StatusResponse?>(null) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var selectedTab by remember { mutableStateOf("inicio") }
    var selectedCountry by remember { mutableStateOf<String?>(null) }  // país sub-filter (null = todos)
    var query by remember { mutableStateOf("") }
    var searchOpen by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        while (true) {
            try {
                catalog = Api.fetchStatus()
                loadError = null
            } catch (e: Exception) {
                loadError = e.message ?: "error"
            }
            delay(30_000)
        }
    }
    // Refresh thumbnails every 15 min so the grid shows what's on NOW
    LaunchedEffect(Unit) {
        while (true) { delay(900_000); gThumbBucket.value = System.currentTimeMillis() / 900_000L }
    }

    // Navigable list for prev/next in the player: live channels by channel number.
    val navList = remember(catalog) {
        catalog?.channels?.filter { it.isLive }?.sortedWith(NAV_COMPARATOR).orEmpty()
    }
    // Pre-warm the DVR for the top channels so the first thing you tap is INSTANT
    LaunchedEffect(navList) {
        navList.take(24).forEach { runCatching { Api.warm(it.id) } }
    }
    val context = LocalContext.current
    // Watch history — recomputed each fresh composition (i.e. on return from a channel).
    val favIds = remember(catalog) { casa.leo.cancha.data.RecentStore.favIds(context) }
    val recentIds = remember(catalog) { casa.leo.cancha.data.RecentStore.ids(context) }
    val mostWatchedIds = remember(catalog) { casa.leo.cancha.data.RecentStore.mostWatched(context) }
    val click: (ChannelStatus) -> Unit = { ch -> onChannelClick(ch, navList) }

    Surface(
        modifier = Modifier.fillMaxSize(),
        colors = androidx.tv.material3.SurfaceDefaults.colors(containerColor = BgPure),
    ) {
        Column(Modifier.fillMaxSize()) {
            HeaderRow(onOpenSearch = { searchOpen = true })
            if (!searchOpen) {
                TabRow(tabsFor(catalog), selectedTab) { selectedTab = it; selectedCountry = null }
                // País sub-filter — only when a type category is active.
                val cat = catalog
                if (selectedTab != "inicio" && cat != null) {
                    val ccs = cat.channels.filter { it.type == selectedTab }.map { it.country }.distinct()
                        .sortedWith(Comparator { a, b -> ES_COLLATOR.compare(countryLabelOf(a), countryLabelOf(b)) })
                    CountryFilterRow(ccs, selectedCountry) { selectedCountry = it }
                }
            }
            if (catalog == null) {
                LoadingState(loadError)
            } else if (searchOpen) {
                SearchOverlay(
                    catalog = catalog!!,
                    query = query,
                    onKey = { c -> query += c },
                    onDelete = { if (query.isNotEmpty()) query = query.dropLast(1) },
                    onClear = { query = "" },
                    onClose = { searchOpen = false; query = "" },
                    onChannelClick = { ch -> searchOpen = false; query = ""; click(ch) },
                )
            } else {
                Content(catalog!!, selectedTab, selectedCountry, favIds, recentIds, mostWatchedIds, click)
            }
        }
    }
}

@Composable
private fun HeaderRow(onOpenSearch: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(start = EDGE, end = EDGE, top = 24.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            "Cancha.",
            style = CanchaType.title1.copy(color = CanchaColors.OnBg, fontStyle = FontStyle.Italic),
        )
        Spacer(Modifier.weight(1f))
        SearchPill(onOpenSearch)
    }
}

@Composable
private fun SearchPill(onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Surface(
        onClick = onClick,
        modifier = Modifier
            .scale(if (focused) 1.04f else 1f)
            .onFocusChanged { focused = it.isFocused }
            .focusable(),
        shape = ClickableSurfaceDefaults.shape(shape = CanchaShapes.chip),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = Color.White.copy(alpha = 0.10f),
            focusedContainerColor = CanchaColors.OnBg,
            contentColor = CanchaColors.OnBg,
            focusedContentColor = BgPure,
        ),
    ) {
        Row(
            Modifier.padding(horizontal = 18.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "Buscar",
                style = CanchaType.body.copy(
                    color = if (focused) BgPure else CanchaColors.OnBg,
                    fontWeight = FontWeight.SemiBold,
                ),
            )
        }
    }
}

private val KB_ROWS = listOf("1234567890", "QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM")

@Composable
private fun SearchOverlay(
    catalog: StatusResponse,
    query: String,
    onKey: (Char) -> Unit,
    onDelete: () -> Unit,
    onClear: () -> Unit,
    onClose: () -> Unit,
    onChannelClick: (ChannelStatus) -> Unit,
) {
    BackHandler(enabled = true) { onClose() }
    val firstKey = remember { FocusRequester() }
    LaunchedEffect(Unit) { runCatching { firstKey.requestFocus() } }

    val q = query.trim().lowercase()
    val matches = if (q.isEmpty()) emptyList() else catalog.channels.filter {
        it.name.lowercase().contains(q) ||
            (COUNTRY_LABEL[it.country] ?: it.country).lowercase().contains(q)
    }.sortedWith(compareBy({ !it.isLive }, { it.name.lowercase() }))

    Column(Modifier.fillMaxSize().padding(horizontal = EDGE)) {
        // Query display (no system keyboard — input is the on-screen one below)
        Row(Modifier.fillMaxWidth().padding(vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(
                if (query.isEmpty()) "Escribe para buscar…" else query,
                style = CanchaType.title2.copy(
                    color = if (query.isEmpty()) CanchaColors.OnBgMute else CanchaColors.OnBg
                ),
            )
        }
        // On-screen keyboard
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            KB_ROWS.forEachIndexed { ri, row ->
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    row.forEachIndexed { ci, ch ->
                        KeyButton(ch.toString(), if (ri == 0 && ci == 0) firstKey else null) {
                            onKey(ch.lowercaseChar())
                        }
                    }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                KeyButton("Espacio", null, wide = true) { onKey(' ') }
                KeyButton("⌫", null) { onDelete() }
                KeyButton("Limpiar", null) { onClear() }
                KeyButton("Cerrar", null) { onClose() }
            }
        }
        Spacer(Modifier.height(22.dp))
        if (q.isNotEmpty()) {
            if (matches.isEmpty()) {
                Text("Sin resultados para “$query”", style = CanchaType.body.copy(color = CanchaColors.OnBgMute))
            } else {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(18.dp)) {
                    items(matches, key = { it.id }) { Tile(it, onChannelClick) }
                }
            }
        }
    }
}

@Composable
private fun KeyButton(
    label: String,
    focusRequester: FocusRequester?,
    wide: Boolean = false,
    onClick: () -> Unit,
) {
    var focused by remember { mutableStateOf(false) }
    Surface(
        onClick = onClick,
        modifier = Modifier
            .then(if (wide) Modifier.width(150.dp) else Modifier.widthIn(min = 50.dp))
            .height(50.dp)
            .scale(if (focused) 1.10f else 1f)
            .then(if (focusRequester != null) Modifier.focusRequester(focusRequester) else Modifier)
            .onFocusChanged { focused = it.isFocused }
            .focusable(),
        shape = ClickableSurfaceDefaults.shape(shape = CanchaShapes.chip),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = Color.White.copy(alpha = 0.08f),
            focusedContainerColor = CanchaColors.OnBg,
            contentColor = CanchaColors.OnBg,
            focusedContentColor = BgPure,
        ),
    ) {
        Box(Modifier.fillMaxSize().padding(horizontal = 12.dp), contentAlignment = Alignment.Center) {
            Text(
                label,
                style = CanchaType.body.copy(
                    color = if (focused) BgPure else CanchaColors.OnBg,
                    fontWeight = FontWeight.SemiBold,
                ),
            )
        }
    }
}

@Composable
private fun TabRow(tabs: List<Tab>, selected: String, onSelect: (String) -> Unit) {
    LazyRow(
        Modifier.fillMaxWidth().padding(horizontal = EDGE, vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(tabs, key = { it.key }) { tab ->
            TabChip(tab.label, tab.flag, tab.key == selected) { onSelect(tab.key) }
        }
    }
}

@Composable
private fun CountryFilterRow(ccs: List<String>, selected: String?, onSelect: (String?) -> Unit) {
    LazyRow(
        Modifier.fillMaxWidth().padding(horizontal = EDGE).padding(bottom = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item { TabChip("Todos los países", null, selected == null) { onSelect(null) } }
        items(ccs, key = { it }) { cc ->
            TabChip(COUNTRY_LABEL[cc] ?: cc, FLAG_CC[cc], selected == cc) { onSelect(cc) }
        }
    }
}

@Composable
private fun TabChip(label: String, flag: String?, selected: Boolean, onClick: () -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Surface(
        onClick = onClick,
        modifier = Modifier
            .scale(if (focused) 1.06f else 1f)
            .onFocusChanged { focused = it.isFocused }
            .focusable(),
        shape = ClickableSurfaceDefaults.shape(shape = CanchaShapes.chip),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (selected) CanchaColors.OnBg else Color.White.copy(alpha = 0.08f),
            focusedContainerColor = if (selected) CanchaColors.OnBg else Color.White.copy(alpha = 0.18f),
            contentColor = if (selected) BgPure else CanchaColors.OnBg,
            focusedContentColor = if (selected) BgPure else CanchaColors.OnBg,
        ),
    ) {
        Row(
            Modifier.padding(horizontal = 18.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (flag != null) {
                FlagChip(flag, width = 22.dp)
                Spacer(Modifier.width(8.dp))
            }
            Text(
                label,
                style = CanchaType.body.copy(
                    color = if (selected) BgPure else CanchaColors.OnBg,
                    fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium,
                ),
            )
        }
    }
}

@Composable
private fun LoadingState(error: String?) {
    Column(
        Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(if (error == null) "Cargando…" else "Error: $error", style = CanchaType.body)
    }
}

@Composable
private fun Content(
    catalog: StatusResponse,
    selectedTab: String,
    selectedCountry: String?,
    favIds: List<String>,
    recentIds: List<String>,
    mostWatchedIds: List<String>,
    onChannelClick: (ChannelStatus) -> Unit,
) {
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(top = 8.dp, bottom = 80.dp),
    ) {
        when (selectedTab) {
            "inicio" -> {
                val byId = catalog.channels.associateBy { it.id }
                // Favoritos first, then Recientes, then Tu más visto
                val favs = favIds.mapNotNull { byId[it] }.sortedWith(::liveFirst)
                if (favs.isNotEmpty()) {
                    item { Rail("Favoritos", favs, onChannelClick, railIcon = RailIcon.FAV) }
                }
                val recent = recentIds.mapNotNull { byId[it] }.sortedWith(::liveFirst)
                if (recent.isNotEmpty()) {
                    item { Rail("Recientes", recent, onChannelClick, railIcon = RailIcon.RECENT) }
                }
                val most = mostWatchedIds.mapNotNull { byId[it] }.sortedWith(::liveFirst)
                if (most.isNotEmpty()) {
                    item { Rail("Tu más visto", most, onChannelClick, railIcon = RailIcon.MOST) }
                }
                // Locale rails (live first, dead at the bottom)
                for (cc in COUNTRY_ORDER) {
                    val list = catalog.channels.filter { it.country == cc }
                        .sortedWith(compareBy({ !it.isLive }, { it.number }, { it.name }))
                    if (list.isEmpty()) continue
                    item { Rail(COUNTRY_LABEL[cc] ?: cc, list, onChannelClick, flag = FLAG_CC[cc]) }
                }
            }
            else -> {
                // A TYPE category is selected → its channels, grouped by country (país sub-filter),
                // countries alphabetical, channels alphabetical (live first).
                var chans = catalog.channels.filter { it.type == selectedTab }
                if (selectedCountry != null) chans = chans.filter { it.country == selectedCountry }
                val groups = chans.groupBy { it.country }
                val orderedCC = groups.keys.sortedWith(
                    Comparator { a, b -> ES_COLLATOR.compare(countryLabelOf(a), countryLabelOf(b)) }
                )
                if (chans.isEmpty()) {
                    item {
                        Box(Modifier.fillMaxWidth().padding(EDGE, 40.dp)) {
                            androidx.tv.material3.Text(
                                "Nada por aquí todavía",
                                style = CanchaType.body.copy(color = CanchaColors.OnBgMute),
                            )
                        }
                    }
                }
                for (cc in orderedCC) {
                    val list = groups[cc]!!.sortedWith(compareBy({ !it.isLive }, { it.name.lowercase() }))
                    item { Rail(COUNTRY_LABEL[cc] ?: cc, list, onChannelClick, flag = FLAG_CC[cc]) }
                }
            }
        }
    }
}

private enum class RailIcon { FAV, RECENT, MOST }

@Composable
private fun Rail(
    title: String,
    channels: List<ChannelStatus>,
    onClick: (ChannelStatus) -> Unit,
    flag: String? = null,
    railIcon: RailIcon? = null,
) {
    Column(Modifier.padding(top = 18.dp, bottom = 18.dp)) {
        Row(
            Modifier.padding(start = EDGE, end = EDGE, bottom = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (flag != null) {
                FlagChip(flag, width = 28.dp)
                Spacer(Modifier.width(11.dp))
            } else if (railIcon != null) {
                androidx.tv.material3.Icon(
                    imageVector = when (railIcon) {
                        RailIcon.FAV -> Icons.Filled.Favorite
                        RailIcon.RECENT -> Icons.Filled.Schedule
                        RailIcon.MOST -> Icons.Filled.Star
                    },
                    contentDescription = null,
                    tint = if (railIcon == RailIcon.FAV) Color(0xFFFF3B5C) else CanchaColors.OnBgDim,
                    modifier = Modifier.size(20.dp),
                )
                Spacer(Modifier.width(10.dp))
            }
            Text(title, style = CanchaType.title2.copy(color = CanchaColors.OnBg))
        }
        LazyRow(
            // vertical padding gives the focused tile (scale 1.08 + glow) room so it isn't clipped
            contentPadding = PaddingValues(horizontal = EDGE, vertical = 22.dp),
            horizontalArrangement = Arrangement.spacedBy(22.dp),
        ) {
            items(channels, key = { it.id }) { Tile(it, onClick) }
        }
    }
}

@Composable
private fun Tile(ch: ChannelStatus, onClick: (ChannelStatus) -> Unit) {
    var focused by remember { mutableStateOf(false) }
    var thumbLoaded by remember(ch.id) { mutableStateOf(false) }
    val offline = !ch.isLive
    val warmScope = rememberCoroutineScope()
    val context = LocalContext.current
    var prerollJob by remember { mutableStateOf<kotlinx.coroutines.Job?>(null) }
    Column(
        Modifier
            .width(340.dp)
            .scale(if (focused) 1.08f else 1f)
            .alpha(if (offline) 0.5f else 1f),
    ) {
        Surface(
            onClick = { if (!offline) onClick(ch) },
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(16f / 9f)
                // Glow: tinted, non-clipping drop so the focused tile lifts off the wall
                .then(
                    if (focused) Modifier.shadow(
                        elevation = 18.dp,
                        shape = CanchaShapes.tile,
                        clip = false,
                        ambientColor = Color.White,
                        spotColor = Color.White,
                    ) else Modifier
                )
                .onFocusChanged {
                    focused = it.isFocused
                    prerollJob?.cancel()
                    if (it.isFocused && !offline) {
                        // Land on a tile → warm its DVR immediately, and if you stay on it
                        // briefly, pre-buffer the actual stream into the shared player so
                        // pressing OK reveals an already-playing channel (no "sintonizando").
                        warmScope.launch { runCatching { Api.warm(ch.id) } }
                        prerollJob = warmScope.launch {
                            kotlinx.coroutines.delay(250)
                            runCatching { casa.leo.cancha.player.PlayerHolder.preroll(context, ch.id) }
                        }
                    }
                }
                .focusable(enabled = !offline),
            shape = ClickableSurfaceDefaults.shape(shape = CanchaShapes.tile),
            colors = ClickableSurfaceDefaults.colors(
                containerColor = CanchaColors.BgElev1,
                focusedContainerColor = CanchaColors.BgElev1,
                contentColor = CanchaColors.OnBg,
                focusedContentColor = CanchaColors.OnBg,
            ),
            border = ClickableSurfaceDefaults.border(
                border = androidx.tv.material3.Border.None,
                focusedBorder = androidx.tv.material3.Border(
                    border = androidx.compose.foundation.BorderStroke(4.dp, CanchaColors.OnBg),
                    shape = CanchaShapes.tile,
                ),
            ),
        ) {
            Box(Modifier.fillMaxSize()) {
                // Fallback bg: country-tinted gradient + serif name (covered when thumb loads)
                if (!thumbLoaded) {
                    Box(Modifier.fillMaxSize().background(CanchaColors.gradFor(ch.country)))
                    Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.22f)))
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(
                            ch.name,
                            style = CanchaType.fallbackLogo.copy(fontStyle = FontStyle.Italic),
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
                // Live thumb (live indicator IS the thumb), refreshed every 15 min via gThumbBucket
                if (!offline) {
                    AsyncImage(
                        model = Api.thumbUrl(ch.id, gThumbBucket.value),
                        contentDescription = ch.name,
                        modifier = Modifier.fillMaxSize(),
                        contentScale = androidx.compose.ui.layout.ContentScale.Crop,
                        onSuccess = { thumbLoaded = true },
                        onError = { thumbLoaded = false },
                    )
                }

                // Channel-number badge TOP-LEFT
                if (ch.number > 0) {
                    Box(
                        Modifier
                            .align(Alignment.TopStart)
                            .padding(10.dp)
                            .clip(RoundedCornerShape(6.dp))
                            .background(Color.Black.copy(alpha = 0.72f))
                            .padding(horizontal = 8.dp, vertical = 4.dp),
                    ) {
                        Text(
                            "Ch ${ch.number}",
                            style = CanchaType.caption.copy(
                                color = CanchaColors.OnBg,
                                fontWeight = FontWeight.Bold,
                            ),
                        )
                    }
                }

                // Channel logo BOTTOM-LEFT (~36% width) once thumb loaded
                if (thumbLoaded && !offline) {
                    Box(
                        Modifier
                            .align(Alignment.BottomStart)
                            .padding(start = 12.dp, bottom = 12.dp)
                            .fillMaxWidth(0.36f),
                    ) {
                        AsyncImage(
                            model = Api.logoUrl(ch.id),
                            contentDescription = null,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }

                // Offline: only "sin señal"
                if (offline) {
                    Box(
                        Modifier
                            .align(Alignment.BottomEnd).padding(12.dp)
                            .clip(CanchaShapes.chip)
                            .background(Color.Black.copy(alpha = 0.55f))
                            .padding(horizontal = 10.dp, vertical = 4.dp)
                    ) {
                        Text("sin señal", style = CanchaType.caption.copy(color = CanchaColors.OnBgMute))
                    }
                }
            }
        }
        Spacer(Modifier.height(10.dp))
        Text(
            ch.name,
            style = CanchaType.tilename.copy(color = CanchaColors.OnBg),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}
