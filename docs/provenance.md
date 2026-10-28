# Provenance

Source authority: clean tracked `apps/cancha/` in the Leo monorepo on peter-projects, commit `dbac69422281b857b9425ee01bb1876ddbdb7c2c`. No original source or runtime was modified. The release is a clean copy with no Git history.

## Retained source

The Python catalogue, prober, HLS rewriting, DVR, YouTube adapter and original web player remain. The native Compose/Media3 Android TV application, build scripts and updater remain. Source comments and [decisions](decisions.md) distinguish original choices from release corrections.

## Release changes

- Authored local HLS signals, actual pipeline/browser proof, recipient-private configuration, documentation, source reference and CI.
- Opaque server-issued URL tickets replace viewer-editable base64 proxy targets; status and public failures hide upstream URLs.
- Original keystore, signing literals, deployment targets and account defaults are excluded or replaced by explicit recipient fields. Optional proxy access requires a project enable flag.
- State/output paths point to recipient state; default catalogue is empty. The first-result command uses its own private generated catalogue and media.
- Shutdown closes recorder/background tasks. The web’s hls.js bundle, fonts and licensed country icons are local. Static companion HTML is derived from the actually served UI.
- The tracked Gradle JAR did not match the configured distribution’s official checksum. The derivative carries the exact official Gradle 8.7 wrapper and distribution checksum, with Apache notice; original bytes remain in the owner’s private baseline.

## Excluded material

`android/keystore/`, original `catalog/channels.yaml`, company/operational notes, deployed APKs, private runtime, credentials and media remain private or retain separate ownership. The original source’s deployment host and signing defaults are never used by the starter. No production box or provider account was contacted.

The original channel catalogue’s stream and logo rights were not established for redistribution. The public example instead creates three independent 20-second signals and extracted frames locally. Country grouping exercises the original guide; it represents authored test inputs.

## Visual proof

`docs/assets/` contains actual Chromium guide and decoded-player views at 1600×1000 and 390×844. They render the source UI and real local HLS/DVR output. [Proof](assets/proof.json) records source/image hashes, runtime versions and network boundaries. Capture uses the app viewport; offscreen drawers are outside that viewport.

The fonts, HLS player library, country SVGs and Gradle wrapper have [separate verified provenance](../third-party-assets.json). These are licensed upstream assets; product screens are rendered from Cancha source.
