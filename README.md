# Cancha

An Android TV app to watch free Latin American TV

Cancha is an Android TV app for streaming free Latin American internet TV during the 2026 World Cup. Its channel guide, mirror selection and rolling HLS buffer support live playback and rewind. The Android TV app and companion web player share the same backend.

[Website](https://atelierneyra.com/cancha) · [Open demo](https://preview.atelierneyra.com/apps/cancha/watch) · [Product tour](docs/product-tour.md) · [Documentation](https://docs.atelierneyra.com/cancha/overview/)

[![Cancha browser guide with Mexican, Peruvian and Colombian channel thumbnails](https://atelierneyra.com/assets/product-motion-v5/cancha-a346548642fd.jpg)](https://preview.atelierneyra.com/apps/cancha/watch)

## Choose a channel, rewind, return to live

1. **Browse the TV guide.** Use the remote to explore channels by country or type, with thumbnails and recent choices.
2. **Open a channel.** The backend selects a healthy configured HLS mirror. The TV client can prewarm the focused or likely next channel.
3. **Watch and rewind.** Channel keys change the feed; seek controls use the available rolling recording.
4. **Return to live or the guide.** The Android TV player and companion browser use the same channel and DVR backend.

## Product areas

| Area | What it does |
| --- | --- |
| Android TV guide | Present remote-navigable channel rails, filters, thumbnails and recents. |
| Media3 player | Play, change channel, seek and return to live; reuse prebuffered streams where available. |
| Mirror health | Probe HLS feeds and apply selection/cooldown rules. |
| DVR | Record and prune a bounded per-channel segment ring on demand. |
| Web companion | Use the same guide and playback service from a browser. |

The Android source builds and has emulator evidence. The hosted web companion uses three authored HLS test signals; your authorized channels and physical TV/remote acceptance belong to your installation.

[Product tour](docs/product-tour.md) follows the viewer’s experience and maps the native guide, player and backend modules.

## First result

Use Python 3.12 and install FFmpeg/FFprobe through your operating system.

```sh
git clone https://github.com/latintzar/cancha-tv.git
cd cancha-tv
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r server/requirements.txt
python3 tools/first-signal.py --serve
```

Open the loopback URL printed by the command. Choose a test signal to play it through Cancha’s actual HLS and DVR pipeline. The command also verifies mirror health, buffered segment delivery and rejection of an unissued proxy target. Generated media, catalogue and state live in a private temporary directory.

The example supplies three authored 20-second signals. Your own authorized catalogue is [configured separately](docs/setup.md).

## Build with it

- [Product tour](docs/product-tour.md): the viewer journey, features and module map.
- [Guide](docs/guide.md): first playback, channels and Android TV.
- [Setup](docs/setup.md): private catalogue, optional proxy and signing.
- [Architecture](docs/architecture.md): actual requests, buffering and playback.
- [Decisions](docs/decisions.md): original engineering choices and release corrections.
- [Source reference](docs/reference/README.md): functions, Kotlin entrypoints and JSON symbols.
- [Release status](RELEASE-STATUS.md): local proof and remaining acceptance.
- [Provenance](docs/provenance.md) and [third-party notices](THIRD-PARTY-NOTICES.md).

MIT, copyright Peter Neyra. [made by atelier neyra](https://atelierneyra.com)
