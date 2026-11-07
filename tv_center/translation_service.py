"""Single persistent private NLLB worker, so a large model loads only once.

Per-segment Python subprocesses would reload ~2.5 GB weights and make
live subtitles unusably slow. This service runs only after explicit NLLB
selection and never accesses the network during inference.
"""
from __future__ import annotations
import atexit
import json
import os
import select
import subprocess
import threading
from pathlib import Path
from .runtime import AIRuntime

class NLLBService:
    def __init__(self):
        self.lock=threading.Lock()
        self.process=None

    def _start(self):
        runtime=AIRuntime().status()
        if not runtime["installed"]:
            raise RuntimeError("Managed Python runtime missing; install NLLB in Model Market")
        root=str(Path(__file__).resolve().parent.parent)
        env=os.environ.copy()
        env["PYTHONPATH"]=root+os.pathsep+env.get("PYTHONPATH","")
        env["HF_HUB_OFFLINE"]="1"
        env["TRANSFORMERS_OFFLINE"]="1"
        self.process=subprocess.Popen(
            [runtime["python"],"-u","-m","tv_center.translation_worker","--serve-nllb"],
            cwd=root,env=env,stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            bufsize=0,close_fds=True)

    def translate(self,text,source,target):
        if not isinstance(text,str) or len(text)>1600:
            raise ValueError("Caption text invalid")
        if source not in ("de","en","tr") or target not in ("de","en","tr"):
            raise ValueError("Unsupported translator language")
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                self._start()
            try:
                payload=json.dumps({"text":text,"source":source,"target":target},
                    ensure_ascii=False).encode("utf-8")+b"\n"
                self.process.stdin.write(payload)
                self.process.stdin.flush()
                ready,_,_=select.select([self.process.stdout],[],[],80)
                if not ready:
                    self.close_locked()
                    raise TimeoutError("NLLB translation exceeded 80 s; try smaller Argos models")
                reply=self.process.stdout.readline(65536)
                if not reply or not reply.endswith(b"\n"):
                    self.close_locked()
                    raise RuntimeError("NLLB translation worker exited without a complete response")
                result=json.loads(reply.decode("utf-8","replace"))
                if "error" in result:
                    raise RuntimeError(result["error"][:280])
                translated=result.get("translated")
                if not isinstance(translated,str) or not translated.strip():
                    raise RuntimeError("NLLB produced no translated text")
                return translated[:1600]
            except (OSError,BrokenPipeError,ValueError) as exc:
                self.close_locked()
                raise RuntimeError("NLLB offline service unavailable: "+str(exc)[:160]) from exc

    def close_locked(self):
        p=self.process
        self.process=None
        if p and p.poll() is None:
            p.terminate()
            try: p.wait(timeout=3)
            except subprocess.TimeoutExpired: p.kill()

    def close(self):
        with self.lock:
            self.close_locked()

_service=NLLBService()
atexit.register(_service.close)

def translate_nllb(text,source,target):
    return _service.translate(text,source,target)
