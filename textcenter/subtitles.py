"""Local caption timeline, offline translation and optional Whisper ASR.

Real transcription is possible ONLY with installed faster-whisper and a
preinstalled multilingual local model. Offline translation requires installed
Argos language packages. No model downloads, remote API, invented subtitles,
or anonymous access. Video and radio use the same caption timeline schema.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from threading import Lock
import uuid

from .compute import LANGUAGES,resolve_device
from .core import Store,utc_now,clean_text

MAX_CUES=20000


def language_pair(source:str,target:str)->tuple[str,str]:
    if source not in LANGUAGES or target not in LANGUAGES:
        raise ValueError("Languages must be en, de or tr")
    return source,target


def local_translate(text:str,source:str,target:str)->str:
    language_pair(source,target)
    if source==target:return text
    if not isinstance(text,str) or len(text)>4000:raise ValueError("Invalid transcript text")
    try:
        import argostranslate.translate
        available=argostranslate.translate.get_installed_languages()
        src=next((x for x in available if x.code==source),None)
        dst=next((x for x in available if x.code==target),None)
        if not src or not dst:
            raise ValueError("Offline Argos translation language package missing")
        return src.get_translation(dst).translate(text)
    except ImportError as exc:
        raise ValueError("Argos Translate is not installed") from exc
    except (AttributeError,LookupError) as exc:
        raise ValueError("No offline Argos translation path for selected languages") from exc


class CaptionStore:
    def __init__(self,store:Store):
        self.store=store
        self._mutex=Lock()
        with self.store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS caption_sessions (
                    id TEXT PRIMARY KEY,
                    media_kind TEXT NOT NULL, source_label TEXT NOT NULL,
                    source_lang TEXT NOT NULL, target_lang TEXT NOT NULL,
                    device TEXT NOT NULL, backend TEXT NOT NULL,
                    created_at TEXT NOT NULL, finished_at TEXT,
                    store_original INTEGER NOT NULL,
                    store_translation INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS caption_cues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL, sequence INTEGER NOT NULL,
                    from_seconds REAL NOT NULL, to_seconds REAL NOT NULL,
                    original_text TEXT NOT NULL,
                    translated_text TEXT NOT NULL DEFAULT '',
                    translated_to TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, sequence)
                );
                CREATE INDEX IF NOT EXISTS caption_session_idx ON caption_cues(session_id,sequence);
            """)

    def new_session(self,*,media_kind:str,source_label:str,source_lang:str,
                    target_lang:str,device:str,backend:str,
                    store_original:bool=False,store_translation:bool=False)->str:
        if media_kind not in ("fm_radio","dvb_tv","recorded_media"):
            raise ValueError("Invalid caption source type")
        language_pair(source_lang,target_lang)
        if type(store_original) is not bool or type(store_translation) is not bool:
            raise ValueError("Saving flags must be boolean")
        if store_translation and not store_original:
            raise ValueError("Saving translations requires storing originals for accurate history")
        label=clean_text(source_label,140)
        if not label:raise ValueError("Source label required")
        session=uuid.uuid4().hex
        with self.store.connect() as db:
            db.execute("""INSERT INTO caption_sessions
                (id,media_kind,source_label,source_lang,target_lang,device,backend,
                 created_at,store_original,store_translation)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (session,media_kind,label,source_lang,target_lang,device,backend,
                 utc_now(),int(store_original),int(store_translation)))
        return session

    def add_cue(self,session_id:str,*,sequence:int,begin:float,end:float,
                original_text:str,translation:str="",translated_to:str="")->dict:
        if not isinstance(session_id,str) or len(session_id)!=32:
            raise ValueError("Invalid session ID")
        if type(sequence) is not int or not 1<=sequence<=MAX_CUES:
            raise ValueError("Caption sequence out of range")
        if type(begin) not in (int,float) or type(end) not in (int,float) or (
            not 0<=begin<end<=86400):
            raise ValueError("Invalid cue timing")
        text=clean_text(original_text,4000)
        translation=clean_text(translation,4000)
        if not text:raise ValueError("Transcript must originate from a speech decoder")
        if translated_to and translated_to not in LANGUAGES:
            raise ValueError("Invalid translation language")
        if translation and not translated_to:
            raise ValueError("Translated text requires language attribution")
        with self.store.connect() as db:
            meta=db.execute("SELECT * FROM caption_sessions WHERE id=?",(session_id,)).fetchone()
            if meta is None:raise KeyError("Caption session missing")
            if not meta["store_original"]:
                return {"stored":False}
            db.execute("""INSERT INTO caption_cues
                (session_id,sequence,from_seconds,to_seconds,
                 original_text,translated_text,translated_to,created_at)
                VALUES(?,?,?,?,?,?,?,?)""",(
                session_id,sequence,float(begin),float(end),text,
                translation if meta["store_translation"] else "",
                translated_to if meta["store_translation"] else "",utc_now()))
        return {"stored":True,"sequence":sequence}

    def finish(self,session_id:str):
        with self.store.connect() as db:
            db.execute("UPDATE caption_sessions SET finished_at=? WHERE id=?",(utc_now(),session_id))

    def sessions(self)->list[dict]:
        with self.store.connect() as db:
            rows=db.execute("""SELECT s.*,
                 (SELECT COUNT(*) FROM caption_cues c WHERE c.session_id=s.id) AS saved_cues
                 FROM caption_sessions s ORDER BY created_at DESC LIMIT 100""").fetchall()
            return [dict(x) for x in rows if x["store_original"]]

    def cues(self,session_id:str)->list[dict]:
        if not isinstance(session_id,str) or len(session_id)!=32:
            raise ValueError("Invalid session ID")
        with self.store.connect() as db:
            return [dict(x) for x in db.execute("""
               SELECT sequence,from_seconds,to_seconds,original_text,translated_text,translated_to
               FROM caption_cues WHERE session_id=? ORDER BY sequence LIMIT ?""",
               (session_id,MAX_CUES)).fetchall()]

    def translate_saved(self,session_id:str,target_lang:str,translator=None)->dict:
        if target_lang not in LANGUAGES:raise ValueError("Invalid target language")
        with self.store.connect() as db:
            meta=db.execute("SELECT * FROM caption_sessions WHERE id=?",(session_id,)).fetchone()
            if meta is None or not meta["store_original"]:
                raise KeyError("No saved original transcript")
            source=meta["source_lang"]
        fn=translator or local_translate
        translated=[]
        for cue in self.cues(session_id):
            if cue["translated_to"]==target_lang and cue["translated_text"]:
                continue
            new=clean_text(fn(cue["original_text"],source,target_lang),4000)
            if not new:raise ValueError("Translator returned empty text; original retained")
            translated.append((new,target_lang,session_id,cue["sequence"]))
        with self.store.connect() as db:
            for item in translated:
                db.execute("""UPDATE caption_cues SET translated_text=?,translated_to=?
                   WHERE session_id=? AND sequence=?""",item)
        return {"translated":len(translated),"target_lang":target_lang,
                "source_lang":source,"session":session_id}

    @staticmethod
    def _clock(seconds:float,vtt:bool)->str:
        ms=max(0,int(round(seconds*1000)))
        hours,remainder=divmod(ms,3_600_000)
        minutes,remainder=divmod(remainder,60_000)
        sec,millis=divmod(remainder,1000)
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"+("." if vtt else ",")+f"{millis:03d}"

    def subtitle_file(self,session_id:str,*,language:str="original",format:str="srt")->bytes:
        if format not in ("srt","vtt"):raise ValueError("Only SRT/VTT export")
        if language not in ("original","translated"):raise ValueError("Invalid caption layer")
        cues=self.cues(session_id)
        lines=["WEBVTT\n"] if format=="vtt" else []
        for n,cue in enumerate(cues,1):
            message=cue["original_text"] if language=="original" else cue["translated_text"]
            if not message:continue
            if format=="srt":lines.append(str(n))
            lines.append(self._clock(cue["from_seconds"],format=="vtt")+
                         " --> "+self._clock(cue["to_seconds"],format=="vtt"))
            lines.append(message+"\n")
        return ("\n".join(lines)).encode("utf-8")


def offline_whisper(asr_audio,*,source_lang:str,device_info:dict,model_dir:str):
    """Run exactly one in-memory speech chunk, never download a model."""
    if source_lang not in LANGUAGES:raise ValueError("Unsupported speech language")
    if not model_dir or not Path(model_dir).is_dir():
        raise ValueError("Local Whisper model directory missing")
    try:from faster_whisper import WhisperModel
    except ImportError as exc:raise ValueError("faster-whisper not installed") from exc
    backend=device_info["backend"]
    selected=device_info["selected"]
    model=WhisperModel(model_dir,device=backend,
                       device_index=int(selected.split(":")[1]) if backend=="cuda" else 0,
                       compute_type="float16" if backend=="cuda" else "int8",
                       local_files_only=True)
    def infer(audio):
        segments,_=model.transcribe(audio,language=source_lang,task="transcribe",
                                    beam_size=2,vad_filter=True,
                                    condition_on_previous_text=False)
        return [(float(s.start),float(s.end),clean_text(s.text,4000)) for s in segments
                if s.text and s.end>s.start]
    return infer
