"""On-demand live radio caption worker: real PCM -> local STT -> optional translation.

The stream owns ONE RTL-SDR and fans out PCM without opening a second tuner.
No inference runs unless explicitly selected; bounded queues drop old chunks
instead of slowing down/destroying live audio. No automatic models/downloads.
"""
from __future__ import annotations
from collections import deque
import os
import queue
from threading import Event, Lock, Thread

from .compute import inventory_compute,resolve_device,LANGUAGES
from .subtitles import CaptionStore,language_pair,offline_whisper,local_translate
from .translation_runtime import select_translation_device,OfflineArgosProcess
from .core import clean_text

CAPTURE_CHUNK_SECONDS=8
PCM_RATE=32000
PCM_BYTES_PER_SECOND=PCM_RATE*2


def prepare_caption_options(options:dict,compute_info:dict|None=None,
                            validate_cuda=None)->dict:
    if not isinstance(options,dict):raise ValueError("Captions configuration must be a JSON object")
    if options.get("enabled") is not True:
        return {"enabled":False}
    source=options.get("source_lang")
    target=options.get("target_lang")
    language_pair(source,target)
    device=options.get("device","auto")
    selected=resolve_device(device,compute_info or inventory_compute(),
                            validate_cuda=validate_cuda)
    translate_live=options.get("translate_live",False)
    save_original=options.get("save_original",False)
    save_translation=options.get("save_translation",False)
    for value in (translate_live,save_original,save_translation):
        if type(value) is not bool:raise ValueError("Caption switches must be booleans")
    if save_translation and not save_original:
        raise ValueError("Saving translations requires also saving originals")
    translation_device=(
        select_translation_device(options.get("translation_device","auto"),
            compute_info or inventory_compute(),check_cuda=validate_cuda)
        if translate_live and source!=target else None
    )
    return {
        "enabled":True,"source_lang":source,"target_lang":target,
        "translation_device":translation_device,
        "device":selected,"translate_live":translate_live,
        "save_original":save_original,"save_translation":save_translation,
        "local_model_path":os.environ.get("TIHULU_WHISPER_MODEL",""),
    }


class LiveCaptionRunner:
    def __init__(self, archive:CaptionStore, config:dict,
                 *,source_label:str,media_kind:str="fm_radio",asr_factory=None,translator=None):
        if not config.get("enabled"):
            raise ValueError("Cannot start captions without explicit consent")
        self.archive=archive
        self.options=config
        self.asr_factory=asr_factory or (
            lambda: offline_whisper(None,
                source_lang=config["source_lang"],
                device_info=config["device"],
                model_dir=config["local_model_path"]))
        self.translator=translator
        self._stop=Event()
        self._lock=Lock()
        self._input:queue.Queue[tuple[int,bytes]] = queue.Queue(maxsize=3)
        self._raw=bytearray()
        self._clip_offset=0
        self._seen=0
        self._cues=deque(maxlen=80)
        self._state={
            "active":False,"status":"idle","error":None,"dropped_segments":0,
            "processed_segments":0,"cue_count":0,"device":config["device"],
            "source_lang":config["source_lang"],"target_lang":config["target_lang"],
            "live_translation":config["translate_live"],
            "save_original":config["save_original"],
            "save_translation":config["save_translation"],
        }
        self.session=archive.new_session(
            media_kind=media_kind,source_label=source_label,
            source_lang=config["source_lang"],target_lang=config["target_lang"],
            device=config["device"]["device_name"],backend="faster-whisper",
            store_original=config["save_original"],
            store_translation=config["save_translation"])
        self._state["session"]=self.session
        self._thread=None

    def start(self):
        with self._lock:
            self._state["active"]=True
            self._state["status"]="loading_local_stt"
        self._thread=Thread(target=self._work,name="tihulu-local-caption",daemon=True)
        self._thread.start()

    def feed_pcm(self,pcm:bytes):
        if self._stop.is_set() or not pcm:return
        with self._lock:
            self._raw.extend(pcm)
            length=PCM_BYTES_PER_SECOND*CAPTURE_CHUNK_SECONDS
            while len(self._raw)>=length:
                chunk=bytes(self._raw[:length])
                del self._raw[:length]
                index=self._clip_offset
                self._clip_offset+=CAPTURE_CHUNK_SECONDS
                try:self._input.put_nowait((index,chunk))
                except queue.Full:self._state["dropped_segments"]+=1

    def status(self)->dict:
        with self._lock:return {**self._state,"cues":list(self._cues)}

    def stop(self):
        self._stop.set()
        with self._lock:
            self._state["active"]=False
            if self._state["status"] not in ("error","completed"):
                self._state["status"]="stopping"

    def _work(self):
        argos=None
        try:
            if self.options["translate_live"] and self.options["source_lang"]!=self.options["target_lang"] and not self.translator:
                argos=OfflineArgosProcess(self.options["translation_device"])
                self.translator=argos.translate
            infer=self.asr_factory()
            with self._lock:self._state["status"]="running"
            while not self._stop.is_set():
                try:start,pcm=self._input.get(timeout=.25)
                except queue.Empty:continue
                # faster-whisper expects 16 kHz float32 audio. Avoid FFmpeg
                # subprocess and downsample mono 32 kHz PCM by exactly 2.
                try:
                    import numpy as np
                except ImportError:
                    # For independent lightweight unit tests; an actual
                    # faster-whisper installation includes NumPy itself.
                    from array import array
                    samples=array("h")
                    samples.frombytes(pcm)
                    audio=[x/32768.0 for x in samples[::2]]
                else:
                    audio=np.frombuffer(pcm,dtype="<i2").astype("float32")[::2]/32768.0
                output=infer(audio)
                with self._lock:self._state["processed_segments"]+=1
                for begin,end,text in output:
                    if self._stop.is_set():break
                    original=clean_text(text,4000)
                    if not original or end<=begin:continue
                    translated=""
                    if self.options["translate_live"] and (
                            self.options["source_lang"]!=self.options["target_lang"]):
                        try:
                            translated=clean_text(self.translator(
                                original,self.options["source_lang"],self.options["target_lang"]),4000)
                        except (ValueError,RuntimeError,ImportError) as error:
                            with self._lock:self._state["error"]="Translation unavailable: "+str(error)[:180]
                    with self._lock:
                        self._seen+=1
                        seq=self._seen
                        cue={
                            "sequence":seq,
                            "begin":round(start+begin,2),
                            "end":round(start+end,2),
                            "original":original,
                            "translated":translated,
                            "translated_to":self.options["target_lang"] if translated else "",
                        }
                        self._cues.append(cue)
                        self._state["cue_count"]=seq
                    if self.options["save_original"]:
                        self.archive.add_cue(
                            self.session,sequence=seq,
                            begin=float(start+begin),end=float(start+end),
                            original_text=original,
                            translation=translated if self.options["save_translation"] else "",
                            translated_to=self.options["target_lang"] if (
                                self.options["save_translation"] and translated) else "")
        except Exception as exc:
            with self._lock:
                self._state["status"]="error"
                self._state["error"]="ASR runtime failed: "+str(exc)[:180]
        finally:
            if argos is not None:argos.close()
            self.archive.finish(self.session)
            with self._lock:
                self._state["active"]=False
                if self._state["status"]!="error":
                    self._state["status"]="completed"
