# Free Latin American internet TV on Android TV

Cancha is an Android TV app for streaming free Latin American internet TV during the 2026 World Cup. Its channel guide, HLS mirror selection and rolling buffer support playback and rewind, with a companion web player on the same backend.

Internet channels have different streams and mirrors. Watching them on a television needs a usable channel guide, healthy feed selection and playback that can recover or rewind.

| Feature | What it does |
| --- | --- |
| Android TV guide | Browse channels through the original native television interface. |
| HLS feed selection | Probe mirrors and select a healthy feed. |
| Playback and rewind | Play the current feed and its rolling DVR buffer. |
| Companion web player | Use the same channel service from a browser. |

## Workflow

Channel guide → Healthy stream selection → Live playback → Buffered rewind

## Design decisions

- The TV app and browser companion share the channel and playback backend.
- A bounded buffer makes the rewind window explicit.

## Status and next steps

The Android TV source builds and has been exercised in an emulator. The hosted web companion uses authored HLS test signals. Channel metadata, feed availability and viewing rights belong to each installation. Build for your Android TV and configure the channels you are entitled to receive.

Source: [docs/architecture.md](../docs/architecture.md), [docs/setup.md](../docs/setup.md), [docs/verification.md](../docs/verification.md).
