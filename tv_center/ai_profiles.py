"""Explicit offline-first AI model profiles for native TV Center.

A profile is a *plan*, not a virtual model installation. Only supported
runtimes are provisioned; Hailo AI HAT+ 2 memory is separate from host RAM.
No downloads, network probes, model imports, or device opens at import time.
"""
from __future__ import annotations

from pathlib import Path

# Installation steps are intentionally reusable across profiles.
# No unverified Hailo Whisper/translation backend is advertised.
PROFILES = {
    "pi5": {
        "name": "Raspberry Pi 5 · 8 GB",
        "description": "Offline, lower-memory CPU speech. Tiny can be slow; benchmark live TV before enabling multiple translations.",
        "components": ("whisper_cpu", "tiny", "argos"),
        "speech": "tiny", "backend": "cpu", "translator": "argos",
        "min_ram_mib": 6000, "min_vram_mib": 0,
        "disk_gb_estimate": "2–4 GB including CPU runtime and language packs",
    },
    "pi5_hat2": {
        "name": "Raspberry Pi 5 · 8 GB + AI HAT+ 2 (8 GB NPU)",
        "description": "Host CPU Whisper Tiny + Argos for now. Hailo-10H has separate 8 GB; these specific Whisper/Argos weights are NOT Hailo-compiled or NPU-accelerated.",
        "components": ("whisper_cpu", "tiny", "argos"),
        "speech": "tiny", "backend": "cpu", "translator": "argos",
        "min_ram_mib": 6000, "min_vram_mib": 0,
        "disk_gb_estimate": "2–4 GB; optional Hailo models are not automatically provisioned",
    },
    "normal": {
        "name": "Normal · regular desktop / laptop",
        "description": "Whisper Small CPU + compact Argos DE/EN/TR. Optional Resemblyzer can be installed separately.",
        "components": ("whisper_cpu", "small", "argos"),
        "speech": "small", "backend": "cpu", "translator": "argos",
        "min_ram_mib": 7500, "min_vram_mib": 0,
        "disk_gb_estimate": "3–5 GB including runtime and translations",
    },
    "performance": {
        "name": "Performance · RTX 5080 / 16 GB VRAM",
        "description": "Verified CUDA Faster-Whisper Large-v3 Turbo + fast Argos + Resemblyzer; small CPU fallback. Recommended for real-time TV captions.",
        "components": ("cuda_turbo", "whisper_cpu", "small", "argos", "resemblyzer"),
        "speech": "small", "backend": "gpu", "translator": "argos",
        "min_ram_mib": 16000, "min_vram_mib": 12000,
        "disk_gb_estimate": "7–12 GB including CUDA wheels and fallback",
    },
    "experimental": {
        "name": "Experimental · 24 GB+ VRAM high-end PC",
        "description": "CUDA Turbo speech, MADLAD-400 3B GPU translation, NLLB comparison, Resemblyzer, and CPU fallback. Heavy and not guaranteed real-time.",
        "components": ("cuda_turbo", "whisper_cpu", "small", "argos",
                       "resemblyzer", "nllb", "madlad"),
        "speech": "small", "backend": "gpu", "translator": "madlad",
        "min_ram_mib": 32000, "min_vram_mib": 24000,
        "disk_gb_estimate": "30–50 GB (large translations and dependencies)",
    },
}

COMPONENTS = {
    "whisper_cpu": ("whisper.cpp CPU engine", "Source compile; offline after installation"),
    "tiny": ("Whisper Tiny multilingual · 78 MB", "Verified GGML CPU weights"),
    "small": ("Whisper Small multilingual · 488 MB", "Verified GGML CPU weights"),
    "argos": ("Argos DE / EN / TR", "4 offline language directions including EN pivot"),
    "cuda_turbo": ("Faster-Whisper Large-v3 Turbo CUDA", "CTranslate2 NVIDIA CUDA + checked model"),
    "resemblyzer": ("Resemblyzer speaker clustering", "Estimated voice clusters, not identity"),
    "nllb": ("NLLB-200 distilled 600M", "CC-BY-NC-4.0; non-commercial only"),
    "madlad": ("MADLAD-400 3B", "Apache-2.0; large CUDA-only translation"),
}


def profile(key):
    if key not in PROFILES:
        raise ValueError("Unknown AI profile")
    return PROFILES[key]


def hardware_issue(key, hardware):
    spec = profile(key)
    ram = hardware.get("ram_mib")
    if isinstance(ram,int) and ram < spec["min_ram_mib"]:
        return "System RAM below profile minimum"
    gpu = hardware.get("gpu") or {}
    if spec["min_vram_mib"]:
        if not gpu.get("detected"):
            return "A verified NVIDIA CUDA GPU is required"
        vram = gpu.get("vram_mib")
        if not isinstance(vram,int) or vram < spec["min_vram_mib"]:
            return "NVIDIA VRAM below profile minimum"
    if key.startswith("pi5") and not hardware.get("raspberry_pi_5"):
        return "This mode is for Raspberry Pi 5 hardware (preview only on this PC)"
    if key == "pi5_hat2":
        # /dev/hailo does not prove Hailo-10H model compatibility.
        detected = hardware.get("npu",{}).get("devices") or []
        if not any("hailo" in str(device).lower() for device in detected):
            return "Hailo device not detected; HAT+ 2 mode is preview-only"
    return None


def local_status(key, *, library=None, starter=None):
    """Inspect cheap local markers; optional Argos pair discovery runs only on request.

    This is intentionally not called from the application's main startup.
    """
    if key not in COMPONENTS:
        raise ValueError("Unknown component")
    if key in ("tiny", "small"):
        from .model_market import ModelLibrary
        lib=library or ModelLibrary()
        return lib._path(key).is_file()
    if key == "whisper_cpu":
        from .whisper_engine import WhisperRuntime
        return WhisperRuntime().ready()
    if key == "argos":
        # A runtime alone does not prove 4 translation directions.
        from .ai_provision import StarterAI
        return bool((starter or StarterAI(library=library)).status()[
            "translation_three_languages_ready"])
    if key == "cuda_turbo":
        from .cuda_faster_whisper import FasterWhisperCUDA
        return FasterWhisperCUDA().installed()
    if key == "resemblyzer":
        from .free_speakers import FreeSpeakerMarket
        return FreeSpeakerMarket().status()["installed"]
    if key == "nllb":
        from .translation_market import TranslationModelMarket
        return TranslationModelMarket().status()["installed"]
    if key == "madlad":
        from .translation_madlad import MadladMarket
        return MadladMarket().status()["installed"]
    return False


def missing_components(key, status):
    spec=profile(key)
    return tuple(component for component in spec["components"]
                 if not status.get(component, False))


def install_components(key, *, library=None, progress=None, installer=None):
    """Explicit user-confirmed batch install, sequential, resumable, no auto-select.

    `installer` is a test seam. A component is verified before marking success,
    never reported installed just because a subprocess returned zero.
    """
    spec=profile(key)
    from .model_market import ModelLibrary
    lib=library or ModelLibrary()
    def notice(message):
        if progress:
            progress(message)
    steps=[]
    # Check hardware BEFORE any irreversible network installs or large
    # downloads; Pi CPU and experimental GPU requirements are not optional.
    from .hardware_market import detect_hardware
    issue=hardware_issue(key,detect_hardware()) if installer is None else None
    if issue:
        raise RuntimeError("Cannot install this mode on current hardware: "+issue)
    for index,component in enumerate(spec["components"],1):
        notice(f"{index}/{len(spec['components'])} · {COMPONENTS[component][0]}")
        if local_status(component,library=lib):
            steps.append((component,"already installed"))
            continue
        if installer is not None:
            installer(component)
        elif component=="whisper_cpu":
            WhisperRuntime().install()
        elif component in ("tiny","small"):
            lib.download(component,progress=lambda got,total:
                notice(f"{component}: {got // 1048576} MiB downloaded"))
        elif component=="argos":
            from .ai_provision import StarterAI
            from .runtime import AIRuntime
            rt=AIRuntime()
            if not rt.status()["installed"]:
                rt.install_argos()
            StarterAI(library=lib)._setup_argos_packs(progress=notice)
        elif component=="cuda_turbo":
            from .cuda_faster_whisper import FasterWhisperCUDA
            FasterWhisperCUDA().install()
        elif component=="resemblyzer":
            from .free_speakers import FreeSpeakerMarket
            FreeSpeakerMarket().install()
        elif component=="nllb":
            from .translation_market import TranslationModelMarket
            TranslationModelMarket().install()
        elif component=="madlad":
            from .translation_madlad import MadladMarket
            MadladMarket().install()
        else:
            raise RuntimeError("Unknown installer")
        if not local_status(component,library=lib):
            raise RuntimeError(COMPONENTS[component][0] +
                               " is not verified after installation")
        steps.append((component,"installed"))
    return steps


def selection_patch(key, *, library, hardware, status):
    """Plan activation separately from installing; fail closed on missing assets."""
    spec=profile(key)
    issue=hardware_issue(key,hardware)
    if issue:
        raise RuntimeError(issue)
    missing=missing_components(key,status)
    if missing:
        raise RuntimeError("Install all first; missing: " +
                           ", ".join(COMPONENTS[x][0] for x in missing))
    chosen=library._path(spec["speech"])
    if not Path(chosen).is_file():
        raise RuntimeError("Missing local CPU Whisper fallback model")
    return {
        "active_profile":key,
        "asr_enabled":True,
        "translation_enabled":True,
        "backend":spec["backend"],
        "translation_model":spec["translator"],
        "model_path":str(chosen),
        "model_dir":str(library.root),
    }
