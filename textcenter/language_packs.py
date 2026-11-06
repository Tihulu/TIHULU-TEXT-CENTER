"""User-approved Argos language-pack discovery and installation.

This is an additive extension to the EN/DE/TR live ASR and translation
pipelines: existing AI files are not modified. Extra packs support standalone
offline text translation. Live captions still need a compatible ASR language
model and dedicated integration. Package downloads are NEVER automatic.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Lock,Thread

LANGUAGE_PATTERN=re.compile(r"^[a-z]{2,3}(?:-[a-z]{2,5})?$")
MAX_INDEX_BYTES=2_000_000


class LanguagePackError(RuntimeError):
    pass


def normalize_code(value):
    if not isinstance(value,str) or not LANGUAGE_PATTERN.fullmatch(value):
        raise ValueError("Invalid ISO language code")
    return value


def available_from_index(raw):
    if not isinstance(raw,list) or len(raw)>10000:
        raise LanguagePackError("Invalid Argos language package index")
    entries=[]
    found=set()
    for item in raw:
        if not isinstance(item,dict) or item.get("type") not in (None,"translate"):
            continue
        src,dst=item.get("from_code"),item.get("to_code")
        try:src,dst=normalize_code(src),normalize_code(dst)
        except ValueError:continue
        if src==dst or (src,dst) in found:continue
        found.add((src,dst))
        entries.append({
            "source":src,"target":dst,
            "source_name":str(item.get("from_name") or src)[:80],
            "target_name":str(item.get("to_name") or dst)[:80],
            "package_version":str(item.get("package_version") or "unknown")[:45],
            "size":"Unknown until provider download",
            "origin":"Argos package index; user approval required",
        })
    return entries[:500]


def _index_path():
    try:
        from argostranslate import settings
        return Path(settings.local_package_index)
    except (ImportError,OSError,AttributeError):
        return None


def _installed():
    try:
        from argostranslate import package
        return sorted({
            (p.from_code,p.to_code)
            for p in package.get_installed_packages()
            if getattr(p,"type","translate")=="translate"
            and isinstance(p.from_code,str) and isinstance(p.to_code,str)
        })
    except (ImportError,OSError,ValueError,RuntimeError,AttributeError):
        return []


class LanguagePacks:
    def __init__(self,*,runner=None,index_path=None,installed=None):
        self.runner=runner or self._run
        self.index_path=index_path if index_path is not None else _index_path
        self.installed=installed or _installed
        self._lock=Lock()
        self._state={"active":False,"status":"idle","pair":None,"error":None}

    @staticmethod
    def _run(command,timeout):
        result=subprocess.run(command,stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,
            check=False)
        return result.returncode, result.stderr.decode("utf-8","replace")[-300:]

    def available(self):
        path=self.index_path() if callable(self.index_path) else self.index_path
        if not path or not Path(path).is_file():
            return []
        p=Path(path)
        if p.stat().st_size>MAX_INDEX_BYTES:
            return []
        try:
            return available_from_index(json.loads(p.read_text(encoding="utf-8")))
        except (OSError,UnicodeError,ValueError,LanguagePackError):
            return []

    def status(self):
        installed=self.installed()
        with self._lock:
            state=dict(self._state)
        return {
            "argos_installed":importlib.util.find_spec("argostranslate") is not None,
            "installed_pairs":[{"source":a,"target":b} for a,b in installed[:500]],
            "available_pairs":self.available(),
            "installer":state,
            "auto_download":False,
            "live_asr_extra_languages":False,
            "note":"Extra installed packs extend offline manual text translation. "
                   "They do NOT automatically add speech recognition languages.",
        }

    def refresh_index(self,*,consent=False):
        if consent is not True:
            raise LanguagePackError("Explicit Internet package-index update approval is required")
        if importlib.util.find_spec("argostranslate") is None:
            raise LanguagePackError("Argos Translate is not installed in this Python environment")
        code,error=self.runner([sys.executable,"-m","argostranslate.argospm","update"],18)
        if code:
            raise LanguagePackError("Argos package index update failed: "+str(error)[:150])
        packages=self.available()
        return {"count":len(packages),"source":"Argos index downloaded on explicit request",
                "models_installed":False}

    def install(self,source,target,*,consent=False):
        src,dst=normalize_code(source),normalize_code(target)
        if consent is not True:
            raise LanguagePackError("Explicit model download and installation approval required")
        if src==dst:raise ValueError("Source and target languages must differ")
        if importlib.util.find_spec("argostranslate") is None:
            raise LanguagePackError("Install argostranslate in a project environment first")
        if (src,dst) not in {(x["source"],x["target"]) for x in self.available()}:
            raise LanguagePackError("This package pair is absent from the explicitly refreshed Argos catalog")
        with self._lock:
            if self._state["active"]:
                raise LanguagePackError("Another language pack is currently installing")
            self._state={"active":True,"status":"running","pair":src+" → "+dst,"error":None}
            job=Thread(target=self._worker,args=(src,dst),daemon=True,
                       name="tihulu-argos-model-installer")
            job.start()
            return dict(self._state)

    def _worker(self,src,dst):
        try:
            code,error=self.runner([sys.executable,"-m","argostranslate.argospm",
                        "install","translate-"+src+"_"+dst],360)
            installed=(src,dst) in self.installed()
            if code or not installed:
                raise LanguagePackError("Argos package installation failed: "+str(error)[:170])
            status="installed";error=None
        except (OSError,subprocess.TimeoutExpired,LanguagePackError) as exc:
            status="failed";error=str(exc)[:230]
        with self._lock:
            self._state.update(active=False,status=status,error=error)

    def translate(self,text,source,target):
        src,dst=normalize_code(source),normalize_code(target)
        if not isinstance(text,str) or not 0<len(text.strip())<=12000:
            raise ValueError("Text length must be 1–12000")
        if src==dst:return {"original":text,"translated":text,"engine":"identity"}
        if (src,dst) not in self.installed():
            raise LanguagePackError("The directed offline Argos package is not installed")
        try:
            import argostranslate.translate as translation
            converted=translation.translate(text,src,dst)
        except (ImportError,RuntimeError,ValueError,KeyError,AttributeError) as exc:
            raise LanguagePackError("Offline model failed: "+str(exc)[:140]) from exc
        if not isinstance(converted,str) or not converted.strip():
            raise LanguagePackError("Translation model produced no text")
        return {
            "original":text,"translated":converted[:12000],
            "engine":"argos_installed_local_cpu",
            "source":src,"target":dst,
        }
