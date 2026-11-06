"""Passive compute inventory and truthful local AI backend suitability.

Hardware presence != an available ASR/translation runtime. NPU is never
advertised as Whisper-compatible without a verified vendor-specific adapter.
Do not start a GPU job or download models merely to inventory devices.
"""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

LANGUAGES={"en":"English","de":"German","tr":"Turkish"}
LANG_PAIRS=tuple((s,t) for s in LANGUAGES for t in LANGUAGES if s!=t)
PCI_GPU_VENDOR={"0x10de":"NVIDIA", "0x1002":"AMD", "0x8086":"Intel"}


def _read(path:Path, limit=200):
    try:return path.read_text(encoding="utf-8",errors="replace").strip()[:limit]
    except OSError:return ""


def _has_package(name:str)->bool:
    try:return importlib.util.find_spec(name) is not None
    except (ImportError,ValueError,AttributeError):return False


def _video_cards(drm:Path)->list[dict]:
    results=[]
    try:cards=sorted(drm.glob("card[0-9]*"))[:16]
    except OSError:cards=[]
    seen=set()
    for card in cards:
        if not re.fullmatch(r"card[0-9]+",card.name):continue
        vendor=_read(card/"device"/"vendor").lower()
        if vendor not in PCI_GPU_VENDOR:continue
        device=_read(card/"device"/"device").lower()
        key=(vendor,device)
        if key in seen:continue
        seen.add(key)
        results.append({
            "id":"pci:"+card.name, "kind":"gpu",
            "name":PCI_GPU_VENDOR[vendor]+" PCI GPU "+device,
            "hardware_detected":True,"inference_compatible":False,
            "note":"PCI presence only; backend support must be verified separately",
        })
    return results


def _nvidia_info(lookup)->list[dict]:
    tool=lookup("nvidia-smi")
    if not tool:return []
    try:
        result=subprocess.run(
            [tool,"--query-gpu=index,name,memory.total","--format=csv,noheader,nounits"],
            capture_output=True,text=True,timeout=1.5,check=False)
    except (OSError,subprocess.TimeoutExpired):
        return []
    if result.returncode!=0:return []
    gpus=[]
    for line in result.stdout.splitlines()[:8]:
        pieces=[x.strip() for x in line.split(",",2)]
        if len(pieces)!=3 or not pieces[0].isdigit():continue
        ident=int(pieces[0])
        if ident>15:continue
        label=re.sub(r"[\x00-\x1f]","",pieces[1])[:110]
        vram=int(pieces[2]) if pieces[2].isdigit() else None
        gpus.append({"id":f"cuda:{ident}","kind":"gpu",
                     "name":label or f"NVIDIA GPU #{ident}",
                     "vram_mib":vram,"hardware_detected":True,
                     "inference_compatible":False,
                     "note":"CUDA runtime/model readiness not proved by nvidia-smi"})
    return gpus


def inventory_compute(*, cpuinfo:Path=Path("/proc/cpuinfo"),
                      drm_root:Path=Path("/sys/class/drm"),
                      dev_root:Path=Path("/dev"),
                      lookup=None, include_driver_query=True,
                      package_lookup=None)->dict:
    lookup=lookup or shutil.which
    present=package_lookup or _has_package
    cpu_name="Unknown CPU"
    info=_read(cpuinfo,12000)
    for line in info.splitlines():
        if line.lower().startswith(("model name","hardware","processor")) and ":" in line:
            val=line.split(":",1)[1].strip()
            if val:
                cpu_name=val[:160]
                break
    cpu={"id":"cpu","kind":"cpu","name":cpu_name if cpu_name!="Unknown CPU" else platform.processor() or "CPU",
         "threads":os.cpu_count() or 1,"hardware_detected":True,"inference_compatible":False,
         "note":"CPU always available, model files/runtime are separate dependencies"}
    gpus=(_nvidia_info(lookup) if include_driver_query else [])
    if not gpus:gpus=_video_cards(drm_root)
    npu=[]
    try:
        nodes=sorted(x.name for x in dev_root.glob("hailo*") if x.name.startswith("hailo"))[:8]
    except OSError:nodes=[]
    if nodes:
        for node in nodes:
            npu.append({"id":"hailo:"+node,"kind":"npu","name":"Hailo accelerator "+node,
                        "hardware_detected":True,"inference_compatible":False,
                        "note":"Hailo hardware detected; compatible speech/translation model runtime is NOT integrated"})
    runtimes={
        "faster_whisper":present("faster_whisper"),
        "ctranslate2":present("ctranslate2"),
        "argostranslate":present("argostranslate"),
        "ffmpeg":bool(lookup("ffmpeg")),
        "rtl_fm":bool(lookup("rtl_fm")),
        "dvbv5_zap":bool(lookup("dvbv5-zap")),
        "hailortcli":bool(lookup("hailortcli")),
    }
    model_dir=os.environ.get("TIHULU_WHISPER_MODEL","")
    model_ready=bool(model_dir and Path(model_dir).is_dir()
                     and (Path(model_dir)/"model.bin").is_file())
    # A CUDA GPU is not sufficient without a loaded CUDA/cuDNN-compatible
    # CTranslate2 runtime; user must pass a successful manual readiness test.
    cpu["inference_compatible"]=runtimes["faster_whisper"] and model_ready
    for gpu in gpus:
        gpu["inference_compatible"]=False
        gpu["note"]="Detected but CUDA/cuDNN/CTranslate2 backend has not been validated"
    return {
        "devices":[cpu,*gpus,*npu],
        "runtimes":runtimes,
        "model_directory_configured":bool(model_dir),
        "whisper_model_local_ready":model_ready,
        "languages":LANGUAGES,
        "translation_pairs":[{"source":s,"target":t} for s,t in LANG_PAIRS],
        "automatic_selection":"cpu" if cpu["inference_compatible"] else None,
        "npu_asr_adapter_integrated":False,
        "notice":"Device enumeration does not certify translation or transcription. No automatic model download or inference is performed.",
    }


def resolve_device(preference:str, info:dict, *, validate_cuda=None)->dict:
    if preference not in ("auto","cpu") and not re.fullmatch(r"cuda:[0-9]+",preference or ""):
        raise ValueError("Choose auto, cpu or a detected CUDA device. NPU requires a compatible runtime.")
    devices={x["id"]:x for x in info["devices"]}
    if not info["whisper_model_local_ready"] or not info["runtimes"]["faster_whisper"]:
        raise ValueError("Install faster-whisper and configure a fully local TIHULU_WHISPER_MODEL directory")
    if preference=="auto":
        for d in info["devices"]:
            if d["id"].startswith("cuda:") and _cuda_ready(d["id"], validate_cuda):
                return {"selected":d["id"],"backend":"cuda","model_local":True,"device_name":d["name"]}
        preference="cpu"
    if preference=="cpu":
        return {"selected":"cpu","backend":"cpu","model_local":True,"device_name":devices["cpu"]["name"]}
    if preference not in devices:
        raise ValueError("Requested CUDA GPU is not detected")
    if not _cuda_ready(preference,validate_cuda):
        raise ValueError("CUDA/cuDNN/CTranslate2 runtime not verified for this device")
    return {"selected":preference,"backend":"cuda","model_local":True,
            "device_name":devices[preference]["name"]}


def _cuda_ready(device_id:str, check=None)->bool:
    if check is not None:return bool(check(device_id))
    try:
        import ctranslate2
        return bool(ctranslate2.get_cuda_device_count()>int(device_id.split(":")[1]))
    except (ImportError,OSError,RuntimeError,ValueError,AttributeError):
        return False
