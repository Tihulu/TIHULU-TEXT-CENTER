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
from .transcripts import TranscriptStore, TranslatorUnavailable, translate_offline
from .tv_teletext_subtitles import TeletextSubtitleSidecar

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
        stream_index=item.get("teletext_subtitle_index",0)
        if type(stream_index) is not int or not 0<=stream_index<=15:stream_index=0
        page=item.get("teletext_subtitle_page","subtitle")
        if page!="subtitle" and (type(page) is not int or not 100<=page<=899):
            page="subtitle"
        channel_lang=item.get("teletext_language")
        if channel_lang not in ("en","de","tr"):channel_lang=None
        channels.append({"id":key,"name":name.strip()[:100],"url":url,
                         "source_status":"operator_configured_not_rf_verified",
                         "teletext_shared_safe":item.get("teletext_shared_safe") is True,
                         "teletext_subtitle_index":stream_index,
                         "teletext_subtitle_page":page,
                         "teletext_language":channel_lang})
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
        self.teletext_sidecar=None
        self.teletext_last_seen=None
        self.caption_source="auto"
        self.caption_enabled=False
        self.caption_show_original=True
        self.caption_show_translation=True
        self.subtitle_language="en"
        self.subtitle_target=None
        self.subtitle_channel=None
        self.subtitle_error=None
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
              subtitle_source="auto",upstream_authorized=False):
        if type(record) is not bool or type(subtitles) is not bool or type(upstream_authorized) is not bool:
            raise ValueError("TV flags must be Boolean")
        if subtitle_source not in ("auto","teletext","speech"):
            raise ValueError("TV subtitle source must be auto/teletext/speech")
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
            self.teletext_sidecar=None
            self.teletext_last_seen=None
            self.caption_source=subtitle_source
            self.caption_enabled=subtitles
            self.subtitle_target=translate_to
            self.caption_show_original=True
            self.caption_show_translation=True
            self.subtitle_language=language
            self.subtitle_channel=channel
            self.subtitle_error=None
            session=uuid.uuid4().hex
            now=datetime.now(timezone.utc)
            name=now.strftime("%Y%m%dT%H%M%SZ")+"-TV-"+channel_id+"-"+session[:10]+".mp4" if record else None
            self.archive.mkdir(parents=True,exist_ok=True,mode=0o700)
            os.chmod(self.archive,0o700)
            try:
                self.record_file=open(self.archive/name,"xb") if name else None
                read_fd=write_fd=None
                subtitle_reason=None
                # Caption models are optional. Never kill actual TV playback
                # merely because a requested Whisper/Argos backend is missing.
                if subtitles and subtitle_source!="teletext":
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
                    "subtitle_source_preference":subtitle_source,
                    "teletext_shared_read_safe":channel["teletext_shared_safe"],
                    "teletext_archive_pages_only":not channel["teletext_shared_safe"],
                    "subtitle_unavailable_reason":subtitle_reason,
                }
                self.last_seen=time.monotonic()
                self.listener=False
                if self.audio_read is not None:
                    self.thread=threading.Thread(target=self._audio_worker,daemon=True,
                                                 name="tihulu-tv-speech")
                    self.thread.start()
                if subtitles and subtitle_source!="speech":
                    self._start_teletext_sidecar()
                self.watchdog=threading.Thread(target=self._watch,daemon=True,
                                               name="tihulu-tv-watchdog")
                self.watchdog.start()
                return self.status()
            except BaseException:
                self._shutdown("error","Unable to initialize TV relay")
                raise

    def _start_teletext_sidecar(self):
        """Never double-open a tuner. Only opt-in multi-client local relays qualify."""
        channel=self.subtitle_channel
        if not channel or not channel.get("teletext_shared_safe"):
            self.subtitle_error=(
                "Teletext subtitle extraction needs an explicitly multi-client-safe "
                "existing MPEG-TS relay. Existing TV Teletext and video remain untouched.")
            return
        if self.teletext_sidecar and self.teletext_sidecar.status()["active"]:
            return
        sidecar=TeletextSubtitleSidecar(on_cue=self._on_received_teletext,
                                      lookup=self.lookup)
        self.teletext_sidecar=sidecar
        try:
            status=sidecar.start(channel["url"],share_safe=True,
                subtitle_index=channel["teletext_subtitle_index"],
                page=channel["teletext_subtitle_page"])
        except (ValueError,OSError,RuntimeError) as exc:
            self.subtitle_error=str(exc)[:220]
            return
        if not status["active"]:
            self.subtitle_error=status.get("error") or "Teletext decoder unavailable"

    def _on_received_teletext(self,cue):
        """Only FFmpeg-decoded timed subtitle text may reach this path."""
        with self.mutex:
            if not self.state["active"] or not self.caption_enabled or self.caption_source=="speech":
                return
            session=self.state["session"]
            channel=self.subtitle_channel
            if not channel or not self.transcripts:
                return
            self.teletext_last_seen=time.monotonic()
            language=channel.get("teletext_language") or (
                self.subtitle_language if self.subtitle_language in ("en","de","tr") else "und")
            target=self.subtitle_target
        translated=None
        if target and language!="und" and language!=target:
            try:translated=translate_offline(cue["text"],language,target)
            except (TranslatorUnavailable,OSError,ValueError,RuntimeError) as exc:
                with self.mutex:self.subtitle_error=(
                    "Actual Teletext decoded; optional translation unavailable: "+str(exc)[:140])
        try:
            self.transcripts.add(
                session=session,medium="dvb_tv",
                source_id="configured_tv:"+channel["id"]+":teletext",
                language=language,text=cue["text"],
                backend="broadcast_teletext",start=cue["start"],end=cue["end"],
                translated=translated,target=target if translated else None,
                translation_engine="argos_offline_teletext" if translated else None)
        except (ValueError,OSError) as exc:
            with self.mutex:self.subtitle_error="Cannot save decoded Teletext cue: "+str(exc)[:140]

    def _effective_subtitle_source(self):
        if not self.caption_enabled:return "off"
        if self.caption_source=="teletext":return (
            "teletext" if self.teletext_last_seen is not None and
            time.monotonic()-self.teletext_last_seen<15 else "teletext_waiting")
        if self.caption_source=="speech":return "speech" if self.speech else "speech_unavailable"
        if self.teletext_last_seen is not None and time.monotonic()-self.teletext_last_seen<15:
            return "teletext"
        return "speech" if self.speech else "unavailable"

    def configure_captions(self,*,enabled=None,source=None,translate_to=None,
                           original_visible=None,translated_visible=None):
        """Update live subtitle preferences without retuning or stopping video.

        The PCM tap for speech must have been provisioned at Play; it is never
        silently added by re-opening the configured tuner stream.
        """
        if enabled is not None and type(enabled) is not bool:
            raise ValueError("Invalid captions enabled flag")
        if source is not None and source not in ("auto","teletext","speech"):
            raise ValueError("Subtitle source must be auto/teletext/speech")
        for value in (original_visible,translated_visible):
            if value is not None and type(value) is not bool:
                raise ValueError("Subtitle display options must be Boolean")
        if translate_to is not None and translate_to not in ("off","en","de","tr"):
            raise ValueError("Invalid live translation language")
        with self.mutex:
            if not self.state["active"]:raise LiveTVError("No active TV session")
            if enabled is not None:self.caption_enabled=enabled
            if source is not None:self.caption_source=source
            if original_visible is not None:self.caption_show_original=original_visible
            if translated_visible is not None:self.caption_show_translation=translated_visible
            if translate_to is not None:
                self.subtitle_target=None if translate_to=="off" else translate_to
                if self.speech:self.speech.target=self.subtitle_target
            should_run=self.caption_enabled and self.caption_source!="speech"
            if self.teletext_sidecar and not should_run:
                self.teletext_sidecar.stop(wait=False)
                self.teletext_sidecar=None
                self.teletext_last_seen=None
            elif should_run and (not self.teletext_sidecar or
                                 not self.teletext_sidecar.status()["active"]):
                self._start_teletext_sidecar()
            return self.status(heartbeat=True)

    def _audio_worker(self):
        with self.mutex:
            fd=self.audio_read
            worker=self.speech
        if fd is None or worker is None:return
        try:
            while not self.stop_flag.is_set():
                chunk=os.read(fd,32768)
                if not chunk:break
                with self.mutex:
                    preferred=self._effective_subtitle_source()
                    enabled=self.caption_enabled
                if enabled and preferred=="speech":
                    worker.feed(chunk)
                else:
                    # Preserve the live-media time axis without launching ASR
                    # while genuine Teletext subtitles are arriving.
                    worker.buffer.clear()
                    worker.samples+=len(chunk)//2
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
        if self.teletext_sidecar:
            self.teletext_sidecar.stop(wait=False)
            self.teletext_sidecar=None
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
            result["captions_enabled"]=self.caption_enabled
            result["caption_original_visible"]=self.caption_show_original
            result["caption_translated_visible"]=self.caption_show_translation
            result["subtitle_source_preference"]=self.caption_source
            result["subtitle_effective_source"]=self._effective_subtitle_source()
            result["teletext"]=(self.teletext_sidecar.status()
                                if self.teletext_sidecar else
                                {"active":False,"status":"not_connected","received":0})
            result["teletext_error"]=self.subtitle_error
            if self.caption_enabled and not self.speech and result["subtitle_effective_source"] in ("speech_unavailable","unavailable"):
                result["asr_fallback_note"]="No compatible speech model/PCM tap; restart with subtitles enabled after installing compatible AI"
            result["speech"]=self.speech.status() if self.speech else {
                "enabled":False,"reason":self.state.get("subtitle_unavailable_reason") or
                    "No user-requested TV transcription"}
            return result

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
