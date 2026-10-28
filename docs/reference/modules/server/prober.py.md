# server/prober.py

[Source](../../../../server/prober.py)

| Function or type | Line | Parameters |
|---|---:|---|
| `_parse_master` | [L36](../../../../server/prober.py#L36) | text |
| `_parse_media` | [L62](../../../../server/prober.py#L62) | text |
| `_parse_fps` | [L82](../../../../server/prober.py#L82) | rate_str |
| `_score` | [L93](../../../../server/prober.py#L93) | m, target_dur, avg_fetch_ms |
| `_fetch_text` | [L115](../../../../server/prober.py#L115) | session, url, proxy, proxy_auth |
| `_fetch_bytes` | [L129](../../../../server/prober.py#L129) | session, url, max_bytes, proxy, proxy_auth |
| `_ffprobe_sync` | [L144](../../../../server/prober.py#L144) | path |
| `probe_mirror` | [L156](../../../../server/prober.py#L156) | mirror, session |
| `probe_catalog` | [L253](../../../../server/prober.py#L253) | catalog |
| `capture_thumb_via_self` | [L266](../../../../server/prober.py#L266) | channel, out_path |
| `capture_thumb` | [L288](../../../../server/prober.py#L288) | channel, mirror, out_path, session |
| `thumb_loop` | [L357](../../../../server/prober.py#L357) | catalog, thumb_dir |
| `prober_loop` | [L397](../../../../server/prober.py#L397) | catalog, snapshot_path |
| `worker` | [L258](../../../../server/prober.py#L258) | m |
| `worker` | [L367](../../../../server/prober.py#L367) | ch |
