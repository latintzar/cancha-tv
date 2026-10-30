# Cancha

An Android TV app to watch free Latin American TV

Cancha is an Android TV app for streaming free Latin American internet TV during the 2026 World Cup. Its channel guide, mirror selection and rolling HLS buffer support live playback and rewind. The Android TV app and companion web player share the same backend.

[Website](https://atelierneyra.com/cancha) · [Open app](https://preview.atelierneyra.com/apps/cancha/watch) · [Documentation](https://docs.atelierneyra.com/cancha/overview/)

![Cancha](https://atelierneyra.com/assets/product-motion-v4/cancha.jpg)

## How it works

Internet channels have different streams and mirrors. Watching them on a television needs a usable channel guide, healthy feed selection and playback that can recover or rewind.

| Feature | What it does |
| --- | --- |
| Android TV guide | Browse channels through the original native television interface. |
| HLS feed selection | Probe mirrors and select a healthy feed. |
| Playback and rewind | Play the current feed and its rolling DVR buffer. |
| Companion web player | Use the same channel service from a browser. |

The Android TV source builds and has been exercised in an emulator. The hosted web companion uses authored HLS test signals. Channel metadata, feed availability and viewing rights belong to each installation. Build for your Android TV and configure the channels you are entitled to receive. [Product guide](docs/PROJECT.md).

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

- [Guide](docs/guide.md): first playback, channels and Android TV.
- [Setup](docs/setup.md): private catalogue, optional proxy and signing.
- [Architecture](docs/architecture.md): actual requests, buffering and playback.
- [Decisions](docs/decisions.md): original engineering choices and release corrections.
- [Source reference](docs/reference/README.md): functions, Kotlin entrypoints and JSON symbols.
- [Release status](RELEASE-STATUS.md): local proof and remaining acceptance.
- [Provenance](docs/provenance.md) and [third-party notices](THIRD-PARTY-NOTICES.md).

MIT, copyright Peter Neyra. [made by atelier neyra](https://atelierneyra.com)
