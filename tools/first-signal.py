#!/usr/bin/env python3
"""Generate an authored HLS signal and run the original Cancha server on loopback."""
from __future__ import annotations
import argparse,contextlib,hashlib,http.server,importlib.metadata,json,os,shutil,socket,subprocess,sys,tempfile,threading,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def private_runtime():
    runtime=Path(tempfile.mkdtemp(prefix='cancha-signal-'));runtime.chmod(0o700)
    for name in ['media','state','logos']:(runtime/name).mkdir(mode=0o700)
    return runtime

def make_signal(media):
    sources=[('', 'testsrc2=size=640x360:rate=25', 'local-test-signal'), ('grid', 'testsrc=size=640x360:rate=25', 'local-grid-test'), ('bars', 'smptebars=size=640x360:rate=25', 'local-bars-test')]
    for name,source,channel_id in sources:
        destination=media/name;destination.mkdir(exist_ok=True)
        command=['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',source,'-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','20','-c:v','libx264','-threads','1','-preset','ultrafast','-pix_fmt','yuv420p','-g','50','-sc_threshold','0','-c:a','aac','-b:a','64k','-hls_time','2','-hls_list_size','0','-hls_flags','independent_segments','-hls_segment_filename',str(destination/'signal-%03d.ts'),'-f','hls',str(destination/'signal.m3u8')]
        result=subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=60)
        if result.returncode:raise RuntimeError('Local FFmpeg signal generation failed.')
        poster=['ffmpeg','-hide_banner','-loglevel','error','-i',str(destination/'signal.m3u8'),'-frames:v','1','-vf','scale=320:180','-threads','1',str(media.parent/'logos'/(channel_id+'.png'))]
        if subprocess.run(poster,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=20).returncode:raise RuntimeError('Local signal frame extraction failed.')

class QuietMediaHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
    def copyfile(self,source,outputfile):
        try: super().copyfile(source,outputfile)
        except (BrokenPipeError,ConnectionResetError): pass

def get(url, *, json_data=False):
    with urllib.request.urlopen(url,timeout=5) as response:data=response.read()
    return json.loads(data) if json_data else data

def wait_for(check, *, deadline=60):
    end=time.monotonic()+deadline
    while time.monotonic()<end:
        try:
            value=check()
            if value:return value
        except (OSError,ValueError,KeyError):pass
        time.sleep(0.1)
    raise RuntimeError('The local signal did not reach its readiness barrier.')

def serve_and_prove(runtime, *, serve=False, capture=None):
    import functools
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    media_server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietMediaHandler,directory=str(runtime/'media')))
    media_thread=threading.Thread(target=media_server.serve_forever,daemon=True);media_thread.start()
    feed='http://127.0.0.1:'+str(media_server.server_port)
    catalog=runtime/'catalog.yaml'
    catalog.write_text('channels:\n  - id: local-test-signal\n    name: Cancha test signal\n    country: MX\n    type: Cultura\n    number: 1\n    tags: [authored, local-test]\n    mirrors:\n      - url: '+feed+'/signal.m3u8\n        source: Authored local HLS\n      - url: '+feed+'/unavailable.m3u8\n        source: Authored unavailable-mirror test\n')
    with catalog.open('a') as handle:
        handle.write('  - id: local-grid-test\n    name: Grid test\n    country: MX\n    type: Cultura\n    number: 2\n    mirrors:\n      - url: '+feed+'/grid/signal.m3u8\n        source: Authored local grid\n  - id: local-bars-test\n    name: Bars test\n    country: PE\n    type: Cultura\n    number: 3\n    mirrors:\n      - url: '+feed+'/bars/signal.m3u8\n        source: Authored local bars\n')
    catalog.chmod(0o600)
    # This process uses only its generated local inputs; inherited service accounts stay out.
    for name in list(os.environ):
        if any(part in name.upper() for part in ['KEY','TOKEN','SECRET','PASSWORD','WEBSHARE']) or name.upper().endswith('_PROXY'):os.environ.pop(name,None)
    os.environ.update({'CANCHA_CATALOG':str(catalog),'CANCHA_LOGO_DIR':str(runtime/'logos'),'CANCHA_HOST':'127.0.0.1','CANCHA_PORT':str(port),'CANCHA_STATE_DIR':str(runtime/'state'),'CANCHA_DVR_DIR':str(runtime/'state/dvr'),'CANCHA_THUMB_DIR':str(runtime/'state/thumbs'),'CANCHA_SNAPSHOT':str(runtime/'state/snapshot.json'),'CANCHA_ENABLE_PROXY':'0','CANCHA_MAX_TRANSCODE':'1'})
    attempts=[];allowed_ports={port,media_server.server_port}
    original_connect=socket.socket.connect;original_dns=socket.getaddrinfo
    def checked_connect(connection,address):
        if connection.family in {socket.AF_INET,socket.AF_INET6}:
            if address[0] not in {'127.0.0.1','::1'} or address[1] not in allowed_ports:
                attempts.append('unconfigured-destination');raise OSError('Local proof permits only its own two services.')
        return original_connect(connection,address)
    def checked_dns(host,*args,**kwargs):
        if host not in {'127.0.0.1','::1','localhost',None}:
            attempts.append('unconfigured-host');raise OSError('Local proof permits loopback names.')
        return original_dns(host,*args,**kwargs)
    socket.socket.connect=checked_connect;socket.getaddrinfo=checked_dns
    import uvicorn
    from server import main
    server=uvicorn.Server(uvicorn.Config(main.app,host='127.0.0.1',port=port,log_level='error',loop='asyncio',access_log=False))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start();base='http://127.0.0.1:'+str(port)
    try:
        status=wait_for(lambda:get(base+'/v1/status',json_data=True))
        assert feed not in json.dumps(status)
        master=get(base+'/v1/local-test-signal/master.m3u8').decode()
        assert '#EXTM3U' in master and feed not in master
        def buffered():
            data=get(base+'/v1/local-test-signal/dvr.m3u8').decode()
            return data if '#EXTINF:' in data else None
        playlist=wait_for(buffered)
        media_path=next(line.strip() for line in playlist.splitlines() if line.strip() and not line.startswith('#'))
        segment=get(urllib.request.urljoin(base,media_path));assert len(segment)>1000
        rejected=0
        import base64
        forged=base64.urlsafe_b64encode(b'http://127.0.0.1/private-unissued-target').decode().rstrip('=')
        mirror_id=main.CATALOG.channels[0].mirrors[0].mirror_id()
        try:get(base+'/v1/local-test-signal/'+mirror_id+'/v/'+forged)
        except urllib.error.HTTPError as error:rejected=error.code
        assert rejected==400
        assert not attempts
        receipt={'python_network_attempts_outside_fixture':0,'source_pin':'dbac69422281b857b9425ee01bb1876ddbdb7c2c','media':'Three independently generated local FFmpeg test signals and tones, 20 seconds each.','actual_stages':['catalogue load','real mirror probes','original master rewrite','original DVR recorder','local buffered segment delivery','unissued proxy-target rejection'],'buffered_segment_bytes':len(segment),'forged_ticket_status':rejected,'provider_model_calls':0,'remote_streams':0,'runtime':{name:importlib.metadata.version(name) for name in ['fastapi','uvicorn','aiohttp','PyYAML']},'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['server/main.py','server/proxy.py','server/tickets.py','server/dvr.py','server/catalog.py','server/prober.py','server/web.py','tools/first-signal.py']}}
        if capture:
            from playwright.sync_api import sync_playwright
            output=Path(capture);output.mkdir(parents=True,exist_ok=True);foreign=[];errors=[];shots=[]
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,args=['--autoplay-policy=no-user-gesture-required'])
                for label,width,height in [('desktop',1600,1000),('phone',390,844)]:
                    context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=1)
                    def route(r):
                        from urllib.parse import urlsplit
                        if urlsplit(r.request.url).netloc!=urlsplit(base).netloc:foreign.append(urlsplit(r.request.url).hostname);r.abort()
                        else:r.continue_()
                    context.route('**/*',route);page=context.new_page();page.on('pageerror',lambda e:errors.append(type(e).__name__))
                    page.goto(base+'/watch',wait_until='domcontentloaded')
                    tile=page.locator('.tile').filter(has_text='Cancha test signal').filter(visible=True).first
                    tile.wait_for(state='visible');page.evaluate('document.fonts.ready')
                    filename='cancha-browse-'+label+'.png';page.screenshot(path=str(output/filename),full_page=False,animations='disabled')
                    shots.append({'path':filename,'scene':'native catalogue','viewport':{'width':width,'height':height},'sha256':hashlib.sha256((output/filename).read_bytes()).hexdigest()})
                    tile.click()
                    page.wait_for_function('Array.from(document.querySelectorAll("video")).some(v => v.readyState >= 2 && v.currentTime > 1)',timeout=30000)
                    page.evaluate('document.fonts.ready');filename='cancha-signal-'+label+'.png';page.screenshot(path=str(output/filename),full_page=False,animations='disabled')
                    shots.append({'path':filename,'viewport':{'width':width,'height':height},'decoded_video':True,'sha256':hashlib.sha256((output/filename).read_bytes()).hexdigest()});context.close()
                browser.close()
            assert not foreign and not errors
            receipt['browser']={'captures':shots,'foreign_requests':0,'page_errors':0,'decoded_local_video':True}
            (output/'proof.json').write_text(json.dumps(receipt,indent=2)+'\n')
        assert not attempts
        receipt_path=runtime/'first-signal.json';receipt_path.write_text(json.dumps(receipt,indent=2)+'\n');receipt_path.chmod(0o600)
        print(json.dumps({'receipt':str(receipt_path),'preview':base+'/watch','buffered_segment_bytes':len(segment),'provider_model_calls':0,'remote_streams':0,'forged_ticket_status':rejected}),flush=True)
        if serve:
            print('The local player is ready. Press Ctrl-C to stop.',flush=True)
            try:
                while thread.is_alive():time.sleep(0.5)
            except KeyboardInterrupt:pass
    finally:
        server.should_exit=True;thread.join(timeout=15);media_server.shutdown();media_server.server_close();sock.close()
        socket.socket.connect=original_connect;socket.getaddrinfo=original_dns

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--serve',action='store_true');parser.add_argument('--capture');args=parser.parse_args()
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):raise SystemExit('Install FFmpeg and FFprobe to generate and inspect the local signal.')
    runtime=private_runtime();make_signal(runtime/'media');serve_and_prove(runtime,serve=args.serve,capture=args.capture)

if __name__=='__main__':main()
