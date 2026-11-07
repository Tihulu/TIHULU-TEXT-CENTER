"""Offline user-owned Argos translation worker.

Launched with the Argos managed venv interpreter. No network or model download,
no shell, and all input arrives as one bounded JSON object over stdin.
"""
from __future__ import annotations
import json
import sys

def main():
    payload = json.load(sys.stdin)
    text = payload.get("text")
    source = payload.get("source")
    target = payload.get("target")
    if (not isinstance(text,str) or not text.strip() or len(text)>1600 or
        source not in ("de","en","tr") or target not in ("de","en","tr") or
        source == target):
        raise ValueError("Invalid offline translation request")
    import os
    engine = os.environ.get("TIHULU_TRANSLATOR_MODEL", "argos")
    if engine == "nllb":
        from .translation_market import run_nllb
        translated = run_nllb(text, source, target)
    elif engine == "argos":
        from textcenter.transcripts import translate_offline
        translated = translate_offline(text, source, target, backend="cpu")
    else:
        raise ValueError("Unknown translation backend")
    print(json.dumps({"translated":translated}, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
