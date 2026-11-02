# Product tour

Cancha is an Android TV app to watch free Latin American TV. Built for the 2026 World Cup, it combines a channel guide, HLS mirror selection and a rolling buffer for playback and rewind, with a companion web player.

Internet channels have different streams and mirrors. Watching them on a television needs a usable channel guide, healthy feed selection and playback that can recover or rewind.

## Choose a channel, rewind, return to live

1. **Browse with the remote.** The Android TV guide groups channels by country and type, shows thumbnails and keeps recent choices. A focused channel can start prewarming before it opens.
2. **Choose a working feed.** The shared backend probes configured HLS mirrors and applies health and cooldown rules. The player receives a rewritten playlist for the selected stream.
3. **Watch and change channel.** Media3 plays the stream. Up/down or channel keys switch channels; a spare player prebuffers a likely next choice.
4. **Rewind the buffer.** Left/right or media seek controls move within the available recording. The server starts an on-demand per-channel recorder and prunes its local segment ring to the configured window.
5. **Return to live.** The player’s live action seeks to the current position. Back returns to the guide; the companion web player uses the same channel and DVR service.

The web demo and local first signal use three authored 20-second HLS signals. The Android client has a compiled/emulator proof; your television, remote, codec behavior and authorized channel catalogue have their own device acceptance.

## Product areas

| Area | What you do | Result |
| --- | --- | --- |
| TV guide | Browse channel rails by country or type. | Remote focus, live-state ordering, thumbnails and recent choices support television use. |
| TV player | Watch, surf channels, seek and return to live. | The main and spare Media3 players reuse prebuffered streams when available. |
| Mirror health | Probe each configured source and select a usable mirror. | The backend keeps selection and recovery in one place. |
| DVR | Record and prune segments on demand. | Playback and rewind share an explicit bounded history. |
| Web companion | Open the guide and player in a browser. | The browser and TV client use the same backend. |
| Private catalogue | Configure channels, mirrors and optional owned proxy settings. | Each installation selects its media sources and access. |

## Design decisions

- **Remote navigation shapes the product.** Channel rails and player key handling are native Android TV components, backed by Compose for TV and Media3.
- **Prewarming improves channel changes.** The focused channel and a likely next choice can load before selection. Other channels load when you select them.
- **One service owns playback.** Both clients use the same mirror selection and DVR endpoints, so channel behavior is shared.
- **A stream URL stays server-side.** Rewritten playlists use bounded, expiring opaque tickets. Stream credentials and signing material belong in your private configuration.

## Reached stage

The repository contains the actual Kotlin TV application, FastAPI channel service and web companion. The included first signal runs real mirror probing, playlist rewriting and buffered playback with authored local signals. Configure an authorized catalogue and build the TV client against your own backend to continue on a physical television.

## Modules

| Source | Responsibility |
| --- | --- |
| [Android guide](../android/app/src/main/kotlin/casa/leo/cancha/ui/HomeScreen.kt) | Present rails, filters, remote focus and channel thumbnails. |
| [Native player](../android/app/src/main/kotlin/casa/leo/cancha/player/PlayerScreen.kt) | Handle channel keys, playback chrome, seeking and live return. |
| [Player prewarming](../android/app/src/main/kotlin/casa/leo/cancha/player/PlayerHolder.kt) | Manage the active and spare Media3 players. |
| [Catalogue](../server/catalog.py) | Load your channel and mirror definitions. |
| [Probes](../server/prober.py) | Measure source health and refresh thumbnails. |
| [HLS proxy](../server/proxy.py) | Rewrite playlists while retaining server-side upstream custody. |
| [DVR ring](../server/dvr.py) | Record, prune and deliver the configured rewind window. |
| [Shared API](../server/main.py) | Serve channel selection, playback and lifecycle routes. |

## Setup and implementation

[First playback](guide.md) · [Setup](setup.md) · [Architecture](architecture.md) · [Decisions](decisions.md) · [Function reference](reference/README.md) · [Public sample](public-preview.md) · [Release status](../RELEASE-STATUS.md)

[made by atelier neyra](https://atelierneyra.com)
