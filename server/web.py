"""Cancha web app — Netflix-grade UI.

Reference: https://www.netflix.com/browse — hero vignettes, tabbed header,
horizontal billboard cards, sticky nav. Adapted for LIVE TV (no scrubber,
no playhead, just back + volume + channel info). Adds:
- Big italic-serif wordmark in nav (instead of square icon)
- Filter tabs: Inicio · Todos · 🇲🇽 · 🇵🇪 · 🇨🇴 · 🇦🇷 · 🇪🇸
- Channel numbers (type 1-99 on remote/keyboard to jump)
- D-pad nav for TV remotes
- Mobile-first responsive
"""

INDEX_HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0a0a0a">
<link rel="icon" href="/brand/cancha-icon.png">
<link rel="apple-touch-icon" href="/brand/cancha-icon.png">
<title>Cancha — TV en vivo</title>

<!-- Self-hosted fonts (no Google Fonts round-trip → no FOUC). Preload the critical ones. -->
<link rel="preload" as="font" type="font/woff2" href="/webfont/inter-400.woff2" crossorigin>
<link rel="preload" as="font" type="font/woff2" href="/webfont/inter-600.woff2" crossorigin>
<link rel="preload" as="font" type="font/woff2" href="/webfont/instrumentserif-400-italic.woff2" crossorigin>
<!-- HLS.js lazy-loaded on first play — see startStream() -->
<link rel="preload" as="script" href="/vendor/hls-1.7.4.min.js">
<style>
  @font-face{font-family:'Instrument Serif';font-style:italic;font-weight:400;font-display:swap;src:url('/webfont/instrumentserif-400-italic.woff2') format('woff2');}
  @font-face{font-family:'Instrument Serif';font-style:normal;font-weight:400;font-display:swap;src:url('/webfont/instrumentserif-400.woff2') format('woff2');}
  @font-face{font-family:'Inter';font-style:normal;font-weight:400;font-display:swap;src:url('/webfont/inter-400.woff2') format('woff2');}
  @font-face{font-family:'Inter';font-style:normal;font-weight:500;font-display:swap;src:url('/webfont/inter-500.woff2') format('woff2');}
  @font-face{font-family:'Inter';font-style:normal;font-weight:600;font-display:swap;src:url('/webfont/inter-600.woff2') format('woff2');}
  @font-face{font-family:'Inter';font-style:normal;font-weight:700;font-display:swap;src:url('/webfont/inter-700.woff2') format('woff2');}
  :root {
    /* Netflix grade dark palette */
    --bg-base: #0a0a0a;
    --bg-141414: #141414;            /* netflix base */
    --bg-elev-1: #181818;
    --bg-elev-2: #232323;
    --bg-elev-3: #2f2f2f;
    --on-bg: #ffffff;
    --on-bg-dim: #d2d2d2;
    --on-bg-mute: #808080;
    --accent-warm: #d97757;
    --accent-warm-strong: #ffa07a;
    --live-red: #ef4444;
    --ok-green: #34d399;
    --focus-ring: #ffffff;
    --shadow-lift: 0 16px 40px -8px rgba(0,0,0,0.85);

    /* Country tints used as background gradients on tiles */
    --mx-grad: linear-gradient(155deg, #d97757 0%, #5d2818 100%);
    --pe-grad: linear-gradient(155deg, #f97316 0%, #7c2d12 100%);
    --co-grad: linear-gradient(155deg, #facc15 0%, #713f12 100%);
    --ar-grad: linear-gradient(155deg, #60a5fa 0%, #1e3a8a 100%);
    --es-grad: linear-gradient(155deg, #ef4444 0%, #7f1d1d 100%);

    --motion-fast: 160ms cubic-bezier(0.2,0.8,0.2,1);
    --motion-med: 280ms cubic-bezier(0.2,0.8,0.2,1);
    --motion-slow: 540ms cubic-bezier(0.5, 0, 0.1, 1);  /* netflix easing */
  }

  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0;
    background: var(--bg-141414);
    color: var(--on-bg);
    font-family: 'Inter', "Netflix Sans", "Helvetica Neue", system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
    overscroll-behavior: none;
  }
  body { font-size: 16px; line-height: 1.5; min-height: 100vh; }
  ::-webkit-scrollbar { width: 10px; height: 10px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--bg-elev-2); border-radius: 8px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--bg-elev-3); }
  button { font-family: inherit; }
  *:focus-visible { outline: none; }
  a { color: inherit; text-decoration: none; }

  /* ============ HEADER (Netflix pinning-header) ============ */
  .pinning-header {
    position: sticky; top: 0; z-index: 50;
    min-height: 68px;
    background-image: linear-gradient(rgba(0,0,0,0.75) 10%, transparent);
    transition: background-color var(--motion-med);
  }
  .pinning-header.solid {
    background-color: var(--bg-141414);
    background-image: none;
  }
  .main-header {
    display: flex; align-items: center; gap: 28px;
    height: 68px;
    padding: 0 4%;
    font-size: 14px;
  }
  .nav-logo {
    display: flex; align-items: baseline; gap: 1px;
    flex: 0 0 auto;
    margin-right: 18px;
    font-family: 'Instrument Serif', serif;
    font-style: italic;
    font-size: 36px;
    line-height: 1;
    letter-spacing: -0.025em;
    color: var(--on-bg);
    text-decoration: none;
    transition: opacity var(--motion-fast);
  }
  .nav-logo:hover { opacity: 0.85; }
  .nav-logo .dot {
    font-style: normal;
    color: var(--accent-warm);
    font-size: 28px;
    margin-left: 0;
  }
  .nav-tabs {
    display: flex; align-items: center;
    gap: 22px;
    list-style: none; margin: 0; padding: 0;
    flex: 1 1 auto;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .nav-tabs::-webkit-scrollbar { display: none; }
  .nav-tabs li { flex: 0 0 auto; }
  .nav-tab {
    color: var(--on-bg-dim);
    cursor: pointer;
    background: transparent; border: 0;
    font-size: 14px; font-weight: 400;
    font-family: inherit;
    padding: 6px 4px;
    white-space: nowrap;
    transition: color var(--motion-fast);
    position: relative;
  }
  .nav-tab:hover, .nav-tab:focus-visible { color: var(--on-bg); }
  .nav-tab.active { color: var(--on-bg); font-weight: 600; }
  .nav-tab.active::after {
    content: '';
    position: absolute;
    left: 0; right: 0; bottom: -2px;
    height: 2px;
    background: var(--on-bg);
  }
  .nav-tab { display: inline-flex; align-items: center; gap: 7px; }
  .flag-chip {
    width: 22px; height: 16px; border-radius: 3px;
    object-fit: cover; flex: 0 0 auto;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,0.12);
  }
  .nav-right {
    display: flex; align-items: center; gap: 14px;
    color: var(--on-bg-dim);
    font-size: 12px;
    flex: 0 0 auto;
  }
  /* Search box — collapses to icon by default, expands on focus/active */
  .search-box {
    display: flex; align-items: center;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px;
    transition: all 260ms cubic-bezier(0.2,0.8,0.2,1);
    overflow: hidden;
  }
  .search-box.expanded {
    background: rgba(0,0,0,0.75);
    border-color: rgba(255,255,255,0.85);
    padding: 4px 8px;
  }
  .search-icon-btn {
    width: 32px; height: 32px;
    background: transparent;
    border: 0; cursor: pointer;
    color: var(--on-bg);
    display: inline-flex; align-items: center; justify-content: center;
    padding: 0;
    transition: opacity var(--motion-fast);
  }
  .search-icon-btn:hover, .search-icon-btn:focus-visible { opacity: 0.8; }
  .search-icon-btn:focus-visible { outline: 1px solid var(--on-bg); outline-offset: 2px; }
  .search-icon-btn svg { width: 18px; height: 18px; }
  /* Categorías button → opens the full-screen menu */
  .cat-btn {
    display: inline-flex; align-items: center; gap: 9px;
    height: 40px; padding: 0 18px; margin-left: 28px;
    background: transparent; border: 0; cursor: pointer;
    color: var(--on-bg); font: inherit; font-size: 15px; font-weight: 600;
    border-radius: 999px; transition: background var(--motion-fast), transform var(--motion-fast);
  }
  .cat-btn svg { width: 20px; height: 20px; }
  .cat-btn:hover, .cat-btn:focus-visible { background: rgba(255,255,255,0.12); outline: none; }
  .cat-btn:focus-visible { background: var(--on-bg); color: var(--bg-base); transform: scale(1.03); }
  /* Full-screen category menu */
  .cat-menu {
    position: fixed; inset: 0; z-index: 200;
    background: rgba(10,10,12,0.86); backdrop-filter: blur(22px) saturate(1.1);
    -webkit-backdrop-filter: blur(22px) saturate(1.1);
    display: none; align-items: center; justify-content: center;
    opacity: 0; transition: opacity 240ms cubic-bezier(0.2,0.8,0.2,1);
  }
  .cat-menu.open { display: flex; opacity: 1; }
  .cat-close {
    position: absolute; top: 4%; right: 4%;
    width: 52px; height: 52px; border-radius: 50%;
    background: rgba(255,255,255,0.08); border: 0; cursor: pointer; color: var(--on-bg);
    display: flex; align-items: center; justify-content: center;
  }
  .cat-close:hover, .cat-close:focus-visible { background: rgba(255,255,255,0.18); outline: none; }
  .cat-close svg { width: 24px; height: 24px; }
  .cat-grid {
    display: grid; gap: 16px;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    width: min(1100px, 86vw); max-height: 86vh; overflow-y: auto;
    padding: 8px; scrollbar-width: none;
  }
  .cat-grid::-webkit-scrollbar { display: none; }
  .cat-item {
    display: flex; align-items: center; gap: 16px;
    padding: 20px 24px; border-radius: 16px; cursor: pointer;
    background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08);
    color: var(--on-bg); font: inherit; font-size: 22px; font-weight: 600;
    text-align: left; letter-spacing: -0.01em;
    transition: background var(--motion-fast), transform var(--motion-fast), border-color var(--motion-fast);
    animation: catIn 360ms cubic-bezier(0.2,0.9,0.3,1) backwards;
  }
  .cat-item:hover, .cat-item:focus-visible {
    background: var(--on-bg); color: var(--bg-base); transform: scale(1.04);
    border-color: var(--on-bg); outline: none;
  }
  .cat-item.active { border-color: var(--accent-warm-strong); }
  .cat-item .flag-chip { width: 34px; height: 25px; border-radius: 5px; }
  .cat-item .cat-ico { width: 26px; height: 26px; flex: 0 0 auto; }
  @keyframes catIn { from { opacity: 0; transform: translateY(14px) scale(0.96); } }
  /* Prominent always-visible search pill (TV-first) */
  .search-pill {
    display: inline-flex; align-items: center; gap: 8px;
    height: 38px; padding: 0 16px 0 13px;
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.30);
    border-radius: 999px;
    color: var(--on-bg); cursor: pointer;
    font-size: 14px; font-weight: 600; letter-spacing: 0.01em;
    transition: background var(--motion-fast), border-color var(--motion-fast), transform var(--motion-fast);
  }
  .search-pill svg { width: 18px; height: 18px; }
  .search-pill:hover { background: rgba(255,255,255,0.18); }
  .search-pill:focus-visible, .search-pill.tv-focus {
    outline: none;
    background: var(--on-bg); color: var(--bg-base);
    border-color: var(--on-bg);
    transform: scale(1.04);
  }
  .search-pill-label { line-height: 1; }
  .search-box input {
    background: transparent;
    border: 0; outline: 0;
    color: var(--on-bg);
    font-family: inherit;
    font-size: 14px;
    padding: 0 8px;
    width: 0;
    transition: width 280ms cubic-bezier(0.2,0.8,0.2,1);
    min-width: 0;
  }
  .search-box.expanded input { width: 220px; }
  .search-box .mic-btn.listening svg { color: var(--live-red); animation: blink 1s ease-in-out infinite; }
  @media (max-width: 900px) {
    .search-box.expanded input { width: 140px; }
    .search-box.expanded { background: rgba(0,0,0,0.85); }
  }
  .nav-status {
    display: flex; align-items: center; gap: 8px;
    font-variant-numeric: tabular-nums;
  }
  .nav-status .pulse {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--ok-green);
    animation: pulse 2.5s ease-out infinite;
  }
  @keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(52,211,153,0.6); }
    70% { box-shadow: 0 0 0 12px rgba(52,211,153,0); }
    100% { box-shadow: 0 0 0 0 rgba(52,211,153,0); }
  }

  /* ============ HERO (Netflix billboard) ============ */
  .billboard {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    max-height: 80vh;
    overflow: hidden;
    margin-top: -68px;
  }
  .billboard-bg {
    position: absolute; inset: 0;
    background-size: cover;
    background-position: center 30%;
    background-repeat: no-repeat;
    /* Calm the busy live frame: knock back brightness + saturation so the hero reads as backdrop */
    filter: brightness(0.78) saturate(0.92);
  }
  /* Stronger left-weighted cinematic scrim for legibility + calm over a busy broadcast frame */
  .trailer-vignette {
    position: absolute; inset: 0;
    background: linear-gradient(95deg, rgba(20,20,20,0.95) 0%, rgba(20,20,20,0.7) 28%, rgba(20,20,20,0.32) 55%, rgba(20,20,20,0.05) 80%, transparent 100%);
    z-index: 8;
  }
  /* Netflix hero-vignette: bottom fade */
  .hero-vignette {
    position: absolute; left: 0; right: 0; bottom: -1px;
    height: 14.7vw; min-height: 90px;
    background: linear-gradient(rgba(20,20,20,0) 0px, rgba(20,20,20,0.15) 15%, rgba(20,20,20,0.35) 29%, rgba(20,20,20,0.58) 44%, rgb(20,20,20) 68%, rgb(20,20,20));
    z-index: 8;
  }
  .billboard-info {
    position: absolute;
    left: 4%; right: 36%;
    bottom: 35%;
    top: 25%;
    z-index: 10;
    display: flex; flex-direction: column;
    justify-content: flex-end;
  }
  .billboard-title-img {
    width: 100%;
    max-width: 480px;
    transform-origin: left bottom;
  }
  .billboard-title-img img {
    max-width: 100%;
    max-height: 200px;
    object-fit: contain;
    filter: drop-shadow(0 4px 18px rgba(0,0,0,0.6));
    display: block;
  }
  .billboard-title-text {
    font-family: 'Instrument Serif', serif;
    font-size: clamp(48px, 6.5vw, 96px);
    line-height: 0.95;
    font-weight: 400;
    letter-spacing: -0.02em;
    color: var(--on-bg);
    margin: 0;
    max-width: 480px;
  }
  .billboard-eyebrow {
    color: var(--accent-warm-strong);
    font-size: 11px; font-weight: 700;
    letter-spacing: 0.18em; text-transform: uppercase;
    margin-bottom: 14px;
    display: flex; align-items: center; gap: 9px;
  }
  .billboard-eyebrow .live-dot {
    width: 8px; height: 8px; border-radius: 50%; background: var(--live-red);
    animation: blink 1.6s ease-in-out infinite;
  }
  @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  .billboard-meta {
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    margin-top: 18px; margin-bottom: 24px;
    font-size: 14px;
    color: var(--on-bg-dim);
  }
  .billboard-meta .chip {
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px; font-weight: 500;
    color: var(--on-bg);
    font-variant-numeric: tabular-nums;
  }
  .billboard-meta .chip-warm {
    background: rgba(217,119,87,0.22);
    color: #ffe3d2;
  }
  .billboard-meta .ch-number {
    background: var(--on-bg);
    color: var(--bg-141414);
    font-weight: 700;
    padding: 4px 10px;
  }
  .billboard-links {
    display: flex; gap: 12px; flex-wrap: wrap;
  }
  /* Netflix Play button */
  .btn-play {
    background: var(--on-bg);
    color: #000;
    border: 0;
    font-weight: 600;
    font-size: 17px;
    padding: 11px 26px;
    border-radius: 4px;
    cursor: pointer;
    display: inline-flex; align-items: center; gap: 10px;
    transition: background-color var(--motion-fast);
  }
  .btn-play:hover, .btn-play:focus-visible { background: rgba(255,255,255,0.75); }
  .btn-play:focus-visible { outline: 2px solid var(--on-bg); outline-offset: 3px; }
  .btn-play svg { width: 22px; height: 22px; fill: currentColor; }
  /* Netflix secondary button */
  .btn-secondary {
    background: rgba(109,109,110,0.7);
    color: var(--on-bg);
    border: 0;
    font-weight: 500;
    font-size: 15px;
    padding: 11px 22px;
    border-radius: 4px;
    cursor: pointer;
    display: inline-flex; align-items: center; gap: 10px;
    transition: background-color var(--motion-fast);
  }
  .btn-secondary:hover, .btn-secondary:focus-visible { background: rgba(109,109,110,0.95); }
  .btn-secondary:focus-visible { outline: 2px solid var(--on-bg); outline-offset: 3px; }
  .btn-secondary svg { width: 20px; height: 20px; }

  /* ============ ROWS (Netflix lolomo) ============ */
  main { padding: 0 0 96px; }
  .lolomo-row { margin: 1.8vw 0; position: relative; }
  .row-title {
    margin: 0;
    padding: 0 4% 12px;
    font-size: clamp(16px, 1.4vw, 22px);
    font-weight: 600;
    letter-spacing: -0.005em;
    color: var(--on-bg);
    display: flex; align-items: center; gap: 12px;
  }
  .row-title .live-pip {
    width: 8px; height: 8px; border-radius: 50%;
    background: #e50914; flex: 0 0 auto;
    box-shadow: 0 0 0 0 rgba(229,9,20,0.55);
    animation: livePip 2s ease-out infinite;
  }
  @keyframes livePip {
    0% { box-shadow: 0 0 0 0 rgba(229,9,20,0.5); }
    70% { box-shadow: 0 0 0 7px rgba(229,9,20,0); }
    100% { box-shadow: 0 0 0 0 rgba(229,9,20,0); }
  }
  .row-title .count {
    font-size: 12px;
    color: var(--on-bg-mute);
    font-weight: 500;
    margin-left: auto;
    padding-right: 4%;
    font-variant-numeric: tabular-nums;
  }
  .row-scroll {
    display: flex;
    gap: 18px;
    /* generous vertical padding so the focused tile + its glow are never clipped */
    padding: 26px max(4%, 28px) 32px;
    overflow-x: auto;
    overflow-y: hidden;
    scroll-snap-type: x proximity;
    scroll-padding-left: max(4%, 28px);
    scrollbar-width: none;
    scroll-behavior: smooth;
    /* soft fade at the edges — width driven by JS (--fl/--fr) so it only shows when there's
       more to scroll on that side, never a hard cut */
    --fl: 0px; --fr: 0px;
    -webkit-mask-image: linear-gradient(to right, transparent 0, #000 var(--fl), #000 calc(100% - var(--fr)), transparent 100%);
    mask-image: linear-gradient(to right, transparent 0, #000 var(--fl), #000 calc(100% - var(--fr)), transparent 100%);
  }
  .row-scroll::-webkit-scrollbar { display: none; }
  /* Web scroll affordance: chevrons that chunk-scroll smoothly, visible on row hover */
  .rail-chev {
    position: absolute; top: 26px; bottom: 32px; width: 4.5%; min-width: 44px;
    display: flex; align-items: center; justify-content: center;
    border: 0; cursor: pointer; z-index: 12; padding: 0;
    color: var(--on-bg); opacity: 0; transition: opacity var(--motion-fast);
    background: linear-gradient(to var(--chev-dir, right), rgba(20,20,20,0.85), transparent);
  }
  .rail-chev.left { left: 0; --chev-dir: left; }
  .rail-chev.right { right: 0; --chev-dir: right; }
  .rail-chev svg { width: 30px; height: 30px; filter: drop-shadow(0 1px 3px rgba(0,0,0,0.6)); transition: transform var(--motion-fast); }
  .lolomo-row:hover .rail-chev.show { opacity: 1; }
  .rail-chev:hover svg { transform: scale(1.25); }
  .rail-chev:not(.show) { pointer-events: none; }

  /* ============ TILE (Netflix title-card 16:9 horizontal) ============ */
  .tile {
    flex: 0 0 auto;
    width: clamp(220px, 20vw, 400px);
    cursor: pointer;
    scroll-snap-align: start;
    background: transparent; border: 0; padding: 0;
    color: inherit; text-align: left;
    font: inherit;
    transition: transform var(--motion-med);
    position: relative;
  }
  .tile:hover, .tile.focus { transform: scale(1.08); z-index: 5; }
  .tile.dim { opacity: 0.5; cursor: not-allowed; }
  .tile.dim:hover, .tile.dim.focus { transform: none; }
  .tile-card {
    aspect-ratio: 16 / 9;
    border-radius: 4px;
    background: var(--bg-elev-1);
    overflow: hidden;
    position: relative;
    display: flex; align-items: center; justify-content: center;
    transition: box-shadow var(--motion-med), outline-color var(--motion-fast), outline-width var(--motion-fast);
    outline: 0 solid transparent;
  }
  /* Live thumbnail background — full-bleed when available */
  .tile-thumb {
    position: absolute; inset: 0; z-index: 0;
    background-size: cover; background-position: center;
    opacity: 0;
    transition: opacity 400ms ease;
  }
  .tile-thumb.loaded { opacity: 1; }
  /* When thumb is loaded, fade the country tint a lot and hide the typographic fallback */
  .tile-card:has(.tile-thumb.loaded) .tile-tint { opacity: 0.18; }
  .tile-card:has(.tile-thumb.loaded) .tile-name-fallback { display: none; }
  .tile-card:has(.tile-thumb.loaded) .tile-logo {
    max-width: 36%; max-height: 32%;
    position: absolute;
    bottom: 10px; left: 10px;
    z-index: 3;
  }
  .tile:hover .tile-card,
  .tile.focus .tile-card {
    box-shadow: var(--shadow-lift);
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .tile-tint {
    position: absolute; inset: 0;
    opacity: 0.7;
    mix-blend-mode: hard-light;
  }
  .tile-tint.MX { background: var(--mx-grad); }
  .tile-tint.PE { background: var(--pe-grad); }
  .tile-tint.CO { background: var(--co-grad); }
  .tile-tint.AR { background: var(--ar-grad); }
  .tile-tint.ES { background: var(--es-grad); }
  .tile-tint.FR { background: linear-gradient(155deg, #3b5bbf 0%, #1a2748 100%); }
  .tile-tint.SN { background: linear-gradient(155deg, #2a9d5c 0%, #123a24 100%); }
  .tile-tint.CI { background: linear-gradient(155deg, #d98a3d 0%, #5a3414 100%); }
  .tile-tint.DE { background: linear-gradient(155deg, #5a5a5a 0%, #1c1c1c 100%); }
  .tile-tint.GB { background: linear-gradient(155deg, #3a4a8f 0%, #171d38 100%); }
  .tile-tint.US { background: linear-gradient(155deg, #3556a8 0%, #16203f 100%); }
  .tile-tint.AFR { background: linear-gradient(155deg, #1b6b43 0%, #0d3322 100%); }
  .row-title .rail-ico { width: 18px; height: 18px; color: var(--on-bg-dim); flex: 0 0 auto; }
  .row-title .rail-flag { width: 26px; height: 19px; }
  .tile-card::after {
    content: '';
    position: absolute; inset: 0; z-index: 2;
    background:
      linear-gradient(180deg, transparent 50%, rgba(0,0,0,0.7) 100%),
      radial-gradient(ellipse 70% 50% at 50% 0%, rgba(255,255,255,0.05), transparent 70%);
    pointer-events: none;
  }
  .tile-name-fallback {
    position: absolute; inset: 0; z-index: 1;
    display: flex; align-items: center; justify-content: center;
    text-align: center; padding: 0 12px;
    color: var(--on-bg);
    font-family: 'Instrument Serif', serif;
    font-size: clamp(20px, 1.6vw, 30px);
    font-weight: 400;
    letter-spacing: -0.015em;
    line-height: 1.05;
    text-shadow: 0 2px 14px rgba(0,0,0,0.7);
  }
  .tile-logo {
    position: relative; z-index: 2;
    max-width: 70%;
    max-height: 60%;
    object-fit: contain;
    filter: drop-shadow(0 4px 14px rgba(0,0,0,0.5));
    opacity: 0;
    transition: opacity var(--motion-fast);
  }
  .tile-logo.loaded { opacity: 1; }
  .tile-card:has(.tile-logo.loaded) .tile-name-fallback { display: none; }
  /* Channel-number badge (top-left) */
  .tile-number {
    position: absolute; top: 8px; left: 8px; z-index: 3;
    background: rgba(0,0,0,0.7);
    backdrop-filter: blur(8px);
    color: var(--on-bg);
    border-radius: 3px;
    padding: 2px 7px;
    font-size: 11px; font-weight: 700;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.04em;
  }
  /* LIVE pill (bottom-left) */
  .tile-live {
    position: absolute; bottom: 8px; left: 8px; z-index: 3;
    display: flex; align-items: center; gap: 6px;
    color: var(--on-bg);
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    text-shadow: 0 1px 6px rgba(0,0,0,0.7);
  }
  .tile-live .dot {
    width: 7px; height: 7px; border-radius: 50%; background: var(--live-red);
    animation: blink 1.6s ease-in-out infinite;
    box-shadow: 0 0 0 1px rgba(0,0,0,0.4);
  }
  /* Quality badge (bottom-right) */
  .tile-quality {
    position: absolute; bottom: 8px; right: 8px; z-index: 3;
    color: var(--on-bg);
    font-size: 10px; font-weight: 600;
    letter-spacing: 0.04em;
    text-shadow: 0 1px 6px rgba(0,0,0,0.8);
  }
  .tile-quality.gold { color: #ffe3d2; font-weight: 700; }
  .tile-offline {
    position: absolute; bottom: 8px; right: 8px; z-index: 3;
    color: var(--on-bg-mute);
    font-size: 10px; font-weight: 600;
    letter-spacing: 0.04em;
    text-shadow: 0 1px 6px rgba(0,0,0,0.8);
  }
  .tile-name {
    margin-top: 8px;
    font-size: 13px;
    font-weight: 500;
    color: var(--on-bg-dim);
    letter-spacing: -0.003em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* ============ SEARCH OVERLAY (full-screen) ============ */
  .search-overlay {
    position: fixed; inset: 0; z-index: 100;
    background: rgba(10,10,10,0.96);
    backdrop-filter: blur(20px);
    display: flex; flex-direction: column;
    opacity: 0; visibility: hidden;
    transition: opacity 280ms ease, visibility 0s linear 280ms;
  }
  .search-overlay.open {
    opacity: 1; visibility: visible;
    transition: opacity 280ms ease;
  }
  .search-close {
    position: absolute; top: 24px; right: 28px;
    width: 44px; height: 44px;
    background: rgba(255,255,255,0.06);
    border: 0; border-radius: 50%;
    color: var(--on-bg);
    cursor: pointer;
    display: inline-flex; align-items: center; justify-content: center;
    transition: background 160ms ease;
    z-index: 1;
  }
  .search-close:hover, .search-close:focus-visible { background: rgba(255,255,255,0.18); }
  .search-close svg { width: 22px; height: 22px; }
  .search-overlay-inner {
    display: grid;
    grid-template-columns: 480px 1fr;
    gap: 40px;
    flex: 1;
    padding: 60px 56px;
    max-width: 100vw;
  }
  .qwerty-pane {
    display: flex; flex-direction: column;
    gap: 20px;
    align-self: center;
  }
  .qwerty-pane input {
    width: 100%;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px;
    color: var(--on-bg);
    font-family: inherit;
    font-size: 20px;
    padding: 14px 18px;
    outline: 0;
    transition: border-color 160ms ease, background 160ms ease;
  }
  .qwerty-pane input:focus {
    border-color: var(--accent-warm-strong);
    background: rgba(255,255,255,0.1);
  }
  .qwerty {
    display: flex; flex-direction: column; gap: 8px;
    user-select: none;
  }
  .qwerty-row {
    display: flex; gap: 6px; justify-content: flex-start;
  }
  .qwerty-row[data-row="1"] { padding-left: 14px; }
  .qwerty-row[data-row="2"] { padding-left: 22px; }
  .qwerty-row[data-row="3"] { padding-left: 36px; }
  .key {
    flex: 0 0 auto;
    min-width: 42px; height: 42px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.08);
    color: var(--on-bg);
    border-radius: 6px;
    font-family: inherit;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    display: inline-flex; align-items: center; justify-content: center;
    transition: background 100ms ease, transform 100ms ease, border-color 100ms ease;
    text-transform: lowercase;
  }
  .key:hover { background: rgba(255,255,255,0.14); }
  .key:active { transform: scale(0.95); }
  .key.focus {
    background: var(--on-bg);
    color: #000;
    border-color: var(--on-bg);
  }
  .key-wide { min-width: 80px; padding: 0 14px; }
  .key-back { color: #ff9a78; }
  .search-results {
    overflow-y: auto;
    align-self: stretch;
    max-height: 80vh;
  }
  .search-results-empty {
    color: var(--on-bg-mute);
    font-size: 15px;
    padding: 80px 0;
    text-align: center;
  }
  .search-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 18px;
  }
  @media (max-width: 900px) {
    .search-overlay-inner { grid-template-columns: 1fr; padding: 24px 18px; gap: 18px; }
    .qwerty-pane { order: 2; align-self: stretch; }
    .qwerty-pane input { font-size: 18px; padding: 12px 14px; }
    .key { min-width: 32px; height: 36px; font-size: 14px; }
    .key-wide { min-width: 64px; }
    .search-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
  }

  /* ============ NUMBER-PAD OVERLAY ============ */
  .numpad-overlay {
    position: fixed; top: 50%; left: 50%;
    transform: translate(-50%, -50%) scale(0.95);
    z-index: 80;
    background: rgba(0,0,0,0.85);
    backdrop-filter: blur(20px);
    border-radius: 12px;
    padding: 24px 48px;
    text-align: center;
    color: var(--on-bg);
    opacity: 0; visibility: hidden;
    transition: opacity 300ms ease, transform 300ms cubic-bezier(0.2,0.8,0.2,1), visibility 0s linear 300ms;
    pointer-events: none;
  }
  .numpad-overlay.show {
    opacity: 1; visibility: visible; transform: translate(-50%, -50%) scale(1);
    transition: opacity 300ms ease, transform 300ms cubic-bezier(0.2,0.8,0.2,1);
  }
  .numpad-label {
    font-size: 11px; font-weight: 600; letter-spacing: 0.2em; text-transform: uppercase;
    color: var(--on-bg-mute);
    margin-bottom: 6px;
  }
  .numpad-digits {
    font-family: 'Instrument Serif', serif;
    font-size: 72px;
    line-height: 1;
    color: var(--accent-warm-strong);
    font-variant-numeric: tabular-nums;
  }
  .numpad-channel {
    font-size: 18px;
    color: var(--on-bg-dim);
    margin-top: 8px;
  }

  /* ============ PLAYER (live — no scrubber, just back + volume + info) ============ */
  .player {
    position: fixed; inset: 0; z-index: 200;
    background: #000;
    opacity: 0;
    visibility: hidden;
    /* open FAST so the channel (its poster) appears the instant you tap — a slow fade reads as "loading" */
    transition: opacity 130ms ease, visibility 0s linear 130ms;
    display: flex; flex-direction: column;
  }
  .player.open {
    opacity: 1; visibility: visible;
    transition: opacity 130ms ease;
  }
  .player video {
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    object-fit: contain;
    background: #000;
    cursor: pointer;
  }
  /* On-demand YouTube channels swap the <video> for an embedded playlist iframe */
  #ytFrame {
    position: absolute; inset: 0; width: 100%; height: 100%;
    border: 0; background: #000; display: none;
  }
  .player.yt video { display: none; }
  .player.yt #ytFrame { display: block; }
  .player.yt .player-bottom { display: none; }   /* YouTube has its own scrubber/controls */
  /* Netflix-grade: TOP vignette with back+flag (thin transparent icons) */
  .player-top {
    position: absolute; left: 0; right: 0; top: 0;
    z-index: 4;
    height: 30%;
    padding: 24px 24px;
    background-image: linear-gradient(rgba(0,0,0,0.3) 0px, rgba(0,0,0,0) 20%);
    pointer-events: none;
    transition: opacity 400ms ease;
    display: flex; align-items: flex-start; justify-content: space-between;
  }
  .player-top > * { pointer-events: auto; }
  .player.idle .player-top { opacity: 0; pointer-events: none; }
  .fav-btn {
    width: 48px; height: 48px; border-radius: 50%;
    background: rgba(0,0,0,0.35); border: 0; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: transform var(--motion-fast), background var(--motion-fast);
  }
  .fav-btn svg { width: 24px; height: 24px; fill: none; stroke: var(--on-bg); stroke-width: 2; }
  .fav-btn:hover, .fav-btn:focus-visible { background: rgba(0,0,0,0.55); transform: scale(1.1); outline: none; }
  .fav-btn.on svg { fill: #ff3b5c; stroke: #ff3b5c; }
  .icon-naked {
    width: 46px; height: 46px;
    border-radius: 4px;
    background: transparent;
    border: 0; cursor: pointer;
    color: var(--on-bg);
    display: inline-flex; align-items: center; justify-content: center;
    transition: transform 0.15s ease;
    padding: 0;
    will-change: transform;
  }
  .icon-naked:hover, .icon-naked.active, .icon-naked:focus-visible { transform: scale(1.3); }
  .icon-naked:focus-visible { outline: 1px solid var(--on-bg); outline-offset: 2px; }
  .icon-naked svg { width: 24px; height: 24px; }

  /* Bottom controls vignette */
  .player-bottom {
    position: absolute; left: 0; right: 0; bottom: 0;
    z-index: 4;
    padding: 16px 24px 24px;
    background-image: linear-gradient(0deg, rgba(0,0,0,0.8) 0px, rgba(0,0,0,0) 100%);
    pointer-events: none;
    transition: opacity 400ms ease;
    display: flex; flex-direction: column; gap: 12px;
  }
  .player.idle .player-bottom { opacity: 0; pointer-events: none; }
  /* Thin scrubber-style LIVE indicator (red 4px bar all the way across) */
  .player-live-bar {
    position: relative;
    height: 4px;
    background: rgba(255,255,255,0.25);
    border-radius: 2px;
    pointer-events: auto;
    overflow: visible;
    cursor: pointer;
  }
  .player-live-bar.rewound .fill { background: var(--accent-warm-strong); opacity: 0.9; animation: none; }
  .player-live-bar .fill {
    position: absolute; top: 0; bottom: 0; left: 0; right: 0;
    background: var(--live-red);
    transform-origin: left center;
    animation: livepulse 3.6s ease-in-out infinite;
  }
  @keyframes livepulse {
    0%, 100% { opacity: 0.55; }
    50% { opacity: 1; }
  }
  .player-live-bar .right-label {
    position: absolute; right: -8px; top: -32px;
    color: var(--on-bg);
    font-size: 13px; font-weight: 600;
    font-variant-numeric: tabular-nums;
    text-shadow: 0 1px 4px rgba(0,0,0,0.7);
  }

  /* Bottom row: left controls / center title / right controls */
  .player-controls-row {
    display: flex; align-items: center; gap: 18px; pointer-events: auto;
  }
  .player-controls-left { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  .player-info {
    flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0;
    text-align: center; align-items: center;
  }
  .player-info .title-row { display: flex; align-items: center; gap: 10px; }
  .player-info .ch-num {
    background: var(--on-bg);
    color: #000;
    font-weight: 700;
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 3px;
    font-variant-numeric: tabular-nums;
  }
  .player-info .ch-name {
    font-size: 18px;
    font-weight: 600;
    line-height: 1.2;
  }
  .player-info .ch-country {
    font-size: 12px; font-weight: 600; letter-spacing: 0.06em;
    color: var(--on-bg-mute);
    border: 1px solid rgba(255,255,255,0.16); border-radius: 999px;
    padding: 2px 9px; white-space: nowrap;
  }
  .player-info .ch-country:empty { display: none; }
  .player-info .ch-name + .ch-meta-sep {
    display: inline-block; width: 1px; height: 14px;
    background: rgba(255,255,255,0.4);
    margin: 0 2px;
  }
  .player-info .live-pill {
    display: inline-flex; align-items: center; gap: 5px;
    color: var(--on-bg);
    font-size: 12px; font-weight: 500;
  }
  .player-info .live-pill .dot {
    width: 7px; height: 7px; border-radius: 50%; background: var(--live-red);
    animation: blink 1.6s ease-in-out infinite;
  }
  .player-info .sub {
    color: var(--on-bg-dim);
    font-size: 11px;
    display: flex; gap: 10px; align-items: center;
    font-variant-numeric: tabular-nums;
  }
  .player-controls-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  .signal-indicator {
    display: inline-flex; align-items: center; justify-content: center;
    width: 18px; height: 18px;
    margin-left: 4px;
    border-radius: 50%;
    transition: color 200ms ease;
  }
  .signal-indicator svg { width: 16px; height: 16px; }
  .signal-indicator.ok { color: var(--ok-green); }
  .signal-indicator.warn { color: #fbbf24; }
  .signal-indicator.bad { color: var(--live-red); }
  /* Quality menu — comfortable fade */
  .quality-menu {
    position: absolute; right: 0; bottom: calc(100% + 12px);
    background: rgba(20,24,30,0.96);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 8px 0;
    min-width: 240px;
    box-shadow: 0 22px 50px -12px rgba(0,0,0,0.9);
    opacity: 0; visibility: hidden;
    transform: translateY(8px);
    transition: opacity 300ms ease, transform 300ms cubic-bezier(0.2,0.8,0.2,1), visibility 0s linear 300ms;
  }
  .quality-menu.open {
    opacity: 1; visibility: visible;
    transform: translateY(0);
    transition: opacity 300ms ease, transform 300ms cubic-bezier(0.2,0.8,0.2,1);
  }
  .quality-menu-head {
    padding: 6px 16px;
    font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--on-bg-mute);
    font-weight: 700;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 4px;
  }
  .quality-item {
    width: 100%;
    display: flex; align-items: center; justify-content: space-between;
    padding: 9px 16px;
    background: transparent; border: 0; color: var(--on-bg);
    font: inherit; font-size: 14px; font-weight: 500;
    cursor: pointer;
    text-align: left;
    transition: background var(--motion-fast);
  }
  .quality-item:hover, .quality-item:focus-visible { background: rgba(255,255,255,0.08); }
  .quality-item.active { color: var(--accent-warm-strong); }
  .quality-item .bw { font-size: 11px; color: var(--on-bg-mute); font-variant-numeric: tabular-nums; }
  .quality-wrapper { position: relative; }

  /* Buffer spinner — only on long stall */
  .buffer-spinner {
    position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
    z-index: 2;
    width: 64px; height: 64px;
    border-radius: 50%;
    border: 3px solid rgba(255,255,255,0.12);
    border-top-color: var(--on-bg);
    animation: spin 0.85s linear infinite;
    opacity: 0; transition: opacity var(--motion-fast);
    pointer-events: none;
  }
  .buffer-spinner.show { opacity: 1; }
  @keyframes spin { to { transform: translate(-50%,-50%) rotate(360deg); } }

  /* Toast for invisible swap */
  .player-toast {
    position: absolute; left: 50%; bottom: 100px; transform: translate(-50%, 16px);
    z-index: 5;
    background: rgba(0,0,0,0.85); backdrop-filter: blur(12px);
    border-radius: 999px; padding: 8px 16px;
    display: inline-flex; align-items: center; gap: 9px;
    font-size: 12px; font-weight: 500; color: var(--on-bg);
    opacity: 0;
    transition: all var(--motion-med);
    pointer-events: none;
  }
  .player-toast.show { opacity: 1; transform: translate(-50%, 0); }
  .player-toast .spin-mini {
    width: 12px; height: 12px; border-radius: 50%;
    border: 2px solid rgba(255,255,255,0.2);
    border-top-color: var(--accent-warm-strong);
    animation: spinmini 0.8s linear infinite;
  }
  @keyframes spinmini { to { transform: rotate(360deg); } }

  /* ============ EMPTY / SKELETON ============ */
  .skel-tile {
    flex: 0 0 auto;
    width: clamp(180px, 16.5vw, 320px);
  }
  .skel-card {
    aspect-ratio: 16 / 9;
    border-radius: 4px;
    background: var(--bg-elev-1);
  }

  /* ============ MOBILE & TABLET ============ */
  @media (max-width: 900px) {
    .pinning-header { min-height: 56px; }
    .main-header { padding: 0 5%; height: 56px; gap: 14px; }
    .nav-logo { font-size: 28px; }
    .nav-logo .dot { font-size: 22px; }
    .nav-tabs { gap: 14px; }
    .nav-tab { font-size: 13px; padding: 4px 2px; }
    .nav-right .nav-status { display: none; }  /* keep search+mic visible on TV/mobile */
    .billboard { aspect-ratio: 1 / 1.2; max-height: none; margin-top: -56px; }
    .billboard-info { left: 5%; right: 5%; bottom: 30%; top: auto; }
    .billboard-title-text { font-size: clamp(40px, 11vw, 72px); }
    .billboard-meta { font-size: 12px; gap: 6px; margin-bottom: 18px; }
    .billboard-meta .chip { padding: 3px 8px; font-size: 11px; }
    .btn-play, .btn-secondary { padding: 10px 18px; font-size: 14px; }
    .lolomo-row { margin: 32px 0; }
    .row-title { padding: 0 5% 10px; }
    .row-scroll { padding: 20px 5% 26px; gap: 12px; }
    .tile { width: 47vw; max-width: 240px; }
    .tile-name { font-size: 12px; }
    .player-top, .player-bottom { padding-left: 16px; padding-right: 16px; }
    .player-info .ch-name { font-size: 15px; }
    .player-controls .icon-btn { width: 38px; height: 38px; }
    .player-controls .icon-btn svg { width: 18px; height: 18px; }
    .player-controls .icon-btn.prev-next { width: 32px; height: 32px; }
  }
  @media (max-width: 480px) {
    .billboard-meta .chip:not(.ch-number):not(.chip-warm) { display: none; }
    .player-info .sub { display: none; }
    /* Tighten the player bar so name + country fit without clipping the right controls */
    .player-controls-row { gap: 8px; }
    .player-info .title-row { gap: 7px; min-width: 0; }
    .player-info .ch-name {
      font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0;
    }
    .player-info .ch-country { font-size: 10px; padding: 1px 7px; }
    #pipBtn { display: none; }            /* PiP is rarely useful on a phone — reclaim the space */
  }

  /* ============ CHANNEL LIST PANEL (Netflix episode-list style) ============ */
  .player-top-right { display: flex; align-items: center; gap: 8px; }
  .ch-list {
    position: absolute; top: 0; right: 0; bottom: 0; z-index: 12;
    width: min(380px, 86vw);
    background: rgba(12,12,12,0.97);
    backdrop-filter: blur(14px);
    border-left: 1px solid rgba(255,255,255,0.08);
    display: flex; flex-direction: column;
    transform: translateX(100%);
    transition: transform 240ms cubic-bezier(0.2,0.8,0.2,1);
    box-shadow: -20px 0 50px rgba(0,0,0,0.5);
  }
  .ch-list.open { transform: translateX(0); }
  .ch-list-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 20px 22px 14px;
  }
  .ch-list-title { font-family: 'Instrument Serif', serif; font-size: 26px; color: var(--on-bg); }
  .ch-list-filters {
    display: flex; gap: 8px; overflow-x: auto; padding: 0 22px 14px; scrollbar-width: none;
  }
  .ch-list-filters::-webkit-scrollbar { display: none; }
  .ch-chip {
    flex: 0 0 auto; border: 0; cursor: pointer;
    border-radius: 999px; padding: 7px 14px; font-size: 12px; font-weight: 600;
    background: rgba(255,255,255,0.08); color: var(--on-bg); white-space: nowrap;
    transition: background var(--motion-fast), color var(--motion-fast);
  }
  .ch-chip.on, .ch-chip:hover, .ch-chip:focus-visible { background: var(--on-bg); color: #000; outline: none; }
  .ch-list-scroll { flex: 1; overflow-y: auto; padding: 0 12px 24px; }
  .ch-country-head {
    position: sticky; top: 0; z-index: 1;
    background: rgba(12,12,12,0.98);
    padding: 12px 10px 6px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--on-bg-mute);
  }
  .ch-row {
    display: flex; align-items: center; gap: 10px; width: 100%;
    border: 0; cursor: pointer; text-align: left;
    background: transparent; color: var(--on-bg-dim);
    border-radius: 8px; padding: 11px 12px; font-size: 15px;
    transition: background var(--motion-fast), color var(--motion-fast);
  }
  .ch-row:hover, .ch-row:focus-visible { background: rgba(255,255,255,0.10); color: var(--on-bg); outline: none; }
  .ch-row.current { color: var(--on-bg); }
  .ch-row .dot { width: 7px; height: 7px; border-radius: 50%; background: #ff3b5c; flex: 0 0 auto; }
  .ch-row .ch-row-num { color: var(--on-bg-mute); font-size: 12px; font-variant-numeric: tabular-nums; min-width: 30px; }
</style>
</head>
<body>

<div class="pinning-header" id="pinningHeader">
  <div class="main-header">
    <a href="#" class="nav-logo" aria-label="Cancha">
      Cancha<span class="dot">.</span>
    </a>
    <button class="cat-btn" id="catBtn" aria-label="Categorías">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      <span id="catBtnLabel">Categorías</span>
    </button>
    <div class="nav-right">
      <button class="search-pill" id="searchToggle" title="Buscar (s)" aria-label="Buscar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <span class="search-pill-label">Buscar</span>
      </button>
      <button class="search-icon-btn mic-btn" id="micBtn" title="Buscar por voz" aria-label="Voz">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
      </button>
    </div>
  </div>
</div>

<!-- Full-screen category menu -->
<div class="cat-menu" id="catMenu" aria-hidden="true">
  <button class="cat-close" id="catClose" aria-label="Cerrar">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M6 18L18 6"/></svg>
  </button>
  <div class="cat-grid" id="catGrid"></div>
</div>

<main id="rails"></main>

<div class="search-overlay" id="searchOverlay">
  <button class="search-close" id="searchOverlayClose" aria-label="Cerrar búsqueda">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M6 18L18 6"/></svg>
  </button>
  <div class="search-overlay-inner">
    <div class="qwerty-pane" id="qwertyPane">
      <input type="text" id="searchInput2" placeholder="Buscar canal por nombre o país…" autocomplete="off" spellcheck="false" autocapitalize="off">
      <div class="qwerty" id="qwerty">
        <div class="qwerty-row" data-row="0">
          <button class="key" data-k="1">1</button><button class="key" data-k="2">2</button><button class="key" data-k="3">3</button><button class="key" data-k="4">4</button><button class="key" data-k="5">5</button><button class="key" data-k="6">6</button><button class="key" data-k="7">7</button><button class="key" data-k="8">8</button><button class="key" data-k="9">9</button><button class="key" data-k="0">0</button>
        </div>
        <div class="qwerty-row" data-row="1">
          <button class="key" data-k="q">q</button><button class="key" data-k="w">w</button><button class="key" data-k="e">e</button><button class="key" data-k="r">r</button><button class="key" data-k="t">t</button><button class="key" data-k="y">y</button><button class="key" data-k="u">u</button><button class="key" data-k="i">i</button><button class="key" data-k="o">o</button><button class="key" data-k="p">p</button>
        </div>
        <div class="qwerty-row" data-row="2">
          <button class="key" data-k="a">a</button><button class="key" data-k="s">s</button><button class="key" data-k="d">d</button><button class="key" data-k="f">f</button><button class="key" data-k="g">g</button><button class="key" data-k="h">h</button><button class="key" data-k="j">j</button><button class="key" data-k="k">k</button><button class="key" data-k="l">l</button><button class="key" data-k="ñ">ñ</button>
        </div>
        <div class="qwerty-row" data-row="3">
          <button class="key" data-k="z">z</button><button class="key" data-k="x">x</button><button class="key" data-k="c">c</button><button class="key" data-k="v">v</button><button class="key" data-k="b">b</button><button class="key" data-k="n">n</button><button class="key" data-k="m">m</button><button class="key key-wide" data-k="space">␣</button><button class="key key-wide key-back" data-k="back">⌫</button>
        </div>
      </div>
    </div>
    <div class="search-results" id="searchResults"></div>
  </div>
</div>

<div class="numpad-overlay" id="numpadOverlay">
  <div class="numpad-label">canal</div>
  <div class="numpad-digits" id="numpadDigits">—</div>
  <div class="numpad-channel" id="numpadChannel">&nbsp;</div>
</div>

<div class="player" id="player" tabindex="-1">
  <video id="video" playsinline></video>
  <iframe id="ytFrame" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>
  <div class="buffer-spinner" id="bufferSpinner"></div>

  <div class="player-top">
    <button class="icon-naked" id="playerBack" title="Volver (Esc)" aria-label="Volver">
      <!-- ArrowLeftMedium (verbatim from netflix) -->
      <svg viewBox="0 0 24 24" fill="none"><path fill="currentColor" fill-rule="evenodd" d="M6.414 11H21v2H6.414l5.293 5.293-1.414 1.414-7-7a1 1 0 0 1 0-1.414l7-7 1.414 1.414z" clip-rule="evenodd"/></svg>
    </button>
    <div class="player-top-right">
      <button class="icon-naked" id="chListBtn" title="Lista de canales (c)" aria-label="Lista de canales">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
      </button>
      <button class="fav-btn" id="favBtn" title="Favorito (g)" aria-label="Favorito">
        <svg viewBox="0 0 24 24"><path d="M12 21s-7.5-4.7-10-9.3C.6 9 1.6 5.5 4.8 4.7 6.9 4.2 9 5.2 12 8c3-2.8 5.1-3.8 7.2-3.3 3.2.8 4.2 4.3 2.8 7C19.5 16.3 12 21 12 21z"/></svg>
      </button>
    </div>
  </div>

  <!-- Netflix-style channel list panel (right side, sticky country headers, country filter) -->
  <div class="ch-list" id="chList" aria-hidden="true">
    <div class="ch-list-head">
      <span class="ch-list-title">Canales</span>
      <button class="icon-naked" id="chListClose" aria-label="Cerrar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></svg>
      </button>
    </div>
    <div class="ch-list-filters" id="chListFilters"></div>
    <div class="ch-list-scroll" id="chListScroll"></div>
  </div>

  <div class="player-bottom">
    <div class="player-live-bar">
      <div class="fill"></div>
      <div class="right-label">EN VIVO</div>
    </div>
    <div class="player-controls-row">
      <div class="player-controls-left">
        <button class="icon-naked" id="prevBtn" title="Canal anterior (←)" aria-label="Canal anterior">
          <svg viewBox="0 0 24 24" fill="none"><path fill="currentColor" d="M6 6h2v12H6zM20 6L9.5 12 20 18z"/></svg>
        </button>
        <button class="icon-naked" id="nextBtn" title="Canal siguiente (→)" aria-label="Canal siguiente">
          <svg viewBox="0 0 24 24" fill="none"><path fill="currentColor" d="M16 6h2v12h-2zM4 6v12l10.5-6z"/></svg>
        </button>
        <button class="icon-naked" id="muteBtn" title="Silencio (M)" aria-label="Silencio">
          <!-- VolumeMedium (verbatim from netflix) -->
          <svg id="muteOn" viewBox="0 0 24 24" fill="none"><path fill="currentColor" fill-rule="evenodd" d="M24 12a14 14 0 0 0-4.1-9.9l-1.415 1.415a12 12 0 0 1 0 16.97L19.9 21.9A14 14 0 0 0 24 12M11 4a1 1 0 0 0-1.707-.707L4.586 8H1a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h3.586l4.707 4.707A1 1 0 0 0 11 20zM5.707 9.707 9 6.414v11.172l-3.293-3.293L5.414 14H2v-4h3.414zM16 12a6 6 0 0 0-1.757-4.243l-1.415 1.415a4 4 0 0 1 0 5.656l1.415 1.415A6 6 0 0 0 16 12m1.07-7.071a10 10 0 0 1 0 14.142l-1.413-1.414a8 8 0 0 0 0-11.314z" clip-rule="evenodd"/></svg>
          <svg id="muteOff" viewBox="0 0 24 24" fill="none" style="display:none"><path fill="currentColor" d="M21.78 17.22 17.56 13 21.78 8.78 20.36 7.36 16.14 11.58 11.92 7.36 10.5 8.78 14.72 13 10.5 17.22 11.92 18.64 16.14 14.42 20.36 18.64 21.78 17.22M11 4a1 1 0 0 0-1.707-.707L4.586 8H1a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h3.586l4.707 4.707A1 1 0 0 0 11 20zM5.707 9.707 9 6.414v11.172l-3.293-3.293L5.414 14H2v-4h3.414z"/></svg>
        </button>
      </div>

      <div class="player-info">
        <div class="title-row">
          <span class="ch-num" id="playerChNum">—</span>
          <span class="ch-name" id="playerChName">—</span>
          <span class="ch-country" id="playerChCountry"></span>
          <!-- signal indicator only appears when there's a PROBLEM (no all-good checkmark noise) -->
          <span class="signal-indicator" id="signalIndicator" style="display:none" title="">
            <svg id="signalWarn" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          </span>
        </div>
      </div>

      <div class="player-controls-right">
        <button class="icon-naked" id="pipBtn" title="PiP (P)" aria-label="Picture in Picture">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><rect x="13" y="12" width="6" height="5" rx="1" fill="currentColor"/></svg>
        </button>
        <button class="icon-naked" id="fsBtn" title="Pantalla completa (F)" aria-label="Pantalla completa">
          <svg id="fsEnter" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9V3h6M21 9V3h-6M3 15v6h6M21 15v6h-6"/></svg>
          <svg id="fsExit" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none"><path d="M9 3v6H3M15 3v6h6M9 21v-6H3M15 21v-6h6"/></svg>
        </button>
      </div>
    </div>
  </div>

  <div class="player-toast" id="playerToast">
    <span class="spin-mini"></span>
    <span id="playerToastText">cambiando…</span>
  </div>
</div>

<script>
const COUNTRY_LABEL = {
  MX: 'México', PE: 'Perú', CO: 'Colombia', AR: 'Argentina', ES: 'España',
  FR: 'Francia', SN: 'Senegal', CI: 'C. Marfil', DE: 'Alemania', GB: 'Reino Unido', US: 'USA', AFR: 'África',
};
// Rounded flag SVGs served by the backend (reliable on TV; emoji flags render as tofu)
const COUNTRY_FLAG_CC = {
  MX: 'mx', PE: 'pe', CO: 'co', AR: 'ar', ES: 'es',
  FR: 'fr', SN: 'sn', CI: 'ci', DE: 'de', GB: 'gb', US: 'us',
};
const COUNTRY_ORDER = ['MX', 'PE', 'CO', 'AR', 'ES', 'FR', 'SN', 'CI', 'DE', 'GB', 'US', 'AFR'];

let CATALOG = null;
let CHANNELS_BY_NUMBER = {};
let FLAT_TILES = [];
let HOVER_PREFETCH = new Map();
let CURRENT_FILTER = 'home';
let SEARCH_QUERY = '';

function qualityTag(ch) {
  const m = ch.best_mirror_summary;
  if (!m) return null;
  const fps = m.fps || 0;
  const h = (m.res || '').split('x')[1] | 0;
  if (h >= 1080 && fps >= 50) return { text: '60fps · HD', gold: true };
  if (h >= 1080) return { text: '1080p', gold: false };
  if (h >= 720)  return { text: '720p', gold: false };
  if (h)         return { text: h + 'p', gold: false };
  return { text: 'live', gold: false };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function prefetchMaster(channelId) {
  if (HOVER_PREFETCH.has(channelId)) return;
  HOVER_PREFETCH.set(channelId, true);
  // Start the DVR recorder so the channel is buffered + instant before the click,
  // and warm the master cache as a fallback.
  try { fetch('/v1/' + channelId + '/warm', { method: 'POST' }); } catch {}
  try { fetch('/v1/' + channelId + '/master.m3u8', { method: 'GET' }); } catch {}
}

function thumbBucket() { return Math.floor(Date.now() / 900000); }  // 15-min window
// Every 15 min, refresh the thumbnails of live tiles so the grid reflects what's on NOW
setInterval(() => {
  document.querySelectorAll('.tile:not(.dim) .tile-thumb').forEach(t => {
    const id = t.closest('.tile')?.dataset.channel; if (!id) return;
    const url = '/thumb/' + id + '.jpg?t=' + thumbBucket();
    const img = new Image();
    img.onload = () => { if (img.naturalWidth > 8) { t.style.backgroundImage = `url('${url}')`; t.classList.add('loaded'); } };
    img.src = url;
  });
}, 900000);

// Lazy thumb loader: only fetch a tile's preview when it nears the viewport. Loading all
// ~60 at once on open stalls the page (esp. mobile) and makes the whole app feel slow.
let _thumbIO = null;
function thumbObserver() {
  if (_thumbIO) return _thumbIO;
  _thumbIO = new IntersectionObserver((entries, obs) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const t = e.target;
      obs.unobserve(t);
      const url = t.dataset.thumb;
      if (!url) return;
      const img = new Image();
      img.onload = () => {
        if (img.naturalWidth > 8 && img.naturalHeight > 8) {
          t.style.backgroundImage = `url('${url}')`;
          t.classList.add('loaded');
        }
      };
      img.src = url;
    });
  }, { rootMargin: '600px' });
  return _thumbIO;
}

function tile(ch, railIdx, colIdx) {
  const q = qualityTag(ch);
  const offline = !ch.best_mirror_score || ch.best_mirror_score <= 0;
  const el = document.createElement('button');
  el.className = 'tile' + (offline ? ' dim' : '');
  el.dataset.channel = ch.id;
  el.dataset.number = ch.number || '';
  el.dataset.rail = railIdx;
  el.dataset.col = colIdx;
  el.tabIndex = offline ? -1 : 0;
  const localLogo = '/logo/' + ch.id;
  // 15-min cache-bucket: same URL within a window (browser-cached), fresh image each new window
  const thumbUrl = '/thumb/' + ch.id + '.jpg?t=' + thumbBucket();
  el.innerHTML = `
    <div class="tile-card">
      <div class="tile-thumb" data-thumb="${thumbUrl}"></div>
      <div class="tile-tint ${ch.country}"></div>
      <div class="tile-name-fallback">${escapeHtml(ch.name)}</div>
      <img class="tile-logo" loading="lazy" src="${localLogo}" alt="${escapeHtml(ch.name)}" onload="this.classList.add('loaded')">
      ${ch.number ? `<div class="tile-number">Ch ${ch.number}</div>` : ''}
      ${offline ? '<div class="tile-offline">sin señal</div>' : ''}
    </div>
    <div class="tile-name">${escapeHtml(ch.name)}</div>
  `;
  // Lazy-load the thumb only when this tile nears the viewport (see thumbObserver)
  if (!offline) {
    thumbObserver().observe(el.querySelector('.tile-thumb'));
  }
  if (!offline) {
    el.addEventListener('click', () => openPlayer(ch));
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPlayer(ch); }
    });
    // Settle on a tile (hover/keyboard focus) → start buffering it in the background so the
    // click reveals an already-playing stream.
    el.addEventListener('mouseenter', () => schedulePreroll(ch));
    el.addEventListener('focus', () => schedulePreroll(ch));
    // Mobile has no hover — warm the DVR the instant a finger lands.
    el.addEventListener('touchstart', () => prefetchMaster(ch.id), { passive: true });
  }
  return el;
}

// Accent strip for elastic matching (tildes, ñ, etc)
function norm(s) {
  return String(s || '').toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/ñ/g, 'n')
    .replace(/[^\w]/g, '');  // strip punctuation & spaces — typo-tolerant
}

// Levenshtein, capped at 2 (cheap fuzzy)
function lev(a, b) {
  if (a === b) return 0;
  if (Math.abs(a.length - b.length) > 2) return 99;
  const dp = new Array(b.length + 1).fill(0).map((_, i) => i);
  for (let i = 0; i < a.length; i++) {
    let prev = i + 1; let prevDiag = i;
    for (let j = 0; j < b.length; j++) {
      const cur = a[i] === b[j] ? prevDiag : Math.min(prevDiag, dp[j+1], prev) + 1;
      prevDiag = dp[j+1]; dp[j+1] = cur; prev = cur;
    }
  }
  return dp[b.length];
}

function searchMatch(ch, q) {
  if (!q) return true;
  const qn = norm(q);
  if (!qn) return true;
  const fields = [
    ch.name,
    COUNTRY_LABEL[ch.country],
    ch.country,
    (ch.tags || []).join(' '),
    String(ch.number || ''),
  ];
  const hay = fields.map(norm).join(' ');
  // substring match (zero typos)
  if (hay.includes(qn)) return true;
  // typo-tolerant: any word in the hay within Levenshtein 1-2 of the query
  if (qn.length >= 3) {
    for (const f of fields) {
      const fn = norm(f);
      if (!fn) continue;
      // Match by sliding window of query length over field
      for (let i = 0; i + qn.length <= fn.length + 2; i++) {
        const slice = fn.slice(i, i + qn.length);
        if (lev(qn, slice) <= (qn.length <= 4 ? 1 : 2)) return true;
      }
      if (lev(qn, fn) <= (qn.length <= 4 ? 1 : 2)) return true;
    }
  }
  return false;
}

function searchScore(ch, q) {
  if (!q) return 0;
  const qn = norm(q);
  const name = norm(ch.name);
  if (name === qn) return 1000;
  if (name.startsWith(qn)) return 500 - (name.length - qn.length);
  if (name.includes(qn)) return 200;
  return 50;
}

function renderRails(catalog, filter) {
  const main = document.getElementById('rails');
  main.innerHTML = '';
  FLAT_TILES = [];
  let railIdx = 0;

  const q = SEARCH_QUERY;
  // When searching, override layout: single rail with results sorted by relevance (live first)
  if (q) {
    const matches = catalog.channels.filter(c => searchMatch(c, q))
      .sort((a, b) => {
        const liveDiff = ((b.best_mirror_score > 0) ? 1 : 0) - ((a.best_mirror_score > 0) ? 1 : 0);
        if (liveDiff) return liveDiff;
        return (a.name || '').localeCompare(b.name || '', 'es');
      });
    if (!matches.length) {
      main.innerHTML = '<div style="padding:96px 4%;text-align:center;color:var(--on-bg-mute);">Sin resultados para "' + escapeHtml(q) + '"</div>';
      return;
    }
    appendRail(main, '', 'Resultados (' + matches.length + ')', null, matches, railIdx);
    return;
  }

  // dead channels always sink to the bottom of any list
  const liveFirst = (a, b) => ((b.best_mirror_score > 0) - (a.best_mirror_score > 0));
  if (filter === 'home') {
    const byId = {};
    for (const c of catalog.channels) byId[c.id] = c;
    // Personal rails first: Favoritos, Recientes, Tu más visto
    const favs = getFavIds().map(id => byId[id]).filter(Boolean).sort(byPopularity);
    if (favs.length) railIdx = appendRail(main, 'fav', 'Favoritos', null, favs, railIdx);
    const recent = getRecentIds().map(id => byId[id]).filter(Boolean).sort(liveFirst);
    if (recent.length) railIdx = appendRail(main, 'recent', 'Recientes', null, recent, railIdx);
    const most = getMostWatchedIds().map(id => byId[id]).filter(Boolean).sort(liveFirst);
    if (most.length) railIdx = appendRail(main, 'most', 'Tu más visto', null, most, railIdx);
    // Then locale rails — always popular→unpopular (by channel number = popularity rank), live first
    for (const cc of COUNTRY_ORDER) {
      const channels = catalog.channels.filter(c => c.country === cc).sort(byPopularity);
      if (channels.length) railIdx = appendRail(main, cc, COUNTRY_LABEL[cc], cc, channels, railIdx);
    }
  } else if (filter === 'all') {
    const all = [...catalog.channels].sort(byPopularity);
    railIdx = appendRail(main, '', 'Todos los canales', null, all, railIdx);
  } else if (filter.indexOf('type:') === 0) {
    // A TYPE category → its channels grouped by country (alphabetical), channels alphabetical.
    const t = filter.slice(5);
    const chans = catalog.channels.filter(c => (c.type || 'Entretenimiento') === t);
    const ccs = [...new Set(chans.map(c => c.country))]
      .sort((a, b) => (COUNTRY_LABEL[a] || a).localeCompare(COUNTRY_LABEL[b] || b, 'es'));
    if (!chans.length) {
      main.innerHTML = '<div style="padding:96px 4%;text-align:center;color:var(--on-bg-mute);">Nada por aquí todavía</div>';
      return;
    }
    for (const cc of ccs) {
      const channels = chans.filter(c => c.country === cc)
        .sort((a, b) => liveFirst(a, b) || (a.name || '').localeCompare(b.name || '', 'es'));
      railIdx = appendRail(main, cc, COUNTRY_LABEL[cc], cc, channels, railIdx);
    }
  } else {
    const cc = filter;
    const channels = catalog.channels.filter(c => c.country === cc).sort(byPopularity);
    if (channels.length) railIdx = appendRail(main, cc, COUNTRY_LABEL[cc], cc, channels, railIdx);
  }
}
// popular first (low channel number = top-ranked), live before dead, then name
function byPopularity(a, b) {
  return ((b.best_mirror_score > 0) - (a.best_mirror_score > 0))
    || (a.number || 999) - (b.number || 999)
    || (a.name || '').localeCompare(b.name || '', 'es');
}

const RAIL_ICON = {
  AFR: '🌍',
  fav: '<svg class="rail-ico" viewBox="0 0 24 24" fill="#ff3b5c" stroke="#ff3b5c" stroke-width="1.5"><path d="M12 21s-7.5-4.7-10-9.3C.6 9 1.6 5.5 4.8 4.7 6.9 4.2 9 5.2 12 8c3-2.8 5.1-3.8 7.2-3.3 3.2.8 4.2 4.3 2.8 7C19.5 16.3 12 21 12 21z"/></svg>',
  recent: '<svg class="rail-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  most: '<svg class="rail-ico" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3l2.6 5.6 6 .7-4.4 4 1.2 6L12 16.9 6.6 19.3l1.2-6-4.4-4 6-.7z"/></svg>',
};
function railIconHtml(icon) {
  if (COUNTRY_FLAG_CC[icon]) return '<img class="flag-chip rail-flag" src="/flag/' + COUNTRY_FLAG_CC[icon] + '.svg" alt="">';
  return RAIL_ICON[icon] || '';
}
const CHEV_L = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>';
const CHEV_R = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>';
function appendRail(main, icon, title, countryCode, channels, railIdx) {
  const live = channels.filter(c => c.best_mirror_score > 0).length;
  const rail = document.createElement('section'); rail.className = 'lolomo-row';
  rail.innerHTML = `
    <h2 class="row-title">
      ${railIconHtml(icon)}
      <span>${title}</span>
      <span class="count">${live} / ${channels.length}</span>
    </h2>
    <button class="rail-chev left" aria-label="Anterior">${CHEV_L}</button>
    <div class="row-scroll"></div>
    <button class="rail-chev right" aria-label="Siguiente">${CHEV_R}</button>
  `;
  const scroll = rail.querySelector('.row-scroll');
  channels.forEach((c, colIdx) => {
    const t = tile(c, railIdx, colIdx);
    scroll.appendChild(t);
    FLAT_TILES.push({ channel: c, el: t, railIdx, colIdx });
  });
  // Edge fade + chevron visibility reflect how much is scrollable each way
  const chevL = rail.querySelector('.rail-chev.left');
  const chevR = rail.querySelector('.rail-chev.right');
  const FADE = 64;
  const sync = () => {
    const maxX = scroll.scrollWidth - scroll.clientWidth;
    const x = scroll.scrollLeft;
    const atStart = x <= 4, atEnd = x >= maxX - 4;
    scroll.style.setProperty('--fl', atStart ? '0px' : FADE + 'px');
    scroll.style.setProperty('--fr', (atEnd || maxX <= 0) ? '0px' : FADE + 'px');
    chevL.classList.toggle('show', !atStart);
    chevR.classList.toggle('show', !atEnd && maxX > 0);
  };
  const chunk = () => Math.max(scroll.clientWidth * 0.8, 320);
  chevL.addEventListener('click', () => scroll.scrollBy({ left: -chunk(), behavior: 'smooth' }));
  chevR.addEventListener('click', () => scroll.scrollBy({ left: chunk(), behavior: 'smooth' }));
  scroll.addEventListener('scroll', sync, { passive: true });
  // initial sync after layout settles
  requestAnimationFrame(sync);
  setTimeout(sync, 300);
  main.appendChild(rail);
  return railIdx + 1;
}

// ===== Header solidify on scroll (Netflix behavior) =====
window.addEventListener('scroll', () => {
  document.getElementById('pinningHeader').classList.toggle('solid', window.scrollY > 80);
});

// ===== Filter tabs =====
// ===== Full-screen category menu =====
const FILTER_LABEL = Object.assign({ home: 'Inicio', all: 'Todos' }, COUNTRY_LABEL);
const TYPE_ORDER = ['Noticias', 'Entretenimiento', 'Películas y Series', 'Documentales', 'Ciencia', 'Cultura', 'Cocina y Viajes', 'Debate', 'Deportes', 'Música'];
// types actually present in the catalog, in preferred order (new categories appear server-side)
function typesPresent() {
  const have = new Set((CATALOG ? CATALOG.channels : []).map(c => c.type || 'Entretenimiento'));
  const ordered = TYPE_ORDER.filter(t => have.has(t));
  for (const t of have) if (!TYPE_ORDER.includes(t)) ordered.push(t);
  return ordered;
}
const TYPE_ICO = '<svg class="cat-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41 11 3.83V3H3v8h.83l9.58 9.59a2 2 0 0 0 2.83 0l4.35-4.35a2 2 0 0 0 0-2.83z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>';
function buildCatMenu() {
  const grid = document.getElementById('catGrid');
  const items = [
    { f: 'home', label: 'Inicio', ico: '<svg class="cat-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/></svg>' },
    ...typesPresent().map(t => ({ f: 'type:' + t, label: t, ico: TYPE_ICO })),
    ...COUNTRY_ORDER.map(cc => ({ f: cc, label: COUNTRY_LABEL[cc], flag: COUNTRY_FLAG_CC[cc], ico: cc === 'AFR' ? '🌍' : '' })),
  ];
  grid.innerHTML = items.map((it, i) =>
    '<button class="cat-item" data-filter="' + it.f + '" style="animation-delay:' + (i * 22) + 'ms">' +
    (it.flag ? '<img class="flag-chip" src="/flag/' + it.flag + '.svg" alt="">' : it.ico) +
    '<span>' + it.label + '</span></button>'
  ).join('');
}
buildCatMenu();
function openCatMenu() {
  document.querySelectorAll('.cat-item').forEach(b => b.classList.toggle('active', b.dataset.filter === CURRENT_FILTER));
  const m = document.getElementById('catMenu');
  m.classList.add('open'); m.setAttribute('aria-hidden', 'false');
  document.querySelector('.cat-item')?.focus();
}
function closeCatMenu() {
  const m = document.getElementById('catMenu');
  m.classList.remove('open'); m.setAttribute('aria-hidden', 'true');
}
document.getElementById('catBtn').addEventListener('click', openCatMenu);
document.getElementById('catClose').addEventListener('click', closeCatMenu);
document.getElementById('catGrid').addEventListener('click', e => {
  const btn = e.target.closest('.cat-item');
  if (!btn) return;
  setFilter(btn.dataset.filter); closeCatMenu();
});
function setFilter(f) {
  CURRENT_FILTER = f;
  let label;
  if (f === 'home') label = 'Categorías';
  else if (f.indexOf('type:') === 0) label = f.slice(5);
  else label = FILTER_LABEL[f] || COUNTRY_LABEL[f] || 'Categorías';
  document.getElementById('catBtnLabel').textContent = label;
  if (CATALOG) renderRails(CATALOG, f);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ===== Personal history (localStorage): recientes + tu más visto =====
function recordWatch(id) {
  try {
    const rec = JSON.parse(localStorage.getItem('cancha:recent') || '[]').filter(x => x !== id);
    rec.unshift(id);
    localStorage.setItem('cancha:recent', JSON.stringify(rec.slice(0, 14)));
    const cnt = JSON.parse(localStorage.getItem('cancha:counts') || '{}');
    cnt[id] = (cnt[id] || 0) + 1;
    localStorage.setItem('cancha:counts', JSON.stringify(cnt));
  } catch {}
}
function getRecentIds() {
  try { return JSON.parse(localStorage.getItem('cancha:recent') || '[]'); } catch { return []; }
}
function getMostWatchedIds() {
  try {
    const cnt = JSON.parse(localStorage.getItem('cancha:counts') || '{}');
    return Object.keys(cnt).filter(k => cnt[k] >= 2).sort((a, b) => cnt[b] - cnt[a]);
  } catch { return []; }
}
// ===== Favorites (heart) =====
function getFavIds() { try { return JSON.parse(localStorage.getItem('cancha:favs') || '[]'); } catch { return []; } }
function isFav(id) { return getFavIds().includes(id); }
function toggleFav(id) {
  let f = getFavIds();
  if (f.includes(id)) f = f.filter(x => x !== id); else f.unshift(id);
  localStorage.setItem('cancha:favs', JSON.stringify(f.slice(0, 60)));
}
function syncFavBtn() {
  if (currentChannel) document.getElementById('favBtn').classList.toggle('on', isFav(currentChannel.id));
}
function toggleCurrentFav() {
  if (!currentChannel) return;
  toggleFav(currentChannel.id); syncFavBtn(); resetIdleTimer();
  showToast(isFav(currentChannel.id) ? '♥ en favoritos' : 'quitado de favoritos');
}

// ===== Player =====
let hls = null;
let currentChannel = null;
let idleTimer = null;
// Pre-roll: the channel you're about to tap buffers (muted, hidden) in the player video while
// you browse, so opening it just reveals an already-playing stream — instant, like live TV.
let prerolledId = null;
let prerollTimer = null;
let centerPrerollTimer = null;
let userMuted = false;  // remembers the mute toggle so reveal respects it
let stallStartedAt = 0;
let stallEpisodes = 0;
let lastSwapAt = 0;
let stallCheckTimer = null;
let availableLevels = [];
const STALL_MIN_MS = 4000;
const STALL_WINDOW_MS = 60_000;
const STALL_THRESHOLD = 3;
const SWAP_COOLDOWN_MS = 20_000;
const IDLE_HIDE_MS = 5000;  // chrome auto-hide after 5s, comfortable fade via CSS

let GRID_STATE = null;  // { scrollY, channelId } — so "back" returns to where we were

// Start buffering a channel in the background (muted, player still hidden) so a later tap
// reveals it instantly. No-op while actively watching, or if it's already the pre-rolled one.
function prerollStream(ch) {
  if (!ch || !ch.best_mirror_score) return;
  if (document.getElementById('player').classList.contains('open')) return;
  if (prerolledId === ch.id && hls) return;
  prerolledId = ch.id;
  startStream(ch.id, true);
}
// Debounced — only pre-roll once you've settled on a tile (hover/focus), not while scanning past.
function schedulePreroll(ch, delay) {
  clearTimeout(prerollTimer);
  prerollTimer = setTimeout(() => prerollStream(ch), delay == null ? 220 : delay);
}
// Mobile: after a scroll settles, pre-roll whichever live tile is nearest the screen centre —
// the one you're most likely about to tap.
function prerollCenteredTile() {
  if (!CATALOG || document.getElementById('player').classList.contains('open')) return;
  const cx = window.innerWidth / 2, cy = window.innerHeight / 2;
  let best = null, bestD = Infinity;
  document.querySelectorAll('.tile:not(.dim)').forEach(t => {
    const r = t.getBoundingClientRect();
    if (r.bottom < 0 || r.top > window.innerHeight || r.right < 0 || r.left > window.innerWidth) return;
    const d = Math.hypot(r.left + r.width / 2 - cx, r.top + r.height / 2 - cy);
    if (d < bestD) { bestD = d; best = t; }
  });
  if (best) {
    const ch = CATALOG.channels.find(c => c.id === best.dataset.channel);
    if (ch) prerollStream(ch);
  }
}

function openPlayer(ch) {
  if (!ch || !ch.best_mirror_score) return;
  clearTimeout(prerollTimer);
  recordWatch(ch.id);  // personal history: recientes + tu más visto
  setTimeout(syncFavBtn, 0);  // reflect favorite state on the heart
  // Remember where we were in the grid before diving into the player
  const focused = document.querySelector('.tile.focus');
  GRID_STATE = {
    scrollY: window.scrollY,
    channelId: (focused && focused.dataset.channel) || ch.id,
  };
  currentChannel = ch;
  document.getElementById('playerChNum').textContent = ch.number ? `Ch ${ch.number}` : '—';
  document.getElementById('playerChName').textContent = ch.name;
  document.getElementById('playerChCountry').textContent = COUNTRY_LABEL[ch.country] || ch.country || '';
  updatePlayerSub(ch);
  const playerEl = document.getElementById('player');
  playerEl.classList.add('open');
  playerEl.classList.remove('idle');  // chrome stays visible while loading; onPlaying starts the auto-hide
  clearTimeout(idleTimer);
  playerEl.focus();
  const video = document.getElementById('video');
  // On-demand YouTube "channel" → swap the HLS video for our always-on player page.
  if (ch.kind === 'youtube') {
    if (hls) { hls.destroy(); hls = null; }
    video.pause(); video.removeAttribute('src'); video.classList.remove('loading');
    prerolledId = null;
    playerEl.classList.add('yt');
    document.getElementById('ytFrame').src =
      '/yt/' + encodeURIComponent(ch.id) + '?name=' + encodeURIComponent(ch.name) + '&muted=1';
    return;
  }
  playerEl.classList.remove('yt');
  document.getElementById('ytFrame').src = '';
  if (prerolledId === ch.id && hls) {
    // Already buffering in the background → just reveal + unmute. INSTANT, no load.
    video.muted = userMuted;
    syncMuteBtn();
    video.play().catch(() => {});
    if (!video.classList.contains('loading')) resetIdleTimer();
  } else {
    startStream(ch.id, userMuted);
  }
  prerolledId = null;  // it's the active stream now
}

function updatePlayerSub(ch) {
  // Compute signal class from mirror health: OK if >0 + low jitter + adequate bitrate
  const m = ch.best_mirror_summary;
  const ind = document.getElementById('signalIndicator');
  if (!m || !ch.best_mirror_score || ch.best_mirror_score <= 0) {
    ind.className = 'signal-indicator bad'; ind.style.display = ''; ind.title = 'Sin señal';
    return;
  }
  const jitter = m.jitter_ms || 0;
  const bw = m.bitrate_mbps || 0;
  const h = (m.res || '').split('x')[1] | 0;
  const good = jitter < 400 && bw > 1.5 && h >= 480;
  // only show the indicator when something's actually wrong — a green "all good" tick is noise
  if (good) {
    ind.style.display = 'none';
  } else {
    ind.className = 'signal-indicator warn'; ind.style.display = '';
    ind.title = jitter > 400 ? 'Jitter alto' : (bw < 1.5 ? 'Bitrate bajo' : 'Resolución baja');
  }
}

let bufferShowTimer = null;
// Lazy-load HLS.js on first play (saves 270KB on initial paint)
let hlsScriptPromise = null;
function loadHls() {
  if (window.Hls) return Promise.resolve();
  if (hlsScriptPromise) return hlsScriptPromise;
  hlsScriptPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = '/vendor/hls-1.7.4.min.js';
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
  return hlsScriptPromise;
}

async function startStream(channelId, muted) {
  const video = document.getElementById('video');
  // DVR ring-buffer playlist: instant tune + rewind + stall-smoothing.
  const src = '/v1/' + channelId + '/dvr.m3u8';
  if (hls) { hls.destroy(); hls = null; }
  availableLevels = [];
  updateLiveBadge(true);
  video.muted = !!muted;  // pre-roll buffers silently; real open reveals with sound
  // Show the channel's thumbnail as the backdrop while it buffers — never a black void
  video.poster = '/thumb/' + channelId + '.jpg?t=' + Math.floor(Date.now() / 900000);
  video.classList.add('loading');
  // PREFER HLS.js everywhere it works (Chrome/Firefox/Edge/Android WebView). Native HLS only
  // for Safari/iOS — Chromium misreports canPlayType('…mpegurl') as "maybe" but can't actually
  // decode HLS, which silently wedged playback at readyState 0. HLS.js first fixes that.
  await loadHls();
  if (window.Hls && Hls.isSupported()) {
    hls = new Hls({
      // Sit ~18s behind live: close enough to feel like "now", far enough to smooth a brief
      // hiccup before you see it (still well under Peter's 1-min ceiling). HLS.js starts on
      // whatever's already buffered, so a pre-rolled channel reveals instantly.
      liveSyncDuration: 18,
      liveMaxLatencyDuration: 36,
      maxBufferLength: 40,
      maxMaxBufferLength: 80,
      backBufferLength: 90,          // seekable rewind
      // fast first frame: prefetch + don't gate the start on a big buffer
      startFragPrefetch: true,
      maxBufferHole: 0.5,
      nudgeMaxRetry: 12,             // nudge over tiny gaps instead of stalling
      highBufferWatchdogPeriod: 1,
      manifestLoadingMaxRetry: 8,
      levelLoadingMaxRetry: 8,
      fragLoadingMaxRetry: 10,
      fragLoadingRetryDelay: 400,
    });
    hls.loadSource(src);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, (e, data) => {
      availableLevels = data.levels || [];
      if (availableLevels.length) {
        const top = availableLevels.map((lv, i) => ({...lv, _i: i}))
          .sort((a, b) => (b.height || 0) - (a.height || 0))[0];
        hls.currentLevel = top._i;  // force max quality
      }
    });
    hls.on(Hls.Events.ERROR, (e, data) => {
      if (data.fatal && (data.type === 'networkError' || data.type === 'mediaError')) {
        showToast('reintentando…');
        maybeSwap(channelId, 'fatal:' + data.details);
      }
    });
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = src;  // Safari / iOS native HLS
  } else {
    alert('Tu navegador no soporta HLS.');
    return;
  }
  video.play().catch(() => { /* autoplay block — user gesture needed; ignore */ });
  stallStartedAt = 0; stallEpisodes = 0;
  if (stallCheckTimer) { clearInterval(stallCheckTimer); stallCheckTimer = null; }
  video.addEventListener('waiting', onWaiting);
  video.addEventListener('playing', onPlaying);
  // Live TV: keep playing even backgrounded / not looking — auto-resume any pause
  video.addEventListener('pause', () => setTimeout(ensurePlaying, 200));
  let lastT = -1, frozenTicks = 0;
  stallCheckTimer = setInterval(() => {
    // Hard-stall watchdog: the playhead is frozen while the video thinks it's playing (not
    // paused, not ended, has data) → it's wedged mid-stream. Re-tune (the forward+back fix).
    // A single sustained freeze never raises enough `waiting` events to hit the episode
    // threshold below, so this catches the "stops midway" case the episode counter misses.
    if (!video.paused && !video.ended && video.readyState >= 2) {
      if (video.currentTime === lastT) {
        if (++frozenTicks >= 6) {   // ~6s of zero progress → wedged
          frozenTicks = 0; lastT = -1;
          maybeSwap(currentChannel?.id, 'frozen playhead');
          return;
        }
      } else { frozenTicks = 0; lastT = video.currentTime; }
    } else { frozenTicks = 0; lastT = -1; }
    if (!stallStartedAt) return;
    if (Date.now() - stallStartedAt > STALL_MIN_MS) {
      stallEpisodes++;
      stallStartedAt = 0;
      setTimeout(() => { stallEpisodes = Math.max(0, stallEpisodes - 1); }, STALL_WINDOW_MS);
      if (stallEpisodes >= STALL_THRESHOLD) {
        maybeSwap(currentChannel?.id, 'repeated stall');
        stallEpisodes = 0;
      }
    }
  }, 1000);
}

function onWaiting() {
  if (!stallStartedAt) stallStartedAt = Date.now();
  clearTimeout(bufferShowTimer);
  // During the initial tune the channel thumbnail is already showing as the backdrop — never
  // flash a spinner over it. Only show one for a genuine mid-playback stall.
  if (document.getElementById('video').classList.contains('loading')) return;
  bufferShowTimer = setTimeout(() => {
    document.getElementById('bufferSpinner').classList.add('show');
  }, 2500);
}
function onPlaying() {
  stallStartedAt = 0;
  clearTimeout(bufferShowTimer);
  document.getElementById('bufferSpinner').classList.remove('show');
  const video = document.getElementById('video');
  video.classList.remove('loading');
  video.removeAttribute('poster');
  resetIdleTimer();  // now that it's actually playing, start the chrome auto-hide countdown
}

function maybeSwap(channelId, reason) {
  if (!channelId) return;
  const now = Date.now();
  if (now - lastSwapAt < SWAP_COOLDOWN_MS) return;
  lastSwapAt = now;
  showToast('cambiando de transmisión…');
  requestSwap(channelId);
}

async function requestSwap(channelId) {
  try {
    await fetch('/v1/' + channelId + '/swap', { method: 'POST' });
    const video = document.getElementById('video');
    const t = video.currentTime;
    startStream(channelId);
    if (t > 0) video.addEventListener('loadedmetadata', () => { try { video.currentTime = t; } catch (e) {} }, { once: true });
    refresh();
  } catch (e) { console.warn('swap failed', e); }
}

function closePlayer() {
  const playerEl = document.getElementById('player');
  playerEl.classList.remove('open');
  const video = document.getElementById('video');
  video.pause();
  video.removeAttribute('src');
  if (hls) { hls.destroy(); hls = null; }
  playerEl.classList.remove('yt');
  document.getElementById('ytFrame').src = '';   // stop YouTube playback
  currentChannel = null;
  prerolledId = null;
  closeChList();
  document.getElementById('bufferSpinner').classList.remove('show');
  hideToast();
  // Refresh the personal rails (Recientes / Tu más visto) to reflect what we just watched
  if (CURRENT_FILTER === 'home' && CATALOG) { LAST_RENDER_SIG = null; renderRails(CATALOG, 'home'); }
  // Restore where we were in the grid (focused tile centred; scroll may shift if a rail was added)
  if (GRID_STATE) {
    const gs = GRID_STATE;
    requestAnimationFrame(() => {
      const tile = FLAT_TILES.find(t => t.channel && t.channel.id === gs.channelId);
      if (tile && tile.el) {
        document.querySelectorAll('.tile.focus').forEach(t => t.classList.remove('focus'));
        tile.el.classList.add('focus');
        tile.el.focus({ preventScroll: true });
        tile.el.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'auto' });
      } else {
        window.scrollTo({ top: gs.scrollY, behavior: 'auto' });
      }
    });
  }
}

function showToast(text) {
  const t = document.getElementById('playerToast');
  document.getElementById('playerToastText').textContent = text;
  t.classList.add('show');
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove('show'), 3500);
}
function hideToast() { document.getElementById('playerToast').classList.remove('show'); }

function resetIdleTimer() {
  const p = document.getElementById('player');
  p.classList.remove('idle');
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => p.classList.add('idle'), IDLE_HIDE_MS);
}

// ===== Player controls + keyboard =====
document.getElementById('playerBack').addEventListener('click', closePlayer);
document.getElementById('favBtn').addEventListener('click', toggleCurrentFav);
document.getElementById('chListBtn').addEventListener('click', () => { openChList(); });
document.getElementById('chListClose').addEventListener('click', closeChList);
document.getElementById('muteBtn').addEventListener('click', toggleMute);
document.getElementById('fsBtn').addEventListener('click', toggleFullscreen);
document.getElementById('pipBtn').addEventListener('click', togglePip);
document.getElementById('prevBtn').addEventListener('click', () => jumpChannel(-1));
document.getElementById('nextBtn').addEventListener('click', () => jumpChannel(1));
// Live bar: click jumps to live edge
document.querySelector('.player-live-bar')?.addEventListener('click', seekToLive);
// Live TV: single click toggles chrome. Double-click = fullscreen.
document.getElementById('video').addEventListener('click', toggleChrome);
document.getElementById('video').addEventListener('dblclick', toggleFullscreen);
// Keep the LIVE badge fresh as playback advances
document.getElementById('video').addEventListener('timeupdate', () => {
  if (Date.now() % 4 < 2) refreshLiveBadge();  // throttle ~ every other tick
});

// No togglePlay — live TV doesn't pause.
// Keep playing no matter what — including backgrounded / screen off
function ensurePlaying() {
  const v = document.getElementById('video');
  if (v.paused) v.play().catch(()=>{});
}
function syncMuteBtn() {
  const v = document.getElementById('video');
  document.getElementById('muteOn').style.display = v.muted ? 'none' : '';
  document.getElementById('muteOff').style.display = v.muted ? '' : 'none';
}
function toggleMute() {
  const v = document.getElementById('video');
  v.muted = !v.muted;
  userMuted = v.muted;
  syncMuteBtn();
}
function toggleFullscreen() {
  const p = document.getElementById('player');
  if (document.fullscreenElement) document.exitFullscreen();
  else p.requestFullscreen().catch(() => {});
}
document.addEventListener('fullscreenchange', () => {
  const fs = !!document.fullscreenElement;
  document.getElementById('fsEnter').style.display = fs ? 'none' : '';
  document.getElementById('fsExit').style.display = fs ? '' : 'none';
});
async function togglePip() {
  const v = document.getElementById('video');
  try {
    if (document.pictureInPictureElement) await document.exitPictureInPicture();
    else if (v.requestPictureInPicture) await v.requestPictureInPicture();
  } catch (e) {}
}

// Channel-flip / list order: countries alphabetical, channels alphabetical within each.
function byNavOrder(a, b) {
  const ca = COUNTRY_LABEL[a.country] || a.country, cb = COUNTRY_LABEL[b.country] || b.country;
  return ca.localeCompare(cb, 'es') || (a.name || '').localeCompare(b.name || '', 'es');
}
function navOrdered() {
  return (CATALOG ? CATALOG.channels.filter(c => c.best_mirror_score > 0) : []).sort(byNavOrder);
}
function jumpChannel(delta) {
  if (!currentChannel || !CATALOG) return;
  const live = navOrdered();
  const idx = live.findIndex(c => c.id === currentChannel.id);
  if (idx === -1) return;
  const next = live[(idx + delta + live.length) % live.length];
  openPlayer(next);
}

// ===== Channel list panel (Netflix episode-list style) =====
let chListCC = null;  // active country filter (null = todos)
function buildChList() {
  const chans = navOrdered();
  const filters = document.getElementById('chListFilters');
  const ccs = [...new Set(chans.map(c => c.country))];
  filters.innerHTML = '';
  const mkChip = (label, cc) => {
    const b = document.createElement('button');
    b.className = 'ch-chip' + (chListCC === cc ? ' on' : '');
    b.textContent = label;
    b.onclick = () => { chListCC = cc; buildChList(); };
    return b;
  };
  filters.appendChild(mkChip('Todos', null));
  ccs.forEach(cc => filters.appendChild(mkChip(COUNTRY_LABEL[cc] || cc, cc)));
  const shown = chListCC ? chans.filter(c => c.country === chListCC) : chans;
  const scroll = document.getElementById('chListScroll');
  scroll.innerHTML = '';
  let lastCC = null;
  shown.forEach(ch => {
    if (ch.country !== lastCC) {
      lastCC = ch.country;
      const h = document.createElement('div');
      h.className = 'ch-country-head';
      h.textContent = COUNTRY_LABEL[ch.country] || ch.country;
      scroll.appendChild(h);
    }
    const cur = currentChannel && ch.id === currentChannel.id;
    const row = document.createElement('button');
    row.className = 'ch-row' + (cur ? ' current' : '');
    row.innerHTML = (cur ? '<span class="dot"></span>' : '') +
      (ch.number ? '<span class="ch-row-num">' + ch.number + '</span>' : '') +
      '<span>' + escapeHtml(ch.name) + '</span>';
    row.onclick = () => { closeChList(); openPlayer(ch); };
    scroll.appendChild(row);
  });
}
function openChList() {
  if (!currentChannel) return;
  buildChList();
  const el = document.getElementById('chList');
  el.classList.add('open');
  el.setAttribute('aria-hidden', 'false');
  setTimeout(() => {
    const cur = document.querySelector('.ch-row.current') || document.querySelector('.ch-row');
    cur && cur.focus();
  }, 60);
}
function closeChList() {
  const el = document.getElementById('chList');
  el.classList.remove('open');
  el.setAttribute('aria-hidden', 'true');
}
function chListOpen() { return document.getElementById('chList').classList.contains('open'); }
function toggleChList() { if (chListOpen()) closeChList(); else openChList(); }

// ===== DVR seek / live-edge =====
function seekBy(delta) {
  const v = document.getElementById('video');
  if (!v.seekable || !v.seekable.length) return;
  const start = v.seekable.start(0);
  const end = v.seekable.end(v.seekable.length - 1);
  const t = Math.max(start, Math.min(end - 1, v.currentTime + delta));
  v.currentTime = t;
  refreshLiveBadge();
  resetIdleTimer();
  // brief toast showing how far behind live
  const behind = Math.round(end - t);
  showToast(behind < 8 ? 'en vivo' : '⏪ -' + fmtBehind(behind));
}
function seekToLive() {
  const v = document.getElementById('video');
  if (!v.seekable || !v.seekable.length) return;
  v.currentTime = v.seekable.end(v.seekable.length - 1) - 1;
  refreshLiveBadge();
  resetIdleTimer();
}
function fmtBehind(s) {
  if (s < 60) return s + 's';
  const m = Math.floor(s / 60), sec = s % 60;
  return m + ':' + String(sec).padStart(2, '0');
}
function refreshLiveBadge() {
  const v = document.getElementById('video');
  if (!v.seekable || !v.seekable.length) { updateLiveBadge(true); return; }
  const end = v.seekable.end(v.seekable.length - 1);
  const behind = end - v.currentTime;
  updateLiveBadge(behind < 12, behind);
}
function updateLiveBadge(atLive, behindSec) {
  const label = document.querySelector('.player-live-bar .right-label');
  const bar = document.querySelector('.player-live-bar');
  if (!label) return;
  if (atLive) {
    label.textContent = 'EN VIVO';
    label.style.color = '#fff';
    bar && bar.classList.remove('rewound');
  } else {
    label.textContent = '⏪ -' + fmtBehind(Math.round(behindSec || 0)) + '  ·  volver a vivo';
    label.style.color = 'var(--accent-warm-strong)';
    bar && bar.classList.add('rewound');
  }
}
function toggleChrome() {
  const p = document.getElementById('player');
  if (p.classList.contains('idle')) { resetIdleTimer(); }
  else { p.classList.add('idle'); }
}

// ===== Number-pad input — type 1-99 to jump to channel =====
let numBuffer = '';
let numTimer = null;
function showNumpad(num) {
  const o = document.getElementById('numpadOverlay');
  document.getElementById('numpadDigits').textContent = num || '—';
  const ch = CHANNELS_BY_NUMBER[parseInt(num, 10)];
  document.getElementById('numpadChannel').textContent = ch ? `→ ${ch.name}` : '';
  o.classList.add('show');
}
function commitNumpad() {
  const n = parseInt(numBuffer, 10);
  numBuffer = '';
  clearTimeout(numTimer);
  document.getElementById('numpadOverlay').classList.remove('show');
  if (!n) return;
  const ch = CHANNELS_BY_NUMBER[n];
  if (ch && ch.best_mirror_score > 0) openPlayer(ch);
}
function cancelNumpad() {
  numBuffer = '';
  clearTimeout(numTimer);
  document.getElementById('numpadOverlay').classList.remove('show');
}
function armNumTimer() {
  // generous window so you can keep typing or backspace before it tunes (normal TV)
  clearTimeout(numTimer);
  numTimer = setTimeout(commitNumpad, 2500);
}
function pushDigit(d) {
  numBuffer = (numBuffer + d).slice(-3);
  showNumpad(numBuffer);
  armNumTimer();
}
function deleteDigit() {
  numBuffer = numBuffer.slice(0, -1);
  if (numBuffer) { showNumpad(numBuffer); armNumTimer(); }
  else cancelNumpad();
}

document.addEventListener('keydown', e => {
  const playerOpen = document.getElementById('player').classList.contains('open');
  // Category menu open: D-pad navigates the grid, OK selects, Back/Esc closes (TV remote: no pointer)
  const catMenu = document.getElementById('catMenu');
  if (catMenu.classList.contains('open')) {
    if (e.key === 'Escape' || e.key === 'GoBack' || e.key === 'Backspace') { e.preventDefault(); closeCatMenu(); document.getElementById('catBtn').focus(); return; }
    const items = Array.from(catMenu.querySelectorAll('.cat-item'));
    let idx = items.indexOf(document.activeElement);
    if (e.key === 'Enter' || e.key === 'Select' || e.key === ' ') { e.preventDefault(); (items[idx] || items[0]).click(); return; }
    if (['ArrowRight', 'ArrowLeft', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
      e.preventDefault();
      if (idx < 0) { items[0].focus(); return; }
      const cols = (getComputedStyle(catMenu.querySelector('.cat-grid')).gridTemplateColumns.split(' ').length) || 4;
      if (e.key === 'ArrowRight') idx = Math.min(items.length - 1, idx + 1);
      else if (e.key === 'ArrowLeft') idx = Math.max(0, idx - 1);
      else if (e.key === 'ArrowDown') idx = Math.min(items.length - 1, idx + cols);
      else if (e.key === 'ArrowUp') idx = Math.max(0, idx - cols);
      items[idx].focus();
      return;
    }
    return;
  }
  // Header focus (catBtn / search) reachable by remote: arrows move, OK activates, down → grid
  const inHeader = ['catBtn', 'searchToggle', 'micBtn'].includes(document.activeElement?.id);
  if (inHeader && !playerOpen) {
    const order = ['catBtn', 'searchToggle', 'micBtn'].map(id => document.getElementById(id)).filter(Boolean);
    let hi = order.indexOf(document.activeElement);
    if (e.key === 'ArrowRight') { e.preventDefault(); order[Math.min(order.length - 1, hi + 1)].focus(); return; }
    if (e.key === 'ArrowLeft') { e.preventDefault(); order[Math.max(0, hi - 1)].focus(); return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); const f = FLAT_TILES.find(t => !t.el.classList.contains('dim')); if (f) setFocus(f.el); return; }
    if (e.key === 'Enter' || e.key === 'Select' || e.key === ' ') { e.preventDefault(); document.activeElement.click(); return; }
  }
  // Digits — anywhere
  if (e.key >= '0' && e.key <= '9' && !e.target.matches('input,textarea')) {
    pushDigit(e.key);
    e.preventDefault();
    return;
  }
  // Mid number-entry: backspace deletes, OK tunes now, Back cancels — and nothing else fires
  if (numBuffer) {
    if (e.key === 'Backspace' || e.key === 'MediaRewind') { e.preventDefault(); deleteDigit(); return; }
    if (e.key === 'Enter' || e.key === 'Select' || e.key === ' ') { e.preventDefault(); commitNumpad(); return; }
    if (e.key === 'Escape' || e.key === 'GoBack') { e.preventDefault(); cancelNumpad(); return; }
  }
  if (playerOpen) {
    // YouTube channel is muted-autoplay on web → unmute on the first key the user presses.
    if (document.getElementById('player').classList.contains('yt')) {
      try { document.getElementById('ytFrame').contentWindow.postMessage('cancha-unmute', '*'); } catch {}
    }
    // Channel list panel owns the keys while it's open.
    if (chListOpen()) {
      if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'GoBack') { e.preventDefault(); closeChList(); return; }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const rows = [...document.querySelectorAll('.ch-row')];
        let i = rows.indexOf(document.activeElement);
        i = (i + (e.key === 'ArrowDown' ? 1 : -1) + rows.length) % rows.length;
        rows[i] && rows[i].focus();
        return;
      }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        e.preventDefault();
        const chips = [...document.querySelectorAll('.ch-chip')];
        const onIdx = Math.max(0, chips.findIndex(c => c.classList.contains('on')));
        const i = (onIdx + (e.key === 'ArrowRight' ? 1 : -1) + chips.length) % chips.length;
        chips[i] && chips[i].click();
        setTimeout(() => { const r = document.querySelector('.ch-row'); r && r.focus(); }, 30);
        return;
      }
      return;  // Enter on a focused row fires its click by default
    }
    if (e.key === 'c' || e.key === 'C') { e.preventDefault(); openChList(); return; }
    if (e.key === 'Escape' || e.key === 'Backspace' || e.key === 'GoBack') { e.preventDefault(); closePlayer(); return; }
    // OK / Enter / Select → toggle chrome (this was doing nothing before)
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'Select') { e.preventDefault(); toggleChrome(); return; }
    if (e.key === 'm' || e.key === 'M') { e.preventDefault(); toggleMute(); resetIdleTimer(); return; }
    if (e.key === 'g' || e.key === 'G') { e.preventDefault(); toggleCurrentFav(); return; }
    if (e.key === 'f' || e.key === 'F') { e.preventDefault(); toggleFullscreen(); resetIdleTimer(); return; }
    if (e.key === 'p' || e.key === 'P') { e.preventDefault(); togglePip(); resetIdleTimer(); return; }
    // LEFT/RIGHT = rewind / forward within the DVR buffer
    if (e.key === 'ArrowLeft' || e.key === 'MediaRewind') { e.preventDefault(); seekBy(-30); return; }
    if (e.key === 'ArrowRight' || e.key === 'MediaFastForward') { e.preventDefault(); seekBy(30); return; }
    // UP/DOWN = channel up/down (volume stays on the remote's hardware buttons)
    if (e.key === 'ArrowUp' || e.key === 'ChannelUp' || e.key === 'PageUp') { e.preventDefault(); jumpChannel(1); return; }
    if (e.key === 'ArrowDown' || e.key === 'ChannelDown' || e.key === 'PageDown') { e.preventDefault(); jumpChannel(-1); return; }
    if (e.key === 'j' || e.key === 'J') { e.preventDefault(); seekBy(-30); return; }
    if (e.key === 'l' || e.key === 'L') { e.preventDefault(); seekToLive(); return; }
    return;
  }
  // Catalog navigation
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'ArrowDown') {
    e.preventDefault();
    moveFocus(e.key);
  } else if (e.key === 'Enter') {
    if (document.activeElement && document.activeElement.classList.contains('tile')) {
      document.activeElement.click();
    }
  }
});

function moveFocus(dir) {
  let cur = document.querySelector('.tile.focus');
  if (!cur) {
    const first = FLAT_TILES.find(t => !t.el.classList.contains('dim'));
    if (first) setFocus(first.el);
    return;
  }
  const ri = parseInt(cur.dataset.rail, 10);
  const ci = parseInt(cur.dataset.col, 10);
  let target = null;
  if (dir === 'ArrowRight') target = FLAT_TILES.find(t => t.railIdx === ri && t.colIdx === ci + 1) || null;
  else if (dir === 'ArrowLeft') target = FLAT_TILES.find(t => t.railIdx === ri && t.colIdx === ci - 1) || null;
  else if (dir === 'ArrowDown') {
    const next = FLAT_TILES.filter(t => t.railIdx === ri + 1);
    target = next.reduce((best, t) => Math.abs(t.colIdx - ci) < Math.abs((best?.colIdx ?? 99) - ci) ? t : best, null);
  } else if (dir === 'ArrowUp') {
    if (ri === 0) { document.getElementById('catBtn').focus(); cur.classList.remove('focus'); return; }
    const prev = FLAT_TILES.filter(t => t.railIdx === ri - 1);
    target = prev.reduce((best, t) => Math.abs(t.colIdx - ci) < Math.abs((best?.colIdx ?? 99) - ci) ? t : best, null);
  }
  if (target) setFocus(target.el);
}
function setFocus(el) {
  document.querySelectorAll('.tile.focus').forEach(t => t.classList.remove('focus'));
  el.classList.add('focus');
  el.focus({ preventScroll: false });
  el.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' });
}

document.getElementById('player').addEventListener('mousemove', resetIdleTimer);
// NOTE: no touchstart->resetIdleTimer — on mobile that fired *before* the video's
// click->toggleChrome, so a tap showed the chrome then immediately hid it again (overlay
// never appeared). On touch, the single video click toggles the chrome; that's enough.

// Don't pause when hidden — keep playing in the background. Just make sure it's still going on return.
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && document.getElementById('player').classList.contains('open')) ensurePlaying();
});


// ===== Load + refresh =====
async function refresh() {
  try {
    const r = await fetch('/v1/status', { cache: 'no-store' });
    const d = await r.json();
    applyCatalog(d);
    // Cache it so a reload paints instantly
    try { sessionStorage.setItem('cancha:catalog', JSON.stringify({ at: Date.now(), d })); } catch {}
  } catch (e) { /* transient — next poll retries */ }
}
let LAST_RENDER_SIG = null;
function catalogSig(d, filter) {
  // Layout depends on: filter + channel live/quality state + personal history (recientes/más visto)
  const hist = (filter === 'home') ? ('|f:' + getFavIds().join(',') + '|h:' + getRecentIds().join(',') + '|m:' + getMostWatchedIds().join(',')) : '';
  return filter + '|' + d.channels.map(c =>
    c.id + ':' + ((c.best_mirror_score > 0) ? 1 : 0) + ':' + (c.best_mirror_summary?.height || 0)
  ).join(',') + hist;
}
function withGridPreserved(fn) {
  // Capture scroll + focus + per-rail horizontal scroll, run fn, then restore
  const scrollY = window.scrollY;
  const focusedId = document.querySelector('.tile.focus')?.dataset.channel;
  const railScroll = [...document.querySelectorAll('.row-scroll')].map(r => r.scrollLeft);
  fn();
  requestAnimationFrame(() => {
    window.scrollTo({ top: scrollY, behavior: 'auto' });
    document.querySelectorAll('.row-scroll').forEach((r, i) => { if (railScroll[i] != null) r.scrollLeft = railScroll[i]; });
    if (focusedId) {
      const tile = FLAT_TILES.find(t => t.channel && t.channel.id === focusedId);
      if (tile && tile.el) {
        tile.el.classList.add('focus');
        const playerOpen = document.getElementById('player').classList.contains('open');
        if (!playerOpen) tile.el.focus({ preventScroll: true });
      }
    }
  });
}
function applyCatalog(d) {
  CATALOG = d;
  CHANNELS_BY_NUMBER = {};
  for (const c of d.channels) if (c.number) CHANNELS_BY_NUMBER[c.number] = c;
  const sig = catalogSig(d, CURRENT_FILTER);
  const changed = sig !== LAST_RENDER_SIG;
  if (changed) {
    LAST_RENDER_SIG = sig;
    if (FLAT_TILES.length) withGridPreserved(() => renderRails(d, CURRENT_FILTER));
    else renderRails(d, CURRENT_FILTER);
  }
  if (currentChannel) {
    const fresh = d.channels.find(c => c.id === currentChannel.id);
    if (fresh) updatePlayerSub(fresh);
  }
}

// Use cached catalog for instant first paint, then refresh in background
(function bootFromCache() {
  try {
    const raw = sessionStorage.getItem('cancha:catalog');
    if (!raw) return;
    const { at, d } = JSON.parse(raw);
    if (Date.now() - at > 5 * 60 * 1000) return; // 5 min freshness
    applyCatalog(d);
  } catch {}
})();

// Pre-warm: when browser is idle, fetch master.m3u8 for every healthy channel so first-click is instant
function prewarmMasters() {
  if (!CATALOG) return;
  const live = CATALOG.channels.filter(c => c.best_mirror_score > 0)
    .sort((a,b) => (a.priority||5)-(b.priority||5));
  // Keep the DVR hot for the most-likely channels so a click is INSTANT (segments already on
  // local disk — no upstream round-trip, no fallback to the slow live path).
  live.slice(0, 24).forEach(ch => { try { fetch('/v1/' + ch.id + '/warm', { method: 'POST' }); } catch {} });
  let i = 0;
  function next() {
    if (i >= live.length) return;
    const ch = live[i++];
    if (!HOVER_PREFETCH.has(ch.id)) {
      HOVER_PREFETCH.set(ch.id, true);
      fetch('/v1/' + ch.id + '/master.m3u8').catch(()=>{});
    }
    if (window.requestIdleCallback) requestIdleCallback(next, { timeout: 800 });
    else setTimeout(next, 200);
  }
  if (window.requestIdleCallback) requestIdleCallback(next, { timeout: 2000 });
  else setTimeout(next, 800);
}

// ===== Search overlay + on-screen QWERTY =====
const searchOverlay = document.getElementById('searchOverlay');
const searchInput2 = document.getElementById('searchInput2');
const searchResults = document.getElementById('searchResults');
const searchToggle = document.getElementById('searchToggle');
const micBtn = document.getElementById('micBtn');
const searchOverlayClose = document.getElementById('searchOverlayClose');
let searchDebounce = null;

function openSearch() {
  searchOverlay.classList.add('open');
  setTimeout(() => searchInput2.focus(), 80);
  renderSearchResults();
}
function closeSearch() {
  searchOverlay.classList.remove('open');
  searchInput2.value = '';
  SEARCH_QUERY = '';
  if (CATALOG) renderRails(CATALOG, CURRENT_FILTER);
}
searchToggle.addEventListener('click', openSearch);
searchOverlayClose.addEventListener('click', closeSearch);
searchInput2.addEventListener('input', () => {
  // instant elastic filter — no debounce, no Enter needed
  SEARCH_QUERY = searchInput2.value.trim();
  renderSearchResults();
});
searchInput2.addEventListener('keydown', e => {
  if (e.key === 'Escape') { e.preventDefault(); closeSearch(); searchToggle.focus(); }
  if (e.key === 'Enter') {
    const matches = computeSearchMatches();
    if (matches.length && matches[0].best_mirror_score > 0) {
      openPlayer(matches[0]); closeSearch();
    }
  }
});
document.addEventListener('keydown', e => {
  if ((e.key === 's' || e.key === 'S' || e.key === '/') && !e.target.matches('input,textarea') && !document.getElementById('player').classList.contains('open')) {
    e.preventDefault();
    openSearch();
  }
});

function computeSearchMatches() {
  if (!CATALOG) return [];
  if (!SEARCH_QUERY) {
    // Show live channels A-Z by default
    return CATALOG.channels.filter(c => c.best_mirror_score > 0)
      .sort((a,b) => (a.name||'').localeCompare(b.name||'','es'));
  }
  return CATALOG.channels.filter(c => searchMatch(c, SEARCH_QUERY))
    .sort((a,b) => {
      const liveDiff = ((b.best_mirror_score > 0) ? 1 : 0) - ((a.best_mirror_score > 0) ? 1 : 0);
      if (liveDiff) return liveDiff;
      return searchScore(b, SEARCH_QUERY) - searchScore(a, SEARCH_QUERY);
    });
}

function renderSearchResults() {
  const matches = computeSearchMatches();
  if (!matches.length) {
    searchResults.innerHTML = '<div class="search-results-empty">Sin resultados para "' + escapeHtml(SEARCH_QUERY) + '"</div>';
    return;
  }
  searchResults.innerHTML = '<div class="search-grid"></div>';
  const grid = searchResults.querySelector('.search-grid');
  matches.forEach((c, i) => {
    const t = tile(c, 0, i);
    t.addEventListener('click', () => { closeSearch(); /* tile click already opens player */ });
    grid.appendChild(t);
  });
}

// On-screen QWERTY — D-pad-navigable
const qwerty = document.getElementById('qwerty');
qwerty.addEventListener('click', e => {
  const k = e.target.closest('.key');
  if (!k) return;
  const key = k.dataset.k;
  pressKey(key);
});
function pressKey(k) {
  if (k === 'back') {
    searchInput2.value = searchInput2.value.slice(0, -1);
  } else if (k === 'space') {
    searchInput2.value += ' ';
  } else {
    searchInput2.value += k;
  }
  SEARCH_QUERY = searchInput2.value.trim();
  renderSearchResults();
}

// D-pad nav inside search overlay (when QWERTY focused)
function moveQwertyFocus(dir) {
  const keys = Array.from(qwerty.querySelectorAll('.key'));
  let cur = qwerty.querySelector('.key.focus');
  if (!cur) { cur = keys[0]; cur.classList.add('focus'); cur.focus(); return; }
  const r = cur.closest('.qwerty-row');
  const rows = Array.from(qwerty.querySelectorAll('.qwerty-row'));
  const ri = rows.indexOf(r);
  const rowKeys = Array.from(r.querySelectorAll('.key'));
  const ki = rowKeys.indexOf(cur);
  let next = null;
  if (dir === 'ArrowLeft') next = rowKeys[ki - 1];
  else if (dir === 'ArrowRight') next = rowKeys[ki + 1];
  else if (dir === 'ArrowDown') {
    const nr = rows[ri + 1];
    if (nr) {
      const nk = Array.from(nr.querySelectorAll('.key'));
      next = nk[Math.min(ki, nk.length - 1)];
    }
  } else if (dir === 'ArrowUp') {
    const pr = rows[ri - 1];
    if (pr) {
      const nk = Array.from(pr.querySelectorAll('.key'));
      next = nk[Math.min(ki, nk.length - 1)];
    } else {
      searchInput2.focus();
      cur.classList.remove('focus');
      return;
    }
  }
  if (next) {
    cur.classList.remove('focus');
    next.classList.add('focus');
    next.focus();
  }
}
qwerty.addEventListener('keydown', e => {
  if (['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)) {
    e.preventDefault(); moveQwertyFocus(e.key);
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    const cur = qwerty.querySelector('.key.focus') || e.target;
    if (cur && cur.classList.contains('key')) pressKey(cur.dataset.k);
  } else if (e.key === 'Escape') {
    e.preventDefault(); closeSearch();
  }
}, true);
// Click a key in search input field then arrow down lands on QWERTY
searchInput2.addEventListener('keydown', e => {
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    const first = qwerty.querySelector('.key');
    if (first) { first.classList.add('focus'); first.focus(); }
  }
});

// ===== Voice (Web Speech API — works in Chrome, Edge, Android TV Chrome; Philips remote mic types into focused input) =====
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let isListening = false;
if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.lang = 'es-MX';
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  recognition.onresult = e => {
    let text = '';
    for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
    if (!searchOverlay.classList.contains('open')) openSearch();
    searchInput2.value = text;
    SEARCH_QUERY = text.trim();
    renderSearchResults();
    if (e.results[e.results.length - 1].isFinal) {
      const matches = computeSearchMatches().filter(c => c.best_mirror_score > 0);
      if (matches.length) setTimeout(() => { openPlayer(matches[0]); closeSearch(); }, 400);
    }
  };
  recognition.onend = () => { isListening = false; micBtn.classList.remove('listening'); };
  recognition.onerror = () => { isListening = false; micBtn.classList.remove('listening'); };
} else {
  micBtn.style.display = 'none';
}
micBtn.addEventListener('click', () => {
  if (!recognition) return;
  if (isListening) { recognition.stop(); return; }
  if (!searchOverlay.classList.contains('open')) openSearch();
  searchInput2.value = '';
  try {
    recognition.start();
    isListening = true;
    micBtn.classList.add('listening');
  } catch (e) {}
});

// Initial skeleton
function renderSkeleton() {
  const main = document.getElementById('rails');
  main.innerHTML = '';
  for (let i = 0; i < 3; i++) {
    const rail = document.createElement('section');
    rail.className = 'lolomo-row';
    rail.innerHTML = `
      <h2 class="row-title"><span>&nbsp;</span></h2>
      <div class="row-scroll">
        ${Array.from({length: 6}, () => '<div class="skel-tile"><div class="skel-card"></div></div>').join('')}
      </div>
    `;
    main.appendChild(rail);
  }
}

if (!CATALOG) renderSkeleton();
refresh().then(() => {
  prewarmMasters();
  // Have HLS.js ready before the first click so it isn't a 270KB cold download on the
  // critical path, then pre-roll whatever's already centred on screen.
  const warm = () => { loadHls(); prerollCenteredTile(); };
  if (window.requestIdleCallback) requestIdleCallback(warm, { timeout: 1500 });
  else setTimeout(warm, 600);
});
// As you scroll and settle, pre-roll the channel nearest the centre (the likely next tap).
addEventListener('scroll', () => {
  clearTimeout(centerPrerollTimer);
  centerPrerollTimer = setTimeout(prerollCenteredTile, 260);
}, { passive: true, capture: true });
setInterval(refresh, 30_000);
</script>

</body>
</html>
"""
