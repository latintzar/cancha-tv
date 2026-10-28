#!/usr/bin/env python3
"""Scan iptv-org for good brand-name channels (docs, movies, series, entertainment) and
verify each is actually playable from this box. Prints WORKING candidates."""
import urllib.request, re, sys
from urllib.parse import urljoin

UA = {"User-Agent": "Mozilla/5.0 Chrome/120"}
COUNTRIES = ["mx", "ar", "co", "pe", "es", "us", "uk", "int"]
# brand/quality names worth adding (docs, movies/series, good entertainment)
GOOD = re.compile(
    r"(discovery|national geographic|nat geo|natgeo|animal planet|investigation|curiosity|"
    r"love nature|odisea|dw espa|dw docu|documental|a&e|history|caza|ciencia y|"
    r"cinecanal|golden|studio universal|universal cine|space|tnt|warner|cine ?canal|"
    r"de pel|dela pel|el garaje|runtime|pelis|movistar|amc|sony|axn|comedy central|"
    r"paramount|mtv|cartoon|nick|disney|tcm|europa europa|retro|clasic)",
    re.I)
SKIP = re.compile(r"(geo-block|\[not 24)", re.I)


def parse(cc):
    try:
        t = urllib.request.urlopen(
            "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/%s.m3u" % cc, timeout=25
        ).read().decode("utf-8", "ignore")
    except Exception as e:
        print("FETCH FAIL", cc, e, file=sys.stderr); return []
    lines = t.splitlines(); out = []
    for i, l in enumerate(lines):
        if not l.startswith("#EXTINF"):
            continue
        name = l.split(",")[-1].strip()
        if SKIP.search(l) or not GOOD.search(name):
            continue
        u = ""
        for j in range(i + 1, min(i + 4, len(lines))):
            if lines[j].startswith("http"):
                u = lines[j].strip(); break
        if u:
            out.append((cc, name, u))
    return out


def verify(url):
    try:
        b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=10).read(200000).decode("utf-8", "ignore")
        if "#EXTM3U" not in b:
            return None
        media = url
        for l in b.splitlines():
            if l.strip() and not l.startswith("#"):
                media = urljoin(url, l.strip()); break
        mb = urllib.request.urlopen(urllib.request.Request(media, headers=UA), timeout=10).read(200000).decode("utf-8", "ignore")
        segs = [l.strip() for l in mb.splitlines() if l.strip() and not l.startswith("#")]
        if not segs:
            return None
        d = urllib.request.urlopen(urllib.request.Request(urljoin(media, segs[-1]), headers=UA), timeout=10).read(800000)
        return len(d) // 1024 if len(d) > 20000 else None
    except Exception:
        return None


cands, seen = [], set()
for cc in COUNTRIES:
    for cc2, name, u in parse(cc):
        key = re.sub(r"\(.*", "", name).strip().lower()
        if key in seen:
            continue
        seen.add(key); cands.append((cc2, name, u))

print("scanned %d candidates, verifying..." % len(cands), file=sys.stderr)
for cc, name, u in cands:
    kb = verify(u)
    if kb:
        print(f"OK\t{cc}\t{kb}KB\t{name}\t{u}")
