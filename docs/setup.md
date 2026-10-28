# Setup

## Private catalogue

The distributed default is an empty catalogue. Store your own YAML outside the checkout:

```yaml
channels:
  - id: owned-channel
    name: My channel
    country: MX
    type: Cultura
    number: 1
    mirrors:
      - url: https://your-stream.example/live/master.m3u8
        source: My primary origin
```

Supported country groups in the original guide are Mexico, Peru, Colombia, Argentina and Spain. Sources may have multiple mirrors, an optional proxy country, category/tags and a logo. YouTube playlist/embed support remains a distinct original adapter, commissioned with recipient-selected playlists.

Catalogue input is trusted operator configuration. The stream origin and its playlists are administrative inputs; keep their permitted hosts, redirects, licensing and deployment egress policy under your control. The proxy ticket boundary prevents a viewer from inventing an arbitrary base64 fetch target.

## Private environment

```sh
install -d -m700 "$HOME/.config/cancha"
python3 tools/runtime-env.py configure --file "$HOME/.config/cancha/runtime.env" --capability player
python3 tools/runtime-env.py doctor --file "$HOME/.config/cancha/runtime.env"
python3 tools/runtime-env.py run --file "$HOME/.config/cancha/runtime.env" -- python3 -m uvicorn server.main:app --host 127.0.0.1 --port 8765
```

Set `CANCHA_CATALOG` to your private catalogue and `CANCHA_STATE_DIR` to your own state directory. Set `CANCHA_HOST`/`CANCHA_PORT` consistently with the selected listener so thumbnail/self-playback requests reach this instance. Optional `CANCHA_LOGO_DIR` supplies owned channel images.

`CANCHA_DVR_WINDOW_S` defaults to360 seconds; idle recorders stop after150 seconds. `CANCHA_MAX_TRANSCODE` bounds concurrent CPU FFmpeg encodes. Choose disk and concurrency limits for your own catalogue before exposing a server. The source beta’s demonstrated local fixture is20 seconds per signal.

The private-file helper accepts only named fields, masks doctor values, rejects unsafe file permissions/links and clears inherited cloud/proxy/project settings. Hidden terminal entry or a selected recipient secret store supplies values. Source, browser storage and chat are separate from that private input path.

## Optional proxy

Webshare remains the original optional transport. Configure its owned host/port/user/password fields through the `proxy` capability and set `CANCHA_ENABLE_PROXY=1` deliberately. The default path performs direct access to the recipient’s configured streams. Real proxy/account acceptance is still separate; preparation used only loopback signals.

## Android signing and updates

Use `-PcanchaBaseUrl=...` for your backend. The `signing` capability holds `CANCHA_ANDROID_KEYSTORE`, store password, key alias and key password. All fields are required when enabling release signing; otherwise the Gradle release configuration remains unsigned.

The retained `scripts/ship-apk.sh` is an operator deployment tool. It requires explicit recipient APK, SDK, keystore, target host, static directory and public APK URL. Passwords are referenced through apksigner environment inputs. It performs publication only when an operator intentionally runs it with those owned resources. The source-preparation work performed no APK signing, uploads or deployment.
