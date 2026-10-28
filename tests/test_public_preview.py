import asyncio
import unittest
from tools.public_preview import PublicPreview

def request(path,method='GET',content_type=b'text/html',body=b'fetch("/v1/status")',status=200,headers=()):
    called=[];sent=[]
    async def app(scope,receive,send):
        called.append(scope['path'])
        await send({'type':'http.response.start','status':status,'headers':[(b'content-type',content_type),*headers]})
        await send({'type':'http.response.body','body':body})
    async def sink(message):sent.append(message)
    asyncio.run(PublicPreview(app,'/apps/cancha')({'type':'http','path':path,'method':method},None,sink))
    return called,sent

class PublicPreviewTests(unittest.TestCase):
    def test_scoped_html_and_playlists(self):
        called,sent=request('/apps/cancha/watch');self.assertEqual(called,['/watch']);self.assertIn(b'/apps/cancha/v1/status',sent[-1]['body'])
        _,sent=request('/apps/cancha/v1/local-test-signal/dvr.m3u8',content_type=b'application/vnd.apple.mpegurl',body=b'#EXTM3U\n/v1/local-test-signal/dvrseg/1.ts')
        self.assertIn(b'/apps/cancha/v1/local-test-signal/dvrseg/1.ts',sent[-1]['body'])
    def test_restrictions_and_redirect(self):
        for path,method in [('/v1/status','GET'),('/apps/cancha/api','GET'),('/apps/cancha/v1/local-test-signal/swap','POST'),('/apps/cancha/v1/other/warm','POST'),('/apps/cancha/watch','DELETE')]:
            called,sent=request(path,method);self.assertFalse(called);self.assertIn(sent[0]['status'],(403,404))
        called,_=request('/apps/cancha/v1/local-test-signal/warm','POST');self.assertTrue(called)
        _,sent=request('/apps/cancha/',content_type=b'',body=b'',status=302,headers=[(b'location',b'/watch')]);self.assertIn((b'location',b'/apps/cancha/watch'),sent[0]['headers'])
