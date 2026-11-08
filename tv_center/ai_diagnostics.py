"""Read-only ASR hardware and model readiness report for the current TV user.

Never opens DVB, downloads models, loads model weights or runs speech inference.
Detected hardware is not represented as an actually working backend.
"""
from __future__ import annotations
import json
from pathlib import Path


def inspect():
    from tv_center.ai_settings import AISettings
    from tv_center.hardware_market import detect_hardware
    from tv_center.runtime import AIRuntime
    from tv_center.translation_market import TranslationModelMarket
    from tv_center.whisper_engine import WhisperRuntime
    from textcenter.compute import detect_devices, choose_backend

    settings = AISettings()
    settings.configure_environment()
    model = settings.values.get("model_path", "")
    hardware = detect_hardware()
    profile = detect_devices(model_path=model)
    choice = choose_backend(profile, settings.values["backend"])
    whisper = WhisperRuntime()
    gpu = hardware["gpu"]
    npu = hardware["npu"]
    return {
        "policy": "Read-only: no RF access, downloads, model inference or TV playback change.",
        "whisper": {
            "enabled": settings.values["asr_enabled"],
            "model": Path(model).name if model else None,
            "model_installed": bool(model and Path(model).is_file()),
            "requested_backend": settings.values["backend"],
            "selected_backend": choice.get("selected"),
            "backend_ready": bool(choice.get("ready")),
            "backend_reason": choice.get("reason"),
            "runtime_cpu": whisper.ready(),
            "runtime_cuda": whisper.ready_gpu(),
            "runtime_npu": bool(profile["speech"].get("ready_npu")),
            "known_gpu_engine": profile["speech"].get("gpu_engine"),
        },
        "hardware": {
            "cpu": hardware["cpu"],
            "nvidia_gpu": gpu["name"],
            "gpu_detected": gpu["detected"],
            "vram_mib": gpu["vram_mib"],
            "cuda_compiler": gpu["cuda_version"],
            "cuda_compiler_path": gpu.get("cuda_compiler"),
            "cuda_compile_possible": gpu["cuda_compile_possible"],
            "cuda_note": gpu["reason"],
            "npu_detected": npu["detected"],
            "npu_runtime_ready": npu["ready"],
            "npu_detail": npu["detail"],
            "raspberry_pi_5": hardware["raspberry_pi_5"],
        },
        "translation": {
            "enabled": settings.values["translation_enabled"],
            "engine": settings.values["translation_model"],
            "argos_runtime_installed": AIRuntime().status()["installed"],
            "nllb_model_installed": TranslationModelMarket().status()["installed"]
        },
        "next_step": (
            "GPU READY: test real audio inference in Kaffeine, verify actual CUDA execution."
            if choice.get("selected") == "gpu" and choice.get("ready") else
            "RTX detected, CUDA Toolkit >=12.8 compiler not available. Check "
            "'ls /usr/local/cuda*/bin/nvcc' and install NVIDIA's cuda-toolkit-12-8 "
            "(toolkit only; do not replace the Pop!_OS NVIDIA driver), then "
            "build CUDA whisper.cpp in TIHULU Model Market."
            if gpu["detected"] and not gpu["cuda_compile_possible"] else
            "GPU found, but the user-owned CUDA whisper.cpp runtime is missing. "
            "Install CUDA Whisper in Model Market, then select a larger "
            "multilingual GGML model and save backend Auto/GPU."
            if gpu["detected"] and not whisper.ready_gpu() else
            "Install/activate a multilingual Whisper model and matching runtime in Model Market."
        )
    }


def main():
    print(json.dumps(inspect(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
