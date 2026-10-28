"""Cancha data models."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Mirror:
    url: str
    source: str = ""
    proxy_country: Optional[str] = None  # MX|PE|CO|AR|ES
    note: str = ""
    # Health state, updated by prober
    last_probe_at: float = 0.0
    last_score: float = -1.0
    real_fps: float = 0.0
    real_codec: str = ""
    real_width: int = 0
    real_height: int = 0
    real_bitrate: int = 0
    field_order: str = ""
    seg_fetch_jitter_ms: int = 0
    last_error: str = ""
    sick_until: float = 0.0  # epoch seconds; mirror unavailable until then
    consecutive_failures: int = 0

    def mirror_id(self) -> str:
        """Stable short id from url."""
        import hashlib
        return hashlib.sha1(self.url.encode()).hexdigest()[:10]


@dataclass
class Channel:
    id: str
    name: str
    country: str
    type: str = "Entretenimiento"   # category: Noticias / Deportes / Películas y Series / Música / Cultura / Entretenimiento
    kind: str = "hls"               # "hls" (live stream) or "youtube" (on-demand playlist embed)
    yt: str = ""                    # YouTube playlist id (UU.../PL...) when kind == youtube
    priority: int = 5
    tags: list[str] = field(default_factory=list)
    mirrors: list[Mirror] = field(default_factory=list)
    logo_url: str = ""
    number: int = 0

    def healthy_mirrors(self, now: float) -> list[Mirror]:
        return [m for m in self.mirrors if m.last_score > 0 and m.sick_until <= now]

    def best_mirror(self, now: float) -> Optional[Mirror]:
        healthy = self.healthy_mirrors(now)
        if not healthy:
            return None
        return max(healthy, key=lambda m: m.last_score)

    def any_mirror(self, now: float) -> Optional[Mirror]:
        """Best available mirror for an ACTIVE recorder — prefer healthy, but never hard-stop
        a live recording just because the prober transiently soured every mirror. The recorder's
        own fetch is the real liveness test, so fall back to the least-bad option."""
        healthy = self.healthy_mirrors(now)
        if healthy:
            return max(healthy, key=lambda m: m.last_score)
        not_sick = [m for m in self.mirrors if m.sick_until <= now]
        pool = not_sick or self.mirrors
        return max(pool, key=lambda m: m.last_score) if pool else None


@dataclass
class Catalog:
    channels: list[Channel] = field(default_factory=list)

    def by_id(self, cid: str) -> Optional[Channel]:
        return next((c for c in self.channels if c.id == cid), None)

    def by_country(self, country: str) -> list[Channel]:
        return [c for c in self.channels if c.country == country]
