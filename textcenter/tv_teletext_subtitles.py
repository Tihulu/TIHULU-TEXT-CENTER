"""Optional real Teletext subtitle extraction from an authorized shared TV relay.

Does not access a DVB device, retune, change the TV Teletext viewer or start
another RF process. A second read of the *existing loopback MPEG-TS relay* is
allowed ONLY with a trusted operator-configured multi-client permission.
FFmpeg/libzvbi text cues are source-attributed; no synthetic text or OCR.
"""
from __future__ import annotations
import os
import re
import signal
import subprocess
import threading
from urllib.parse import urlsplit

_TIME=re.compile(r"^(\d{2,3}):(\d\d):(\d\d)[,.](\d{3})$")
_TIMELINE=re.compile(
    r"^(\d{2,3}:\d\d:\d\d[,.]\d{3})\s*-->\s*(\d{2,3}:\d\d:\d\d[,.]\d{3})(?:\s+.*)?$")
_INDEX=re.compile(r"^\d{1,9}$")


def _seconds(stamp):
    found=_TIME.fullmatch(stamp.strip())
    if not found:return None
    hours,minutes,seconds,millis=map(int,found.groups())
    if hours>23 or minutes>59 or seconds>59:return None
    return hours*3600+minutes*60+seconds+millis/1000


def parse_subrip_cue(block):
    """Accept bounded, timed plain-text SRT only; reject broken huge durations.

    Real FFmpeg Teletext streams can produce ~1193-hour ends without
    -fix_sub_duration. Such times are never treated as valid captions.
    """
    if not isinstance(block,str) or len(block)>5000:return None
    lines=[x.strip() for x in block.replace("\r","").split("\n") if x.strip()]
    if not lines:return None
    if _INDEX.fullmatch(lines[0]):lines=lines[1:]
    if len(lines)<2:return None
    match=_TIMELINE.fullmatch(lines[0])
    if not match:return None
    start,end=(_seconds(x) for x in match.groups())
    if start is None or end is None or not 0<=start<end<86400:return None
    if end-start>30:return None  # stale/broken teletext timing
    raw="\n".join(lines[1:])
    # Teletext formatting/control bytes are not actual speech text.
    cleaned="".join(ch for ch in raw if ch=="\n" or ch=="\t" or ord(ch)>=32).strip()
    if not cleaned or len(cleaned)>2400:return None
    return {"start":start,"end":end,"text":cleaned}


def teletext_ffmpeg_argv(binary,url,*,subtitle_index=0,page="subtitle"):
    """Operate on a *fixed operator-configured local relay*, never user URLs."""
    if not isinstance(binary,str) or not binary:raise ValueError("ffmpeg unavailable")
    if not isinstance(url,str):raise ValueError("Missing relay URL")
    parsed=urlsplit(url)
    if (parsed.scheme!="http" or parsed.hostname!="127.0.0.1" or
        parsed.username or parsed.password or parsed.fragment or parsed.query or
        not parsed.port or not 1024<=parsed.port<=65535 or
        not parsed.path.startswith("/stream/") or parsed.path=="/stream/"):
        raise ValueError("Not an authorized fixed local TV stream")
    if type(subtitle_index) is not int or not 0<=subtitle_index<=15:
        raise ValueError("Invalid subtitle stream index")
    if page!="subtitle" and (type(page) is not int or not 100<=page<=899):
        raise ValueError("Invalid Teletext subtitle page")
    # libzvbi is the only supported text source. If stream/codec not present,
    # this separate decoder fails closed without touching TV video/ASR.
    return [binary,"-hide_banner","-loglevel","error","-nostdin",
        "-txt_page",str(page),"-txt_format","text","-fix_sub_duration",
        "-i",url,"-map","0:s:"+str(subtitle_index),
        "-c:s","srt","-f","srt","pipe:1"]


class TeletextSubtitleSidecar:
    def __init__(self,*,on_cue,popen=None,lookup=None):
        import shutil
        self.on_cue=on_cue
        self.popen=popen or subprocess.Popen
        self.lookup=lookup or shutil.which
        self.lock=threading.RLock()
        self.process=None
        self.worker=None
        self.stop_flag=threading.Event()
        self.state={"active":False,"status":"idle","received":0,"error":None,
                    "source":"real_decoded_teletext","requires_safe_relay":True}

    def status(self):
        with self.lock:return dict(self.state)

    def start(self,url,*,share_safe=False,subtitle_index=0,page="subtitle"):
        if share_safe is not True:
            raise ValueError("Second stream read requires explicitly safe multi-client relay")
        with self.lock:
            if self.state["active"]:raise RuntimeError("Teletext reader already running")
            executable=self.lookup("ffmpeg")
            if not executable:
                self.state.update(status="unavailable",error="ffmpeg unavailable")
                return self.status()
            argv=teletext_ffmpeg_argv(executable,url,
                subtitle_index=subtitle_index,page=page)
            self.stop_flag.clear()
            kwargs={"stdin":subprocess.DEVNULL,"stdout":subprocess.PIPE,
                    "stderr":subprocess.DEVNULL,"close_fds":True}
            if os.name=="nt":
                kwargs["creationflags"]=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
            else:kwargs["start_new_session"]=True
            try:self.process=self.popen(argv,**kwargs)
            except OSError as exc:
                self.state.update(status="unavailable",
                                  error="Teletext ffmpeg decoder unavailable: "+str(exc)[:110])
                return self.status()
            self.state.update(active=True,status="waiting_for_real_subtitles",
                received=0,error=None)
            self.worker=threading.Thread(target=self._run,
                daemon=True,name="tihulu-tv-teletext-subtitle-reader")
            self.worker.start()
            return self.status()

    def _run(self):
        pending=[]
        count=0
        try:
            proc=self.process
            assert proc is not None and proc.stdout is not None
            for raw in proc.stdout:
                if self.stop_flag.is_set():break
                # Text is decoded only from FFmpeg's actual subtitle packets.
                line=raw.decode("utf-8","replace")
                if not line.strip():
                    if pending:
                        cue=parse_subrip_cue("".join(pending))
                        pending=[];count=0
                        if cue:
                            try:self.on_cue(cue)
                            except (OSError,ValueError,RuntimeError):pass
                            else:
                                with self.lock:
                                    self.state["received"]+=1
                                    self.state["status"]="receiving_real_teletext"
                else:
                    count+=len(line)
                    if count>5000:
                        pending=[];count=0
                    else:pending.append(line)
        except (OSError,ValueError) as exc:
            with self.lock:self.state["error"]=str(exc)[:130]
        finally:
            with self.lock:
                if self.process is proc and not self.stop_flag.is_set():
                    self.state.update(active=False,status="decoder_ended",
                        error=self.state["error"] or
                        "No supported Teletext subtitle packets or libzvbi decoder unavailable")
                if proc and proc.stdout:
                    try:proc.stdout.close()
                    except (OSError,ValueError):pass

    def stop(self,*,wait=False):
        with self.lock:
            self.stop_flag.set()
            proc=self.process
            if proc is not None and proc.poll() is None:
                try:
                    if os.name=="nt":proc.terminate()
                    else:os.killpg(proc.pid,signal.SIGTERM)
                    proc.wait(timeout=0.8)
                except (OSError,subprocess.TimeoutExpired):
                    try:
                        if os.name=="nt":proc.kill()
                        else:os.killpg(proc.pid,signal.SIGKILL)
                        proc.wait(timeout=0.5)
                    except (OSError,subprocess.TimeoutExpired):pass
            self.process=None
            self.state.update(active=False,status="stopped")
            worker=self.worker
        if wait and worker and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=2)
        return self.status()
