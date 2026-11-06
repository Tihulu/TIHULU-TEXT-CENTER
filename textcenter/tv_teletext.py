"""Read-only DVB Teletext *subtitle* tap of an authorized shared MPEG-TS relay.

No modification to the TV application's own Teletext UI, tuner, firmware or
scan. A second stream reader is allowed ONLY with per-channel explicit
subtitle_shared_read=True; some local relays cannot safely serve two readers.
"""
from __future__ import annotations
import html
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time

LANGUAGES={"eng":"en","en":"en","deu":"de","ger":"de","de":"de","tur":"tr","tr":"tr"}
_TIMING=re.compile(r"(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})")
_TAGS=re.compile(r"<[^>]{0,100}>")


def parse_cue(block: str) -> dict | None:
    if not isinstance(block,str) or len(block)>8000:return None
    lines=block.replace("\r\n","\n").strip().split("\n")
    index=next((i for i,line in enumerate(lines[:4]) if _TIMING.fullmatch(line.strip())),None)
    if index is None:return None
    match=_TIMING.fullmatch(lines[index].strip())
    def seconds(value):
        hours,minutes,secs=value.split(":")
        return int(hours)*3600+int(minutes)*60+float(secs.replace(",","."))
    start,end=seconds(match["start"]),seconds(match["end"])
    if not 0<=start<end<=86400 or end-start>3600:return None
    body=html.unescape(_TAGS.sub("","\n".join(lines[index+1:]))).replace("\x00","").strip()
    if not body or len(body)>3000 or not any(c.isalnum() for c in body):return None
    return {"start":start,"end":end,"text":body}


def teletext_streams(data:bytes,preferred_language="auto")->list[dict]:
    if len(data)>256_000:return []
    try:payload=json.loads(data)
    except (ValueError,UnicodeDecodeError):return []
    if not isinstance(payload,dict) or not isinstance(payload.get("streams"),list):return []
    entries=[]
    for value in payload["streams"][:96]:
        if not isinstance(value,dict) or value.get("codec_type")!="subtitle" or value.get("codec_name")!="dvb_teletext":continue
        index=value.get("index")
        if type(index) is not int or not 0<=index<96:continue
        tags=value.get("tags") if isinstance(value.get("tags"),dict) else {}
        lang=LANGUAGES.get(str(tags.get("language","")).strip().lower(),"und")
        entries.append({"index":index,"language":lang,"codec":"dvb_teletext"})
    pref=preferred_language if preferred_language in ("en","de","tr") else "und"
    return sorted(entries,key=lambda x:(x["language"]!=pref,x["index"]))


def teletext_argv(ffmpeg:str,url:str,index:int)->list[str]:
    if type(index) is not int or not 0<=index<96:raise ValueError("Invalid subtitle stream index")
    return [ffmpeg,"-nostdin","-hide_banner","-loglevel","error",
        "-txt_page","subtitle","-txt_format","text",
        "-i",url,"-map",f"0:{index}",
        "-c:s","srt","-flush_packets","1","-f","srt","pipe:1"]


def terminate_owned(proc):
    if proc is None or proc.poll() is not None:return
    try:
        if os.name=="nt":proc.terminate()
        else:os.killpg(proc.pid,signal.SIGTERM)
        proc.wait(timeout=0.6)
    except (OSError,subprocess.TimeoutExpired,ProcessLookupError):
        if proc.poll() is None:
            try:
                if os.name=="nt":proc.kill()
                else:os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=0.4)
            except (OSError,subprocess.TimeoutExpired,ProcessLookupError):pass


class TVTeletextTap:
    """Isolated read-only ffmpeg subtitle decoder, not an RF receiver."""
    def __init__(self,*,which=None,run=None,popen=None,clock=None):
        self.which=which or shutil.which
        self.run=run or subprocess.run
        self.popen=popen or subprocess.Popen
        self.clock=clock or time.monotonic
        self.lock=threading.RLock()
        self.stop_flag=threading.Event()
        self.process=None
        self.thread=None
        self.state={"active":False,"status":"idle","reason":None,
                    "candidate_stream":None,"language":"und",
                    "cues":0,"last_cue_at":None,"source":"broadcast_teletext",
                    "shared_read_required":True}

    def status(self):
        with self.lock:return dict(self.state)

    def start(self,*,url,language="auto",on_cue=None,shared_read=False):
        if shared_read is not True:raise ValueError("TV relay did not authorize independent read-only subtitle tap")
        if not callable(on_cue):raise ValueError("Actual subtitle cue consumer required")
        from .live_tv import validate_local_tv_url
        validate_local_tv_url(url)
        with self.lock:
            if self.state["active"]:raise ValueError("Subtitle tap already active")
            self.stop_flag.clear()
            self.state.update(active=True,status="probing",reason=None,cues=0,
                              candidate_stream=None,last_cue_at=None,language="und")
            self.thread=threading.Thread(target=self._run,args=(url,language,on_cue),
                                         daemon=True,name="tihulu-tv-teletext-subtitles")
            self.thread.start()
            return self.status()

    def _run(self,url,language,on_cue):
        reason=None
        try:
            ffprobe,ffmpeg=self.which("ffprobe"),self.which("ffmpeg")
            if not ffmpeg or not ffprobe:raise RuntimeError("ffmpeg and ffprobe are required for subtitle extraction")
            listed=self.run([ffmpeg,"-hide_banner","-decoders"],
                            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL,timeout=4,check=False)
            if listed.returncode or b"libzvbi_teletextdec" not in listed.stdout[:1_000_000]:
                raise RuntimeError("ffmpeg lacks libzvbi DVB Teletext decoder")
            if self.stop_flag.is_set():return
            found=self.run([ffprobe,"-v","error","-probesize","1000000",
                            "-analyzeduration","2000000","-show_streams",
                            "-of","json",url],
                           stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL,timeout=6,check=False)
            if found.returncode:raise RuntimeError("Could not probe authorized MPEG-TS subtitle streams")
            candidates=teletext_streams(found.stdout,language)
            if not candidates:raise RuntimeError("No advertised DVB Teletext text subtitle stream")
            chosen=candidates[0]
            if self.stop_flag.is_set():return
            opts={"stdin":subprocess.DEVNULL,"stdout":subprocess.PIPE,
                  "stderr":subprocess.DEVNULL,"close_fds":True}
            if os.name=="nt":opts["creationflags"]=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
            else:opts["start_new_session"]=True
            proc=self.popen(teletext_argv(ffmpeg,url,chosen["index"]),**opts)
            with self.lock:
                self.process=proc
                self.state.update(status="listening",candidate_stream=chosen["index"],
                                  language=chosen["language"])
            assert proc.stdout is not None
            block=[]
            for data in proc.stdout:
                if self.stop_flag.is_set():break
                if len(data)>8192: block.clear();continue
                line=data.decode("utf-8","replace").rstrip("\r\n")
                if not line.strip():
                    cue=parse_cue("\n".join(block))
                    block.clear()
                    if cue is not None:
                        try:on_cue(cue,chosen["language"])
                        except (ValueError,RuntimeError,OSError) as exc:
                            reason="Received subtitle could not be stored: "+str(exc)[:100]
                        else:
                            with self.lock:
                                self.state["cues"]+=1
                                self.state["last_cue_at"]=self.clock()
                                self.state["status"]="receiving"
                elif len(block)<64:block.append(line)
                else:block.clear()
            if not self.stop_flag.is_set():
                reason=reason or "Subtitle stream ended or decoder failed"
        except (ValueError,RuntimeError,OSError,subprocess.TimeoutExpired) as exc:
            reason=str(exc)[:200]
        finally:
            with self.lock:
                terminate_owned(self.process)
                if self.process and self.process.stdout:
                    try:self.process.stdout.close()
                    except OSError:pass
                self.process=None
                self.state.update(active=False,
                    status="stopped" if self.stop_flag.is_set() else "unavailable",
                    reason=reason)

    def stop(self,*,wait=False):
        self.stop_flag.set()
        with self.lock:proc,thread=self.process,self.thread
        terminate_owned(proc)
        if wait and thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2)
        with self.lock:
            self.state["active"]=False
            if self.state["status"]!="unavailable":self.state["status"]="stopped"
            return dict(self.state)
