"""Cancha backend v0 — FastAPI app.

Routes:
  GET  /                          → status page (JSON)
  GET  /v1/peter.m3u              → personalized M3U (every channel, points at /v1/<ch>/master.m3u8)
  GET  /v1/{channel}/master.m3u8  → fetches best mirror's master, rewrites variant URLs
  GET  /v1/{channel}/{mirror}/v/{b64}  → proxies variant playlist, rewrites segment URLs
  GET  /v1/{channel}/{mirror}/s/{b64}  → proxies segment bytes (optionally via Webshare)
  POST /v1/{channel}/swap?from={mirror_id}  → marks mirror sick, returns redirect to new master
  GET  /v1/status                 → JSON dashboard of channel health
  GET  /v1/version.json           → APK update endpoint (placeholder)
"""
from __future__ import annotations
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from urllib.parse import urljoin

import aiohttp
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse, StreamingResponse, RedirectResponse, HTMLResponse, FileResponse

from .catalog import load_catalog, CATALOG_PATH, LOGO_DIR
from .models import Catalog, Channel, Mirror
from .prober import prober_loop, probe_catalog, thumb_loop
from . import youtube
from .dvr import DvrManager
from .proxy import (
    b64url_encode, b64url_decode,
    rewrite_master, rewrite_variant, webshare_proxy_url, webshare_proxy_auth,
)
from .web import INDEX_HTML

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cancha")

UA = "Mozilla/5.0 (Linux; Android TV) AppleWebKit/537.36 Chrome/120 Safari/537.36"
SNAPSHOT_PATH = os.environ.get("CANCHA_SNAPSHOT", os.path.join(os.environ.get("CANCHA_STATE_DIR", ".state"), "snapshot.json"))
THUMB_DIR = os.environ.get("CANCHA_THUMB_DIR", os.path.join(os.environ.get("CANCHA_STATE_DIR", ".state"), "thumbs"))
LISTEN_HOST = os.environ.get("CANCHA_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("CANCHA_PORT", "8765"))

# Globals populated at startup
CATALOG: Catalog = Catalog()
HTTP_SESSION: aiohttp.ClientSession | None = None
PROBER_TASK: asyncio.Task | None = None
DVR: "DvrManager | None" = None
# Master playlist in-RAM cache for instant tune-in (TTL ~3s — live HLS playlists need fresh segments)
_MASTER_CACHE: dict[str, tuple[float, str, str, str]] = {}  # channel_id → (expires_at, rewritten_text, mirror_id, etag)
_MASTER_CACHE_TTL = 3.0


def _find_mirror(channel: Channel, mirror_id: str) -> Mirror | None:
    return next((m for m in channel.mirrors if m.mirror_id() == mirror_id), None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global CATALOG, HTTP_SESSION, PROBER_TASK
    log.info("Loading recipient catalogue")
    try:
        CATALOG = load_catalog(CATALOG_PATH)
    except Exception:
        raise RuntimeError("Configure a valid recipient catalogue.") from None
    log.info("Loaded %d channels with %d total mirrors",
             len(CATALOG.channels), sum(len(c.mirrors) for c in CATALOG.channels))

    # Initial probe so /peter.m3u is useful immediately
    log.info("Initial probe pass…")
    await probe_catalog(CATALOG)
    healthy = sum(1 for c in CATALOG.channels for m in c.mirrors if m.last_score > 0)
    total = sum(1 for c in CATALOG.channels for _ in c.mirrors)
    log.info("Initial probe: %d/%d mirrors healthy", healthy, total)

    HTTP_SESSION = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30, connect=10),
        connector=aiohttp.TCPConnector(limit=128),  # ssl=False breaks Webshare proxy CONNECT
    )
    PROBER_TASK = asyncio.create_task(prober_loop(CATALOG, SNAPSHOT_PATH))
    THUMB_TASK = asyncio.create_task(thumb_loop(CATALOG, THUMB_DIR))

    global DVR
    def _dvr_session():
        return aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20, connect=10),
            connector=aiohttp.TCPConnector(limit=64),
        )
    DVR = DvrManager(CATALOG, _dvr_session)
    DVR.start()
    # Populate YouTube channels' recent-video lists now, then refresh hourly in the background.
    try:
        await youtube.refresh_yt(CATALOG, HTTP_SESSION)
    except Exception:
        pass
    YT_TASK = asyncio.create_task(youtube.yt_loop(CATALOG, _dvr_session))
    log.info("Prober + thumb + DVR + YouTube started.")
    try:
        yield
    finally:
        log.info("Shutting down…")
        tasks = [PROBER_TASK, THUMB_TASK, YT_TASK]
        for task in tasks:
            if task: task.cancel()
        await asyncio.gather(*(task for task in tasks if task), return_exceptions=True)
        if DVR:
            await DVR.close()
        if HTTP_SESSION:
            await HTTP_SESSION.close()



app = FastAPI(lifespan=lifespan, title="Cancha", version="0.0.1")


@app.get("/", response_class=Response)
async def root_redirect():
    return RedirectResponse("/watch", status_code=302)


@app.get("/watch", response_class=Response)
async def watch_page():
    html = INDEX_HTML
    if os.environ.get("CANCHA_ATELIER_NAV") == "1":
        import re
        tag = '<link rel="stylesheet" href="./native-nav/atelier-inset.css"><script defer src="./native-nav/atelier-nav.js" data-project="cancha"></script>'
        html = html.replace("</head>", tag + "</head>", 1)
        html = re.sub(r"(<body\b[^>]*>)", lambda m: m.group(1) + '<div id="atelier-native-app">', html, count=1, flags=re.I)
        html = re.sub(r"</body>", "</div></body>", html, count=1, flags=re.I)
    return Response(content=html, media_type="text/html; charset=utf-8")


@app.get("/native-nav/{name}")
async def atelier_nav_asset(name: str):
    if os.environ.get("CANCHA_ATELIER_NAV") != "1" or name not in {"atelier-nav.js", "atelier-nav.css", "atelier-inset.css"}:
        raise HTTPException(404)
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "web", "native-nav", name))


@app.get("/yt/{channel_id}", response_class=HTMLResponse)
async def yt_player(channel_id: str, name: str = "", muted: int = 1):
    """On-demand YouTube channel player page (IFrame API, always-on rotation).
    Loaded by the web iframe and the native WebView. muted=1 for web (browser autoplay),
    muted=0 for the TV app (sound on)."""
    ch = CATALOG.by_id(channel_id)
    if not ch or getattr(ch, "kind", "") != "youtube":
        raise HTTPException(404, "not a youtube channel")
    html = youtube.player_html(name or ch.name, ch.yt or "", youtube.YT_CACHE.get(channel_id, []), muted)
    return HTMLResponse(html, headers={"Cache-Control": "no-store",
                                       "X-Frame-Options": "SAMEORIGIN"})


@app.get("/api", response_class=JSONResponse)
async def api_root():
    by_country: dict[str, int] = {}
    healthy_by_country: dict[str, int] = {}
    for c in CATALOG.channels:
        by_country[c.country] = by_country.get(c.country, 0) + 1
        if c.best_mirror(time.time()):
            healthy_by_country[c.country] = healthy_by_country.get(c.country, 0) + 1
    return {
        "app": "cancha",
        "version": "0.0.1",
        "channels": len(CATALOG.channels),
        "by_country": by_country,
        "healthy_by_country": healthy_by_country,
        "snapshot": SNAPSHOT_PATH,
    }


# ===== M3U for OTT Nav ========================================================

@app.get("/v1/channels.m3u", response_class=PlainTextResponse)
@app.get("/v1/peter.m3u", response_class=PlainTextResponse)
async def personalized_m3u(request: Request):
    """Generate a flat M3U pointing every channel at our /master.m3u8 endpoint.

    OTT Nav imports this; on tune it hits /v1/<ch>/master.m3u8 which picks the live-best mirror.
    """
    base = str(request.base_url).rstrip("/")
    out = ["#EXTM3U"]
    # Order: priority asc within country, country in our priority order
    country_order = ["MX", "PE", "CO", "AR", "ES"]
    for cc in country_order:
        channels = sorted(
            [c for c in CATALOG.channels if c.country == cc],
            key=lambda c: (c.priority, c.name),
        )
        for ch in channels:
            best = ch.best_mirror(time.time())
            tag_quality = "—"
            if best:
                if best.real_height >= 1080 and best.real_fps >= 50:
                    tag_quality = "60fps HD"
                elif best.real_height >= 1080:
                    tag_quality = "1080p"
                elif best.real_height >= 720:
                    tag_quality = "720p"
                else:
                    tag_quality = "SD"
            group = {"MX": "México", "PE": "Perú", "CO": "Colombia", "AR": "Argentina", "ES": "España"}[cc]
            display = f"{ch.name}" + (f"  •  {tag_quality}" if best else "  •  (sin señal)")
            out.append(
                f'#EXTINF:-1 tvg-id="{ch.id}" tvg-name="{ch.name}" '
                f'group-title="{group}",{display}'
            )
            out.append(f"{base}/v1/{ch.id}/master.m3u8")
    return "\n".join(out) + "\n"


# ===== HLS master/variant/segment proxying ===================================

async def _upstream_get_text(url: str, proxy: str | None, proxy_auth=None) -> tuple[str, str]:
    """Returns (body, final_url)."""
    assert HTTP_SESSION is not None
    kw = {"headers": {"User-Agent": UA}}
    if proxy:
        kw["proxy"] = proxy
        if proxy_auth:
            kw["proxy_auth"] = proxy_auth
    async with HTTP_SESSION.get(url, **kw) as r:
        r.raise_for_status()
        data = await r.content.read(500_000)
        return data.decode("utf-8", "ignore"), str(r.url)


@app.get("/v1/{channel_id}/master.m3u8")
async def channel_master(channel_id: str, request: Request):
    ch = CATALOG.by_id(channel_id)
    if not ch:
        raise HTTPException(404, "channel not found")
    now = time.time()

    # 1. Serve from RAM cache if fresh — sub-ms tune
    cached = _MASTER_CACHE.get(channel_id)
    if cached and cached[0] > now:
        _, rewritten, mirror_id, _etag = cached
        return PlainTextResponse(rewritten, headers={
            "Content-Type": "application/vnd.apple.mpegurl",
            "Cache-Control": "no-cache, no-store",
            "X-Cancha-Mirror": mirror_id,
            "X-Cancha-Cache": "hit",
        })

    best = ch.best_mirror(now)
    if not best:
        return PlainTextResponse(
            f"# {ch.name}: no healthy mirror right now (cancha is probing)\n", status_code=503
        )
    proxy = webshare_proxy_url(best.proxy_country)
    proxy_auth = webshare_proxy_auth(best.proxy_country)
    try:
        text, final_url = await _upstream_get_text(best.url, proxy, proxy_auth)
    except Exception as e:
        log.warning("master fetch failed for %s mirror=%s: %s", ch.id, best.mirror_id(), e)
        best.consecutive_failures += 1
        raise HTTPException(502, "Retry the channel or choose another mirror.") from None

    if "EXT-X-STREAM-INF" in text:
        rewritten = rewrite_master(text, final_url, ch.id, best.mirror_id())
    else:
        rewritten = rewrite_variant(text, final_url, ch.id, best.mirror_id())

    # Cache for ~3s
    _MASTER_CACHE[channel_id] = (now + _MASTER_CACHE_TTL, rewritten, best.mirror_id(), "")

    return PlainTextResponse(rewritten, headers={
        "Content-Type": "application/vnd.apple.mpegurl",
        "Cache-Control": "no-cache, no-store",
        "X-Cancha-Mirror": best.mirror_id(),
        "X-Cancha-Score": str(round(best.last_score, 1)),
        "X-Cancha-Fps": str(best.real_fps),
        "X-Cancha-Res": f"{best.real_width}x{best.real_height}",
        "X-Cancha-Bitrate-Mbps": str(round(best.real_bitrate / 1_000_000, 2)),
        "X-Cancha-Cache": "miss",
    })


@app.get("/v1/{channel_id}/dvr.m3u8")
async def channel_dvr(channel_id: str):
    """DVR playlist: a sliding 15-min window over the recorded ring buffer.
    Starts the recorder on first request (smart-dumping). Falls back to live master
    while the buffer is still filling so the user never sees an error."""
    ch = CATALOG.by_id(channel_id)
    if not ch:
        raise HTTPException(404, "channel not found")
    assert DVR is not None
    DVR.touch(channel_id, play=True)  # actually tuned → may start a transcode
    pl = DVR.playlist(channel_id)
    if pl is None:
        # Cold tune: wait briefly for the recorder's first segment so we serve the DVR
        # (instant cushion + smoothing) instead of raw upstream. Hot/warm-on-focus
        # channels skip this entirely. Capped so a dead mirror never hangs the request.
        waited = 0.0
        while pl is None and waited < 3.5:
            await asyncio.sleep(0.2)
            waited += 0.2
            pl = DVR.playlist(channel_id)
        if pl is None:
            if DVR.needs_transcode_cached(channel_id):
                # transcoded channel → raw master is an unplayable codec in-browser.
                # Tell the client to retry; the AAC playlist is seconds away.
                return Response(status_code=503, headers={"Retry-After": "1", "Cache-Control": "no-store"})
            # plain channel → raw master is at least playable; start now.
            return await channel_master(channel_id, None)  # type: ignore
    return PlainTextResponse(pl, headers={
        "Content-Type": "application/vnd.apple.mpegurl",
        "Cache-Control": "no-cache, no-store",
        "X-Cancha-Dvr": "live",
    })


@app.get("/v1/{channel_id}/dvrseg/{filename}")
async def channel_dvr_seg(channel_id: str, filename: str):
    assert DVR is not None
    path = DVR.seg_path(channel_id, filename)
    if not path:
        raise HTTPException(404, "segment not found")
    with open(path, "rb") as f:
        data = f.read()
    return Response(content=data, media_type="video/mp2t",
                    # short cache: segment filenames repeat after a DVR restart, so long edge
                    # caching could serve a stale pre-transcode (mp2) segment for a new aac one
                    headers={"Cache-Control": "public, max-age=20"})


@app.post("/v1/{channel_id}/warm")
async def channel_warm(channel_id: str):
    """Start recording a channel so it's instant when tuned. Called on hover/prewarm."""
    if not CATALOG.by_id(channel_id):
        raise HTTPException(404, "channel not found")
    assert DVR is not None
    DVR.touch(channel_id)
    return JSONResponse(DVR.status(channel_id))


@app.get("/v1/{channel_id}/dvr/status")
async def channel_dvr_status(channel_id: str):
    assert DVR is not None
    return JSONResponse(DVR.status(channel_id))


@app.get("/v1/app/latest")
async def app_latest():
    """Self-update manifest for the sideloaded Android TV app."""
    import json as _json
    path = os.environ.get("CANCHA_APP_VERSION_FILE", os.path.join(os.environ.get("CANCHA_STATE_DIR", ".state"), "static", "app-version.json"))
    try:
        with open(path) as f:
            return JSONResponse(_json.load(f))
    except Exception:
        return JSONResponse({"version_code": 0, "version_name": "", "url": "", "notes": ""})


@app.get("/v1/{channel_id}/{mirror_id}/v/{b64url}")
async def variant_playlist(channel_id: str, mirror_id: str, b64url: str):
    ch = CATALOG.by_id(channel_id)
    if not ch:
        raise HTTPException(404, "channel not found")
    mirror = _find_mirror(ch, mirror_id)
    if not mirror:
        raise HTTPException(404, "mirror not found")
    try:
        upstream = b64url_decode(b64url)
    except Exception:
        raise HTTPException(400, "Reload the channel playlist.")
    proxy = webshare_proxy_url(mirror.proxy_country)
    proxy_auth = webshare_proxy_auth(mirror.proxy_country)
    try:
        text, final_url = await _upstream_get_text(upstream, proxy, proxy_auth)
    except Exception as e:
        raise HTTPException(502, "Try another configured channel mirror.") from None
    rewritten = rewrite_variant(text, final_url, channel_id, mirror_id)
    return PlainTextResponse(rewritten, headers={
        "Content-Type": "application/vnd.apple.mpegurl",
        "Cache-Control": "no-cache, no-store",
    })


@app.get("/v1/{channel_id}/{mirror_id}/s/{b64url}")
async def segment_proxy(channel_id: str, mirror_id: str, b64url: str, request: Request):
    ch = CATALOG.by_id(channel_id)
    if not ch:
        raise HTTPException(404, "channel not found")
    mirror = _find_mirror(ch, mirror_id)
    if not mirror:
        raise HTTPException(404, "mirror not found")
    try:
        upstream = b64url_decode(b64url)
    except Exception:
        raise HTTPException(400, "Reload the channel playlist.")
    proxy = webshare_proxy_url(mirror.proxy_country)
    proxy_auth = webshare_proxy_auth(mirror.proxy_country)

    assert HTTP_SESSION is not None
    headers = {"User-Agent": UA}
    # forward range header if present (live HLS sometimes uses byte ranges)
    if "range" in request.headers:
        headers["Range"] = request.headers["range"]

    kw = {"headers": headers}
    if proxy:
        kw["proxy"] = proxy
        if proxy_auth:
            kw["proxy_auth"] = proxy_auth

    async def stream():
        try:
            async with HTTP_SESSION.get(upstream, **kw) as r:
                # propagate content-type if upstream knows it
                async for chunk in r.content.iter_chunked(64 * 1024):
                    yield chunk
        except Exception as e:
            log.warning("segment proxy failed %s: %s", channel_id, e)

    return StreamingResponse(stream(), media_type="video/mp2t")


# ===== Swap & status ==========================================================

@app.post("/v1/{channel_id}/swap")
async def swap_mirror(channel_id: str, from_: str | None = None):
    ch = CATALOG.by_id(channel_id)
    if not ch:
        raise HTTPException(404, "channel not found")
    if from_:
        m = _find_mirror(ch, from_)
        if m:
            m.sick_until = time.time() + 300  # 5 min cooldown
            log.info("Mirror %s marked sick for 5min", from_)
    new_best = ch.best_mirror(time.time())
    return JSONResponse({
        "ok": True,
        "master_url": f"/v1/{channel_id}/master.m3u8",
        "new_mirror_id": new_best.mirror_id() if new_best else None,
        "new_mirror_score": round(new_best.last_score, 1) if new_best else None,
    })


@app.get("/v1/status", response_class=JSONResponse)
async def status(response: Response):
    now = time.time()
    # Edge-cache briefly so repeat loads + multiple clients hit the CDN, not the box.
    response.headers["Cache-Control"] = "public, max-age=6, s-maxage=6, stale-while-revalidate=30"
    return {
        "at": now,
        "channels": [
            {
                "id": c.id,
                "name": c.name,
                "country": c.country,
                "type": c.type,
                "kind": c.kind,
                "yt": c.yt,
                "priority": c.priority,
                "logo_url": c.logo_url,
                "tags": c.tags,
                "number": c.number,
                "best_mirror_score": (100.0 if youtube.is_live(c) else None) if c.kind == "youtube" else (round(c.best_mirror(now).last_score, 1) if c.best_mirror(now) else None),
                "best_mirror_summary": (
                    {
                        "fps": c.best_mirror(now).real_fps,
                        "codec": c.best_mirror(now).real_codec,
                        "res": f"{c.best_mirror(now).real_width}x{c.best_mirror(now).real_height}",
                        "bitrate_mbps": round(c.best_mirror(now).real_bitrate / 1_000_000, 2),
                        "field": c.best_mirror(now).field_order,
                        "jitter_ms": c.best_mirror(now).seg_fetch_jitter_ms,
                    } if c.best_mirror(now) else None
                ),
            }
            for c in CATALOG.channels
        ],
    }


STATIC_DIR = os.environ.get("CANCHA_STATIC_DIR", os.path.join(os.environ.get("CANCHA_STATE_DIR", ".state"), "static"))


@app.get("/v1/version.json")
async def version():
    return {"latest": "0.1.0", "apk_url": "https://cancha.watch/apk/latest"}


@app.get("/apk/latest")
async def apk_latest():
    path = os.path.join(STATIC_DIR, "cancha-latest.apk")
    if not os.path.exists(path):
        raise HTTPException(404, "no apk")
    with open(path, "rb") as f:
        data = f.read()
    mtime = int(os.path.getmtime(path))
    return Response(content=data, media_type="application/vnd.android.package-archive",
                    headers={
                        "Content-Disposition": 'attachment; filename="cancha-latest.apk"',
                        # Short TTL so version bumps propagate fast through Vercel edge
                        "Cache-Control": "public, max-age=30, must-revalidate",
                        "ETag": f'"apk-{mtime}"',
                    })


@app.get("/brand/{name}")
async def brand_asset(name: str):
    if "/" in name or ".." in name:
        raise HTTPException(400, "bad name")
    path = os.path.join(STATIC_DIR, name)
    if not os.path.exists(path):
        raise HTTPException(404, "no asset")
    with open(path, "rb") as f:
        data = f.read()
    mime = "image/png" if name.endswith(".png") else "application/octet-stream"
    return Response(content=data, media_type=mime,
                    headers={"Cache-Control": "public, max-age=86400"})


# 1x1 transparent PNG — served when a channel has no local logo (clean console)
_BLANK_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63"
    "fcffff3f0305000003020150e6e8120000000049454e44ae426082"
)


@app.get("/logo/{channel_id}")
async def channel_logo(channel_id: str):
    """Serve channel logo from the local catalog/logos/ directory.
    Falls back to a 1x1 transparent PNG so the client never sees a 404 noise."""
    if "/" in channel_id or ".." in channel_id:
        raise HTTPException(400, "bad id")
    for ext, mime in [(".png", "image/png"), (".svg", "image/svg+xml"),
                      (".jpg", "image/jpeg"), (".webp", "image/webp"),
                      (".gif", "image/gif")]:
        path = os.path.join(LOGO_DIR, channel_id + ext)
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = f.read()
            return Response(content=data, media_type=mime,
                            headers={"Cache-Control": "public, max-age=86400"})
    # Transparent fallback (so the <img> onload still fires and console stays clean)
    return Response(content=_BLANK_PNG, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=600"})


FLAG_DIR = os.path.join(os.path.dirname(__file__), "assets", "flags")


WEBFONT_DIR = os.path.join(os.path.dirname(__file__), "webfont")


@app.get("/webfont/{name}")
async def webfont(name: str):
    """Self-hosted woff2 fonts — no external Google Fonts round-trip → no FOUC."""
    if "/" in name or ".." in name or not name.endswith(".woff2"):
        raise HTTPException(400, "bad name")
    path = os.path.join(WEBFONT_DIR, name)
    if not os.path.exists(path):
        raise HTTPException(404, "no font")
    with open(path, "rb") as f:
        data = f.read()
    return Response(content=data, media_type="font/woff2",
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/flag/{code}.svg")
async def country_flag(code: str):
    """Rounded country/region flag SVGs (locale icons). Reliable on TV unlike emoji flags."""
    code = code.lower()
    if "/" in code or ".." in code:
        raise HTTPException(400, "bad code")
    path = os.path.join(FLAG_DIR, code + ".svg")
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
        return Response(content=data, media_type="image/svg+xml",
                        headers={"Cache-Control": "public, max-age=604800"})
    raise HTTPException(404, "no flag")


@app.get("/favicon.ico")
async def favicon():
    return Response(content=_BLANK_PNG, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/thumb/{channel_id}.jpg")
async def channel_thumb(channel_id: str):
    """Serve the latest live thumbnail (captured by thumb_loop every 10 min). 404 until captured."""
    if "/" in channel_id or ".." in channel_id:
        raise HTTPException(400, "bad id")
    path = os.path.join(THUMB_DIR, f"{channel_id}.jpg")
    if not os.path.exists(path):
        # 1x1 transparent PNG fallback (so <img> onload still fires; CSS bg gracefully hidden)
        return Response(content=_BLANK_PNG, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=30",
                                  "X-Thumb-Status": "pending"})
    with open(path, "rb") as f:
        data = f.read()
    mtime = int(os.path.getmtime(path))
    return Response(content=data, media_type="image/jpeg",
                    headers={
                        "Cache-Control": "public, max-age=300, stale-while-revalidate=600",
                        "X-Thumb-Captured-At": str(mtime),
                    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host=LISTEN_HOST, port=LISTEN_PORT, log_level="info")


@app.get("/vendor/hls-1.7.4.min.js")
async def hls_vendor():
    path = os.path.join(os.path.dirname(__file__), "vendor", "hls.min.js")
    with open(path, "rb") as handle:
        return Response(handle.read(), media_type="application/javascript", headers={"Cache-Control":"public, max-age=31536000, immutable"})
