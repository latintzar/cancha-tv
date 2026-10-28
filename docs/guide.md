# Guide

## Play a local signal

Run `python3 tools/first-signal.py --serve`. It generates three independent FFmpeg HLS signals and extracted frames, starts a loopback media origin and the original Cancha application, probes four configured mirrors, then verifies master rewriting, buffered segment delivery and rejection of a forged proxy target. One mirror intentionally returns404 to exercise a real failed probe.

The printed player URL opens the native channel guide. Choose a signal, then use the player’s guide, pause and rewind controls. The input clips are20 seconds long; they demonstrate the protocol and buffer using authored content. A private JSON receipt records actual stages, runtime/source hashes and zero external-provider/model calls.

The first-result process permits Python connections only to its own two loopback services. The optional `--capture /absolute/directory` path also drives actual Chromium, blocks foreign browser requests and captures desktop/phone guide and decoded-player scenes. Install the Playwright version used by CI for that check.

## Use your channels

Create a private YAML catalogue using the [schema](setup.md). Start the app through the selected private runtime file. Cancha uses measured mirror health and cooldowns; an active recorder can keep trying a usable mirror while a probe transiently reports poor health.

Keep stream URLs and tokens on the server. Rewritten playlists contain opaque, short-lived tickets; the viewer’s status response hides upstream URLs and detailed upstream exceptions. The current ticket store serves one application process. Restarting it requires clients to reload their channel playlists.

## Android TV

Use JDK17 and Android SDK34. From `android/`:

```sh
bash ./gradlew :app:assembleDebug -PcanchaBaseUrl=https://your-cancha.example
```

The default backend targets the Android emulator’s host loopback (`10.0.2.2:8765`). Choose your own HTTPS backend for a device. Debug installs use the SDK’s generated debug signer; release signing uses the recipient’s private fields. The original private keystore and deployed APK are excluded.

The native client keeps the original Compose for TV, Media3 player, prewarming, channel navigation and update path. Compilation and physical TV/remote/codec/update acceptance are distinguished in [status](../RELEASE-STATUS.md).
