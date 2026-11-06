"""Explicit continuous local TV relay from a PRE-ASSIGNED MPEG-TS endpoint.

No TV tuner access. No dvbv5-zap, tune/release operation or auto-service scan.
A trusted local TV/Radio Center must provide a pre-authorized dedicated
MPEG-TS stream on loopback. Channels are from a fixed local config file,
never user-submitted URLs. ffmpeg converts to fragmented H264/AAC MP4 for
browser playback, optional local recording and optional PCM speech tap.

An incoming HTTP stream might have *its own* tuning side effects, so the
operator MUST authorize its upstream tuner lease independently. No protected
TV/Flight Radar service may be preempted.
"""
from __future__ import annotations

from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
from urllib.parse import urlsplit
import uuid

from .live_fm import MAX_RECORD_BYTES,SESSION_TIMEOUT
from .compute import detect_devices
from .speech import SpeechPipeline, SpeechError
from .transcripts import TranscriptStore

MAX_CHANNELS=64


class LiveTVError(RuntimeError):
    pass


def validate_local_tv_url(value:str)->str:
    if not isinstance(value,str) or len(value)>600:
        raise ValueError("TV source URL too long or missing")
    u=urlsplit(value)
    if u.scheme!="http" or u.hostname!="127.0.0.1" or u.username or u.password or u.fragment:
        raise ValueError("TV source must be loopback HTTP without credentials")
    if not u.port or not 1024<=u.port<=65535:
        raise ValueError("TV source port must be explicit, unprivileged")
    if not u.path.startswith("/stream/") or u.path=="/stream/":
        raise ValueError("TV stream path must be /stream/<known channel>")
    if u.query or any(ord(x)<33 or ord(x)>126 for x in value):
        raise ValueError("TV source URL queries and control characters are disabled")
    return value


def load_channels(path:str|Path|None=None)->list[dict]:
    filename=path if path is not None else os.environ.get("TIHULU_TV_CHANNELS_FILE")
    if not filename:
        return []
    file=Path(filename).expanduser()
    if not file.is_file() or file.stat().st_size>24_000:
        return []
    try:
        obj=json.loads(file.read_text(encoding="utf-8"))
    except (ValueError,UnicodeError,OSError):
        return []
    if not isinstance(obj,dict) or obj.get("version")!=1 or not isinstance(obj.get("channels"),list):
        return []
    channels=[]
    ids=set()
    for item in obj["channels"][:MAX_CHANNELS]:
        if not isinstance(item,dict):
            continue
        key=item.get("id")
        name=item.get("name")
        try:url=validate_local_tv_url(item.get("url"))
        except ValueError:continue
        if not isinstance(key,str) or not re.fullmatch(r"[a-z0-9_-]{1,32}",key) or key in ids:
            continue
        if not isinstance(name,str) or not name.strip():
            continue
        ids.add(key)
        channels.append({"id":key,"name":name.strip()[:100],"url":url,
                         "source_status":"operator_configured_not_rf_verified"})
    return channels


def tv_ffmpeg_argv(binary:str,url:str,pcm_fd:int|None=None)->list[str]:
    validate_local_tv_url(url)
    args=[binary,"-hide_banner","-loglevel","error","-nostdin",
          "-i",url,
          "-map","0:v:0","-map","0:a:0?",
          "-c:v","libx264","-preset","ultrafast","-tune","zerolatency",
          "-crf","29","-pix_fmt","yuv420p","-threads","2",
          "-c:a","aac","-b:a","96k","-ar","44100",
          "-movflags","frag_keyframe+empty_moov+default_base_moof",
          "-f","mp4","pipe:1"]
    if pcm_fd is not None:
        args += ["-map","0:a:0","-vn","-ac","1","-ar","32000",
                 "-f","s16le",f"pipe:{pcm_fd}"]
    return args


class LiveTV:
    def __init__(self,*,archive_dir:Path,transcripts:TranscriptStore|None=None,
                 channels_file:str|Path|None=None,lookup=None,timeout=SESSION_TIMEOUT):
        self.archive=Path(archive_dir)
        self.transcripts=transcripts
        self.channels_file=channels_file
        self.lookup=lookup or shutil.which
        self.timeout=timeout
        self.mutex=threading.RLock()
        self.stop_flag=threading.Event()
        self.process=None
        self.thread=None
        self.watchdog=None
        self.speech=None
        self.teletext=None
        self.subtitle_source="off"
        self.subtitle_started=0.0
        self.caption_processing_enabled=False
        self.caption_config={}
        self.audio_read=None
        self.listener=False
        self.record_file=None
        self.last_seen=0
        self.state={"active":False,"status":"idle","session":None,"channel_id":None,
                    "channel_name":None,"error":None,"recording":False,
                    "recording_name":None,"recorded_bytes":0,
                    "listener_connected":False,"format":"video/mp4",
                    "source_status":"no source configured"}

    def channels(self):
        return load_channels(self.channels_file)

    def availability(self):
        channels=self.channels()
        if not channels:return {"ready":False,"reason":"No authorized upstream TV channel stream configured"}
        if not self.lookup("ffmpeg"):
            return {"ready":False,"reason":"ffmpeg missing"}
        if self.state["active"]:
            return {"ready":False,"reason":"TV stream already active"}
        return {"ready":True,
                "reason":"Configured upstream MPEG-TS relay available (not a DVB tuner lock)"}

    def start(self,channel_id,*,record=False,subtitles=False,language="en",
              translate_to=None,backend="auto",translation_backend="auto",
              upstream_authorized=False,subtitle_source="auto",
              auxiliary_teletext_consent=False):
        if type(record) is not bool or type(subtitles) is not bool or type(upstream_authorized) is not bool or type(auxiliary_teletext_consent) is not bool:
            raise ValueError("TV flags must be Boolean")
        if subtitle_source not in ("auto","broadcast","speech","off"):
            raise ValueError("TV caption source must be auto, broadcast, speech or off")
        if not subtitles or subtitle_source=="off":
            subtitles=False
            subtitle_source="off"
        if not upstream_authorized:
            raise LiveTVError("User must confirm dedicated upstream TV tuner lease")
        with self.mutex:
            if self.state["active"]:raise LiveTVError("TV session already active")
            available=self.availability()
            if not available["ready"]:raise LiveTVError(available["reason"])
            channel=next((x for x in self.channels() if x["id"]==channel_id),None)
            if channel is None:raise ValueError("Unknown configured TV channel")
            ffmpeg=self.lookup("ffmpeg")
            self.stop_flag.clear()
            self.audio_read=None
            self.speech=None
            self.teletext=None
            self.subtitle_source=subtitle_source
            self.caption_processing_enabled=subtitles
            self.caption_config={
                "language":language,"target":translate_to,"backend":backend,
                "translation_backend":translation_backend,
                "auxiliary_teletext_consent":auxiliary_teletext_consent,
            }
            session=uuid.uuid4().hex
            now=datetime.now(timezone.utc)
            name=now.strftime("%Y%m%dT%H%M%SZ")+"-TV-"+channel_id+"-"+session[:10]+".mp4" if record else None
            self.archive.mkdir(parents=True,exist_ok=True,mode=0o700)
            os.chmod(self.archive,0o700)
            try:
                self.record_file=open(self.archive/name,"xb") if name else None
                read_fd=write_fd=None
                subtitle_reason=None
                teletext_reason=None
                # Speech fallback uses real PCM only. A broadcast-only selection
                # must not start Whisper or fake audio-based captions.
                if subtitles and subtitle_source in ("auto","speech"):
                    try:
                        if self.transcripts is None:
                            raise SpeechError("TV transcript archive unavailable")
                        self.speech=SpeechPipeline(
                            store=self.transcripts,session=session,
                            source_id="configured_tv:"+channel_id,
                            source_language=language,target_language=translate_to,
                            backend=backend,profile=detect_devices(),
                            medium="dvb_tv",translation_backend=translation_backend)
                        read_fd,write_fd=os.pipe()
                        os.set_inheritable(write_fd,True)
                    except (SpeechError,ValueError,ImportError,RuntimeError,OSError) as exc:
                        self.speech=None
                        subtitle_reason=str(exc)[:220]
                        if read_fd is not None:os.close(read_fd)
                        if write_fd is not None:os.close(write_fd)
                        read_fd=write_fd=None
                try:
                    self.process=subprocess.Popen(
                        tv_ffmpeg_argv(ffmpeg,channel["url"],write_fd),
                        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        pass_fds=(write_fd,) if write_fd is not None else (),
                        start_new_session=True,close_fds=True)
                finally:
                    if write_fd is not None:os.close(write_fd)
                self.audio_read=read_fd
                self.state={
                    "active":True,"status":"running","session":session,
                    "channel_id":channel_id,"channel_name":channel["name"],
                    "recording":record,"recording_name":name,
                    "recorded_bytes":0,"listener_connected":False,
                    "source_status":"operator_configured_upstream_stream_not_dvb_verified",
                    "error":None,"format":"video/mp4",
                    "subtitles_requested":subtitles,
                    "subtitles_active":self.speech is not None,
                    "subtitle_source_requested":subtitle_source,
                    "auxiliary_teletext_consented":auxiliary_teletext_consent,
                    "subtitle_unavailable_reason":subtitle_reason,
                }
                self.last_seen=time.monotonic()
                self.subtitle_started=self.last_seen
                self.listener=False
                if subtitles and subtitle_source in ("auto","broadcast"):
                    if not auxiliary_teletext_consent:
                        teletext_reason=("No secondary Teletext reader consent; "
                            "the existing TV Teletext viewer is untouched")
                    else:
                        from .tv_teletext_subtitles import TVTeletextTap
                        try:
                            self.teletext=TVTeletextTap(self.transcripts)
                            self.teletext.start(
                                url=channel["url"],session=session,
                                source_id="configured_tv:"+channel_id,
                                target=translate_to)
                        except (OSError,ValueError,RuntimeError) as exc:
                            teletext_reason="Teletext decoder unavailable: "+str(exc)[:180]
                            self.teletext=None
                self.state["teletext_unavailable_reason"]=teletext_reason
                self.state["subtitles_active"]=bool(self.speech or self.teletext)
                if self.audio_read is not None:
                    self.thread=threading.Thread(target=self._audio_worker,daemon=True,
                                                 name="tihulu-tv-speech")
                    self.thread.start()
                self.watchdog=threading.Thread(target=self._watch,daemon=True,
                                               name="tihulu-tv-watchdog")
                self.watchdog.start()
                return self.status()
            except BaseException:
                self._shutdown("error","Unable to initialize TV relay")
                raise

    def _audio_worker(self):
        with self.mutex:
            fd=self.audio_read
        if fd is None:return
        try:
            while not self.stop_flag.is_set():
                chunk=os.read(fd,32768)
                if not chunk:break
                with self.mutex:
                    worker=self.speech
                    source=self.subtitle_source
                    teletext=self.teletext
                    since=self.subtitle_started
                    processing=self.caption_processing_enabled
                if worker is None:continue
                if not processing:
                    worker.skip(chunk)
                    continue
                if source=="auto" and teletext is not None:
                    status=teletext.status()
                    # Probe/decoder needs a brief grace window; do not create
                    # duplicate AI captions while real subtitle cues are fresh.
                    if status["recent"] or (time.monotonic()-since<8 and
                        status["status"] in ("checking_decoder","waiting_for_real_cues")):
                        worker.skip(chunk)
                        continue
                worker.feed(chunk)
        except OSError:
            pass

    def _watch(self):
        while not self.stop_flag.wait(0.5):
            with self.mutex:
                if not self.state["active"]:return
                if time.monotonic()-self.last_seen>self.timeout:
                    self._shutdown("stopped","Browser heartbeat expired")
                    return

    def _shutdown(self,status="stopped",error=None):
        self.stop_flag.set()
        if self.teletext:
            self.teletext.stop(wait=False)
        if self.process is not None and self.process.poll() is None:
            try:
                if os.name=="nt":
                    self.process.terminate()
                else:
                    os.killpg(self.process.pid,signal.SIGTERM)
                self.process.wait(timeout=0.8)
            except (OSError,subprocess.TimeoutExpired):
                try:
                    if os.name=="nt":
                        self.process.kill()
                    else:
                        os.killpg(self.process.pid,signal.SIGKILL)
                    self.process.wait(timeout=0.3)
                except (OSError,subprocess.TimeoutExpired):pass
        if self.process and self.process.stdout:
            try:self.process.stdout.close()
            except OSError:pass
        self.process=None
        if self.audio_read is not None:
            try:os.close(self.audio_read)
            except OSError:pass
            self.audio_read=None
        if self.speech:self.speech.stop()
        if self.record_file:
            try:self.record_file.close()
            except OSError:pass
            self.record_file=None
        self.state.update(active=False,status=status,error=error,listener_connected=False)
        self.listener=False

    def status(self,heartbeat=False):
        with self.mutex:
            if heartbeat and self.state["active"]:self.last_seen=time.monotonic()
            result=dict(self.state)
            result["speech"]=self.speech.status() if self.speech else {
                "enabled":False,"reason":self.state.get("subtitle_unavailable_reason") or
                    "Speech transcription not selected or installed"}
            teletext=self.teletext.status() if self.teletext else {
                "active":False,"recent":False,"status":"not_started",
                "error":self.state.get("teletext_unavailable_reason")}
            result["teletext_subtitles"]=teletext
            result["caption_source_active"]=(
                "off" if not self.caption_processing_enabled
                else "broadcast_teletext" if teletext["recent"]
                else "speech_transcription" if self.speech is not None
                else "waiting_for_broadcast" if self.teletext is not None
                else "unavailable" if self.state.get("subtitles_requested")
                else "off"
            )
            result["caption_processing_enabled"]=self.caption_processing_enabled
            result["subtitles_active"]=self.caption_processing_enabled and bool(
                self.speech is not None or teletext["recent"])
            result["caption_source_explanation"]=(
                "Real DVB Teletext text cues take priority over speech in Auto mode; "
                "unknown or missing text subtitles trigger real audio transcription "
                "only when a compatible local ASR model is ready"
            )
            return result

    def configure_captions(self,*,processing=None,translate_to=None,
                           target_enabled=None,subtitle_source=None):
        """Pause/resume optional caption computation without changing TV stream.

        Starting Whisper late requires the PCM pipe to have been armed during
        stream start; TV video never restarts or changes its tuner lease here.
        """
        from .compute import validate_language
        if processing is not None and type(processing) is not bool:
            raise ValueError("caption processing must be Boolean")
        if target_enabled is not None and type(target_enabled) is not bool:
            raise ValueError("translation flag must be Boolean")
        if subtitle_source is not None and subtitle_source not in (
                "auto","broadcast","speech","off"):
            raise ValueError("Unknown TV caption source")
        if translate_to is not None:
            validate_language(translate_to)
        with self.mutex:
            if not self.state["active"]:
                raise LiveTVError("Start TV before controlling captions")
            source=subtitle_source or self.subtitle_source
            enabled=processing if processing is not None else self.caption_processing_enabled
            if source=="off":enabled=False
            config=self.caption_config
            target=(translate_to or config.get("target")) if target_enabled is not False else None
            if target_enabled is True and not target:
                raise ValueError("Choose a translation language before enabling translation")
            if source in ("auto","speech") and enabled and self.audio_read is None:
                if source=="speech" or not (config["auxiliary_teletext_consent"]):
                    raise LiveTVError("No live PCM tap was armed; start the next TV session with captions enabled")
            if source=="broadcast" and enabled and not config["auxiliary_teletext_consent"]:
                raise LiveTVError("A separate Teletext decoder reader requires explicit permission")
            # All hardware-facing changes are to an app-owned read-only
            # subtitle worker; never restart the main ffmpeg video process.
            if self.teletext and (not enabled or source=="speech"):
                self.teletext.stop(wait=False)
                self.teletext=None
            if (enabled and source in ("auto","broadcast") and
                config["auxiliary_teletext_consent"] and self.teletext is None):
                channel=next((x for x in self.channels() if x["id"]==self.state["channel_id"]),None)
                if channel is not None:
                    from .tv_teletext_subtitles import TVTeletextTap
                    self.teletext=TVTeletextTap(self.transcripts)
                    self.teletext.start(url=channel["url"],session=self.state["session"],
                        source_id="configured_tv:"+channel["id"],target=target,
                        offset=time.monotonic()-self.subtitle_started)
            if self.teletext:
                self.teletext.set_translation_target(target)
            if self.speech:
                if (not enabled or source=="broadcast"):
                    self.speech.stop()
                    self.speech=None
                else:
                    self.speech.set_translation_target(target)
            if enabled and source in ("auto","speech") and self.speech is None and self.audio_read is not None:
                try:
                    self.speech=SpeechPipeline(
                        store=self.transcripts,session=self.state["session"],
                        source_id="configured_tv:"+self.state["channel_id"],
                        source_language=config["language"],target_language=target,
                        backend=config["backend"],profile=detect_devices(),
                        medium="dvb_tv",translation_backend=config["translation_backend"])
                    self.state["subtitle_unavailable_reason"]=None
                except (SpeechError,ValueError,ImportError,RuntimeError) as exc:
                    self.state["subtitle_unavailable_reason"]=str(exc)[:220]
            self.subtitle_source=source
            self.caption_processing_enabled=enabled
            config["target"]=target
            self.state["subtitle_source_requested"]=source
            self.state["subtitles_requested"]=enabled
            return self.status()

    def stop(self):
        with self.mutex:
            if self.state["active"]:self._shutdown()
            return self.status()

    def stream(self,session):
        with self.mutex:
            if not self.state["active"] or self.state["session"]!=session:
                raise LiveTVError("TV session unavailable")
            if self.listener:
                raise LiveTVError("TV already has a viewer")
            self.listener=True
            self.state["listener_connected"]=True
            self.last_seen=time.monotonic()
            proc=self.process
        try:
            assert proc and proc.stdout
            while not self.stop_flag.is_set():
                chunk=proc.stdout.read(16384)
                if not chunk:break
                with self.mutex:
                    if self.record_file:
                        if self.state["recorded_bytes"]+len(chunk)<=MAX_RECORD_BYTES:
                            self.record_file.write(chunk)
                            self.state["recorded_bytes"]+=len(chunk)
                        else:
                            self.record_file.close()
                            self.record_file=None
                            self.state["recording"]=False
                            self.state["error"]="TV recording reached 1 GiB; playback continues"
                yield chunk
        finally:
            self.stop()

    def recordings(self):
        if not self.archive.exists():return []
        paths=sorted(self.archive.glob("*-TV-*.mp4"),reverse=True)[:100]
        return [{"name":p.name,"bytes":p.stat().st_size}
                for p in paths if p.is_file() and p.stat().st_size]

    def recording(self,name):
        if not isinstance(name,str) or "/" in name or "\\" in name or ".." in name:
            return None
        if len(name)>120 or not name.endswith(".mp4") or "-TV-" not in name:
            return None
        file=self.archive/name
        return file if file.is_file() and file.stat().st_size>0 else None
