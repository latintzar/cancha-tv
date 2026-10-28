# Decisions

Retrospective source reading and release record,2026-10-28. Original source pin: `dbac69422281b857b9425ee01bb1876ddbdb7c2c` in the Leo monorepo, `apps/cancha/`.

## Measure the feed rather than trust its label

`server/prober.py` inspects actual media and updates mirror health. `Channel.best_mirror` selects the highest healthy score outside its cooldown. This supports a personal guide whose source quality can change over time. The tradeoff is probe traffic and a need to configure bounded concurrency.

## Keep an active recorder resilient to probe noise

`Channel.any_mirror` deliberately keeps trying a usable source while recording, even when a health probe temporarily reports poor results. The recorder’s actual fetch remains the liveness test. This avoids stopping a working channel solely because an independent probe had a bad interval.

## Buffer on demand

The original `dvr.py` explains instant tune-in, stall smoothing, rewind and a margin behind the live edge. A local ring decouples playback from momentary upstream delays. Duration pruning, idle shutdown and bounded transcode count control the resource tradeoff. The current default ring is6 minutes; the retained introductory comment’s earlier15-minute ambition is historical.

## Share playback between web and TV

The original Compose/Media3 client and web player use the same status, warm, master, DVR and update endpoints. Prewarming prepares a buffer before tune-in. Device codecs, remote focus and package installation still need physical-device acceptance.

## Issue upstream references on the server

The release replaces unauthenticated base64 target decoding with bounded, expiring opaque tickets. It also clears upstream URLs/detailed failures from viewer status/errors. Viewers can follow issued playlist references; stream URLs and their query credentials remain server-side. The tradeoff is single-process ticket ownership and playlist reload after a restart.

## Preserve the UI with owned example media

The runnable example drives the original guide/player with three independently generated FFmpeg signals and extracted frames. It exercises actual media decoding and buffering. Original channel URLs, broadcast images and private operational state remain separate from the source grant.

## Own signing and optional service access

The release excludes the original keystore, removes literal signing inputs and deployment defaults, and adds recipient-private configuration. Optional proxy access has an explicit project enable flag. The supplied Gradle wrapper is verified against the configured official distribution; local JS/fonts/flags carry their own notices. These changes make the derivative reviewable without borrowing the original operator’s accounts.
