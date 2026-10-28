# Source beta · 2026-10-28

The release contains Cancha’s original web/FastAPI/Android TV implementation, a runnable local signal entrypoint, recipient-owned configuration, source references and tests. Original source pin: `dbac69422281b857b9425ee01bb1876ddbdb7c2c`, `apps/cancha/`.

## Verified

The local first result generates three independent authored 20-second HLS signals and frames. It loads the real catalogue, performs real HTTP/FFprobe health checks (including one unavailable mirror), rewrites the original playlists, records through the original DVR and serves an actual buffered segment. Forged proxy targets return400 before any upstream fetch.

Chromium plays decoded video in the original UI at 1600×1000 and 390×844; guide and player captures use native source. Browser foreign requests and page errors are0. Python network access is limited to the fixture’s own two loopback services. No external streams, model/provider calls, cloud writes, messages, signing or deployment were performed.

Unit coverage includes ticket privacy/expiry/tampering/concurrency/capacity, public proxy rejection, masked status, HLS URI rewriting, media duration parsing, mirror cooldowns, private configuration and literal-signing-input guards. Source/function navigation and local Markdown links are checked.

The preparation host has the tested Python/FFmpeg/browser tools. Exact runtime versions are in the proof. CI performs a fresh requirements install and repeats the local media/browser check. It also attempts Android debug compilation with JDK17; this CI result is recorded separately after repository publication.

## Separate acceptance

Real external/paid proxy accounts, broadcast/source rights, live-feed failure behavior, long-window recording, non-H264/AAC conversion, multiworker deployment, browser voice permission and physical Android TV/remote/codec/update behavior require recipient acceptance. The host has no Java/Android SDK; no local APK build or device claim is made.

The original Android toolchain/API levels and native UI are retained as source. The first-result input clips are finite authored fixtures, distinct from continuous live broadcast. The original private catalogue, logos, signing key and deployed APK remain excluded.

The ticket store is bounded process memory; use one worker, and reload playlists after a restart. Catalogue and upstream playlist administration remain trusted recipient configuration. The public source beta is prepared for review; publication/deployment is a separate release operation.
