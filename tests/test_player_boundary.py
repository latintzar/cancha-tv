import asyncio,base64,json,time,unittest
from fastapi import HTTPException
from server import main
from server.models import Catalog,Channel,Mirror

class PlayerBoundaryTests(unittest.TestCase):
 def setUp(self):
  self.old=main.CATALOG
  self.mirror=Mirror('https://stream.example.invalid/feed.m3u8?access=synthetic_fixture',last_score=100,last_probe_at=time.time(),last_error='upstream-unavailable')
  main.CATALOG=Catalog([Channel(id='authored',name='Authored channel',country='MX',mirrors=[self.mirror])])
 def tearDown(self):main.CATALOG=self.old
 def test_unissued_variant_rejected_before_fetch(self):
  fake=base64.urlsafe_b64encode(b'http://127.0.0.1/unissued').decode().rstrip('=')
  with self.assertRaises(HTTPException) as caught:asyncio.run(main.variant_playlist('authored',self.mirror.mirror_id(),fake))
  self.assertEqual(caught.exception.status_code,400)
 def test_status_keeps_upstream_private(self):
  response=asyncio.run(main.status(main.Response()));body=response.body.decode() if hasattr(response,'body') else json.dumps(response)
  self.assertNotIn('synthetic_fixture',body);self.assertNotIn(self.mirror.url,body)
 def test_ticket_is_required_for_segments(self):
  with self.assertRaises(HTTPException) as caught:asyncio.run(main.segment_proxy('authored',self.mirror.mirror_id(),'unissued',None))
  self.assertEqual(caught.exception.status_code,400)
 def test_variant_failure_keeps_upstream_details_private(self):
  from server.proxy import b64url_encode
  previous=main._upstream_get_text
  async def failed(*args,**kwargs):raise RuntimeError('synthetic_private_upstream_detail')
  main._upstream_get_text=failed
  try:
   with self.assertRaises(HTTPException) as caught:asyncio.run(main.variant_playlist('authored',self.mirror.mirror_id(),b64url_encode(self.mirror.url)))
   self.assertNotIn('synthetic_private_upstream_detail',str(caught.exception.detail))
  finally:main._upstream_get_text=previous
 def test_master_failure_keeps_upstream_details_private(self):
  previous=main._upstream_get_text
  async def failed(*args,**kwargs):raise RuntimeError('synthetic_private_upstream_detail')
  main._upstream_get_text=failed;main._MASTER_CACHE.clear()
  try:
   request=main.Request({'type':'http','scheme':'http','server':('127.0.0.1',1),'path':'/v1/authored/master.m3u8','root_path':'','headers':[],'method':'GET','query_string':b''})
   with self.assertRaises(HTTPException) as caught:asyncio.run(main.channel_master('authored',request))
   self.assertNotIn('synthetic_private_upstream_detail',str(caught.exception.detail))
  finally:main._upstream_get_text=previous

if __name__=='__main__':unittest.main()
