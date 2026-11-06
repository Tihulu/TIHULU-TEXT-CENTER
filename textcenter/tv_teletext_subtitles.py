"""Read-only, optional live DVB-Teletext subtitle extractor.

Only runs on an explicitly authorized, separately multi-client-safe loopback
MPEG-TS relay. Never opens /dev/dvb, changes channels or stops TV playback.
DVB bitmap subtitles do not become text without a real OCR decoder.
"""
from __future__ import annotations

import json
import os
import queue
import re
import shutil
import signal
import subprocess
from threading import Event, RLock, Thread, current_thread
import time

from .compute import LANGUAGES
from .core import clean_text
from .live_tv import validate_local_tv_url
from .transcripts import TranscriptStore, TranslatorUnavailable

LANGUAGE_TAGS = {
    "eng": "en", "en": "en", "deu": "de", "ger": "de",
    "de": "de", "tur": "tr", "tr": "tr",
}
SRT_TIME = re.compile(
    r"^([0-9]{2,3}):([0-5][0-9]):([0-5][0-9]),([0-9]{3})\s+-->\s+"
    r"([0-9]{2,3}):([0-5][0-9]):([0-5][0-9]),([0-9]{3})"
)
MAX_CUE_LENGTH = 2500
FRESH_SECONDS = 10.0


def parse_srt_cue(lines):
    """Ignore malformed timestamps, hours-long duration errors and empty cues."""
    lines=[v.strip() for v in lines if isinstance(v,str)]
    head=next((i for i,line in enumerate(lines) if SRT_TIME.match(line)),None)
    if head is None:return None
    matched=SRT_TIME.match(lines[head])
    def seconds(parts):
        h,m,s,ms=(int(v) for v in parts)
        return h*3600+m*60+s+ms/1000
    start=seconds(matched.groups()[:4])
    end=seconds(matched.groups()[4:])
    if not (0 <= start < end <= 86399 and end-start <= 30):return None
    text=clean_text(" ".join(lines[head+1:]),MAX_CUE_LENGTH)
    if not text or sum(c.isalnum() for c in text)<3:return None
    # DVB Teletext graphics/mosaic characters are not translatable captions.
    if sum(c.isalnum() for c in text)/max(len(text),1)<0.17:return None
    return start,end,text


def teletext_probe_stream(url, ffprobe, *, runner=None):
    """Inspect a source from the authorized channel config, never user URLs."""
    validate_local_tv_url(url)
    run=runner or subprocess.run
    try:
        result=run([
            ffprobe,"-v","error","-analyzeduration","1500000",
            "-probesize","1500000","-show_entries",
            "stream=index,codec_name,codec_type:stream_tags=language",
            "-of","json",url
        ],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
           timeout=7,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise RuntimeError("The authorized TV relay could not be probed") from exc
    if result.returncode!=0 or len(result.stdout)>100000:
        raise RuntimeError("TV subtitle probe returned no valid stream metadata")
    try:
        streams=json.loads(result.stdout).get("streams",[])
    except (ValueError,TypeError,AttributeError) as exc:
        raise RuntimeError("TV subtitle probe did not return JSON streams") from exc
    for stream in streams:
        if stream.get("codec_name")!="dvb_teletext" or stream.get("codec_type")!="subtitle":
            continue
        index=stream.get("index")
        if type(index) is not int or index<0 or index>100:continue
        tags=stream.get("tags") or {}
        language=LANGUAGE_TAGS.get(str(tags.get("language","")).lower(),"und")
        return {"index":index,"language":language,"codec":"dvb_teletext"}
    return None


class TVTeletextTap:
    def __init__(self,transcripts:TranscriptStore,*, lookup=None,runner=None,popen=None,probe=None):
        self.transcripts=transcripts
        self.lookup=lookup or shutil.which
        self.runner=runner or subprocess.run
        self.popen=popen or subprocess.Popen
        self.probe=probe or teletext_probe_stream
        self.lock=RLock()
        self.stopping=Event()
        self.thread=None
        self.translate_thread=None
        self.process=None
        self.pending=queue.Queue(maxsize=16)
        self.session=None
        self.source_id=None
        self.target=None
        self.last_cue_at=None
        self.started_at=None
        self.cues=0
        self.status_message="idle"
        self.error=None
        self.stream_index=None
        self.language="und"

    def status(self):
        with self.lock:
            age=time.monotonic()-self.last_cue_at if self.last_cue_at is not None else None
            return {
                "active":bool(self.process is not None and self.process.poll() is None),
                "status":self.status_message,"source":"broadcast_dvb_teletext",
                "recent":age is not None and age<=FRESH_SECONDS,
                "last_cue_age_seconds":round(age,1) if age is not None else None,
                "segments_completed":self.cues,"stream_index":self.stream_index,
                "language":self.language,"error":self.error,
                "requires_authorized_secondary_reader":True,
            }

    def start(self,*,url,session,source_id,target=None,offset=0.0):
        validate_local_tv_url(url)
        if self.thread and self.thread.is_alive():
            raise RuntimeError("Teletext decoder already active")
        if not isinstance(session,str) or not re.fullmatch(r"[0-9a-f]{32}",session):
            raise ValueError("Invalid TV caption session")
        if target is not None and target not in LANGUAGES:
            raise ValueError("Unsupported translation language")
        if not isinstance(offset,(int,float)) or not 0<=offset<86400:
            raise ValueError("Invalid subtitle offset")
        with self.lock:
            self.session=session
            self.source_id=clean_text(source_id,85)
            self.target=target
            self.stopping.clear()
            self.last_cue_at=None
            self.started_at=time.monotonic()-offset
            self.cues=0
            self.status_message="checking_decoder"
            self.error=None
            self.stream_index=None
            self.pending=queue.Queue(maxsize=16)
            self.thread=Thread(target=self._worker,args=(url,),daemon=True,name="tihulu-tv-teletext-tap")
            self.thread.start()
        return self.status()

    def _worker(self,url):
        proc=None
        try:
            ffmpeg=self.lookup("ffmpeg")
            ffprobe=self.lookup("ffprobe")
            if not ffmpeg or not ffprobe:
                raise RuntimeError("FFmpeg/ffprobe missing; real Teletext subtitle decode unavailable")
            decoder=self.runner([ffmpeg,"-hide_banner","-decoders"],
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,timeout=4,check=False)
            if decoder.returncode!=0 or b"libzvbi_teletext" not in decoder.stdout:
                raise RuntimeError("This FFmpeg build lacks libzvbi DVB Teletext decoding")
            if self.stopping.is_set():return
            stream=self.probe(url,ffprobe,runner=self.runner)
            if stream is None:
                raise RuntimeError("No DVB Teletext subtitle stream detected in this TV relay")
            with self.lock:
                self.stream_index=stream["index"]
                self.language=stream["language"]
                self.status_message="waiting_for_real_cues"
            if self.stopping.is_set():return
            args=[
                ffmpeg,"-hide_banner","-loglevel","error","-nostdin",
                "-txt_page","subtitle","-txt_format","text","-fix_sub_duration",
                "-i",url,"-map","0:"+str(self.stream_index),
                "-c:s","srt","-f","srt","pipe:1",
            ]
            options={"stdin":subprocess.DEVNULL,"stdout":subprocess.PIPE,
                     "stderr":subprocess.DEVNULL,"close_fds":True}
            if os.name=="nt":
                options["creationflags"]=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
            else:
                options["start_new_session"]=True
            proc=self.popen(args,**options)
            with self.lock:self.process=proc
            if self.target and self.language in LANGUAGES and self.language!=self.target:
                self.translate_thread=Thread(target=self._translate,daemon=True,
                    name="tihulu-tv-teletext-translate")
                self.translate_thread.start()
            pending=[]
            while not self.stopping.is_set():
                line=proc.stdout.readline()
                if not line:break
                if len(line)>8192:
                    pending=[]
                    continue
                decoded=line.decode("utf-8","replace").strip()
                if decoded:
                    if len(pending)<14:pending.append(decoded)
                    else:pending=[]
                elif pending:
                    cue=parse_srt_cue(pending)
                    if cue:self._store(cue)
                    pending=[]
            if pending:
                cue=parse_srt_cue(pending)
                if cue and not self.stopping.is_set():self._store(cue)
            if not self.stopping.is_set():
                raise RuntimeError("Teletext decoder ended without a continuing subtitle stream")
        except (RuntimeError,OSError,ValueError,TypeError,subprocess.TimeoutExpired) as exc:
            with self.lock:
                if not self.stopping.is_set():
                    self.error=str(exc)[:220]
                    self.status_message="unavailable"
        finally:
            self._stop_process(proc)
            with self.lock:
                if self.process is proc:self.process=None
                if self.stopping.is_set():self.status_message="stopped"

    def _store(self,cue):
        start,end,text=cue
        with self.lock:
            # ffmpeg SRT timestamps are relative to its new input open; align
            # with time since original TV session start, including probe delay.
            estimated_start=max(0.0,time.monotonic()-self.started_at)
            duration=max(0.1,min(20,end-start))
            begin=max(0.0,estimated_start-duration)
            finish=min(86399.0,max(begin+0.1,estimated_start))
            if finish<=begin:return
            if self.stopping.is_set():return
            source=f"{self.source_id}:teletext:{self.stream_index}"
            language=self.language
            session=self.session
        try:
            caption_id=self.transcripts.add(
                session=session,medium="dvb_tv",source_id=source,
                language=language,text=text,backend="broadcast_teletext_libzvbi",
                start=begin,end=finish
            )
        except (ValueError,OSError):return
        with self.lock:
            self.cues+=1
            self.last_cue_at=time.monotonic()
            self.status_message="receiving_real_teletext"
        if self.target and language in LANGUAGES and language!=self.target:
            try:self.pending.put_nowait(caption_id)
            except queue.Full:pass

    def _translate(self):
        while not self.stopping.is_set():
            try:caption_id=self.pending.get(timeout=0.3)
            except queue.Empty:continue
            try:self.transcripts.translate_later(caption_id,self.target,backend="auto")
            except (TranslatorUnavailable,ValueError,ImportError,RuntimeError) as exc:
                with self.lock:self.error="Teletext translation unavailable: "+str(exc)[:180]
            finally:self.pending.task_done()

    def set_translation_target(self,target):
        if target is not None and target not in LANGUAGES:
            raise ValueError("Unsupported Teletext translation language")
        with self.lock:
            self.target=target
            if (target and self.language in LANGUAGES and target!=self.language
                and self.process is not None
                and (self.translate_thread is None or not self.translate_thread.is_alive())):
                self.translate_thread=Thread(target=self._translate,daemon=True,
                    name="tihulu-tv-teletext-translate")
                self.translate_thread.start()
        return self.target

    @staticmethod
    def _stop_process(proc):
        if proc is None:return
        try:
            if proc.poll() is None:
                if os.name=="nt":proc.terminate()
                else:os.killpg(proc.pid,signal.SIGTERM)
                proc.wait(timeout=0.6)
        except (OSError,subprocess.TimeoutExpired):
            try:
                if os.name=="nt":proc.kill()
                else:os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=0.3)
            except (OSError,subprocess.TimeoutExpired):pass
        if proc.stdout:
            try:proc.stdout.close()
            except (OSError,ValueError):pass

    def stop(self,*,wait=False):
        self.stopping.set()
        with self.lock:
            proc=self.process
            thread=self.thread
            translated=self.translate_thread
        self._stop_process(proc)
        if wait:
            for current in (thread,translated):
                if current and current is not current_thread() and current.is_alive():
                    current.join(timeout=2)
        with self.lock:
            self.status_message="stopped"
        return self.status()
