"""Read-only prefix adapter for the authored Cancha preview.

The only POST admitted is the native warm operation for an authored channel;
it starts a bounded local recorder. All upstream origins are fixture loopback.
"""
import re

CHANNELS=('local-test-signal','local-grid-test','local-bars-test')
TEXT_PREFIXES=('/v1/','/brand/','/webfont/','/vendor/','/flag/','/logo/','/thumb/','/watch')

class PublicPreview:
    def __init__(self,app,prefix):
        if not re.fullmatch(r'/[a-z0-9-]+(?:/[a-z0-9-]+)*',prefix):
            raise ValueError('Prefix must be a nonempty absolute path without a trailing slash')
        self.app=app;self.prefix=prefix
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        path=scope['path'];method=scope['method']
        if path==self.prefix:path='/'
        elif path.startswith(self.prefix+'/'):path=path[len(self.prefix):]
        else:return await self.reject(send,404)
        channel='|'.join(CHANNELS)
        get_allowed=(path in ("/native-nav/atelier-nav.js","/native-nav/atelier-nav.css","/native-nav/atelier-inset.css", '/','/watch','/v1/status','/favicon.ico') or
            re.fullmatch(r'/(?:brand|webfont|vendor|flag|logo|thumb)/[^/]+',path) or
            re.fullmatch(r'/v1/(?:'+channel+r')/(?:master\.m3u8|dvr\.m3u8|dvr/status|dvrseg/[^/]+|[^/]+/[vs]/[^/]+)',path))
        warm_allowed=method=='POST' and re.fullmatch(r'/v1/(?:'+channel+r')/warm',path)
        if not ((method in ('GET','HEAD') and get_allowed) or warm_allowed):return await self.reject(send,403)
        scope=dict(scope,path=path,raw_path=path.encode('utf-8'),root_path='')
        started=None;body=[];is_text=False
        async def rewrite(message):
            nonlocal started,is_text
            if message['type']=='http.response.start':
                started=message
                headers=message.get('headers',[])
                ctype=next((v.decode('latin1').lower() for k,v in headers if k.lower()==b'content-type'),'')
                is_text=any(t in ctype for t in ('text/html','application/json','mpegurl','text/plain'))
                if not is_text:
                    headers=[(k,self.prefix.encode()+v if k.lower()==b'location' and v.startswith(b'/') else v) for k,v in headers]
                    await send(dict(message,headers=headers));started=None
                return
            if message['type']!='http.response.body':return await send(message)
            if not is_text:return await send(message)
            body.append(message.get('body',b''))
            if message.get('more_body',False):return
            data=b''.join(body)
            for token in TEXT_PREFIXES:data=data.replace(token.encode(),(self.prefix+token).encode())
            headers=[]
            for key,value in started.get('headers',[]):
                if key.lower()==b'content-length':continue
                if key.lower()==b'location' and value.startswith(b'/'):value=self.prefix.encode()+value
                headers.append((key,value))
            headers.append((b'content-length',str(len(data)).encode()))
            await send(dict(started,headers=headers));await send({'type':'http.response.body','body':data})
        await self.app(scope,receive,rewrite)
    @staticmethod
    async def reject(send,status):
        await send({'type':'http.response.start','status':status,'headers':[(b'content-type',b'text/plain'),(b'content-length',b'0')]})
        await send({'type':'http.response.body','body':b''})
