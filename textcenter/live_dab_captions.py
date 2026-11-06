"""Opt-in speech tap of a real, already-running welle-cli DAB audio service.

Only this class's own ffmpeg decoder is started/stopped. The welle-cli RF
process (which may belong to another application) is NEVER controlled.
Audio playback does not depend on ASR success.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
import time
import uuid

from .compute import detect_devices
from .dab_bridge import DABError, DAB_HZ, _local_get, open_dab_audio
from .speech import SpeechPipeline, SpeechError, SAMPLE_RATE
from .transcripts import TranscriptStore

SESSION_TIMEOUT = 18


class LiveDABCaptionError(RuntimeError):
    pass


class LiveDABCaptions:
    def __init__(self, transcripts: TranscriptStore, *, timeout=SESSION_TIMEOUT,
                 which=None, opener=None, profile=None, popen=None):
        self.transcripts = transcripts
        self.timeout = timeout
        self.which = which or shutil.which
        self.opener = opener or open_dab_audio
        self.profile = profile or detect_devices
        self.popen = popen or subprocess.Popen
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.decoder = None
        self.stream = None
        self.speech = None
        self.producer = None
        self.consumer = None
        self.watcher = None
        self.last_seen = 0
        self.state = {
            "active": False, "status": "idle", "session": None,
            "channel": None, "service_id": None,
            "unavailable_reason": None, "error": None,
            "source": "real_welle_cli_mp3"
        }

    def status(self, heartbeat=False):
        with self.lock:
            if heartbeat and self.state["active"]:
                self.last_seen = time.monotonic()
            result = dict(self.state)
            result["speech"] = self.speech.status() if self.speech else {
                "enabled": False,
                "reason": self.state.get("unavailable_reason") or "No active speech decoder"
            }
            return result

    def start(self, *, channel, service_id, language="en",
              translate_to=None, backend="auto", translation_backend="auto"):
        if channel not in DAB_HZ:
            raise ValueError("Unsupported or unverified DAB channel")
        if not isinstance(service_id, str):
            raise ValueError("Invalid DAB service identifier")
        with self.lock:
            if self.state["active"]:
                raise LiveDABCaptionError("Stop existing DAB captions before changing service")
            self.stop_event.clear()
            sid = service_id.lower()
            session = uuid.uuid4().hex
            self.state = {
                "active": False, "status": "starting", "session": session,
                "channel": channel, "service_id": sid, "error": None,
                "unavailable_reason": None, "source": "real_welle_cli_mp3"
            }
            try:
                self.speech = SpeechPipeline(
                    store=self.transcripts, session=session,
                    source_id="dab:"+channel+":"+sid, source_language=language,
                    target_language=translate_to, backend=backend,
                    profile=self.profile(), medium="dab",
                    translation_backend=translation_backend
                )
            except (SpeechError, ValueError, ImportError, RuntimeError) as exc:
                self.speech = None
                self.state.update(status="unavailable",
                                  unavailable_reason=str(exc)[:220])
                return self.status()
            binary = self.which("ffmpeg")
            if not binary:
                self.speech.stop()
                self.speech = None
                self.state.update(status="unavailable",
                    unavailable_reason="ffmpeg is not installed; DAB audio remains playable")
                return self.status()
            try:
                # The opener validates live decoder FIC service metadata and
                # opens only a fixed loopback MP3 URL without redirects.
                self.stream = self.opener(sid)
                current = _local_get("/channel", 64).decode("ascii","ignore").strip().upper()
                if current != channel:
                    raise LiveDABCaptionError("DAB decoder is not currently tuned to selected block")
                args=[binary,"-nostdin","-hide_banner","-loglevel","error",
                      "-f","mp3","-i","pipe:0","-vn","-ac","1",
                      "-ar",str(SAMPLE_RATE),"-f","s16le","pipe:1"]
                opts={"stdin":subprocess.PIPE,"stdout":subprocess.PIPE,
                      "stderr":subprocess.DEVNULL,"close_fds":True}
                if os.name=="nt":
                    opts["creationflags"]=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
                else:
                    opts["start_new_session"]=True
                self.decoder=self.popen(args,**opts)
            except (DABError, LiveDABCaptionError, OSError, ValueError) as exc:
                self._stop_locked("unavailable",str(exc)[:220])
                return self.status()
            self.state.update(active=True,status="running")
            self.last_seen=time.monotonic()
            self.producer=threading.Thread(target=self._feed_mp3,
                                          daemon=True,name="tihulu-dab-mp3-tap")
            self.consumer=threading.Thread(target=self._decode_pcm,
                                          daemon=True,name="tihulu-dab-speech-pcm")
            self.watcher=threading.Thread(target=self._watch,
                                         daemon=True,name="tihulu-dab-speech-watchdog")
            self.producer.start()
            self.consumer.start()
            self.watcher.start()
            return self.status()

    def _feed_mp3(self):
        try:
            stream=self.stream
            decoder=self.decoder
            assert stream is not None and decoder is not None and decoder.stdin is not None
            while not self.stop_event.is_set():
                block=stream.read(8192)
                if not block:
                    break
                decoder.stdin.write(block)
                decoder.stdin.flush()
        except (OSError, ValueError, BrokenPipeError, TimeoutError):
            pass
        finally:
            if self.decoder and self.decoder.stdin:
                try:self.decoder.stdin.close()
                except (OSError,ValueError):pass

    def _decode_pcm(self):
        reason=None
        try:
            decoder=self.decoder
            assert decoder is not None and decoder.stdout is not None
            while not self.stop_event.is_set():
                chunk=decoder.stdout.read(16384)
                if not chunk:
                    break
                if self.speech:
                    self.speech.feed(chunk)
        except (OSError,ValueError) as exc:
            reason="Audio decoder ended: "+str(exc)[:100]
        finally:
            with self.lock:
                if self.state["active"]:
                    self._stop_locked("stopped",reason or "DAB audio tap ended")

    def _watch(self):
        while not self.stop_event.wait(1):
            with self.lock:
                if not self.state["active"]:
                    return
                if time.monotonic()-self.last_seen>self.timeout:
                    self._stop_locked("stopped","Browser heartbeat expired")
                    return
                expected=self.state["channel"]
            try:
                actual=_local_get("/channel",64).decode("ascii","ignore").strip().upper()
                if actual!=expected:
                    with self.lock:
                        if self.state["active"]:
                            self._stop_locked("stopped","DAB block changed")
                    return
            except DABError:
                with self.lock:
                    if self.state["active"]:
                        self._stop_locked("stopped","DAB receiver disconnected")
                return

    @staticmethod
    def _terminate(proc):
        if proc is None or proc.poll() is not None:return
        try:
            if os.name=="nt":proc.terminate()
            else:os.killpg(proc.pid,signal.SIGTERM)
            proc.wait(timeout=0.6)
        except (OSError,subprocess.TimeoutExpired):
            try:
                if os.name=="nt":proc.kill()
                else:os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=0.4)
            except (OSError,subprocess.TimeoutExpired):pass

    def _stop_locked(self,status="stopped",reason=None):
        self.stop_event.set()
        self._terminate(self.decoder)
        if self.stream:
            try:self.stream.close()
            except (OSError,ValueError):pass
        self.stream=None
        if self.decoder:
            for pipe in (self.decoder.stdin,self.decoder.stdout):
                if pipe:
                    try:pipe.close()
                    except (OSError,ValueError):pass
        self.decoder=None
        if self.speech:
            self.speech.stop()
            self.speech=None
        self.state.update(active=False,status=status,
                          unavailable_reason=reason if status=="unavailable" else
                            self.state.get("unavailable_reason"),
                          error=reason if status not in ("unavailable","idle") else None)

    def stop(self,*,wait=False):
        with self.lock:
            if self.state["active"] or self.decoder or self.speech:
                self._stop_locked()
            snapshot=self.status()
        if wait:
            for thread in (self.producer,self.consumer,self.watcher):
                if thread and thread.is_alive() and thread is not threading.current_thread():
                    thread.join(timeout=2)
        return snapshot
