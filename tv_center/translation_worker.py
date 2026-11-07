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

def serve_nllb():
    from .translation_market import run_nllb
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            if len(line) > 10000:
                raise ValueError("Translation request is too long")
            payload=json.loads(line)
            text=payload["text"]
            source=payload["source"]
            target=payload["target"]
            if not isinstance(text,str) or not 0 < len(text) <= 1600:
                raise ValueError("Invalid caption")
            result={"translated":run_nllb(text,source,target)}
        except (KeyError,TypeError,ValueError,RuntimeError,OSError) as err:
            result={"error":str(err)[:300]}
        print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--serve-nllb"]:
        serve_nllb()
    else:
        main()
