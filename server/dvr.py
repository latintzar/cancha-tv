"""Cancha DVR — per-channel rolling ring buffer.

Why: solves four problems at once —
  1. Instant tune-in: when a channel is already recording, the first segments are
     already on local disk → the player gets data with zero upstream round-trip.
  2. Stall-smoothing: transient upstream hiccups don't reach the viewer because we
     serve from the buffer, which is always a bit behind live.
  3. 15-min rewind: the buffer IS the seekable window.
  4. Pre-delay cushion: we serve from ~LIVE-edge minus a margin.

Design ("smart dumping"):
  - A recorder task starts the first time a channel is requested.
  - It pulls the best mirror's top variant playlist on a tick, downloads new
    segments to /opt/cancha/dvr/<channel>/, keeps the last DVR_WINDOW_S seconds,
    deletes older ones.
  - It stops (and wipes its dir) after DVR_IDLE_STOP_S with no access — so we only
    ever record what someone is actually (or about to be) watching.
  - Additive: the live master.m3u8 path is untouched and remains the fallback.
"""
from __future__ import annotations
import asyncio
import os
import re
import time
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional, Any
from urllib.parse import urljoin

import aiohttp

from .models import Catalog, Channel, Mirror
from .proxy import webshare_proxy_url, webshare_proxy_auth

DVR_DIR = os.environ.get("CANCHA_DVR_DIR", os.path.join(os.environ.get("CANCHA_STATE_DIR", ".state"), "dvr"))
DVR_WINDOW_S = int(os.environ.get("CANCHA_DVR_WINDOW_S", "360"))      # 6 min ring (instant-zap + oops-rewind; full 15 was overkill for personal use)
DVR_IDLE_STOP_S = int(os.environ.get("CANCHA_DVR_IDLE_STOP_S", "150"))  # stop after 2.5 min idle
UA = "Mozilla/5.0 (Linux; Android TV) AppleWebKit/537.36 Chrome/120 Safari/537.36"
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=20, connect=10)


@dataclass
class Seg:
    seq: int            # monotonic local sequence
    filename: str       # on-disk name
    duration: float
    fetched_at: float


@dataclass
class DvrChannel:
    channel_id: str
    dir: str
    segs: list[Seg] = field(default_factory=list)
    seen_uris: set = field(default_factory=set)
    next_seq: int = 0
    last_access: float = 0.0
    started_at: float = 0.0
    task: Optional[asyncio.Task] = None
    media_seq_base: int = 0    # EXT-X-MEDIA-SEQUENCE of oldest seg
    ready: bool = False
    transcode_audio: Optional[bool] = None  # None=undetected; True if MP2 audio → remux to AAC for web
    ff_mode: bool = False                    # True = continuous ffmpeg→HLS transcode (MP2 channels)
    ff_proc: Any = None                      # the long-lived ffmpeg subprocess
    want_play: bool = False                  # True once actually tuned (vs just pre-warmed)

    def total_duration(self) -> float:
        return sum(s.duration for s in self.segs)


def _parse_master(text: str):
    variants = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXT-X-STREAM-INF:"):
            attrs = line[len("#EXT-X-STREAM-INF:"):]
            bw = re.search(r"BANDWIDTH=(\d+)", attrs)
            uri = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if uri and not uri.startswith("#"):
                variants.append({"bandwidth": int(bw.group(1)) if bw else 0, "uri": uri})
            i += 2
        else:
            i += 1
    return sorted(variants, key=lambda v: -v["bandwidth"])


def _parse_media(text: str):
    target = 6.0
    segs = []
    lines = text.split("\n")
    i = 0
    cur_dur = None
    for line in lines:
        s = line.strip()
        if s.startswith("#EXT-X-TARGETDURATION:"):
            try:
                target = float(s.split(":", 1)[1])
            except Exception:
                pass
        elif s.startswith("#EXTINF:"):
            m = re.search(r"#EXTINF:([\d.]+)", s)
            cur_dur = float(m.group(1)) if m else target
        elif s and not s.startswith("#"):
            segs.append((s, cur_dur if cur_dur is not None else target))
            cur_dur = None
    return target, segs


MAX_TRANSCODE = int(os.environ.get("CANCHA_MAX_TRANSCODE", "3"))  # concurrent ffmpeg encodes cap

# Channels known to use a codec browsers (MSE) can't decode — these MUST be transcoded
# every time they record (warm or play); their raw segments are unplayable on the web, so
# we never serve direct mode for them. Probing also catches new ones, but seeding the known
# set removes the first-tune probe race (and a wrong raw-master fallback) entirely.
FORCE_TRANSCODE = {"caracol-tv", "tv-peru"}

# When transcoding, default is a full video re-encode with forced keyframes (fixes
# irregular-GOP OTA feeds like Caracol that otherwise segment 0.6s–9.8s and break HLS.js).
# Channels listed here instead KEEP their h264 video untouched and only fix the audio —
# for feeds whose video is fine but won't survive a re-decode (tv-peru connects mid-GOP
# with no in-band PPS → "non-existing PPS" decode errors). dump_extra re-injects SPS/PPS
# into each segment so the copied video still starts cleanly.
COPY_VIDEO_TRANSCODE = {"tv-peru"}


class DvrManager:
    def __init__(self, catalog: Catalog, session_factory):
        self.catalog = catalog
        self.session_factory = session_factory  # () -> aiohttp.ClientSession
        self.channels: dict[str, DvrChannel] = {}
        self._janitor_task: Optional[asyncio.Task] = None
        self.active_ff = 0  # number of running transcodes (CPU cap)
        self.tx_cache: dict[str, bool] = {}  # channel_id -> needs-transcode (probed once)

    async def close(self):
        """Stop recorders and their subprocesses before closing the app's sessions."""
        tasks = [self._janitor_task] + [entry.task for entry in self.channels.values()]
        for channel_id in list(self.channels):
            self._stop(channel_id)
        for task in tasks:
            if task: task.cancel()
        await asyncio.gather(*(task for task in tasks if task), return_exceptions=True)

    def needs_transcode_cached(self, cid: str) -> bool:
        """Sync, race-free: True if this channel must be transcoded for web playback.
        Known set is authoritative; probe results are remembered after the first record."""
        return cid in FORCE_TRANSCODE or self.tx_cache.get(cid, False)

    def start(self):
        os.makedirs(DVR_DIR, exist_ok=True)
        self._janitor_task = asyncio.create_task(self._janitor())

    async def _janitor(self):
        while True:
            await asyncio.sleep(30)
            now = time.time()
            for cid, dvr in list(self.channels.items()):
                if now - dvr.last_access > DVR_IDLE_STOP_S:
                    self._stop(cid)

    def _stop(self, cid: str):
        dvr = self.channels.pop(cid, None)
        if not dvr:
            return
        if dvr.task:
            dvr.task.cancel()
        if dvr.ff_proc:
            try:
                dvr.ff_proc.kill()
            except Exception:
                pass
        try:
            shutil.rmtree(dvr.dir, ignore_errors=True)
        except Exception:
            pass

    def touch(self, cid: str, play: bool = False):
        """Mark a channel as wanted. play=True means actually tuned (may start a transcode);
        play=False is a pre-warm (never burns an encode slot)."""
        ch = self.catalog.by_id(cid)
        if not ch:
            return None
        dvr = self.channels.get(cid)
        if dvr is None:
            d = os.path.join(DVR_DIR, cid)
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d, exist_ok=True)
            dvr = DvrChannel(channel_id=cid, dir=d, last_access=time.time(),
                             started_at=time.time(), want_play=play)
            self.channels[cid] = dvr
            dvr.task = asyncio.create_task(self._record(ch, dvr))
        elif play:
            # Incompatible-codec channels already transcode from creation (warm or play),
            # so there's nothing to upgrade — just note that it's now actively tuned.
            dvr.want_play = True
        dvr.last_access = time.time()
        return dvr

    async def _record(self, ch: Channel, dvr: DvrChannel):
        try:
            # Channels with browser-incompatible codecs (MP2/AC3 audio, HEVC video) get a
            # continuous ffmpeg→HLS transcode to h264/AAC. Only when actually tuned (not pre-warm),
            # and capped so encodes can't saturate the box. The flag is set either way so a later
            # play can upgrade a pre-warmed download-loop recorder.
            dvr.transcode_audio = await self._needs_transcode(ch)
            if dvr.transcode_audio:
                # Browser-incompatible codec → MUST transcode, warm OR play. Direct segments
                # are unplayable in MSE, so we never serve them: wait for an encode slot
                # rather than ever falling back to a raw playlist.
                while self.active_ff >= MAX_TRANSCODE:
                    await asyncio.sleep(1.0)
                self.active_ff += 1
                try:
                    await self._record_ffmpeg(ch, dvr)
                finally:
                    self.active_ff -= 1
                return
            async with self.session_factory() as session:
                media_url = None
                target = 6.0
                last_new = time.time()   # when the buffer last grew (for the stale-source watchdog)
                while True:
                    best = ch.any_mirror(time.time())
                    if not best:
                        await asyncio.sleep(2)
                        continue
                    # AUTO-REPAIR: if the buffer hasn't grown in a while the source has stalled
                    # (returns 200 but no fresh segments, or its token expired). Deprioritize this
                    # mirror and re-resolve so any_mirror rotates to a different one. We recover
                    # inside the DVR cushion, so the viewer never sees the gap.
                    stale_s = min(15.0, max(10.0, target * 2.0))
                    if time.time() - last_new > stale_s:
                        best.sick_until = time.time() + 45
                        media_url = None
                        last_new = time.time()
                        continue
                    proxy = webshare_proxy_url(best.proxy_country)
                    proxy_auth = webshare_proxy_auth(best.proxy_country)
                    try:
                        # Resolve media playlist URL (once, or re-resolve if it goes stale)
                        if media_url is None:
                            text, final = await self._get(session, best.url, proxy, proxy_auth)
                            variants = _parse_master(text)
                            media_url = urljoin(final, variants[0]["uri"]) if variants else final
                        mtext, mfinal = await self._get(session, media_url, proxy, proxy_auth)
                        target, seglist = _parse_media(mtext)
                        for uri, dur in seglist:
                            absu = urljoin(mfinal, uri)
                            if absu in dvr.seen_uris:
                                continue
                            dvr.seen_uris.add(absu)
                            # cap memory of seen set
                            if len(dvr.seen_uris) > 4000:
                                dvr.seen_uris = set(list(dvr.seen_uris)[-2000:])
                            data = await self._get_bytes(session, absu, proxy, proxy_auth)
                            # skip truncated/garbage segments (a real ~1s+ TS segment is never
                            # under ~1KB) so a flaky upstream can never wedge the player
                            if not data or len(data) < 1200:
                                continue
                            last_new = time.time()   # a real fresh segment landed
                            # NOTE: MP2-audio channels (some LATAM OTA, e.g. Caracol) don't play
                            # in browsers (MSE has no MP2). Per-segment transcode to AAC breaks
                            # HLS.js cross-segment splicing, so it's disabled here — these channels
                            # play fine on the native TV app (ExoPlayer handles MP2). A continuous
                            # per-channel ffmpeg→HLS transcode is the proper web fix (separate work).
                            fn = f"s{dvr.next_seq:08d}.ts"
                            with open(os.path.join(dvr.dir, fn), "wb") as f:
                                f.write(data)
                            dvr.segs.append(Seg(dvr.next_seq, fn, dur, time.time()))
                            dvr.next_seq += 1
                            dvr.ready = True
                        self._prune(dvr)
                    except Exception:
                        # transient — re-resolve media playlist next loop
                        media_url = None
                        await asyncio.sleep(2)
                        continue
                    await asyncio.sleep(max(2.0, target * 0.5))
        except asyncio.CancelledError:
            pass

    def _prune(self, dvr: DvrChannel):
        while dvr.total_duration() > DVR_WINDOW_S and len(dvr.segs) > 3:
            old = dvr.segs.pop(0)
            dvr.media_seq_base += 1
            try:
                os.unlink(os.path.join(dvr.dir, old.filename))
            except OSError:
                pass

    async def _get(self, session, url, proxy, proxy_auth):
        kw = {"headers": {"User-Agent": UA}}
        if proxy:
            kw["proxy"] = proxy
            if proxy_auth:
                kw["proxy_auth"] = proxy_auth
        async with session.get(url, **kw) as r:
            r.raise_for_status()
            data = await r.content.read(400_000)
            return data.decode("utf-8", "ignore"), str(r.url)

    @staticmethod
    def _audio_codec_sync(data: bytes) -> str:
        try:
            p = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=codec_name", "-of", "csv=p=0", "pipe:0"],
                input=data, capture_output=True, timeout=10,
            )
            return p.stdout.decode("utf-8", "ignore")
        except Exception:
            return ""

    @staticmethod
    def _to_aac_sync(data: bytes) -> Optional[bytes]:
        try:
            p = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error",
                 "-copyts", "-i", "pipe:0",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                 "-f", "mpegts", "pipe:1"],
                input=data, capture_output=True, timeout=20,
            )
            return p.stdout if p.returncode == 0 and len(p.stdout) > 1200 else None
        except Exception:
            return None

    # Run ffmpeg/ffprobe in a thread pool — async subprocess is unreliable under uvloop.
    async def _audio_codec(self, data: bytes) -> str:
        return await asyncio.get_event_loop().run_in_executor(None, self._audio_codec_sync, data)

    async def _to_aac(self, data: bytes) -> Optional[bytes]:
        return await asyncio.get_event_loop().run_in_executor(None, self._to_aac_sync, data)

    async def _get_bytes(self, session, url, proxy, proxy_auth):
        kw = {"headers": {"User-Agent": UA}}
        if proxy:
            kw["proxy"] = proxy
            if proxy_auth:
                kw["proxy_auth"] = proxy_auth
        try:
            async with session.get(url, **kw) as r:
                r.raise_for_status()
                # read the FULL body — content.read(n) returns only the first chunk for large
                # segments, which truncated big segments (e.g. Caracol's 2.9MB) to a few KB and
                # made playback impossible. Read to EOF in a loop, capped at 16MB.
                chunks = []
                total = 0
                async for chunk in r.content.iter_chunked(65536):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > 16_000_000:
                        break
                return b"".join(chunks)
        except Exception:
            return None

    # ---- continuous transcode (browser-incompatible codec channels) ----

    # browsers (MSE) can't decode these — channel must be transcoded for web
    BAD_AUDIO = {"mp2", "mp1", "ac3", "eac3", "dts", "truehd", "aac_latm"}
    OK_VIDEO = {"h264", "avc1"}

    @staticmethod
    def _codecs_sync(data: bytes):
        try:
            p = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name",
                 "-of", "csv=p=0", "pipe:0"],
                input=data, capture_output=True, timeout=10,
            )
            v = a = None
            for line in p.stdout.decode("utf-8", "ignore").splitlines():
                pp = line.split(",")
                if len(pp) >= 2:
                    if pp[0] == "video" and not v:
                        v = pp[1]
                    if pp[0] == "audio" and not a:
                        a = pp[1]
            return v, a
        except Exception:
            return None, None

    async def _codecs(self, data: bytes):
        return await asyncio.get_event_loop().run_in_executor(None, self._codecs_sync, data)

    async def _needs_transcode(self, ch: Channel) -> bool:
        """Fetch one segment and decide if the channel needs transcoding for web playback
        (MP2/AC3/aac_latm audio, or non-h264 video like HEVC). Cached after the first probe."""
        if ch.id in FORCE_TRANSCODE:
            self.tx_cache[ch.id] = True
            return True
        if ch.id in self.tx_cache:
            return self.tx_cache[ch.id]
        try:
            async with self.session_factory() as session:
                best = ch.any_mirror(time.time())
                if not best:
                    return False
                proxy = webshare_proxy_url(best.proxy_country)
                proxy_auth = webshare_proxy_auth(best.proxy_country)
                text, final = await self._get(session, best.url, proxy, proxy_auth)
                variants = _parse_master(text)
                media_url = urljoin(final, variants[0]["uri"]) if variants else final
                mtext, mfinal = await self._get(session, media_url, proxy, proxy_auth)
                _, seglist = _parse_media(mtext)
                if not seglist:
                    return False
                seg = urljoin(mfinal, seglist[-1][0])
                data = await self._get_bytes(session, seg, proxy, proxy_auth)
                if not data:
                    return False
                v, a = await self._codecs(data)
                need = (a in self.BAD_AUDIO) or (v is not None and v not in self.OK_VIDEO)
                self.tx_cache[ch.id] = need
                return need
        except Exception:
            return False

    @staticmethod
    def _ffmpeg_proxy_url(cc: Optional[str]) -> Optional[str]:
        """Webshare residential proxy URL (with embedded auth) for ffmpeg's http_proxy env."""
        if not cc or os.environ.get("CANCHA_ENABLE_PROXY") != "1":
            return None
        user = os.environ.get("WEBSHARE_PROXY_USER", "")
        pw = os.environ.get("WEBSHARE_PROXY_PASS", "")
        host = os.environ.get("WEBSHARE_PROXY_HOST", "p.webshare.io")
        port = os.environ.get("WEBSHARE_PROXY_PORT", "80")
        if not user or not pw:
            return None
        return f"http://{user}-CC-{cc.upper()}:{pw}@{host}:{port}"

    async def _record_ffmpeg(self, ch: Channel, dvr: DvrChannel):
        """Run a long-lived ffmpeg that ingests the live stream and writes continuous AAC HLS.
        ffmpeg owns segmentation + timestamps, so segments splice cleanly in HLS.js."""
        dvr.ff_mode = True
        seg_pat = os.path.join(dvr.dir, "t%08d.ts")
        pl_path = os.path.join(dvr.dir, "ff.m3u8")
        loop = asyncio.get_event_loop()
        try:
            while True:
                best = ch.any_mirror(time.time())
                if not best:
                    await asyncio.sleep(3)
                    continue
                # Guarantee the output dir exists right before launch — a janitor sweep can
                # rmtree it between touch() and here, and ffmpeg then dies "No such file or
                # directory" on every relaunch, silently producing zero segments.
                os.makedirs(dvr.dir, exist_ok=True)
                env = os.environ.copy()
                purl = self._ffmpeg_proxy_url(best.proxy_country)
                if purl:
                    env["http_proxy"] = purl
                    env["https_proxy"] = purl
                iargs: list[str] = []   # input-level flags (before -i)
                oargs: list[str] = []   # extra muxer flags (before -f)
                if ch.id in COPY_VIDEO_TRANSCODE:
                    # video is fine but won't survive a re-decode → copy it, only fix audio.
                    # These feeds also emit non-monotonic audio DTS (e.g. 4096 >= 4096) that
                    # intermittently stalls the HLS muxer → zero segments. Regenerate
                    # timestamps (genpts+igndts) and relax interleaving so it writes reliably.
                    vargs = ["-c:v", "copy", "-bsf:v", "dump_extra"]
                    iargs = ["-fflags", "+genpts+igndts"]
                    oargs = ["-max_interleave_delta", "0", "-avoid_negative_ts", "make_zero"]
                else:
                    # full re-encode with FORCED regular keyframes → clean 4s segments.
                    # (copy-splitting an irregular-GOP source gives 0.6s–9.8s segments that
                    # HLS.js refuses to buffer.) ultrafast keeps CPU sane for personal use.
                    # Cap at 720p: a full-HD realtime x264 encode pegs a whole core and the
                    # 2-core box falls behind (load > cores → stalls). 720p halves the pixel
                    # work, stays crisp on a TV, and a bitrate cap keeps bandwidth sane.
                    vargs = ["-c:v", "libx264", "-preset", "ultrafast", "-profile:v", "main",
                             "-vf", "scale=-2:min(720\\,ih)",
                             "-maxrate", "3M", "-bufsize", "5M",
                             "-pix_fmt", "yuv420p", "-g", "96", "-keyint_min", "96",
                             "-sc_threshold", "0", "-force_key_frames", "expr:gte(t,n_forced*4)"]
                cmd = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    *iargs,
                    "-user_agent", UA, "-i", best.url,
                    "-map", "0:v:0", "-map", "0:a:0?",
                    *vargs,
                    # keep audio glued to video: resample to absorb any PTS drift in the source
                    # (re-encoding a ragged live feed can otherwise let audio slip out of sync)
                    "-af", "aresample=async=1:min_hard_comp=0.100:first_pts=0",
                    "-c:a", "aac", "-b:a", "128k",
                    *oargs,
                    "-f", "hls", "-hls_time", "4",
                    "-hls_list_size", str(max(6, DVR_WINDOW_S // 4)),
                    "-hls_flags", "delete_segments+omit_endlist+independent_segments",
                    "-hls_segment_type", "mpegts",
                    "-hls_segment_filename", seg_pat, pl_path,
                ]
                proc = await loop.run_in_executor(
                    None,
                    lambda: subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL),
                )
                dvr.ff_proc = proc
                # poll until ffmpeg exits (stream dropped); mark ready once the playlist appears.
                # WATCHDOG: ffmpeg can hang (alive but producing nothing) if its input stalls. If no
                # new segment lands for a while, kill it so the outer loop relaunches on a fresh
                # mirror — auto-repair within the DVR cushion so the viewer never chokes.
                last_seg_mtime = 0.0
                last_progress = time.time()
                while proc.poll() is None:
                    await asyncio.sleep(1.5)
                    try:
                        ts = [f for f in os.listdir(dvr.dir) if f.endswith(".ts")]
                        newest = max((os.path.getmtime(os.path.join(dvr.dir, f)) for f in ts), default=0.0)
                    except Exception:
                        newest = last_seg_mtime
                    if newest > last_seg_mtime:
                        last_seg_mtime = newest
                        last_progress = time.time()
                        if not dvr.ready and os.path.exists(pl_path):
                            try:
                                if "t" in open(pl_path).read():
                                    dvr.ready = True
                            except Exception:
                                pass
                    elif time.time() - last_progress > 12:
                        # stalled — deprioritize this mirror and relaunch (the next iteration's
                        # any_mirror picks a fresh one).
                        if best:
                            best.sick_until = time.time() + 45
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        break
                dvr.ff_proc = None
                await asyncio.sleep(1)  # upstream dropped / stalled → relaunch
        except asyncio.CancelledError:
            if dvr.ff_proc:
                try:
                    dvr.ff_proc.kill()
                except Exception:
                    pass
            raise

    def _rewrite_ff(self, cid: str, text: str) -> str:
        """Point ffmpeg's segment lines at our /dvrseg/ endpoint."""
        out = []
        for line in text.split("\n"):
            s = line.strip()
            if s.startswith("#EXT-X-ENDLIST"):
                continue
            if s and not s.startswith("#"):
                out.append(f"/v1/{cid}/dvrseg/{s}")
            else:
                out.append(line)
        return "\n".join(out)

    def playlist(self, cid: str) -> Optional[str]:
        """Build a sliding-window media playlist over the ring buffer (live, seekable)."""
        dvr = self.channels.get(cid)
        if not dvr:
            return None
        # transcode channels: serve ffmpeg's own HLS playlist (rewritten to our /dvrseg/ endpoint)
        if dvr.ff_mode:
            p = os.path.join(dvr.dir, "ff.m3u8")
            if not os.path.exists(p):
                return None
            try:
                txt = open(p).read()
            except Exception:
                return None
            return self._rewrite_ff(cid, txt) if "t" in txt else None
        if not dvr.segs:
            return None
        target = max(int(round(max((s.duration for s in dvr.segs), default=6))), 1)
        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            f"#EXT-X-TARGETDURATION:{target}",
            f"#EXT-X-MEDIA-SEQUENCE:{dvr.media_seq_base}",
        ]
        for s in dvr.segs:
            lines.append(f"#EXTINF:{s.duration:.3f},")
            lines.append(f"/v1/{cid}/dvrseg/{s.filename}")
        # No EXT-X-ENDLIST → player treats as live with a long seekable back-buffer.
        return "\n".join(lines) + "\n"

    def seg_path(self, cid: str, filename: str) -> Optional[str]:
        if "/" in filename or ".." in filename:
            return None
        dvr = self.channels.get(cid)
        if not dvr:
            return None
        dvr.last_access = time.time()
        p = os.path.join(dvr.dir, filename)
        return p if os.path.exists(p) else None

    def status(self, cid: str) -> dict:
        dvr = self.channels.get(cid)
        if not dvr:
            return {"recording": False}
        return {
            "recording": True,
            "ready": dvr.ready,
            "mode": "transcode" if dvr.ff_mode else "direct",
            "buffer_s": round(dvr.total_duration(), 1),
            "segs": len(dvr.segs),
            "idle_s": round(time.time() - dvr.last_access, 1),
        }
