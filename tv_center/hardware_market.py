"""Hardware suitability for verified offline TV speech and translation models.

Detection is read-only and does not equate GPU presence with CUDA runtime
readiness. Raspberry Pi's optional Hailo accelerator is a separate backend.
"""
from __future__ import annotations
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess


def _command(command, timeout=3):
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                timeout=timeout,check=False)
        return result.stdout.decode("utf-8","replace").strip() if result.returncode == 0 else ""
    except (OSError,subprocess.TimeoutExpired):
        return ""


def _find_executable(executable, alternatives=()):
    return shutil.which(executable) or next(
        (name for name in alternatives if Path(name).is_file()
         and os.access(name,os.X_OK)), None)


def detect_hardware():
    nvidia_smi = _find_executable("nvidia-smi",
                                 ("/usr/bin/nvidia-smi","/bin/nvidia-smi",
                                  "/usr/local/bin/nvidia-smi"))
    gpu = _command([nvidia_smi,"--query-gpu=name,memory.total,compute_cap",
                    "--format=csv,noheader,nounits"]) if nvidia_smi else ""
    if not gpu and nvidia_smi:
        gpu = _command([nvidia_smi,"--query-gpu=name,memory.total",
                        "--format=csv,noheader,nounits"])
    name, vram_mib, compute_cap = None, None, None
    if gpu:
        fields=[x.strip() for x in gpu.splitlines()[0].split(",")]
        name=fields[0][:120]
        if len(fields)>1:
            try: vram_mib=int(float(fields[1]))
            except (TypeError,ValueError): pass
        if len(fields)>2:
            compute_cap=fields[2]
    if not name:
        # NVIDIA module provenance is useful when PATH or nvidia-smi is
        # unavailable inside the Qt app's sanitized launcher environment.
        for p in Path("/proc/driver/nvidia/gpus").glob("*/information"):
            try:
                txt=p.read_text(encoding="utf-8",errors="replace")[:4000]
                match=re.search(r"^Model:\s*(.+)$",txt,re.M)
                if match:
                    name=match.group(1).strip()[:120]; break
            except OSError:
                pass
    nvcc=_find_executable("nvcc",("/usr/local/cuda/bin/nvcc",
                                  "/usr/local/cuda-12.8/bin/nvcc",
                                  "/usr/local/cuda-13.0/bin/nvcc"))
    version_text=_command([nvcc,"--version"]) if nvcc else ""
    version=re.search(r"release\s+(\d+)\.(\d+)",version_text)
    cuda_version=(int(version.group(1)),int(version.group(2))) if version else None
    is_blackwell=bool(name and re.search(r"\b(?:RTX\s*50\d{2}|Blackwell)\b",name,re.I))
    can_compile=bool(nvcc and cuda_version and
                     (not is_blackwell or cuda_version >= (12,8)))
    ram_mib=None
    try:
        meminfo=Path("/proc/meminfo").read_text(encoding="ascii")
        match=re.search(r"^MemTotal:\s+(\d+)\s+kB",meminfo,re.M)
        if match: ram_mib=int(match.group(1))//1024
    except OSError:
        pass
    pi5=False
    try:
        pi5="Raspberry Pi 5" in Path("/proc/device-tree/model").read_bytes().decode(
            "utf-8","replace")
    except OSError:
        pass
    npu=list(Path("/dev").glob("hailo*"))
    return {
        "cpu": platform.processor() or platform.machine() or "CPU",
        "architecture": platform.machine(),
        "ram_mib":ram_mib,
        "gpu":{"detected":bool(name),"name":name or "Not detected",
               "vram_mib":vram_mib,"compute_capability":compute_cap,
               "driver_tool":bool(nvidia_smi),
               "cuda_compiler":nvcc,"cuda_version":(
                   ".".join(map(str,cuda_version)) if cuda_version else None),
               "cuda_compile_possible":can_compile,
               "reason":(
                   "CUDA >=12.8 required for Blackwell RTX 50-series"
                   if is_blackwell and not can_compile else
                   "CUDA toolkit (nvcc) not detected; GPU can be detected without a CUDA speech runtime"
                   if name and not nvcc else
                   "CUDA compile toolchain detected; inference still requires a compiled runtime and tested model"
                   if name else "No NVIDIA GPU found")},
        "npu":{"detected":bool(npu),"devices":[p.name for p in npu],
               "ready":False,
               "detail":("Hailo present; install a compatible Hailo Whisper pipeline, "
                         "not ordinary GGML CUDA models" if npu else
                         "No Hailo device found; optional NPU is not required")},
        "raspberry_pi_5":pi5,
    }


def model_fit(key, size_mb, hardware):
    """Estimated disk/RAM suitability, never performance or WER claims."""
    gpu=hardware["gpu"]
    ram=hardware.get("ram_mib")
    disk_mb=int(size_mb)
    # Model weights plus whisper.cpp runtime/activations; conservative margin.
    required_ram_mb=max(700, disk_mb * 3)
    if ram is not None and required_ram_mb > ram * 0.70:
        return "Not recommended · insufficient free-system-memory margin"
    if gpu["detected"] and gpu["vram_mib"] is not None:
        if required_ram_mb < gpu["vram_mib"] * 0.75:
            if gpu["cuda_compile_possible"]:
                return "Recommended for NVIDIA CUDA once runtime installed"
            return "Fits GPU memory estimate · CUDA backend still missing"
        return "Large for GPU VRAM · CPU or smaller quantized model"
    if key.startswith("large") and hardware["raspberry_pi_5"]:
        return "Not recommended for Pi 5 live captions"
    if key.startswith("medium") and hardware["raspberry_pi_5"]:
        return "May be too slow for Pi 5 live captions"
    return "CPU capable in principle · live speed unverified"
