# server/dvr.py

[Source](../../../../server/dvr.py)

| Function or type | Line | Parameters |
|---|---:|---|
| `Seg` | [L44](../../../../server/dvr.py#L44) |  |
| `DvrChannel` | [L52](../../../../server/dvr.py#L52) |  |
| `_parse_master` | [L72](../../../../server/dvr.py#L72) | text |
| `_parse_media` | [L90](../../../../server/dvr.py#L90) | text |
| `DvrManager` | [L129](../../../../server/dvr.py#L129) |  |
| `total_duration` | [L68](../../../../server/dvr.py#L68) | self |
| `__init__` | [L130](../../../../server/dvr.py#L130) | self, catalog, session_factory |
| `close` | [L138](../../../../server/dvr.py#L138) | self |
| `needs_transcode_cached` | [L147](../../../../server/dvr.py#L147) | self, cid |
| `start` | [L152](../../../../server/dvr.py#L152) | self |
| `_janitor` | [L156](../../../../server/dvr.py#L156) | self |
| `_stop` | [L164](../../../../server/dvr.py#L164) | self, cid |
| `touch` | [L180](../../../../server/dvr.py#L180) | self, cid, play |
| `_record` | [L202](../../../../server/dvr.py#L202) | self, ch, dvr |
| `_prune` | [L285](../../../../server/dvr.py#L285) | self, dvr |
| `_get` | [L294](../../../../server/dvr.py#L294) | self, session, url, proxy, proxy_auth |
| `_audio_codec_sync` | [L306](../../../../server/dvr.py#L306) | data |
| `_to_aac_sync` | [L318](../../../../server/dvr.py#L318) | data |
| `_audio_codec` | [L332](../../../../server/dvr.py#L332) | self, data |
| `_to_aac` | [L335](../../../../server/dvr.py#L335) | self, data |
| `_get_bytes` | [L338](../../../../server/dvr.py#L338) | self, session, url, proxy, proxy_auth |
| `_codecs_sync` | [L368](../../../../server/dvr.py#L368) | data |
| `_codecs` | [L387](../../../../server/dvr.py#L387) | self, data |
| `_needs_transcode` | [L390](../../../../server/dvr.py#L390) | self, ch |
| `_ffmpeg_proxy_url` | [L424](../../../../server/dvr.py#L424) | cc |
| `_record_ffmpeg` | [L436](../../../../server/dvr.py#L436) | self, ch, dvr |
| `_rewrite_ff` | [L545](../../../../server/dvr.py#L545) | self, cid, text |
| `playlist` | [L558](../../../../server/dvr.py#L558) | self, cid |
| `seg_path` | [L588](../../../../server/dvr.py#L588) | self, cid, filename |
| `status` | [L598](../../../../server/dvr.py#L598) | self, cid |
