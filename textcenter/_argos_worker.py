"""Trusted local worker. Called only by the fixed OfflineArgosProcess backend."""
from __future__ import annotations
import json
import os
import sys

if __name__=="__main__":
    backend=sys.argv[1] if len(sys.argv)==2 else ""
    if backend not in ("cpu","cuda"):
        sys.exit(2)
    os.environ["ARGOS_DEVICE_TYPE"]=backend
    try:
        import argostranslate.translate
    except ImportError:
        sys.exit(3)
    for line in sys.stdin:
        try:
            if len(line)>10000:raise ValueError("Input exceeds translation limit")
            obj=json.loads(line)
            text=obj.get("text")
            source=obj.get("source");target=obj.get("target")
            if source not in ("en","de","tr") or target not in ("en","de","tr"):
                raise ValueError("Unsupported source/target language")
            if not isinstance(text,str) or len(text)>4000:
                raise ValueError("Invalid text")
            installed=argostranslate.translate.get_installed_languages()
            src=next((x for x in installed if x.code==source),None)
            dst=next((x for x in installed if x.code==target),None)
            if not src or not dst:
                raise ValueError("Offline Argos language model missing")
            value=src.get_translation(dst).translate(text)
            print(json.dumps({"ok":True,"text":value},ensure_ascii=False),flush=True)
        except Exception as exc:
            print(json.dumps({"ok":False,"error":str(exc)[:200]},ensure_ascii=False),flush=True)
