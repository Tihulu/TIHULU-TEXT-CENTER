"""Opt-in continuous local FM radio MP3 stream, recording and shared PCM captions.

FM audio is read once from the RTL-SDR and fanned to:
 - ffmpeg (MP3 browser audio)
 - optionally a local Whisper subtitle worker (same PCM, NO second tune)
 - optionally a bounded original MP3 recording on disk
The stream runs until stopped/disconnected, with 24h/512MiB safety limits.
It never kills readsb, changes another receiver's frequency or transmits RF.
"""
from __future__ import annotations
from datetime import datetime,timezone
import fcntl
import os
from pathlib import Path
import queue
import selectors
import shutil
import signal
import subprocess
from threading import Event,Lock,Thread
import time
import uuid

from .fm_audio import audio_argv,LOCK_NAME
from .fm_rds import validate_request
from .conflicts import find_receiver_conflicts
from .receivers import receiver_inventory
from .caption_live import LiveCaptionRunner,prepare_caption_options
from .subtitles import CaptionStore

MAX_RECORDING_BYTES=512*1024*1024
MAX_LIVE_SECONDS=24*3600
MAX_IDLE_WITHOUT_LISTENER=16


class LiveRadioError(RuntimeError):
    pass


def ffmpeg_mp3_command(executable:str)->list[str]:
    return [executable,"-hide_banner","-loglevel","error","-nostdin",
            "-f","s16le","-ar","32000","-ac","1","-i","pipe:0",
            "-map","0:a:0","-vn","-c:a","libmp3lame",
            "-b:a","96k","-f","mp3","pipe:1"]


class LiveRadio:
    def __init__(self,store,*,inventory=None,lookup=None,conflicts=None,
                 rds=None,survey=None,preview=None,lock_dir=None,
                 record_dir=None,compute=None,asr_factory=None,translator=None):
        self.store=store
        self.inventory=inventory or receiver_inventory
        self.lookup=lookup or shutil.which
        self.conflicts=conflicts or find_receiver_conflicts
        self.rds,self.survey,self.preview=rds,survey,preview
        self.lock_dir=lock_dir or store.filename.parent/".receiver-locks"
        self.record_dir=Path(record_dir or os.environ.get("TIHULU_RECORDINGS_DIR",
                                str(store.filename.parent/"recordings")))
        self.compute=compute
        self.asr_factory=asr_factory
        self.translator=translator
        self.archive=CaptionStore(store)
        self._mutex=Lock()
        self._stop=Event()
        self._thread=None
        self._lock_fd=None
        self._procs=[]
        self._client=False
        self._client_last=time.monotonic()
        self._chunks=queue.Queue(maxsize=128)
        self._captions=None
        self._state={
            "status":"idle","active":False,"frequency_hz":None,
            "session":None,"record":False,"recording_id":None,
            "started_at":None,"ended_at":None,
            "stream_clients":0,"bytes_encoded":0,"error":None,
            "recorded_bytes":0,"caption_enabled":False,
        }

    def availability(self):
        inv=self.inventory()
        if inv.get("platform")!="Linux" or inv.get("rtl_usb_count")!=1:
            return {"ready":False,"reason":"Exactly one compatible Linux RTL-SDR must be present"}
        if not self.lookup("rtl_fm") or not self.lookup("ffmpeg"):
            return {"ready":False,"reason":"Live FM needs both rtl_fm and ffmpeg (MP3 encoder)"}
        for controller in (self.rds,self.survey,self.preview):
            if controller is not None and controller.status(heartbeat=False)["active"] if (
                controller is not None and controller is not self.preview
            ) else (controller is not None and controller.status()["active"]):
                return {"ready":False,"reason":"Receiver already used by another Text Center session"}
        busy=self.conflicts()
        if busy:
            return {"ready":False,
                    "reason":"Potential SDR owner: "+", ".join(sorted({x["process"] for x in busy}))}
        return {"ready":True,"reason":"Local MP3 radio stream can be started manually with exclusive SDR ownership"}

    def _lock(self):
        self.lock_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
        os.chmod(self.lock_dir,0o700)
        fd=os.open(self.lock_dir/LOCK_NAME,
            os.O_CREAT|os.O_RDWR|os.O_CLOEXEC|getattr(os,"O_NOFOLLOW",0),0o600)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise LiveRadioError("Local radio capture lock is already held")
        self._lock_fd=fd

    def _unlock(self):
        fd,self._lock_fd=self._lock_fd,None
        if fd is not None:
            try:fcntl.flock(fd,fcntl.LOCK_UN)
            finally:os.close(fd)

    def start(self,*,frequency_mhz:object,record:object=False,
              captions:dict|None=None)->dict:
        hz,_=validate_request(frequency_mhz,10)
        if type(record) is not bool:raise ValueError("Recording consent must be boolean")
        opts=prepare_caption_options(captions or {},self.compute() if self.compute else None)
        with self._mutex:
            if self._state["active"]:
                raise LiveRadioError("FM live stream already running")
            capability=self.availability()
            if not capability["ready"]:raise LiveRadioError(capability["reason"])
            self._lock()
            try:
                if self.conflicts():
                    raise LiveRadioError("SDR acquired by another service during preflight")
                self._captions=None
                if opts["enabled"]:
                    self._captions=LiveCaptionRunner(
                        self.archive,opts,source_label=f"FM RF {hz/1e6:.3f} MHz",
                        asr_factory=self.asr_factory,translator=self.translator)
                self._stop.clear()
                self._client=False
                self._client_last=time.monotonic()
                self._chunks=queue.Queue(maxsize=128)
                ident=uuid.uuid4().hex
                rec_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+ident
                self._state={
                    "status":"starting","active":True,"frequency_hz":hz,
                    "session":ident,"record":record,
                    "recording_id":rec_id if record else None,
                    "started_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "ended_at":None,"stream_clients":0,
                    "bytes_encoded":0,"recorded_bytes":0,"error":None,
                    "caption_enabled":opts["enabled"],
                }
                self._thread=Thread(target=self._run,args=(hz,rec_id if record else None),
                                    daemon=True,name="tihulu-live-fm")
                self._thread.start()
                return self._snapshot()
            except BaseException:
                self._unlock()
                self._state["active"]=False
                self._state["status"]="error"
                raise

    def _snapshot(self):
        result=dict(self._state)
        result["captions"]=self._captions.status() if self._captions else {
            "active":False,"status":"disabled","cues":[]}
        return result

    def status(self):
        with self._mutex:
            return self._snapshot()

    def stop(self,*,wait=False):
        with self._mutex:
            self._stop.set()
            if self._state["active"]:self._state["status"]="stopping"
            worker=self._thread
            state=self._snapshot()
        if wait and worker and worker.is_alive():worker.join(timeout=5)
        return state

    def stream_chunks(self,session:str):
        """Exactly one browser subscriber. GET does not start or retune RF."""
        if not isinstance(session,str) or len(session)!=32:
            raise LiveRadioError("Invalid session")
        with self._mutex:
            if not self._state["active"] or self._state["session"]!=session:
                raise LiveRadioError("No active stream with that session")
            if self._client:
                raise LiveRadioError("Only one local player can attach to this stream")
            self._client=True
            self._client_last=time.monotonic()
            self._state["stream_clients"]=1
            q=self._chunks
        try:
            while True:
                try:chunk=q.get(timeout=.7)
                except queue.Empty:
                    with self._mutex:active=self._state["active"]
                    if not active and q.empty():break
                    continue
                if chunk is None:break
                yield chunk
        finally:
            with self._mutex:
                self._client=False
                self._state["stream_clients"]=0
                self._client_last=time.monotonic()
                if not self._state["record"]:self._stop.set()

    def recordings(self):
        try:entries=sorted(self.record_dir.glob("*.mp3"),reverse=True)[:100]
        except OSError:entries=[]
        result=[]
        for path in entries:
            if not path.is_file() or path.is_symlink():continue
            try:
                size=path.stat().st_size
            except OSError:continue
            if not (0<size<=MAX_RECORDING_BYTES):continue
            result.append({"id":path.stem,"bytes":size,"mime":"audio/mpeg",
                           "name":path.name})
        return result

    def recording(self,ident:str)->bytes|None:
        # This basic read endpoint is intentionally capped; large recordings
        # should eventually be streamed by offset / linked external SSD.
        if not isinstance(ident,str) or not (
            len(ident)==49 and ident[15]=="_" and all(c in "0123456789abcdef" for c in ident[16:])
            and ident[:8].isdigit() and ident[9:15].isdigit()
        ):
            return None
        path=self.record_dir/(ident+".mp3")
        try:
            if path.is_symlink() or not path.is_file():return None
            if path.stat().st_size>32*1024*1024:return None
            return path.read_bytes()
        except OSError:return None

    @staticmethod
    def _terminate(proc):
        if proc is None or proc.poll() is not None:return
        try:
            os.killpg(proc.pid,signal.SIGTERM)
            proc.wait(timeout=1)
        except (OSError,subprocess.TimeoutExpired):
            try:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=.5)
            except (OSError,subprocess.TimeoutExpired):pass

    def _run(self,hz:int,rec_id:str|None):
        tuner=None;encoder=None;record_file=None;pump=None
        error=None
        try:
            if self.conflicts():
                raise LiveRadioError("RTL-SDR owner conflict before opening device")
            decoder=self.lookup("rtl_fm")
            ffmpeg=self.lookup("ffmpeg")
            if not decoder or not ffmpeg:
                raise LiveRadioError("rtl_fm or ffmpeg executable disappeared")
            if rec_id:
                self.record_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
                os.chmod(self.record_dir,0o700)
                fd=os.open(self.record_dir/(rec_id+".mp3"),
                    os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_CLOEXEC|
                    getattr(os,"O_NOFOLLOW",0),0o600)
                record_file=os.fdopen(fd,"wb")
            tuner=subprocess.Popen(
                audio_argv(decoder,hz),stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                start_new_session=True,close_fds=True)
            encoder=subprocess.Popen(
                ffmpeg_mp3_command(ffmpeg),stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                start_new_session=True,close_fds=True)
            self._procs=[tuner,encoder]
            if self._captions:self._captions.start()
            with self._mutex:self._state["status"]="running"
            assert tuner.stdout is not None and encoder.stdin is not None
            assert encoder.stdout is not None
            def pump_pcm():
                try:
                    while not self._stop.is_set():
                        part=os.read(tuner.stdout.fileno(),16_384)
                        if not part:break
                        if self._captions:self._captions.feed_pcm(part)
                        encoder.stdin.write(part)
                        encoder.stdin.flush()
                except (OSError,BrokenPipeError,ValueError):
                    self._stop.set()
                finally:
                    try:encoder.stdin.close()
                    except OSError:pass
            pump=Thread(target=pump_pcm,name="tihulu-fm-pcm-fanout",daemon=True)
            pump.start()
            os.set_blocking(encoder.stdout.fileno(),False)
            deadline=time.monotonic()+MAX_LIVE_SECONDS
            with selectors.DefaultSelector() as sel:
                sel.register(encoder.stdout,selectors.EVENT_READ)
                while not self._stop.is_set():
                    if time.monotonic()>=deadline:
                        error="24-hour safety limit reached; stream stopped"
                        break
                    with self._mutex:
                        attached=self._client
                        idle=time.monotonic()-self._client_last
                        save=self._state["record"]
                    if not attached and not save and idle>MAX_IDLE_WITHOUT_LISTENER:
                        error="No browser player attached; released receiver"
                        break
                    if tuner.poll() is not None and encoder.poll() is not None:
                        break
                    for key,_ in sel.select(timeout=.25):
                        try:chunk=os.read(key.fileobj.fileno(),8192)
                        except BlockingIOError:continue
                        if not chunk:
                            if encoder.poll() is not None:self._stop.set()
                            continue
                        with self._mutex:
                            self._state["bytes_encoded"]+=len(chunk)
                        if record_file:
                            record_file.write(chunk)
                            with self._mutex:
                                self._state["recorded_bytes"]+=len(chunk)
                            if self._state["recorded_bytes"]>=MAX_RECORDING_BYTES:
                                error="512-MiB recording quota reached; stream stopped"
                                self._stop.set()
                                break
                        if attached:
                            try:self._chunks.put_nowait(chunk)
                            except queue.Full:
                                error="Browser streaming buffer too slow; stopped without dropping audio bytes"
                                self._stop.set()
                                break
            if not self._stop.is_set() and tuner.poll() not in (None,0):
                error="rtl_fm ended unexpectedly; confirm driver, antenna and exclusive hardware ownership"
            if not self._stop.is_set() and encoder.poll() not in (None,0):
                error="ffmpeg MP3 encoder ended unexpectedly; verify libmp3lame support"
        except (LiveRadioError,OSError,ValueError) as exc:
            error=str(exc)[:240]
        finally:
            self._stop.set()
            self._terminate(tuner)
            self._terminate(encoder)
            if pump and pump.is_alive():pump.join(timeout=1)
            for proc in (tuner,encoder):
                if proc is None:continue
                for stream in (proc.stdout,proc.stderr,proc.stdin):
                    if stream is not None:
                        try:stream.close()
                        except OSError:pass
            if record_file:
                try:record_file.flush();record_file.close()
                except OSError:pass
            if self._captions:self._captions.stop()
            with self._mutex:
                self._procs=[]
                self._state["active"]=False
                self._state["status"]="error" if error else "completed"
                self._state["error"]=error
                self._state["ended_at"]=datetime.now(timezone.utc).isoformat(timespec="seconds")
                self._unlock()
            try:self._chunks.put_nowait(None)
            except queue.Full:pass
