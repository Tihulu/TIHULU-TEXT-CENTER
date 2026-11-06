"""Truthful heterogeneous compute selection for local satellite decoding.

Only kernels actually implemented for Robot36 are offered. GPU acceleration
requires a working CUDA CuPy runtime and performs the large audio-to-frequency
trace there. CPU always handles I/O, sync validation and PNG writing.
No OpenVINO/AI-HAT NPU SSTV kernels exist; never claim they run this DSP.
"""
from __future__ import annotations

from functools import lru_cache
from .npu_sstv import probe_real_sstv_npu
from typing import Iterable

VALID_TARGETS = ("cpu", "gpu", "npu")


@lru_cache(maxsize=1)
def compute_capabilities() -> dict:
    cpu = {"available": True, "name": "Portable CPU",
           "role": "WAV input, line synchronization, image assembly, ZIP",
           "implementation": "Python standard library; optional vectorized NumPy"}
    try:
        import numpy  # noqa: F401
        cpu["implementation"] = "NumPy vectorization + Python image processing"
    except ImportError:
        pass

    gpu = {"available": False, "name": "CUDA/CuPy (optional)",
           "role": "PCM zero-crossing / FM tone-frequency trace",
           "reason": "No working CuPy/CUDA runtime found. WebGPU browser acceleration is a separate backend."}
    try:
        import cupy as cp
        count = cp.cuda.runtime.getDeviceCount()
        if count:
            # Actually exercise the kernel rather than trusting a driver name.
            test = cp.arange(16, dtype=cp.float32)
            if float(cp.sum(test).get()) == 120:
                gpu.update(available=True,
                           name="CuPy CUDA (" + str(count) + " device(s))",
                           reason="")
    except Exception as exc:
        gpu["reason"] = "CUDA/CuPy not runnable: " + str(exc)[:160]

    return {
        "cpu": cpu, "gpu": gpu,
        "npu": probe_real_sstv_npu(),
        "auto": {"available": True, "name": "Optimized for this device",
                 "role": "Choose a tested backend for this WAV's length; keep CPU fallback"},
    }


def resolve_compute_backend(mode="auto", targets=None, *, seconds=0, capabilities=None):
    """Return an auditable execution plan; never silently accept unavailable NPU."""
    caps = capabilities if capabilities is not None else compute_capabilities()
    if mode not in ("auto", "custom"):
        raise ValueError("Compute mode must be auto or custom")
    if mode == "custom":
        if not isinstance(targets, list) or not targets or len(targets) > 3:
            raise ValueError("Select 1-3 CPU/GPU/NPU backends")
        if any(not isinstance(x, str) or x not in VALID_TARGETS for x in targets):
            raise ValueError("Unknown compute backend")
        if len(set(targets)) != len(targets):
            raise ValueError("Duplicate compute backend")
        unavailable = [x for x in targets if not caps.get(x, {}).get("available")]
        if unavailable:
            raise ValueError("Compute backend unavailable for Robot36: " +
                             "; ".join(x + ": " + caps.get(x, {}).get("reason", "")
                                       for x in unavailable))
        selected = list(targets)
    else:
        # For short segments/short captures CUDA transfer and compile overhead
        # can dominate. GPU is selected for long WAVs if a real kernel works.
        selected = ["cpu"]
        if seconds >= 120 and caps["gpu"]["available"]:
            selected.append("gpu")
        if (seconds >= 120 and caps.get("npu", {}).get("available") and
                caps["npu"].get("auto_beneficial")):
            selected.append("npu")
    use_gpu = "gpu" in selected
    return {
        "mode": mode,
        "requested_targets": list(targets or []) if mode == "custom" else [],
        "selected_targets": selected,
        "trace_backend": "cupy-cuda" if use_gpu else
                         "numpy-cpu" if caps["cpu"]["implementation"].startswith("NumPy vectorization") else "python-cpu",
        "npu_stages": (["real OpenVINO NPU 8-bin audio DFT synchronization-tone screening"]
                       if "npu" in selected else []),
        "cpu_mandatory_stages": ["WAV I/O", "Robot36 alignment", "pixel assembly", "PNG output"],
        "note": ("NPU computes actual 8-bin audio DFT to screen synchronization tones; " if "npu" in selected else "") +
            ("CuPy computes real tone traces on GPU; CPU aligns and renders pixels." if use_gpu else
             "CPU computes accurate Robot36 trace, validates sync and assembles images."),
    }


def vectorized_frequency_trace(raw: bytes, rate: int, *, gpu=False) -> list[float]:
    """Compute same 1 ms trace as portable decoder, using real NumPy/CuPy math.

    Called only with verified devices by the outer resolver. Return Python
    numbers so the existing image decoder can validate actual RF evidence.
    """
    if gpu:
        import cupy as xp
        import numpy as np
        # Host WAV bytes are copied to actual CUDA VRAM. No simulated GPU.
        samples = xp.asarray(np.frombuffer(raw, dtype="<i2"), dtype=xp.float32)
    else:
        import numpy as xp
        samples = xp.frombuffer(raw, dtype="<i2").astype(xp.float32)
    crosses_idx = xp.nonzero((samples[:-1] < 0) & (samples[1:] >= 0))[0]
    left = samples[crosses_idx]
    right = samples[crosses_idx + 1]
    crossing = (crosses_idx.astype(xp.float64)
                - left / xp.where(right == left, 1.0, right - left)) / float(rate)
    n = int(len(raw) / 2 / rate * 1000)
    center = (xp.arange(n, dtype=xp.float64) + .5) / 1000.0
    lo = xp.searchsorted(crossing, center - .003, side="left")
    hi = xp.searchsorted(crossing, center + .003, side="right")
    count = hi - lo
    # For silent audio crossing is empty. Never fabricate syncs.
    if int(crossing.size) == 0:
        return [0.0] * n
    left_idx = xp.clip(lo, 0, int(crossing.size)-1)
    right_idx = xp.clip(hi-1, 0, int(crossing.size)-1)
    dt = crossing[right_idx] - crossing[left_idx]
    valid = (count >= 5) & (dt > 0)
    freq = xp.where(valid, (count-1)/xp.maximum(dt, 1e-20), 0.0)
    freq = xp.where(valid, xp.clip(freq, 400.0, 4000.0), 0.0)
    if gpu:
        return xp.asnumpy(freq).tolist()
    return freq.tolist()
