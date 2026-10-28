"""On-demand YouTube "channels": each channel plays a rotating list of a real channel's
recent videos (via RSS — no API key) or a curated PL… playlist, embedded with the YouTube
IFrame Player API. Always-on: random video, clean start, auto-advance, loop, skip-on-error.

Why RSS over the uploads playlist (UU…): YouTube BLOCKS embedding uploads playlists, but
explicit video IDs (and PL… playlists) embed fine. RSS gives ~15 latest video IDs per channel.
"""
from __future__ import annotations
import asyncio
import json
import re
import aiohttp

# channel_id (our catalog id) -> [youtube videoId, ...]
YT_CACHE: dict[str, list[str]] = {}
_VID_RE = re.compile(r"<yt:videoId>([\w-]{11})</yt:videoId>")
_UA = "Mozilla/5.0 (Linux; Android TV) AppleWebKit/537.36 Chrome/120 Safari/537.36"


async def _fetch_rss(session: aiohttp.ClientSession, ucid: str) -> list[str]:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ucid}"
    try:
        async with session.get(url, headers={"User-Agent": _UA},
                               timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status != 200:
                return []
            text = await r.text()
            # dedupe-preserve-order, cap at 15 (RSS gives the latest uploads)
            seen, out = set(), []
            for vid in _VID_RE.findall(text):
                if vid not in seen:
                    seen.add(vid); out.append(vid)
            return out[:15]
    except Exception:
        return []


async def refresh_yt(catalog, session: aiohttp.ClientSession) -> None:
    for ch in catalog.channels:
        if getattr(ch, "kind", "") != "youtube":
            continue
        yt = (getattr(ch, "yt", "") or "")
        if yt.startswith("UC"):
            ids = await _fetch_rss(session, yt)
            if ids:
                YT_CACHE[ch.id] = ids
            await asyncio.sleep(0.25)  # be gentle on YouTube's RSS host


async def yt_loop(catalog, session_factory) -> None:
    """Periodic background refresh of every YouTube channel's recent-video list (~hourly)."""
    async with session_factory() as session:
        while True:
            try:
                await refresh_yt(catalog, session)
            except Exception:
                pass
            await asyncio.sleep(3600)


def is_live(ch) -> bool:
    """A YouTube channel is 'live' if we have something to play: a PL… playlist, or cached
    RSS video ids. An empty UC channel (RSS unreachable / channel dark) reads as down so a
    dead tile self-removes instead of opening into a black player."""
    yt = (getattr(ch, "yt", "") or "")
    if yt.startswith("PL"):
        return True
    return bool(YT_CACHE.get(ch.id))


# ---- the player page ---------------------------------------------------------
# IFrame Player API. Random starting video, CLEAN start (no mid-seek), sequential auto-advance,
# loop-wrap, skip-on-error. Web passes muted=1 (browser autoplay) + auto-unmute on first key;
# native TV passes muted=0 (sound on). No pause/seek controls (pure always-playing).
_PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 /* Match the app's type system (Inter) so the tune-in OSD reads as ONE product,
    not a generic YouTube embed — most visible on the TV where this OSD is the only
    channel identity shown. Served same-origin, so /webfont/ is reachable. */
 @font-face{font-family:'Inter';font-weight:400;font-display:swap;src:url('/webfont/inter-400.woff2') format('woff2')}
 @font-face{font-family:'Inter';font-weight:600;font-display:swap;src:url('/webfont/inter-600.woff2') format('woff2')}
 html,body{margin:0;height:100%;background:#0a0a0a;overflow:hidden}
 #p{position:fixed;inset:0;width:100%;height:100%}
 #osd{position:fixed;left:26px;top:26px;z-index:9;max-width:78%;
   background:rgba(10,10,10,.66);border-radius:10px;padding:11px 15px;
   color:#fff;font:600 18px/1.2 'Inter',system-ui,sans-serif;
   opacity:0;transition:opacity .35s;pointer-events:none}
 #osd.show{opacity:1}
 #osd .s{display:block;font-weight:400;font-size:12px;color:#808080;margin-top:4px}
</style></head><body>
<div id="p"></div><div id="osd"></div>
<script>
var IDS=__IDS__, PLID="__PLID__", NAME="__NAME__", MUTED=__MUTED__;
var player, osdT;
function esc(s){return (s||"").replace(/[<>&]/g,function(c){return{"<":"&lt;",">":"&gt;","&":"&amp;"}[c]})}
function osd(t){var o=document.getElementById("osd");
 o.innerHTML=esc(NAME)+(t?'<span class="s">'+esc(t)+'</span>':'');
 o.classList.add("show");clearTimeout(osdT);osdT=setTimeout(function(){o.classList.remove("show")},4500)}
function ri(n){return Math.floor(Math.random()*Math.max(1,n))}
window.onYouTubeIframeAPIReady=function(){
 player=new YT.Player("p",{width:"100%",height:"100%",
  playerVars:{autoplay:1,controls:0,rel:0,modestbranding:1,playsinline:1,fs:0,iv_load_policy:3,disablekb:1},
  events:{
   onReady:function(e){
    if(MUTED){e.target.mute()}
    if(PLID){e.target.loadPlaylist({list:PLID,listType:"playlist",index:ri(15)})}
    else if(IDS.length){e.target.loadPlaylist(IDS,ri(IDS.length),0)}
    try{e.target.setLoop(true)}catch(x){}
   },
   onStateChange:function(e){
    if(e.data===YT.PlayerState.PLAYING){var d=player.getVideoData?player.getVideoData():null;osd(d&&d.title)}
    else if(e.data===YT.PlayerState.ENDED){
     try{var pl=player.getPlaylist()||[],ix=player.getPlaylistIndex();
      if(ix>=pl.length-1){player.playVideoAt(0)}else{player.nextVideo()}}
     catch(x){if(IDS.length)player.loadPlaylist(IDS,0,0)}
    }
   },
   onError:function(e){try{player.nextVideo();player.playVideo()}catch(x){}}
  }})};
// web: muted autoplay, then unmute on first engagement (key/tap, or parent postMessage)
function unmuteOnce(){try{if(player&&player.unMute){player.unMute();player.setVolume(100)}}catch(e){}
 removeEventListener("keydown",unmuteOnce);removeEventListener("click",unmuteOnce);removeEventListener("message",onMsg)}
function onMsg(ev){if(ev&&ev.data==="cancha-unmute")unmuteOnce()}
addEventListener("keydown",unmuteOnce);addEventListener("click",unmuteOnce);addEventListener("message",onMsg);
var s=document.createElement("script");s.src="https://www.youtube.com/iframe_api";document.head.appendChild(s);
</script></body></html>"""


def player_html(name: str, yt: str, video_ids: list[str], muted: int) -> str:
    plid = yt if (yt or "").startswith("PL") else ""
    ids = [] if plid else (video_ids or [])
    return (_PAGE
            .replace("__IDS__", json.dumps(ids))
            .replace("__PLID__", plid)
            .replace("__NAME__", (name or "").replace('"', "'").replace("\\", ""))
            .replace("__MUTED__", "1" if muted else "0"))
