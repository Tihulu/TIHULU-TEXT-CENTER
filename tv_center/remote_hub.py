"""Opt-in paired remote media hub. No DVB/SDR device ownership, no Internet bind.

This first server slice exposes a PIN-protected browser, shared host-encoded
HLS for user-approved local files and verified local welle DAB services,
and optional MPRIS control of the existing TIHULU player. It does NOT
re-broadcast DVD, unshared DVB-TS, all desktop windows or arbitrary files.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import mimetypes
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import urlopen

MEDIA_EXTS=frozenset({".mkv",".mp4",".webm",".mov",".avi",".ts",
                      ".mp3",".flac",".wav",".m4a",".ogg",".opus",".aac"})
MPRIS_DEST="org.mpris.MediaPlayer2.tihulu_media_center"
# Pinned KDE Kaffeine v2.0.19 uses MPRIS 1, NOT MPRIS 2.
# Its native Qt DBus objects are /Player, /TrackList and /Television.
MPRIS_INTERFACE="org.freedesktop.MediaPlayer"
MPRIS_PLAYER_PATH="/Player"
MPRIS_TRACKLIST_PATH="/TrackList"
MPRIS_TV_PATH="/Television"

PAGE="""<!doctype html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TIHULU Remote Media Hub</title><style>
body{background:#0b1524;color:#dfedf8;font:16px system-ui;margin:0;padding:1rem;max-width:1050px}
h1{font-size:1.35rem;color:#73d9f0} section{border:1px solid #2d5772;border-radius:12px;margin:12px 0;padding:14px;background:#102537}
button,input{background:#193c51;color:#fff;padding:9px;border:1px solid #477b94;border-radius:7px;max-width:100%}
button{cursor:pointer;margin:3px} button:focus{outline:2px solid #78e4e9}
.item{display:flex;gap:8px;align-items:center;flex-wrap:wrap;border-bottom:1px solid #26485d;padding:7px 0}
video,audio{width:100%;max-height:60vh;background:black}
small{color:#a5c6d4} #caption{min-height:2.5rem;white-space:pre-wrap;text-align:center}
</style></head><body><h1>TIHULU Remote Media Hub</h1>
<section id="login"><label>Pairing PIN from host terminal <input id="pin" type="password" inputmode="numeric" maxlength="8"></label><button onclick="pair()">Pair device</button></section>
<section id="controls" hidden>
<p><button onclick="loadCatalog()">Refresh catalog</button>
<button onclick="command('PlayPause')">Host Play/Pause</button>
<button onclick="command('Stop')">Host Stop</button>
<button onclick="command('Next')">Next</button>
<button onclick="command('Previous')">Previous</button>
<button onclick="stopRemote()">Stop remote stream</button></p>
<p><label>Native TV channel (name or number)
<input id="tvchannel" maxlength="90" placeholder="Channel name or number"></label>
<button onclick="tvTune()">Tune native TV (host)</button></p>
<p><label>Native player volume (0–100)
<input id="volume" type="range" min="0" max="100" value="60"></label>
<button onclick="setVolume()">Apply host volume</button></p>
<label><input id="host" type="checkbox"> Also play on host computer</label>
<p id="status">Remote server connected</p>
<div id="catalog"></div><h2>Verified live DAB services</h2><div id="dab"></div>
</section><section><div style="position:relative"><video controls playsinline id="player"></video>
<div id="caption" aria-live="polite" style="position:absolute;bottom:2.5rem;left:5%;width:90%;
box-sizing:border-box;white-space:pre-wrap;text-align:center;
color:#fff;background:rgba(0,0,0,.72);font-size:1.15rem;pointer-events:none"></div></div>
<p><small>Host performs encoding. Multiple authenticated devices can watch the
same HLS stream. Safari supports HLS natively; on some browsers use VLC
with an authenticated proxy. This is not guaranteed on Firefox without an HLS player.</small></p>
<label>Caption display delay (ms, UI only) <input id="offset" type="number" value="0" min="-20000" max="20000"></label>
</section>
<script>
let csrf='';
async function api(path,body){let r=await fetch(path,{method:body?'POST':'GET',
credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},
body:body?JSON.stringify(body):undefined});let x=await r.json();if(!r.ok)throw Error(x.error||r.status);return x}
async function pair(){try{let x=await api('/api/pair',{pin:document.getElementById('pin').value});
csrf=x.csrf;document.getElementById('login').hidden=true;
document.getElementById('controls').hidden=false;await loadCatalog()}catch(e){alert(e.message)}}
async function statusCheck(){if(!csrf)return;try{let state=await api('/api/status');
document.getElementById('status').textContent=state.state+
 ' · '+state.source+' · '+(state.playlist_ready?'HLS PLAYLIST READY':'waiting for HLS output');
}catch(e){document.getElementById('status').textContent=e.message}}
async function loadCatalog(){try{let x=await api('/api/catalog');let el=document.getElementById('catalog');
el.replaceChildren();for(let m of x.items){let div=document.createElement('div');div.className='item';
let name=document.createElement('span');name.textContent=m.name;let b=document.createElement('button');
b.textContent='Stream';b.onclick=()=>start('file',m.id);div.append(name,b);el.append(div)}
let services=(await api('/api/dab')).items;let dab=document.getElementById('dab');dab.replaceChildren();
for(let m of services){let row=document.createElement('div');row.className='item';
let label=document.createElement('span');label.textContent=m.name+' · '+m.sid;
let b=document.createElement('button');b.textContent='Stream DAB';
b.onclick=()=>start('dab',m.sid);row.append(label,b);dab.append(row)}
}catch(e){document.getElementById('status').textContent=e.message}}
async function start(kind,id){try{let x=await api('/api/start',{kind:kind,id:id,
host:document.getElementById('host').checked});document.getElementById('status').textContent=x.status;
let video=document.getElementById('player');video.src='/hls/stream.m3u8?serial='+x.serial;
video.load();video.play().catch(()=>{}); }catch(e){alert(e.message)}}
async function tvTune(){try{await api('/api/control',{
action:'TVChannel',channel:document.getElementById('tvchannel').value});
await statusCheck()}catch(e){alert(e.message)}}
async function setVolume(){try{await api('/api/control',{
action:'VolumeSet',value:Number(document.getElementById('volume').value)});
}catch(e){alert(e.message)}}
async function stopRemote(){try{await api('/api/stop',{});document.getElementById('player').removeAttribute('src');
document.getElementById('player').load();}catch(e){alert(e.message)}}
async function command(cmd){try{await api('/api/control',{action:cmd})}catch(e){alert(e.message)}}
setInterval(statusCheck,4000);
setInterval(async()=>{if(!csrf)return;try{let x=await api('/api/captions');let el=document.getElementById('caption');
let delay=Number(document.getElementById('offset').value)||0;
if(x.timestamp&&Date.now()-(x.timestamp*1000)<30000){
let now=Date.now();setTimeout(()=>{if(csrf)el.textContent=x.text||''},Math.max(0,Math.min(20000,delay)));
}else{el.textContent=''}
}catch(e){}},3000);
</script></body></html>"""


class RemoteHub:
    def __init__(self,media_root,*,welle_port=None,caption_pid=None,
                 native_pid=None):
        self.root=Path(media_root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Media root must be a directory")
        self.welle_port=welle_port
        self.native_pid=native_pid
        if native_pid is not None and (type(native_pid)!=int or
                not 1<=native_pid<=999999999):
            raise ValueError("Invalid local native player PID")
        if welle_port is not None and (type(welle_port)!=int or not 1024<=welle_port<=65535):
            raise ValueError("Invalid local welle port")
        self.caption_pid=caption_pid if caption_pid is not None else native_pid
        self.pin=f"{secrets.randbelow(100000000):08d}"
        self.sessions={}
        self.failures={}
        self.lock=threading.RLock()
        self.proc=None
        self.started=time.monotonic()
        self.serial=0
        self.current_source="none"
        self.cache=Path(tempfile.mkdtemp(prefix="tihulu-remote-hls-"))
        os.chmod(self.cache,0o700)
        self.files=self._catalog()

    def _catalog(self):
        found={}
        for p in self.root.rglob("*"):
            if len(found)>=500: break
            if not p.is_file() or p.is_symlink() or p.suffix.lower() not in MEDIA_EXTS:
                continue
            if self.root not in p.resolve().parents:
                continue
            token=hashlib.sha256(str(p.relative_to(self.root)).encode()).hexdigest()[:20]
            found[token]=p
        return found

    def active_welle_port(self):
        if self.welle_port:return self.welle_port
        if self.native_pid is None:return None
        runtime=Path(os.environ.get("XDG_RUNTIME_DIR",""))
        if not runtime.is_absolute() or not runtime.is_dir():
            return None
        file=runtime/f"tihulu-welle-{self.native_pid}.port"
        try:
            if file.is_symlink() or file.stat().st_uid!=os.getuid() or (
                    file.stat().st_size>8):
                return None
            number=int(file.read_text().strip())
            return number if 1024<=number<=65535 else None
        except (OSError,ValueError):
            return None

    def dab_services(self):
        port=self.active_welle_port()
        if port is None:return []
        try:
            with urlopen(f"http://127.0.0.1:{port}/mux.json",timeout=2) as r:
                data=json.loads(r.read(250000))
        except (OSError,ValueError,TimeoutError):
            return []
        services=[]
        import re
        for entry in data.get("services",[]):
            if not isinstance(entry,dict):continue
            sid=entry.get("sid","")
            stream=entry.get("url_mp3","")
            if (isinstance(sid,str) and isinstance(stream,str) and
                    re.fullmatch(r"(?:0x)?[A-Fa-f0-9]{1,8}",sid) and
                    re.fullmatch(r"/mp3/[A-Fa-f0-9x]+",stream)):
                label=entry.get("label")
                name=label.get("label") if isinstance(label,dict) else label
                services.append({"sid":sid,"url":stream,
                                 "name":str(name or sid)[:90]})
        return services[:100]

    def play_local(self,url):
        if shutil.which("dbus-send") is None:
            return False
        args=["dbus-send","--session","--print-reply","--reply-timeout=2000",
              "--dest="+MPRIS_DEST,MPRIS_TRACKLIST_PATH,
              MPRIS_INTERFACE+".AddTrack","string:"+url,"boolean:true"]
        try:
            done=subprocess.run(args,stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                timeout=3,check=False)
            return done.returncode==0
        except (OSError,subprocess.TimeoutExpired):
            return False

    def control(self,action,*,channel=None,value=None):
        known={"PlayPause":"Pause","Play":"Play","Pause":"Pause",
               "Stop":"Stop","Next":"Next","Previous":"Prev",
               "VolumeSet":"VolumeSet","TVChannel":"PlayChannel"}
        if action not in known:
            raise ValueError("Invalid native MPRIS control action")
        if shutil.which("dbus-send") is None:
            raise RuntimeError("DBus tools not installed")
        is_tv=action=="TVChannel"
        if is_tv:
            if not isinstance(channel,str) or not 0<len(channel.strip())<=90 or (
                    any(ord(c)<32 for c in channel)):
                raise ValueError("Enter valid native TV channel name or number")
        if action=="VolumeSet":
            if type(value)!=int or not 0<=value<=100:
                raise ValueError("Native volume must be integer 0–100")
        args=["dbus-send","--session","--print-reply","--reply-timeout=2000",
              "--dest="+MPRIS_DEST,
              MPRIS_TV_PATH if is_tv else MPRIS_PLAYER_PATH,
              MPRIS_INTERFACE+"."+known[action]]
        if is_tv:args+=["string:"+channel.strip()]
        elif action=="VolumeSet":args+=["int32:"+str(value)]
        try:
            run=subprocess.run(args,stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                timeout=3,check=False)
        except (OSError,subprocess.TimeoutExpired):
            raise RuntimeError("Native Kaffeine DBus command unavailable")
        if run.returncode:
            raise RuntimeError("Native TIHULU DBus command failed. "
                               "Is the standalone player running on this login?")

    def start(self,kind,identifier,host=False):
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg not installed on host")
        if kind=="file":
            path=self.files.get(identifier)
            if path is None or path.is_symlink() or not path.is_file() or (
                    self.root not in path.resolve().parents):
                raise ValueError("File not in explicitly shared media catalog")
            source=str(path)
            host_source=path.as_uri()
        elif kind=="dab":
            entry=next((e for e in self.dab_services() if e["sid"]==identifier),None)
            if entry is None:
                raise ValueError("DAB service not present in live mux; cannot stream")
            source=f"http://127.0.0.1:{self.active_welle_port()}"+entry["url"]
            host_source=source
        else:
            raise ValueError("Unsupported source type")
        with self.lock:
            self.stop()
            self.serial+=1
            for child in self.cache.iterdir():
                if child.is_file() and child.name.startswith(("stream.","seg_")):
                    child.unlink()
            args=["ffmpeg","-nostdin","-hide_banner","-loglevel","error"]
            if kind=="file":args+=["-re"]
            args+=["-i",source,"-map","0:v:0?","-map","0:a:0?",
                   "-c:v","libx264","-preset","veryfast",
                   "-pix_fmt","yuv420p","-c:a","aac","-b:a","128k",
                   "-f","hls","-hls_time","4","-hls_list_size","8",
                   "-hls_flags","delete_segments+independent_segments",
                   "-hls_segment_filename",str(self.cache/"seg_%06d.ts"),
                   str(self.cache/"stream.m3u8")]
            self.proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.current_source=(str(path.relative_to(self.root)) if kind=="file"
                                 else "DAB "+identifier)
            on_host=self.play_local(host_source) if host else None
            return {"serial":self.serial,"status":"HLS source starting on host; "
                    "local playback "+("requested" if on_host else
                    "not requested or native MPRIS unavailable")}

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc=None
        self.current_source="none"

    def status(self):
        with self.lock:
            state=("idle" if self.proc is None else
                   "encoding on host" if self.proc.poll() is None else
                   "encoder exited (check source or FFmpeg codecs)")
            return {"state":state,"source":self.current_source,
                    "serial":self.serial,
                    "playlist_ready":(self.cache/"stream.m3u8").is_file()}

    def captions(self):
        if self.caption_pid is None:return {}
        path=Path(os.environ.get("XDG_RUNTIME_DIR",""))/(
            f"tihulu-radio-captions-{self.caption_pid}.json")
        try:
            if path.is_symlink() or path.stat().st_uid!=os.getuid() or (
                    path.stat().st_size>15000):return {}
            data=json.loads(path.read_text(encoding="utf-8"))
            original=str(data.get("original",""))[:800]
            translations=data.get("translations",{})
            if not isinstance(translations,dict):translations={}
            text="\n".join([original]+[
                "["+str(k)[:5]+"] "+str(v)[:800]
                for k,v in list(translations.items())[:5]])
            return {"text":text[:3000],"timestamp":data.get("timestamp")}
        except (OSError,ValueError,TypeError):
            return {}

    def close(self):
        with self.lock:
            self.stop()
            shutil.rmtree(self.cache,ignore_errors=True)


def create_handler(hub):
    class Handler(BaseHTTPRequestHandler):
        server_version="TIHULU-Hub/0.1"
        def log_message(self,fmt,*args):
            # Do not log raw PIN, cookie or token-bearing URLs.
            pass
        def send_data(self,code,payload,mime="application/json",headers=None):
            raw=(json.dumps(payload,ensure_ascii=False).encode("utf-8")
                 if mime=="application/json" else payload)
            self.send_response(code)
            self.send_header("Content-Type",mime)
            self.send_header("Content-Length",str(len(raw)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Referrer-Policy","no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'unsafe-inline' 'self'; "
                             "style-src 'unsafe-inline' 'self'; media-src 'self'")
            if headers:
                for k,v in headers.items():self.send_header(k,v)
            self.end_headers()
            self.wfile.write(raw)
        def session(self):
            jar=SimpleCookie()
            try:jar.load(self.headers.get("Cookie",""))
            except Exception:return None
            item=jar.get("tihulu_session")
            if not item:return None
            token=item.value
            with hub.lock:
                current=hub.sessions.get(token)
            return current if current and current["expires"]>time.time() else None
        def require(self,csrf=False):
            session=self.session()
            if not session:
                self.send_data(401,{"error":"Pair with host PIN first"})
                return None
            if csrf and not hmac.compare_digest(
                self.headers.get("X-CSRF-Token",""),session["csrf"]):
                self.send_data(403,{"error":"Bad CSRF token"})
                return None
            return session
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=="/":
                self.send_data(200,PAGE.encode("utf-8"),"text/html; charset=utf-8")
                return
            if not self.require():return
            if path=="/api/catalog":
                items=[{"id":k,"name":str(v.relative_to(hub.root))[:240]}
                       for k,v in hub.files.items()]
                self.send_data(200,{"items":items})
            elif path=="/api/dab":
                self.send_data(200,{"items":[{"sid":e["sid"],"name":e["name"]}
                    for e in hub.dab_services()]})
            elif path=="/api/captions":
                self.send_data(200,hub.captions())
            elif path=="/api/status":
                self.send_data(200,hub.status())
            elif path.startswith("/hls/"):
                name=path.removeprefix("/hls/")
                if not (name=="stream.m3u8" or
                        __import__("re").fullmatch(r"seg_\d{6}\.ts",name)):
                    self.send_data(404,{"error":"Unknown stream object"})
                    return
                file=hub.cache/name
                if not file.is_file() or file.is_symlink():
                    self.send_data(404,{"error":"HLS not ready or segment rotated"})
                    return
                data=file.read_bytes()
                if len(data)>8*1024*1024:
                    self.send_data(413,{"error":"Segment too large"});return
                mime=("application/vnd.apple.mpegurl" if name.endswith(".m3u8")
                      else "video/mp2t")
                self.send_data(200,data,mime)
            else:
                self.send_data(404,{"error":"Unknown route"})
        def do_POST(self):
            length=int(self.headers.get("Content-Length","0") or 0)
            if not 0<length<2500:
                self.send_data(413,{"error":"Invalid request size"});return
            source=self.headers.get("Origin")
            if source and urlsplit(source).netloc!=self.headers.get("Host"):
                self.send_data(403,{"error":"Cross-site request refused"});return
            try:payload=json.loads(self.rfile.read(length))
            except (ValueError,TypeError):
                self.send_data(400,{"error":"Invalid JSON"});return
            if not isinstance(payload,dict):
                self.send_data(400,{"error":"Expected object"});return
            path=urlsplit(self.path).path
            if path=="/api/pair":
                remote=self.client_address[0]
                now=time.monotonic()
                with hub.lock:
                    recent=[x for x in hub.failures.get(remote,[]) if now-x<600]
                    if len(recent)>=5:
                        self.send_data(429,{"error":"Too many pairing attempts"});return
                    if not isinstance(payload.get("pin"),str) or not hmac.compare_digest(
                            payload["pin"],hub.pin):
                        recent.append(now)
                        hub.failures[remote]=recent
                        self.send_data(403,{"error":"Incorrect PIN"});return
                    hub.failures.pop(remote,None)
                    token=secrets.token_urlsafe(32)
                    session={"csrf":secrets.token_urlsafe(24),
                             "expires":time.time()+8*3600}
                    hub.sessions[token]=session
                self.send_data(200,{"csrf":session["csrf"]},headers={
                    "Set-Cookie":"tihulu_session="+token+
                    "; Path=/; HttpOnly; SameSite=Strict"})
                return
            if not self.require(csrf=True):return
            try:
                if path=="/api/start":
                    result=hub.start(payload.get("kind"),payload.get("id"),
                        payload.get("host") is True)
                    self.send_data(200,result)
                elif path=="/api/stop":
                    with hub.lock:hub.stop()
                    self.send_data(200,{"status":"remote stopped"})
                elif path=="/api/control":
                    hub.control(payload.get("action"),
                                channel=payload.get("channel"),value=payload.get("value"))
                    self.send_data(200,{"status":"sent to native MPRIS player"})
                else:self.send_data(404,{"error":"Unknown route"})
            except (RuntimeError,ValueError,OSError) as exc:
                self.send_data(400,{"error":str(exc)[:180]})
    return Handler


def main(argv=None):
    parser=argparse.ArgumentParser(description="Opt-in local paired TIHULU media hub")
    parser.add_argument("--media-root",default=str(Path.home()/"Videos"),
                        help="Explicit directory to share; no arbitrary client paths")
    parser.add_argument("--bind",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8788)
    parser.add_argument("--welle-port",type=int,default=None,
                        help="Already-running local welle port (does NOT own SDR)")
    parser.add_argument("--native-pid",type=int,default=None,
                        help="Existing TIHULU native app PID for attached DAB/AI (no USB access)")
    parser.add_argument("--caption-pid",type=int,default=None,
                        help="Explicit app PID to share radio AI caption JSON")
    parser.add_argument("--unsafe-lan",action="store_true",
                        help="EXPERT: bind without TLS; use HTTPS reverse proxy instead")
    args=parser.parse_args(argv)
    if not 1024<=args.port<=65535:parser.error("Port out of range")
    if args.bind not in ("127.0.0.1","::1","localhost") and not args.unsafe_lan:
        parser.error("Non-loopback bind requires --unsafe-lan; prefer Tailscale HTTPS Serve")
    hub=RemoteHub(args.media_root,welle_port=args.welle_port,
                  caption_pid=args.caption_pid,native_pid=args.native_pid)
    server=ThreadingHTTPServer((args.bind,args.port),create_handler(hub))
    print(f"TIHULU Remote Hub: http://{args.bind}:{args.port}",flush=True)
    print("Pairing PIN (host terminal only): "+hub.pin,flush=True)
    print("Only user-approved media folder and VERIFIED local DAB; "
          "no DVB tuner stealing, no universal TV/DVD mirroring.",flush=True)
    try:server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:pass
    finally:
        server.server_close()
        hub.close()
    return 0

if __name__=="__main__":
    raise SystemExit(main())
