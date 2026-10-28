import re,unittest
from server.proxy import rewrite_master,rewrite_variant,b64url_decode
from server.models import Channel,Mirror
from server.dvr import _parse_media

class HlsContractTests(unittest.TestCase):
 def test_relative_variant_is_issued_opaque_reference(self):
  text='#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1000000\nvideo/main.m3u8\n';rewritten=rewrite_master(text,'https://stream.example.invalid/root/master.m3u8','authored','mirror')
  path=next(x for x in rewritten.splitlines() if x and not x.startswith('#'));token=path.rsplit('/',1)[1]
  self.assertEqual(b64url_decode(token),'https://stream.example.invalid/root/video/main.m3u8');self.assertNotIn('stream.example.invalid',rewritten)
 def test_segments_and_key_uris_stay_server_owned(self):
  text='#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key.bin"\n#EXTINF:2,\nsegment.ts?access=synthetic_fixture\n';rewritten=rewrite_variant(text,'https://stream.example.invalid/root/main.m3u8','authored','mirror')
  self.assertNotIn('synthetic_fixture',rewritten);self.assertNotIn('key.bin',rewritten)
  paths=re.findall(r'(?:URI=")?(/v1/[^"\n]+)',rewritten);urls=[b64url_decode(x.rsplit('/',1)[1]) for x in paths]
  self.assertIn('https://stream.example.invalid/root/key.bin',urls);self.assertIn('https://stream.example.invalid/root/segment.ts?access=synthetic_fixture',urls)
 def test_original_media_parser_retains_segment_duration(self):
  target,segments=_parse_media('#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:2.25,\na.ts\n#EXTINF:4.5,\nb.ts\n')
  self.assertEqual(target,6);self.assertEqual(segments,[('a.ts',2.25),('b.ts',4.5)])
 def test_health_selection_obeys_cooldown(self):
  high=Mirror('https://stream.example.invalid/high',last_score=90,sick_until=100);low=Mirror('https://stream.example.invalid/low',last_score=50)
  channel=Channel('authored','Authored','MX',mirrors=[high,low]);self.assertIs(channel.best_mirror(99),low);self.assertIs(channel.best_mirror(101),high)

if __name__=='__main__':unittest.main()
