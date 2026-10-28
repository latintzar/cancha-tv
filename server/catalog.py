"""YAML catalog loader."""
from __future__ import annotations
import os
import yaml
from .models import Catalog, Channel, Mirror

LOGO_DIR = os.environ.get(
    "CANCHA_LOGO_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "catalog", "logos"),
)


def load_catalog(path: str) -> Catalog:
    with open(path, "r") as f:
        raw = yaml.safe_load(f) or {}
    cat = Catalog()
    for ch_raw in raw.get("channels", []):
        mirrors = []
        for m_raw in ch_raw.get("mirrors", []):
            mirrors.append(Mirror(
                url=m_raw["url"],
                source=m_raw.get("source", ""),
                proxy_country=m_raw.get("proxy_country"),
                note=m_raw.get("note", ""),
            ))
        cat.channels.append(Channel(
            id=ch_raw["id"],
            name=ch_raw["name"],
            country=ch_raw["country"],
            type=ch_raw.get("type", "Entretenimiento"),
            kind=ch_raw.get("kind", "hls"),
            yt=ch_raw.get("yt", ""),
            priority=ch_raw.get("priority", 5),
            tags=ch_raw.get("tags", []),
            mirrors=mirrors,
            logo_url=ch_raw.get("logo_url", ""),
            number=ch_raw.get("number", 0),
        ))
    return cat


CATALOG_PATH = os.environ.get(
    "CANCHA_CATALOG",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "catalog", "channels.yaml")
)
