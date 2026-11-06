"""Offline-first speech/translation compute discovery and explicit backend selection.

Device presence and executable presence never imply model compatibility.
Nothing downloads models or makes network calls. CPU fallback is a device,
NOT an assertion that recognition/translation software is installed.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import platform
import shutil
import subprocess

LANGUAGES = ("en", "de", "tr")
BACKENDS = ("auto", "cpu", "gpu", "npu")


def _command_output(argv: list[str], timeout: float = 1.5) -> str:
    try:
        r=subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, timeout=timeout, check=False)
        if r.returncode == 0:
            return r.stdout.decode("utf-8", "replace")[:400]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def detect_devices(*, executable_lookup=None, device_root=None,
                   model_path=None, system=None, command_runner=None) -> dict:
    lookup = executable_lookup or shutil.which
    dev = Path("/dev") if device_root is None else Path(device_root)
    model_file = model_path if model_path is not None else os.environ.get("TIHULU_WHISPER_MODEL", "")
    model = Path(model_file).expanduser() if model_file else None
    system = system or platform.system()
    run = command_runner or _command_output
    devices=[{"id":"cpu","name":platform.processor() or platform.machine() or "System CPU",
              "detected":True,"runtime_ready":True,
              "detail":"Always available for ordinary computation; speech model may be missing"}]
    nvidia = run(["nvidia-smi","--query-gpu=name","--format=csv,noheader,nounits"]) if lookup("nvidia-smi") else ""
    if nvidia.strip():
        devices.append({"id":"gpu","name":nvidia.strip().splitlines()[0][:100],
                        "detected":True,"runtime_ready":False,
                        "detail":"NVIDIA GPU detected; model/backend CUDA compatibility not verified"})
    elif system=="Darwin" and platform.machine() in ("arm64","aarch64"):
        devices.append({"id":"gpu","name":"Apple Silicon GPU / Metal",
                        "detected":True,"runtime_ready":False,
                        "detail":"Metal device inferred; selected speech engine compatibility not verified"})
    else:
        devices.append({"id":"gpu","name":"No compatible GPU detected",
                        "detected":False,"runtime_ready":False,
                        "detail":"No verified CUDA or Metal speech backend"})
    try:
        npus=sorted(x.name for x in dev.glob("hailo*"))[:5]
    except OSError:
        npus=[]
    devices.append({"id":"npu","name":"Hailo NPU ("+", ".join(npus)+")" if npus else "No Hailo NPU detected",
                    "detected":bool(npus),"runtime_ready":False,
                    "detail":"NPU device node != working speech/translation model runtime. Explicit compatible adapter required."})
    executable=lookup("whisper-cli") or lookup("main")
    speech_ready=bool(executable and model and model.is_file() and model.stat().st_size>1024)
    argos=importlib.util.find_spec("argostranslate") is not None
    return {
        "devices":devices,"languages":list(LANGUAGES),"options":list(BACKENDS),
        "speech":{
            "engine":"whisper.cpp CLI","executable":executable,
            "model_path":str(model) if model else None,
            "model_installed":bool(model and model.is_file()),
            "ready_cpu":speech_ready,"ready_gpu":False,"ready_npu":False,
            "note":"whisper.cpp model must already be installed; configured with TIHULU_WHISPER_MODEL. No inference can be claimed without real capture and model."
        },
        "translation":{
            "engine":"Argos Translate","python_package_installed":argos,
            "ready":argos,"installed_pairs_verified":False,
            "note":"Installed language pairs, not Python package alone, determine offline translation capability; no models auto-downloaded."
        },
        "policy":"auto selects a verified runtime, never assumes an NPU/GPU can run arbitrary Whisper or Argos models",
    }


def choose_backend(profile:dict, selection:str="auto") -> dict:
    if selection not in BACKENDS:
        raise ValueError("Backend must be auto/cpu/gpu/npu")
    available={x["id"]:x for x in profile["devices"]}
    if selection=="auto":
        # Whitelisted runtime, not GPU presence. Later adapters can report ready_gpu.
        for key in ("npu","gpu","cpu"):
            if profile["speech"].get("ready_"+key) and available[key]["detected"]:
                return {"selected":key,"ready":True,"detected_device":available[key]["name"]}
        return {"selected":"cpu","ready":False,
                "detected_device":available["cpu"]["name"],
                "reason":"No compatible installed speech executable/model"}
    item=available[selection]
    ready=bool(profile["speech"].get("ready_"+selection) and item["detected"])
    return {"selected":selection,"ready":ready,"detected_device":item["name"],
            "reason":None if ready else "Selected hardware is detected only or model runtime is missing"}


def validate_language(value):
    if value not in LANGUAGES:
        raise ValueError("Language must be en, de or tr")
    return value
