"""Explicit DVB-T/T2/C live TV and lossless TS recording, Hauppauge hardware-gated.

Config file is operator-provided via TIHULU_DVB_CHANNELS_FILE after real
dvbv5-scan. No implicit scan or tuning on app startup. This uses a separate
DVB frontend and a local cooperative lease; it NEVER owns the RTL-SDR.
Physical device/driver acceptance is still required.
"""
from __future__ import annotations
import configparser
from datetime import datetime,timezone
import fcntl
import os
from pathlib import Path
import queue
import re
import selectors
import shutil
import signal
import subprocess
from threading import Thread
import time
import uuid

from .caption_live import LiveCaptionRunner,prepare_caption_options
from .dvb_hardware import diagnose_dvb
from .radio_live import (LiveRadio,LiveRadioError,MAX_IDLE_WITHOUT_LISTENER,
                         MAX_LIVE_SECONDS)
from .core import utc_now

MAX_TV_RECORDING=2*1024*1024*1024
MAX_CHANNEL_CONFIG=1_000_000
DVB_LOCK_NAME="dvb_frontend0.lock"


def tv_channels(path:Path|None=None)->dict:
    filename=path or os.environ.get("TIHULU_DVB_CHANNELS_FILE","")
    if not filename:return {"ready":False,"channels":[],"reason":"Set TIHULU_DVB_CHANNELS_FILE to a real dvbv5-scan channel list"}
    file=Path(filename).expanduser()
    try:
        if file.is_symlink() or not file.is_file() or file.stat().st_size>MAX_CHANNEL_CONFIG:
            raise ValueError("Invalid or oversized channel file")
        contents=file.read_text(encoding="utf-8")
    except (OSError,UnicodeError,ValueError):
        return {"ready":False,"channels":[],"reason":"Configured DVB channel file unreadable or unsafe"}
    parser=configparser.ConfigParser(interpolation=None,strict=False)
    parser.optionxform=str
    try:parser.read_string(contents)
    except configparser.Error:
        return {"ready":False,"channels":[],"reason":"DVB file is not a valid sectioned channels.conf"}
    channels=[]
    for name in parser.sections()[:150]:
        if not name.strip() or len(name)>160:continue
        data=parser[name]
        if "FREQUENCY" not in data or "DELIVERY_SYSTEM" not in data:continue
        channels.append({"name":name,"delivery":data.get("DELIVERY_SYSTEM","")[:40],
                         "frequency":data.get("FREQUENCY","")[:30]})
    return {"ready":bool(channels),"channels":channels,
            "reason":"Operator-provided channels; service still requires real DVB tuning",
            "channel_file":str(file) if channels else None}


def tv_conflicts(*,proc_root:Path=Path("/proc"))->list[dict]:
    known={"tvheadend","kaffeine","dvbv5-zap","vlc","mpv","mplayer","mythbackend","me-tv"}
    found=[]
    try:processes=[p for p in proc_root.iterdir() if p.name.isdigit()][:2048]
    except OSError:return found
    for path in processes:
        if int(path.name)==os.getpid():continue
        try:name=(path/"comm").read_text().strip()[:48]
        except OSError:continue
        if name.lower() in known:
            found.append({"process":name,"pid":int(path.name)})
    return found[:20]


def zap_command(executable:str, channels_file:str, service:str)->list[str]:
    if not service or len(service)>160 or any(c in "\x00\r\n" for c in service):
        raise ValueError("Invalid DVB service")
    return [executable,"-a","0","-f","0","-c",channels_file,
            "-r","-P",service]


def tv_ffmpeg_command(exe:str,*,audio_fd:int|None=None)->list[str]:
    # H.264 Baseline + AAC in fragmented ISO-BMFF for browser MSE,
    # 480p low-energy default to limit costly HEVC/1080i transcodes on Pi.
    args=[exe,"-hide_banner","-loglevel","error","-nostdin",
          "-fflags","+genpts+discardcorrupt","-f","mpegts","-i","pipe:0",
          "-map","0:v:0","-map","0:a:0?",
          "-vf","scale=w=854:h=-2:flags=fast_bilinear",
          "-c:v","libx264","-preset","ultrafast","-tune","zerolatency",
          "-profile:v","baseline","-pix_fmt","yuv420p",
          "-g","48","-c:a","aac","-b:a","96k",
          "-movflags","frag_keyframe+empty_moov+default_base_moof",
          "-f","mp4","pipe:1"]
    if audio_fd is not None:
        args += ["-map","0:a:0","-ar","32000","-ac","1",
                 "-f","s16le",f"pipe:{audio_fd}"]
    return args


class LiveTV(LiveRadio):
    def __init__(self,store,*,diagnose=None,channels=None,lookup=None,
                 conflicts=None,lock_dir=None,record_dir=None,
                 compute=None,asr_factory=None,translator=None):
        super().__init__(store,lookup=lookup or shutil.which,
            lock_dir=lock_dir or store.filename.parent/".receiver-locks",
            record_dir=record_dir or store.filename.parent/"tv_recordings",
            compute=compute,asr_factory=asr_factory,translator=translator)
        self.diagnose=diagnose or diagnose_dvb
        self.channel_list=channels or tv_channels
        self.tv_conflicts=conflicts or tv_conflicts
        self._state["service"]=None

    def availability(self):
        device=self.diagnose()
        if not device["model_confirmed"] or not device["dvb_frontends"]:
            return {"ready":False,
                    "reason":"Hauppauge WinTV-soloHD not yet confirmed with a working DVB frontend"}
        if not self.lookup("dvbv5-zap") or not self.lookup("ffmpeg"):
            return {"ready":False,"reason":"Install dvbv5-zap (dvb-tools) and ffmpeg"}
        if not self.lookup("ffmpeg"):
            return {"ready":False,"reason":"FFmpeg video decoder/encoder not installed"}
        conf=self.channel_list()
        if not conf["ready"]:
            return {"ready":False,"reason":conf["reason"]}
        busy=self.tv_conflicts()
        if busy:
            return {"ready":False,"reason":"Other TV app/recording may own DVB tuner: "+
                    ", ".join(sorted({x["process"] for x in busy}))}
        return {"ready":True,
                "reason":"DVB service tuning can be attempted with explicitly selected channel",
                "services":len(conf["channels"])}

    def _lock(self):
        self.lock_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
        os.chmod(self.lock_dir,0o700)
        fd=os.open(self.lock_dir/DVB_LOCK_NAME,
            os.O_CREAT|os.O_RDWR|os.O_CLOEXEC|getattr(os,"O_NOFOLLOW",0),0o600)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise LiveRadioError("A cooperating DVB capture already owns the tuner")
        self._lock_fd=fd

    def channel_status(self):
        return {"hardware":self.diagnose(),"channel_list":self.channel_list(),
                "capability":self.availability(),
                "stream":self.status()}

    def start(self,*,service:str,record:object=False,captions:dict|None=None):
        if type(record) is not bool:raise ValueError("Recording consent must be Boolean")
        conf=self.channel_list()
        if not conf["ready"]:raise LiveRadioError(conf["reason"])
        if service not in {x["name"] for x in conf["channels"]}:
            raise ValueError("Select a channel from the real configured DVB channel list")
        opts=prepare_caption_options(captions or {},self.compute() if self.compute else None)
        with self._mutex:
            if self._state["active"]:raise LiveRadioError("TV stream already running")
            ready=self.availability()
            if not ready["ready"]:raise LiveRadioError(ready["reason"])
            self._lock()
            try:
                if self.tv_conflicts():raise LiveRadioError("TV frontend became busy before tuning")
                self._captions=(
                    LiveCaptionRunner(self.archive,opts,
                       source_label=f"DVB TV {service}",
                       media_kind="dvb_tv",
                       asr_factory=self.asr_factory,translator=self.translator)
                    if opts["enabled"] else None
                )
                self._stop.clear();self._client=False;self._client_last=time.monotonic()
                self._chunks=queue.Queue(maxsize=128)
                token=uuid.uuid4().hex
                id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+token
                self._state={
                    "status":"starting","active":True,"frequency_hz":None,
                    "service":service,"session":token,
                    "record":record,"recording_id":id if record else None,
                    "started_at":utc_now(),"ended_at":None,
                    "stream_clients":0,"bytes_encoded":0,"recorded_bytes":0,
                    "error":None,"caption_enabled":opts["enabled"],
                    "source_status":"DVB service pending actual transport stream",
                }
                self._thread=Thread(target=self._run_tv,
                    args=(service,conf["channel_file"],id if record else None),
                    daemon=True,name="tihulu-dvb-live")
                self._thread.start()
                return self._snapshot()
            except BaseException:
                self._unlock()
                self._state["active"]=False
                self._state["status"]="error"
                raise

    def recordings(self):
        try:paths=sorted(self.record_dir.glob("*.ts"),reverse=True)[:100]
        except OSError:paths=[]
        result=[]
        for path in paths:
            try:
                if path.is_symlink() or not path.is_file():continue
                size=path.stat().st_size
                if 0<size<=MAX_TV_RECORDING:
                    result.append({"id":path.stem,"name":path.name,
                                   "bytes":size,"mime":"video/mp2t"})
            except OSError:pass
        return result

    def recording_path(self,ident:str)->Path|None:
        if not isinstance(ident,str) or not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z_[0-9a-f]{32}",ident):
            return None
        path=self.record_dir/(ident+".ts")
        try:
            if path.is_symlink() or not path.is_file():return None
            if not (1<=path.stat().st_size<=MAX_TV_RECORDING):return None
        except OSError:return None
        return path

    def _run_tv(self,service:str,channels_file:str,rec_id:str|None):
        zap=None;enc=None;record_file=None;dvr_fd=None;pipe=None;audio_pipe=None;audio_thread=None
        failure=None
        try:
            if self.tv_conflicts():raise LiveRadioError("DVB frontend busy before tune")
            tvtool=self.lookup("dvbv5-zap")
            ffmpeg=self.lookup("ffmpeg")
            if not tvtool or not ffmpeg:raise LiveRadioError("DVB or video tools disappeared")
            if rec_id:
                self.record_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
                os.chmod(self.record_dir,0o700)
                fd=os.open(self.record_dir/(rec_id+".ts"),
                    os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_CLOEXEC|
                    getattr(os,"O_NOFOLLOW",0),0o600)
                record_file=os.fdopen(fd,"wb")
            zap=subprocess.Popen(
                zap_command(tvtool,channels_file,service),
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
            self._procs=[zap]
            # Tuning and transport may require time. The worker does not claim
            # lock until transport bytes actually arrive.
            dev="/dev/dvb/adapter0/dvr0"
            deadline=time.monotonic()+8
            while not os.path.exists(dev) and time.monotonic()<deadline and not self._stop.is_set():
                time.sleep(.1)
            if self._stop.is_set():raise LiveRadioError("TV start cancelled")
            if not os.path.exists(dev):
                raise LiveRadioError("DVB DVR node missing after tune")
            dvr_fd=os.open(dev,os.O_RDONLY|os.O_NONBLOCK|os.O_CLOEXEC)
            extra=()
            if self._captions:
                audio_pipe=os.pipe()
                extra=(audio_pipe[1],)
            enc=subprocess.Popen(
                tv_ffmpeg_command(ffmpeg,audio_fd=audio_pipe[1] if audio_pipe else None),
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True,
                pass_fds=extra)
            if audio_pipe:
                os.close(audio_pipe[1])
                audio_pipe=(audio_pipe[0],None)
                os.set_blocking(audio_pipe[0],False)
            self._procs.append(enc)
            if self._captions:self._captions.start()
            assert enc.stdin and enc.stdout
            os.set_blocking(enc.stdout.fileno(),False)
            no_input_since=time.monotonic()
            def pump_ts():
                nonlocal no_input_since
                try:
                    with selectors.DefaultSelector() as sel:
                        sel.register(dvr_fd,selectors.EVENT_READ)
                        while not self._stop.is_set():
                            events=sel.select(timeout=.25)
                            if not events:
                                if time.monotonic()-no_input_since>12:self._stop.set()
                                continue
                            try:raw=os.read(dvr_fd,188*400)
                            except BlockingIOError:continue
                            if not raw:continue
                            no_input_since=time.monotonic()
                            with self._mutex:
                                self._state["source_status"]="Actual MPEG-TS bytes from local DVB DVR"
                            if record_file:
                                record_file.write(raw)
                                with self._mutex:self._state["recorded_bytes"]+=len(raw)
                                if self._state["recorded_bytes"]>=MAX_TV_RECORDING:
                                    self._stop.set();break
                            enc.stdin.write(raw);enc.stdin.flush()
                except (OSError,BrokenPipeError,ValueError):
                    self._stop.set()
                finally:
                    try:enc.stdin.close()
                    except OSError:pass
            pipe=Thread(target=pump_ts,name="tihulu-tv-ts-fanout",daemon=True)
            pipe.start()
            if audio_pipe and self._captions:
                def consume_audio():
                    with selectors.DefaultSelector() as sel:
                        sel.register(audio_pipe[0],selectors.EVENT_READ)
                        while not self._stop.is_set():
                            for _,_ in sel.select(timeout=.25):
                                try:pcm=os.read(audio_pipe[0],8192)
                                except BlockingIOError:continue
                                if not pcm:return
                                self._captions.feed_pcm(pcm)
                audio_thread=Thread(target=consume_audio,name="tihulu-tv-pcm-captions",daemon=True)
                audio_thread.start()
            with self._mutex:self._state["status"]="running"
            with selectors.DefaultSelector() as sel:
                sel.register(enc.stdout,selectors.EVENT_READ)
                deadline=time.monotonic()+MAX_LIVE_SECONDS
                while not self._stop.is_set():
                    if time.monotonic()>deadline:
                        failure="TV stream stopped at 24-hour safety limit"
                        break
                    with self._mutex:
                        watching=self._client
                        idle=time.monotonic()-self._client_last
                        recording=self._state["record"]
                    if not watching and not recording and idle>MAX_IDLE_WITHOUT_LISTENER:
                        break
                    if zap.poll() is not None:
                        failure="DVB tuner command exited unexpectedly"
                        break
                    for item,_ in sel.select(timeout=.2):
                        try:raw=os.read(item.fileobj.fileno(),16384)
                        except BlockingIOError:continue
                        if not raw:
                            if enc.poll() is not None:
                                failure="TV transcoder ended unexpectedly"
                                self._stop.set()
                            continue
                        with self._mutex:self._state["bytes_encoded"]+=len(raw)
                        if watching:
                            try:self._chunks.put_nowait(raw)
                            except queue.Full:
                                failure="Video player cannot keep up; stream stopped instead of dropping MP4 fragments"
                                self._stop.set()
                                break
            if self._state["bytes_encoded"]==0 and failure is None and not self._stop.is_set():
                failure="No real DVB video decoded"
        except (OSError,LiveRadioError,ValueError) as exc:
            failure=str(exc)[:230]
        finally:
            self._stop.set()
            self._terminate(enc);self._terminate(zap)
            if pipe and pipe.is_alive():pipe.join(timeout=1)
            if audio_thread and audio_thread.is_alive():audio_thread.join(timeout=1)
            if dvr_fd is not None:
                try:os.close(dvr_fd)
                except OSError:pass
            if audio_pipe:
                try:os.close(audio_pipe[0])
                except OSError:pass
                if audio_pipe[1] is not None:
                    try:os.close(audio_pipe[1])
                    except OSError:pass
            for proc in (enc,zap):
                if proc:
                    for stream in (proc.stdin,proc.stdout,proc.stderr):
                        if stream:
                            try:stream.close()
                            except OSError:pass
            if record_file:
                try:record_file.flush();record_file.close()
                except OSError:pass
            if self._captions:self._captions.stop()
            with self._mutex:
                self._procs=[]
                self._state["active"]=False
                self._state["status"]="error" if failure else "completed"
                self._state["error"]=failure
                self._state["ended_at"]=utc_now()
                self._unlock()
            try:self._chunks.put_nowait(None)
            except queue.Full:pass
