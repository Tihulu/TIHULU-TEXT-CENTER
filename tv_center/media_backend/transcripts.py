"""Media-owned transcript store; no other application's database schema.

Local captions and recording_export remain the authoritative cue timeline.
This durable optional store supports the previous explicit TranscriptStore API.
No database or directories are created on import.
"""
from __future__ import annotations
import re
import uuid
from .database import MediaTranscriptStore as Store, clean_text, utc_now
from .languages import LANGUAGES, validate_language
from .translation import TranslatorUnavailable, translate_offline, installed_translation_pairs

class TranscriptStore:
    def __init__(self,store:Store):
        self.store=store
        with store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS captions (
                    id TEXT PRIMARY KEY, session TEXT NOT NULL, medium TEXT NOT NULL,
                    source_id TEXT NOT NULL, original_language TEXT NOT NULL,
                    original_text TEXT NOT NULL, translated_language TEXT,
                    translated_text TEXT, translator_engine TEXT,
                    compute_backend TEXT NOT NULL, started_seconds REAL NOT NULL,
                    ended_seconds REAL NOT NULL, captured_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS captions_recent
                    ON captions(session,started_seconds);
            """)

    def add(self,*,session:str,medium:str,source_id:str,language:str,
            text:str,backend:str,start:float,end:float,
            translated=None,target=None,translation_engine=None)->str:
        if not isinstance(session,str) or not re.fullmatch(r"[0-9a-f]{32}",session):
            raise ValueError("Invalid session")
        if medium not in ("fm","dab","dvb_tv"):
            raise ValueError("Invalid stream medium")
        if language not in (*LANGUAGES,"und") or (target is not None and target not in LANGUAGES):
            raise ValueError("Unsupported subtitle language")
        if type(start) not in (int,float) or type(end) not in (int,float) or not (0<=start<end<86400):
            raise ValueError("Invalid subtitle timing")
        original=clean_text(text,3000)
        if not original:
            raise ValueError("Empty speech transcript")
        row={
            "id":uuid.uuid4().hex,"session":session,"medium":medium,
            "source_id":clean_text(source_id,120),"original_language":language,
            "original_text":original,
            "translated_language":target if isinstance(translated,str) and translated.strip() else None,
            "translated_text":clean_text(translated,12000) if isinstance(translated,str) and translated.strip() else None,
            "translator_engine":(translation_engine or "argos_offline") if translated else None,
            "compute_backend":clean_text(backend,80),"started_seconds":float(start),
            "ended_seconds":float(end),"captured_at":utc_now(),
        }
        with self.store.connect() as db:
            db.execute("""INSERT INTO captions
              (id,session,medium,source_id,original_language,original_text,
               translated_language,translated_text,translator_engine,compute_backend,
               started_seconds,ended_seconds,captured_at)
              VALUES(:id,:session,:medium,:source_id,:original_language,:original_text,
                :translated_language,:translated_text,:translator_engine,:compute_backend,
                :started_seconds,:ended_seconds,:captured_at)""",row)
        return row["id"]

    def list(self,session:str|None=None,limit:int=200)->list[dict]:
        limit=max(1,min(limit,2000))
        with self.store.connect() as db:
            if session:
                return [dict(x) for x in db.execute(
                    "SELECT * FROM captions WHERE session=? ORDER BY started_seconds LIMIT ?",
                    (session,limit)).fetchall()]
            return [dict(x) for x in db.execute(
                "SELECT * FROM captions ORDER BY captured_at DESC LIMIT ?",
                (limit,)).fetchall()]

    def translate_later(self,caption_id:str,target_language:str,
                        translator=None,backend:str="auto")->dict:
        target=validate_language(target_language)
        with self.store.connect() as db:
            row=db.execute("SELECT * FROM captions WHERE id=?",(caption_id,)).fetchone()
        if row is None:
            raise KeyError("Unknown caption")
        original=row["original_language"]
        if original not in LANGUAGES:
            raise TranslatorUnavailable("Original speech language unknown; select language before translating")
        if translator is None:
            result=translate_offline(row["original_text"],original,target,backend=backend)
        else:
            result=translator(row["original_text"],original,target)
        # Match the original Text Center normalization contract for delayed
        # translations as well as initial captured and exported subtitles.
        result = clean_text(result, 12000)
        with self.store.connect() as db:
            db.execute("""UPDATE captions SET translated_language=?,translated_text=?,
                 translator_engine=? WHERE id=?""",
                       (target,result,("argos_"+backend if backend!="auto" else "argos_auto")
                        if target!=original else "identity",caption_id))
            updated=db.execute("SELECT * FROM captions WHERE id=?",(caption_id,)).fetchone()
            return dict(updated)

    @staticmethod
    def _clock(seconds,separator=",")->str:
        millis=round(seconds*1000)
        hours,millis=divmod(millis,3_600_000)
        mins,millis=divmod(millis,60_000)
        secs,millis=divmod(millis,1000)
        return f"{hours:02}:{mins:02}:{secs:02}{separator}{millis:03}"

    def export(self,session:str,*,fmt:str="srt",translated:bool=False)->str:
        if fmt not in ("srt","vtt"):raise ValueError("Only SRT or VTT export")
        items=self.list(session,limit=2000)
        lines=["WEBVTT",""] if fmt=="vtt" else []
        for i,row in enumerate(items,1):
            original=row["original_text"]
            translated_text=row["translated_text"] if translated else None
            content=translated_text if translated_text else (
                f"[UNTRANSLATED {row['original_language'].upper()}] {original}"
                if translated else original
            )
            # Make untrusted source text a single plain subtitle line.
            content=re.sub(r"[\x00-\x1f\x7f]"," ",content).strip()
            if fmt=="srt":lines.append(str(i))
            sep="." if fmt=="vtt" else ","
            lines.append(self._clock(row["started_seconds"],sep)+
                " --> "+self._clock(row["ended_seconds"],sep))
            lines.extend((content,""))
        return "\n".join(lines)
