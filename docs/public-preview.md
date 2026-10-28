# Authored public preview

Run the original player and DVR against three locally generated 20-second HLS test signals:

```sh
python3 tools/first-signal.py --serve --port 18541 --prefix /apps/cancha
```

Proxy `/apps/cancha/` to the loopback listener without stripping the prefix. The player is at `/apps/cancha/watch`. The optional prefix adapter admits the three authored channels, their native playback, assets, and bounded warm operation; it rejects mirror swaps and other writes. Source media and process state are generated in a private temporary directory. Set `TMPDIR` to a service-owned runtime directory for automatic cleanup by the service manager. Only the generated local feeds are used, and inherited provider credentials are cleared. The three authored 20-second examples repeat as bounded live HLS streams, so the original DVR and mirror checks keep running.

Run `python3 tools/first-signal.py --prefix /apps/cancha --capture /tmp/cancha-preview-proof` for the prefixed media and browser proof. The default command without `--prefix` retains its local recipient behavior.
