"""Background quality prober: ffprobe-on-real-segments.

Every PROBE_INTERVAL seconds, walks each Mirror, downloads a few live-edge segments,
ffprobes them for real fps + codec + bitrate, scores the mirror.

Score formula (higher = better):
  base = real_fps * 100
  + (real_bandwidth_kbps / 1000) * 50
  - (seg_fetch_jitter_ms / 100)
  - (consecutive_failures * 500)
  field_penalty: interlaced (-50)
  resolution_bonus: 1080+ (+200), 720+ (+100)
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import subprocess
import tempfile
import time
from typing import Optional
from urllib.parse import urljoin

import aiohttp

from .models import Catalog, Channel, Mirror
from .proxy import webshare_proxy_url, webshare_proxy_auth

PROBE_INTERVAL = int(os.environ.get("CANCHA_PROBE_INTERVAL", "60"))
PROBE_CONCURRENCY = int(os.environ.get("CANCHA_PROBE_CONCURRENCY", "8"))
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=45, connect=15)  # residential proxy = slow handshake
UA = "Mozilla/5.0 (Linux; Android TV) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def _parse_master(text: str):
    """Return list of variants sorted by bandwidth desc."""
    variants = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXT-X-STREAM-INF:"):
            attrs = line[len("#EXT-X-STREAM-INF:"):]
            bw_m = re.search(r"BANDWIDTH=(\d+)", attrs)
            res_m = re.search(r"RESOLUTION=(\d+x\d+)", attrs)
            fr_m = re.search(r"FRAME-RATE=([\d.]+)", attrs)
            uri = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if uri and not uri.startswith("#"):
                variants.append({
                    "bandwidth": int(bw_m.group(1)) if bw_m else 0,
                    "resolution": res_m.group(1) if res_m else "",
                    "manifest_fps": float(fr_m.group(1)) if fr_m else None,
                    "uri": uri,
                })
            i += 2
        else:
            i += 1
    return sorted(variants, key=lambda v: -v["bandwidth"])


def _parse_media(text: str):
    target = None
    segments = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXT-X-TARGETDURATION:"):
            try:
                target = float(line.split(":", 1)[1])
            except Exception:
                pass
        elif line.startswith("#EXTINF:"):
            uri = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if uri and not uri.startswith("#"):
                segments.append(uri)
        i += 1
    return target, segments


def _parse_fps(rate_str: str) -> float:
    if not rate_str or "/" not in rate_str:
        return 0.0
    try:
        n, d = rate_str.split("/")
        n, d = float(n), float(d)
        return n / d if d > 0 else 0.0
    except Exception:
        return 0.0


def _score(m: Mirror, target_dur: Optional[float], avg_fetch_ms: float) -> float:
    # Baseline: the playlist parsed AND a real segment downloaded → the stream is PLAYABLE.
    # Health is "can we play it", not "did ffprobe give us perfect metadata". The fps/res/
    # bitrate numbers (often unknowable from one mid-GOP TS segment) are only quality tie-breakers.
    s = 100.0
    s += m.real_fps * 2.0
    s += (m.real_bitrate / 1000.0) * 0.02
    s -= m.seg_fetch_jitter_ms / 100.0
    s -= m.consecutive_failures * 1000.0
    if m.real_height >= 1080:
        s += 60
    elif m.real_height >= 720:
        s += 30
    if m.field_order and m.field_order != "progressive":
        s -= 10
    # fetch-pace penalty: if a segment fetch takes longer than its own playback duration, dock
    if target_dur and avg_fetch_ms > target_dur * 1000:
        s -= (avg_fetch_ms - target_dur * 1000) / 50.0
    # A successfully-probed mirror (no failures) is ALWAYS healthy, even with slow/jittery fetch.
    return max(s, 1.0) if m.consecutive_failures == 0 else s


async def _fetch_text(session: aiohttp.ClientSession, url: str,
                       proxy: str | None = None, proxy_auth=None) -> tuple[str, int]:
    t0 = time.monotonic()
    kw = {"headers": {"User-Agent": UA}}
    if proxy:
        kw["proxy"] = proxy
        if proxy_auth:
            kw["proxy_auth"] = proxy_auth
    async with session.get(url, **kw) as r:
        r.raise_for_status()
        data = await r.content.read(200_000)
    return data.decode("utf-8", "ignore"), int((time.monotonic() - t0) * 1000)


async def _fetch_bytes(session: aiohttp.ClientSession, url: str,
                        max_bytes: int = 6_000_000,
                        proxy: str | None = None, proxy_auth=None) -> tuple[bytes, int]:
    t0 = time.monotonic()
    kw = {"headers": {"User-Agent": UA}}
    if proxy:
        kw["proxy"] = proxy
        if proxy_auth:
            kw["proxy_auth"] = proxy_auth
    async with session.get(url, **kw) as r:
        r.raise_for_status()
        data = await r.content.read(max_bytes)
    return data, int((time.monotonic() - t0) * 1000)


def _ffprobe_sync(path: str) -> dict:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_streams", "-show_format", path],
            capture_output=True, text=True, timeout=12,
        )
        return json.loads(r.stdout or "{}")
    except Exception as e:
        return {"error": str(e)[:200]}


async def probe_mirror(mirror: Mirror, session: aiohttp.ClientSession) -> None:
    """Mutates mirror in place with current health state."""
    now = time.time()
    proxy = webshare_proxy_url(mirror.proxy_country)
    proxy_auth = webshare_proxy_auth(mirror.proxy_country)
    try:
        text, _ttfb = await _fetch_text(session, mirror.url, proxy=proxy, proxy_auth=proxy_auth)
        variants = _parse_master(text)
        if variants:
            media_url = urljoin(mirror.url, variants[0]["uri"])
        else:
            media_url = mirror.url

        media_text, _ = await _fetch_text(session, media_url, proxy=proxy, proxy_auth=proxy_auth)
        target_dur, segs = _parse_media(media_text)
        if not segs:
            raise RuntimeError("no segments in media playlist")

        seg_urls = [urljoin(media_url, s) for s in segs[-3:]]
        fetch_ms_list = []
        sample_bytes: Optional[bytes] = None
        for su in seg_urls:
            data, ms = await _fetch_bytes(session, su, proxy=proxy, proxy_auth=proxy_auth)
            fetch_ms_list.append(ms)
            if sample_bytes is None:
                sample_bytes = data
        avg_fetch_ms = sum(fetch_ms_list) / len(fetch_ms_list)
        jitter_ms = max(fetch_ms_list) - min(fetch_ms_list)

        # Liveness = the playlist parsed and the segment fetches didn't error (a 404/dead source
        # raises in _fetch_bytes → caught below → sick). Only reject a truly empty body; don't
        # require a minimum size, because _fetch_bytes may return just the first chunk.
        if not sample_bytes:
            raise RuntimeError("empty segment body")

        # 4. ffprobe sample — BEST-EFFORT metadata only (resolution/fps/bitrate for the quality
        # badge). It must NOT gate health: plenty of playable streams have segments ffprobe can't
        # fully parse (mid-GOP TS, no in-band SPS/PPS, odd codecs — e.g. Caracol / TV Perú).
        pj = {}
        fd, tmp_path = tempfile.mkstemp(suffix=".ts", prefix="cancha-probe-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(sample_bytes or b"")
            pj = await asyncio.get_event_loop().run_in_executor(None, _ffprobe_sync, tmp_path)
        except Exception:
            pj = {}
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        video = next((s for s in pj.get("streams", []) if s.get("codec_type") == "video"), None)
        if video:
            # r_frame_rate can be the codec timebase (e.g. 90000/1) for HLS-TS streams; prefer avg
            r_fps = _parse_fps(video.get("r_frame_rate"))
            a_fps = _parse_fps(video.get("avg_frame_rate"))
            if r_fps > 120:
                real_fps = a_fps
            elif a_fps > 0 and a_fps < r_fps:
                real_fps = a_fps
            else:
                real_fps = r_fps or a_fps
            mirror.real_fps = round(real_fps, 2)
            mirror.real_codec = video.get("codec_name", "")
            mirror.real_width = int(video.get("width") or video.get("coded_width") or 0)
            mirror.real_height = int(video.get("height") or video.get("coded_height") or 0)
            mirror.field_order = (video.get("field_order") or "progressive")
            fmt = pj.get("format", {})
            br = fmt.get("bit_rate") or video.get("bit_rate")
            mirror.real_bitrate = int(br) if br else 0
            if mirror.real_bitrate > 80_000_000:  # bogus container-level rate from a partial read
                mirror.real_bitrate = 0
        # else: ffprobe couldn't parse the segment — fine, it still downloaded → playable.

        mirror.seg_fetch_jitter_ms = jitter_ms
        mirror.last_probe_at = now
        mirror.last_error = ""
        mirror.consecutive_failures = 0
        mirror.last_score = _score(mirror, target_dur, avg_fetch_ms)
        # If the mirror is sick but recovered well, clear sickness
        if mirror.sick_until > now and mirror.last_score > 0:
            mirror.sick_until = 0
    except Exception as e:
        mirror.last_error = str(e)[:200]
        mirror.last_probe_at = now
        mirror.consecutive_failures += 1
        # Grace: a SINGLE transient probe failure (proxy blip, slow fetch, momentary 5xx) must
        # not black out a channel that was just healthy — keep the last-known-good score and only
        # mark it down once it fails repeatedly. This kills the "channel turns off for ~30s then
        # comes back" flicker, which was the prober souring a working mirror for one cycle.
        if mirror.consecutive_failures >= 2:
            mirror.last_score = -1
        if mirror.consecutive_failures >= 4:
            mirror.sick_until = now + 180  # 3 min cooldown after sustained failure


async def probe_catalog(catalog: Catalog) -> None:
    """Probe every mirror of every channel, in parallel batches."""
    sem = asyncio.Semaphore(PROBE_CONCURRENCY)
    connector = aiohttp.TCPConnector(limit=PROBE_CONCURRENCY * 2)  # NOTE: ssl=False breaks Webshare proxy CONNECT — leave default
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT, connector=connector) as session:
        async def worker(m: Mirror):
            async with sem:
                await probe_mirror(m, session)

        tasks = [worker(m) for c in catalog.channels for m in c.mirrors]
        await asyncio.gather(*tasks, return_exceptions=True)


async def capture_thumb_via_self(channel: Channel, out_path: str) -> bool:
    """Let ffmpeg ingest our own HLS endpoint at 127.0.0.1:8765. It handles GOP + keyframes properly."""
    self_url = f"http://127.0.0.1:8765/v1/{channel.id}/master.m3u8"
    try:
        # ffmpeg with HLS native: walks the playlist, decodes from first keyframe forward
        r = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-headers", "User-Agent: Cancha/0.1 (thumb-grab)\r\n",
             "-i", self_url,
             "-ss", "1.5",  # skip ~1.5s into stream to ensure clean decode buffer
             "-vf", "scale='if(gt(a,16/9),640,-2)':'if(gt(a,16/9),-2,360)',crop=640:360",
             "-frames:v", "1",
             "-q:v", "5",
             "-an",
             out_path],
            capture_output=True, timeout=20,
        )
        return os.path.exists(out_path) and os.path.getsize(out_path) > 2000
    except Exception:
        return False


async def capture_thumb(channel: Channel, mirror: Mirror, out_path: str,
                          session: aiohttp.ClientSession) -> bool:
    """Fetch latest segment of mirror, extract a frame with ffmpeg → JPEG 640x360."""
    proxy = webshare_proxy_url(mirror.proxy_country)
    proxy_auth = webshare_proxy_auth(mirror.proxy_country)
    try:
        text, _ = await _fetch_text(session, mirror.url, proxy=proxy, proxy_auth=proxy_auth)
        variants = _parse_master(text)
        if variants:
            media_url = urljoin(mirror.url, variants[0]["uri"])
        else:
            media_url = mirror.url
        media_text, _ = await _fetch_text(session, media_url, proxy=proxy, proxy_auth=proxy_auth)
        _, segs = _parse_media(media_text)
        if not segs:
            return False
        # Fetch the last 3 segments so we get a full GOP with a keyframe
        seg_urls = [urljoin(media_url, s) for s in segs[-3:]]
        chunks = []
        for su in seg_urls:
            d, _ = await _fetch_bytes(session, su, max_bytes=6_000_000,
                                       proxy=proxy, proxy_auth=proxy_auth)
            chunks.append(d)
        # Concat in memory + write
        fd, tmp_ts = tempfile.mkstemp(suffix=".ts", prefix="cancha-thumb-")
        try:
            with os.fdopen(fd, "wb") as f:
                for c in chunks:
                    f.write(c)
            # Decode from the START so we hit the first IDR keyframe, then skip ~3s in
            # to land on real program content (skips channel logos / commercial bumpers at segment edges)
            # Fast approach: skip-input until first keyframe, then take next frame after some time
            r = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error",
                 "-fflags", "+genpts+discardcorrupt",
                 "-skip_frame", "nokey",
                 "-i", tmp_ts,
                 "-vsync", "vfr",
                 "-vf", "scale='if(gt(a,16/9),640,-2)':'if(gt(a,16/9),-2,360)',crop=640:360",
                 "-frames:v", "1",
                 "-q:v", "5",
                 out_path],
                capture_output=True, timeout=15,
            )
            # If keyframe-only approach failed (some streams have no clean keyframes in our window), retry permissive
            if not (os.path.exists(out_path) and os.path.getsize(out_path) > 1500):
                r = subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error",
                     "-fflags", "+genpts+discardcorrupt",
                     "-ss", "3", "-i", tmp_ts,
                     "-vf", "scale='if(gt(a,16/9),640,-2)':'if(gt(a,16/9),-2,360)',crop=640:360",
                     "-frames:v", "1",
                     "-q:v", "5",
                     out_path],
                    capture_output=True, timeout=12,
                )
        finally:
            try: os.unlink(tmp_ts)
            except OSError: pass
        return os.path.exists(out_path) and os.path.getsize(out_path) > 1500
    except Exception as e:
        # not fatal; we'll try again next cycle
        return False


THUMB_INTERVAL = int(os.environ.get("CANCHA_THUMB_INTERVAL", "600"))  # 10 min
THUMB_CONCURRENCY = int(os.environ.get("CANCHA_THUMB_CONCURRENCY", "3"))


async def thumb_loop(catalog: Catalog, thumb_dir: str) -> None:
    """Every THUMB_INTERVAL seconds, capture a fresh thumbnail for each healthy channel."""
    os.makedirs(thumb_dir, exist_ok=True)
    # Initial delay so first probe finishes
    await asyncio.sleep(20)
    sem = asyncio.Semaphore(THUMB_CONCURRENCY)
    connector = aiohttp.TCPConnector(limit=THUMB_CONCURRENCY * 2)
    while True:
        t0 = time.monotonic()
        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT, connector=connector) as session:
            async def worker(ch: Channel):
                async with sem:
                    best = ch.best_mirror(time.time())
                    if not best:
                        return
                    out = os.path.join(thumb_dir, f"{ch.id}.jpg")
                    # Primary: ffmpeg via our own HLS endpoint (clean GOP, handles ABR)
                    ok = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: subprocess.run(
                            ["ffmpeg", "-y", "-loglevel", "error",
                             "-i", f"http://127.0.0.1:8765/v1/{ch.id}/master.m3u8",
                             "-ss", "1.5",
                             "-vf", "scale='if(gt(a,16/9),640,-2)':'if(gt(a,16/9),-2,360)',crop=640:360",
                             "-frames:v", "1", "-q:v", "5", "-an", out],
                            capture_output=True, timeout=25,
                        ).returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 2000
                    )
                    if not ok:
                        # Fallback: segment-fetch approach
                        ok = await capture_thumb(ch, best, out, session)
                    if ok:
                        os.utime(out)
            tasks = [worker(c) for c in catalog.channels]
            await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = int(time.monotonic() - t0)
        have_thumbs = sum(1 for c in catalog.channels if os.path.exists(os.path.join(thumb_dir, f"{c.id}.jpg")))
        print(f"[thumbs] cycle done in {elapsed}s — {have_thumbs} thumbnails", flush=True)
        await asyncio.sleep(max(60, THUMB_INTERVAL - elapsed))


async def prober_loop(catalog: Catalog, snapshot_path: Optional[str] = None) -> None:
    """Run forever: probe + sleep + dump snapshot."""
    while True:
        t0 = time.monotonic()
        try:
            await probe_catalog(catalog)
        except Exception as e:
            print(f"[prober] catalog probe failed: {e}", flush=True)
        elapsed = int(time.monotonic() - t0)
        healthy = sum(1 for c in catalog.channels for m in c.mirrors if m.last_score > 0)
        total = sum(1 for c in catalog.channels for _ in c.mirrors)
        print(f"[prober] cycle done in {elapsed}s — {healthy}/{total} mirrors healthy", flush=True)
        if snapshot_path:
            try:
                snapshot = {
                    "at": time.time(),
                    "channels": [{
                        "id": c.id,
                        "name": c.name,
                        "country": c.country,
                        "priority": c.priority,
                        "mirrors": [{
                            "id": m.mirror_id(),
                            "url": m.url,
                            "score": round(m.last_score, 1),
                            "fps": m.real_fps,
                            "codec": m.real_codec,
                            "res": f"{m.real_width}x{m.real_height}" if m.real_width else "",
                            "bitrate_mbps": round(m.real_bitrate / 1_000_000, 2) if m.real_bitrate else 0,
                            "field": m.field_order,
                            "jitter_ms": m.seg_fetch_jitter_ms,
                            "fails": m.consecutive_failures,
                            "sick": m.sick_until > time.time(),
                            "error": m.last_error,
                        } for m in c.mirrors],
                    } for c in catalog.channels],
                }
                with open(snapshot_path, "w") as f:
                    json.dump(snapshot, f, indent=2)
            except Exception as e:
                print(f"[prober] snapshot write failed: {e}", flush=True)
        await asyncio.sleep(max(5, PROBE_INTERVAL - elapsed))
