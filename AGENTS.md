# Agent setup

Read README.md, docs/setup.md and RELEASE-STATUS.md. The source contains Cancha’s actual web, FastAPI and Android TV implementations.

1. Run the authored local signal before configuring external sources. It needs Python, the listed packages and CPU FFmpeg/FFprobe; provider accounts are separate.
2. Keep catalogues, stream credentials, DVR output and signing material outside the checkout. Use recipient-owned HLS sources and independently licensed media.
3. For private runtime values, use `tools/runtime-env.py configure` in a hidden terminal or the recipient’s private secret store. Its allowlisted file needs mode0600 in a mode0700 directory. Doctor prints field-presence booleans; return field/path/line metadata rather than secret values.
4. The helper clears inherited accounts. Optional Webshare access requires the recipient’s explicit proxy enable flag and owned credentials. Keep values out of browser code and source.
5. Android uses a recipient backend selected at build time. Release signing requires the recipient’s keystore and signing values; the original signer is excluded. Native device behavior is a separate acceptance item.
6. Preserve the original player/guide layout and shared backend. The public proxy accepts only server-issued opaque URL tickets. Keep the registry bound, expiring and private when changing playlist rewriting.
7. Original source/runtime and hosted services remain independent. This release’s default catalogue is empty; the first-result command creates only its own local signals.
