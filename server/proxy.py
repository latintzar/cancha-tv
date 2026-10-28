"""HLS master rewriting + segment proxying.

Strategy: when the player requests /v1/<channel>/master.m3u8, we pick the best mirror,
fetch its master, rewrite each variant URL + each segment URL inside variant playlists
to point back through this backend, so segments stream through us (and optionally
through a Webshare residential exit for the geo-walled ones).

URLs we synthesize:
  /v1/<channel>/<mirror_id>/v/<b64url>     — proxied variant playlist
  /v1/<channel>/<mirror_id>/s/<b64url>     — proxied segment
"""
from __future__ import annotations
import os
from urllib.parse import urljoin
from .tickets import UrlTickets

_URL_TICKETS = UrlTickets()

UA = "Mozilla/5.0 (Linux; Android TV) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def b64url_encode(s: str) -> str:
    """Issue an opaque server-owned upstream ticket."""
    return _URL_TICKETS.issue(s)


def b64url_decode(s: str) -> str:
    """Resolve only a ticket issued by this server."""
    return _URL_TICKETS.resolve(s)


def rewrite_master(text: str, base_url: str, channel_id: str, mirror_id: str) -> str:
    """Rewrite #EXT-X-STREAM-INF target lines to point at our /v/ endpoint."""
    out_lines = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("#EXT-X-STREAM-INF:") and i + 1 < len(lines):
            out_lines.append(line)
            next_uri = lines[i + 1].strip()
            if next_uri and not next_uri.startswith("#"):
                absolute = urljoin(base_url, next_uri)
                out_lines.append(f"/v1/{channel_id}/{mirror_id}/v/{b64url_encode(absolute)}")
            else:
                out_lines.append(lines[i + 1])
            i += 2
            continue
        if stripped.startswith("#EXT-X-MEDIA:") and "URI=" in stripped:
            # rewrite alt-media URIs (audio tracks)
            import re
            def _r(m):
                uri = m.group(1)
                absolute = urljoin(base_url, uri)
                return f'URI="/v1/{channel_id}/{mirror_id}/v/{b64url_encode(absolute)}"'
            new_line = re.sub(r'URI="([^"]+)"', _r, stripped)
            out_lines.append(new_line)
            i += 1
            continue
        out_lines.append(line)
        i += 1
    return "\n".join(out_lines)


def rewrite_variant(text: str, base_url: str, channel_id: str, mirror_id: str) -> str:
    """Rewrite a media playlist: segment lines + #EXT-X-MAP + #EXT-X-KEY URI."""
    import re
    out_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#EXT-X-MAP:") or stripped.startswith("#EXT-X-KEY:"):
            def _r(m):
                uri = m.group(1)
                absolute = urljoin(base_url, uri)
                return f'URI="/v1/{channel_id}/{mirror_id}/s/{b64url_encode(absolute)}"'
            out_lines.append(re.sub(r'URI="([^"]+)"', _r, stripped))
        elif stripped and not stripped.startswith("#"):
            absolute = urljoin(base_url, stripped)
            out_lines.append(f"/v1/{channel_id}/{mirror_id}/s/{b64url_encode(absolute)}")
        else:
            out_lines.append(line)
    return "\n".join(out_lines)


# ---- Webshare residential proxy resolution ---------------------------------
# Webshare residential backconnect format:
#   http://<USER>-CC-<COUNTRY>:<PASS>@<HOST>:<PORT>
# Single env config:
#   WEBSHARE_PROXY_USER = sgxrlffh
#   WEBSHARE_PROXY_PASS = wn93fwszoeku
#   WEBSHARE_PROXY_HOST = p.webshare.io
#   WEBSHARE_PROXY_PORT = 80
# Country: 2-letter ISO (MX, PE, CO, AR, ES, ...). If not set or unavailable, returns None
# and the segment is fetched direct (no proxy).

_WEBSHARE_USER = os.environ.get("WEBSHARE_PROXY_USER", "")
_WEBSHARE_PASS = os.environ.get("WEBSHARE_PROXY_PASS", "")
_WEBSHARE_HOST = os.environ.get("WEBSHARE_PROXY_HOST", "p.webshare.io")
_WEBSHARE_PORT = os.environ.get("WEBSHARE_PROXY_PORT", "80")


def webshare_proxy_url(country_code: str | None) -> str | None:
    """Returns just the proxy URL (no embedded auth). Pair with webshare_proxy_auth()."""
    if not country_code or os.environ.get("CANCHA_ENABLE_PROXY") != "1":
        return None
    if not _WEBSHARE_USER or not _WEBSHARE_PASS:
        return None
    return f"http://{_WEBSHARE_HOST}:{_WEBSHARE_PORT}"


def webshare_proxy_auth(country_code: str | None):
    """Returns aiohttp.BasicAuth for the country code, or None if no proxy is set."""
    if not country_code or os.environ.get("CANCHA_ENABLE_PROXY") != "1":
        return None
    if not _WEBSHARE_USER or not _WEBSHARE_PASS:
        return None
    import aiohttp
    cc = country_code.upper()
    # Webshare residential country-targeting: username includes -CC-<COUNTRY>
    return aiohttp.BasicAuth(f"{_WEBSHARE_USER}-CC-{cc}", _WEBSHARE_PASS)
