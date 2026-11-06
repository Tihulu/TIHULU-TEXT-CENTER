"""Isolated reusable offline Argos translation service for CPU/CUDA selection.

Per-session child process ensures changing CPU/GPU doesn't mutate global
CTranslate2/Argos environment in the HTTP server. No Internet or model download.
NPUs require a separate, compatible translation runtime and remain blocked.
"""
from __future__ import annotations
import json
import os
import re
import selectors
import subprocess
import sys
from threading import Lock
import time

from .compute import LANGUAGES,_cuda_ready


def select_translation_device(preference:str,compute_info:dict,*,check_cuda=None)->dict:
    if not compute_info.get("runtimes",{}).get("argostranslate"):
        raise ValueError("Install Argos Translate and its offline language models")
    candidates={x["id"]:x for x in compute_info.get("devices",[])}
    if preference not in ("auto","cpu") and not re.fullmatch(r"cuda:[0-9]+",preference or ""):
        raise ValueError("Translation backend must be auto, CPU or a detected CUDA device; NPU adapter unavailable")
    if preference=="auto":
        preference=next((d for d in candidates if d.startswith("cuda:") and _cuda_ready(d,check_cuda)),"cpu")
    if preference=="cpu":
        return {"id":"cpu","kind":"cpu","name":candidates.get("cpu",{}).get("name","CPU")}
    if preference not in candidates or not _cuda_ready(preference,check_cuda):
        raise ValueError("Selected CUDA GPU is not available for the translation runtime")
    return {"id":preference,"kind":"cuda","name":candidates[preference]["name"]}


class OfflineArgosProcess:
    def __init__(self,device:dict,*,exe=None):
        if device.get("kind") not in ("cpu","cuda"):
            raise ValueError("Unsupported translation processor")
        self.device=device
        env=os.environ.copy()
        env["ARGOS_DEVICE_TYPE"]="cuda" if device["kind"]=="cuda" else "cpu"
        if device["kind"]=="cuda":
            env["CUDA_VISIBLE_DEVICES"]=device["id"].split(":")[1]
        interpreter=exe or sys.executable
        self._proc=subprocess.Popen(
            [interpreter,"-m","textcenter._argos_worker",
             "cuda" if device["kind"]=="cuda" else "cpu"],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,env=env,
            close_fds=True,start_new_session=True)
        self._mutex=Lock()
        self._buffer=bytearray()

    def translate(self,text:str,source:str,target:str)->str:
        if source not in LANGUAGES or target not in LANGUAGES:
            raise ValueError("Only English, German and Turkish supported")
        if source==target:return text
        if not isinstance(text,str) or not text or len(text)>4000:
            raise ValueError("Invalid translation input")
        with self._mutex:
            if self._proc.poll() is not None:raise ValueError("Offline Argos worker exited")
            assert self._proc.stdin and self._proc.stdout
            request=json.dumps({"text":text,"source":source,"target":target},
                               ensure_ascii=False).encode("utf-8")+b"\n"
            self._proc.stdin.write(request)
            self._proc.stdin.flush()
            deadline=time.monotonic()+20
            with selectors.DefaultSelector() as selector:
                selector.register(self._proc.stdout,selectors.EVENT_READ)
                while time.monotonic()<deadline:
                    if b"\n" in self._buffer:
                        response,_,rest=self._buffer.partition(b"\n")
                        self._buffer=bytearray(rest)
                        try:obj=json.loads(response)
                        except ValueError as exc:raise ValueError("Invalid translation worker response") from exc
                        if not obj.get("ok"):
                            raise ValueError(str(obj.get("error","Offline language model missing"))[:220])
                        result=obj.get("text")
                        if not isinstance(result,str) or len(result)>8000:
                            raise ValueError("Invalid translated text")
                        return result
                    if self._proc.poll() is not None:
                        raise ValueError("Offline translator exited before returning a result")
                    if not selector.select(timeout=.25):continue
                    chunk=os.read(self._proc.stdout.fileno(),8192)
                    if not chunk:raise ValueError("Offline translator stopped unexpectedly")
                    self._buffer.extend(chunk)
                    if len(self._buffer)>12000:raise ValueError("Translation worker response too large")
            raise ValueError("Offline translation exceeded the 20-second deadline")

    def close(self):
        if self._proc.poll() is None:
            try:self._proc.terminate();self._proc.wait(timeout=2)
            except (OSError,subprocess.TimeoutExpired):
                try:self._proc.kill();self._proc.wait(timeout=1)
                except (OSError,subprocess.TimeoutExpired):pass
        for pipe in (self._proc.stdin,self._proc.stdout):
            if pipe is not None:
                try:pipe.close()
                except OSError:pass
