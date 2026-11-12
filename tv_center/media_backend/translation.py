"""Source-attributed offline transcript persistence and *real* local translation.

No placeholder translations: Argos models must be installed for the selected
language pair. Original and translated text are stored separately. Captions
can be exported as SRT/VTT, including later off-line translation.
"""
from __future__ import annotations
from datetime import datetime,timezone
import importlib.util
import json
import os
import subprocess
import sys
import re
import sqlite3
import uuid

from .languages import LANGUAGES, validate_language
from tv_center.language_codes import language_code, translation_language


class TranslatorUnavailable(RuntimeError):
    pass


def installed_translation_pairs() -> list[dict]:
    if importlib.util.find_spec("argostranslate") is None:
        return []
    try:
        import argostranslate.translate as translate
        languages=translate.get_installed_languages()
        pairs=[]
        for source in languages:
            if not translation_language(source.code):continue
            for target in languages:
                if not translation_language(target.code) or target.code==source.code:
                    continue
                try:
                    source.get_translation(target)
                except (ValueError,LookupError,AttributeError):
                    continue
                pairs.append({"source":source.code,"target":target.code,
                              "engine":"argos_offline"})
        return pairs
    except (ImportError,RuntimeError,OSError):
        return []


def translation_devices() -> dict:
    """Real Argos package/pair availability, separate from speech readiness."""
    pairs=installed_translation_pairs()
    cuda=False
    try:
        import ctranslate2
        cuda=ctranslate2.get_cuda_device_count()>0
    except (ImportError,OSError,RuntimeError,ValueError):
        pass
    return {
        "pairs":pairs,
        "cpu_available":bool(pairs),
        "gpu_available":bool(pairs) and cuda,
        "npu_available":False,
        "npu_note":"No verified NPU translator backend; ASR NPU support is separate",
        "engines":["argos_cpu","argos_cuda" if cuda else "argos_cuda_unavailable"],
        "no_automatic_download":True,
    }


# Run CTranslate2 CUDA in its own Python process: its device choice is
# initialized on import, and never changes the main server process's CPU
# Argos translation setting. Source text is sent over stdin, NOT argv.
_GPU_WORKER = """
import json,sys
import argostranslate.translate as argos
r=json.load(sys.stdin)
langs={x.code:x for x in argos.get_installed_languages()}
src,dst=langs[r['source']],langs[r['target']]
result=src.get_translation(dst).translate(r['text'])
json.dump({'translated':result},sys.stdout)
"""


def translate_offline(text:str,source:str,target:str,backend:str="auto")->str:
    source,target=language_code(source),language_code(target)
    if backend not in ("auto","cpu","gpu","npu"):
        raise ValueError("Translator backend must be auto, cpu, gpu or npu")
    if not isinstance(text,str) or not text.strip() or len(text)>12000:
        raise ValueError("Translation text must be 1–12000 characters")
    if source==target:
        return text
    # An Argos CPU request must never enumerate every translation graph
    # or initialise CTranslate2 CUDA merely to translate ONE phrase.
    # Cold GPU discovery on each six-second live clip can exceed the
    # caption budget and produce false "language pack unavailable" errors.
    if backend=="npu":
        raise TranslatorUnavailable("No tested NPU translation engine/model installed")
    if backend=="auto":
        backend="cpu"  # explicit GPU is separately selectable and verified
    if backend=="gpu":
        devices=translation_devices()
        if not devices["gpu_available"]:
            raise TranslatorUnavailable("CUDA CTranslate2 GPU translation unavailable or models missing")
        env=os.environ.copy()
        env["ARGOS_DEVICE_TYPE"]="cuda"
        env["TRANSFORMERS_OFFLINE"]="1"
        env["HF_HUB_OFFLINE"]="1"
        try:
            output=subprocess.run([sys.executable,"-c",_GPU_WORKER],
                input=json.dumps({"text":text,"source":source,"target":target}).encode("utf-8"),
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                timeout=55,env=env,check=False)
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise TranslatorUnavailable("CUDA translation subprocess unavailable") from exc
        if output.returncode!=0 or len(output.stdout)>64000:
            raise TranslatorUnavailable("Local CUDA translation failed")
        try:translated=json.loads(output.stdout)["translated"]
        except (ValueError,KeyError,TypeError) as exc:
            raise TranslatorUnavailable("Invalid local CUDA translation result") from exc
        if not isinstance(translated,str) or not translated.strip():
            raise TranslatorUnavailable("CUDA translation produced no text")
        return translated[:12000]
    try:
        import argostranslate.translate as translate
        languages={x.code:x for x in translate.get_installed_languages()}
        if source not in languages or target not in languages:
            raise TranslatorUnavailable(
                "Argos language packages unavailable for "+
                source.upper()+" → "+target.upper()+
                "; install both directions or matching English pivot packs")
        src_lang, dst_lang=languages[source],languages[target]
        try:
            model=src_lang.get_translation(dst_lang)
        except (KeyError,AttributeError,ValueError,LookupError):
            model=None
        if model is not None:
            # Argos may itself return a composite source→English→target
            # model when both directed packs are installed.
            output=model.translate(text)
        elif source!="en" and target!="en" and "en" in languages:
            english=languages["en"]
            try:
                to_english=src_lang.get_translation(english)
                from_english=english.get_translation(dst_lang)
            except (KeyError,AttributeError,ValueError,LookupError) as exc:
                raise TranslatorUnavailable(
                    "Argos route missing: "+source.upper()+
                    " → EN → "+target.upper()+
                    ". Install both required directed language packs.") from exc
            intermediate=to_english.translate(text)
            if not isinstance(intermediate,str) or not intermediate.strip():
                raise TranslatorUnavailable(
                    "Argos English-pivot first stage produced no text")
            output=from_english.translate(intermediate)
        else:
            raise TranslatorUnavailable(
                "Argos direct translation package missing: "+
                source.upper()+" → "+target.upper())
    except (ImportError,KeyError,AttributeError,ValueError,LookupError) as exc:
        raise TranslatorUnavailable(
            "Argos Translate model missing for "+source.upper()+
            " → "+target.upper()) from exc
    if not isinstance(output,str) or not output.strip():
        raise TranslatorUnavailable("Translation engine did not return text")
    return output[:12000]


