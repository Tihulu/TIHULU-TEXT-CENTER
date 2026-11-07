"""Real, optional Intel OpenVINO NPU Robot36 tone-screening kernel.

This is *not* an emulated NPU, nor a promise that Hailo / Apple ANE run
OpenVINO. The actual static MatMul signal model must compile and infer on
the literal OpenVINO "NPU" device. The model computes genuine audio
frequency-channel coefficients; CPU validates synchronization and images.
No uploaded audio, neural hallucinations or synthetic RF output.
"""
from __future__ import annotations

from functools import lru_cache
from time import perf_counter
import math

NPU_BATCH = 128
NPU_HOP_MS = 2
TONES = (1000.0, 1100.0, 1200.0, 1300.0,
         1450.0, 1600.0, 1900.0, 2300.0)


def _openvino_runtime():
    import numpy as np
    import openvino as ov
    return np, ov


@lru_cache(maxsize=3)
def _build_npu_kernel(sample_rate: int):
    """Verify actual NPU compilation and run a real 1200 Hz test vector."""
    if not isinstance(sample_rate, int) or not 8000 <= sample_rate <= 96000:
        raise ValueError("NPU Robot36 only supports 8–96 kHz WAV")
    np, ov = _openvino_runtime()
    core = ov.Core()
    if "NPU" not in core.available_devices:
        raise RuntimeError("OpenVINO reports no real NPU device")
    window = max(64, int(round(sample_rate * .008 / 16)) * 16)
    indices = np.arange(window, dtype=np.float32)
    # Weight the audio samples; the NPU computes the 8 complex dot products
    # through a single real matrix multiplication. CPU does not fake output.
    hann = np.hanning(window).astype(np.float32)
    weights = np.stack([
        hann * (np.cos(2*math.pi*f*indices/sample_rate)
                if part == 0 else np.sin(2*math.pi*f*indices/sample_rate))
        for f in TONES for part in (0, 1)
    ], axis=1).astype(np.float32)
    p = ov.opset13.parameter([NPU_BATCH, window], np.float32, name="pcm_window")
    y = ov.opset13.matmul(p, ov.opset13.constant(weights), False, False)
    model = ov.Model([y], [p], "tihulu-real-robot36-npu-dft")
    compiled = core.compile_model(model, "NPU")
    probe = np.zeros((NPU_BATCH, window), dtype=np.float32)
    probe[0] = np.sin(2*math.pi*1200*indices/sample_rate)
    out = np.asarray(compiled({compiled.input(0): probe})[compiled.output(0)])
    if out.shape != (NPU_BATCH, 16) or not np.isfinite(out).all():
        raise RuntimeError("OpenVINO NPU returned an invalid DFT shape/value")
    energies = (out[0].reshape(8, 2)**2).sum(axis=1)
    if int(np.argmax(energies)) != TONES.index(1200.0) or energies.max() <= 1:
        raise RuntimeError("Physical NPU did not distinguish the injected 1200 Hz test tone")
    # Device performance, not a hardware-name guess. Auto will only prefer
    # the NPU if inference beats identical NumPy CPU matmul significantly.
    cpu_times, npu_times = [], []
    for _ in range(3):
        t = perf_counter()
        np.matmul(probe, weights)
        cpu_times.append(perf_counter() - t)
        t = perf_counter()
        compiled({compiled.input(0): probe})
        npu_times.append(perf_counter() - t)
    cpu_s = sorted(cpu_times)[1]
    npu_s = sorted(npu_times)[1]
    return {"np": np, "compiled": compiled, "weights": weights,
            "sample_rate": sample_rate, "window_samples": window,
            "benchmark_cpu_ms": round(cpu_s*1000, 3),
            "benchmark_npu_ms": round(npu_s*1000, 3),
            "auto_beneficial": bool(npu_s < cpu_s*.80),
            "device": "NPU"}


def probe_real_sstv_npu() -> dict:
    """No NPU marked available unless an actual device runs the SSTV model."""
    try:
        kernel = _build_npu_kernel(48000)
    except (ImportError, ValueError, RuntimeError, OSError, Exception) as exc:
        return {
            "available": False,
            "name": "OpenVINO Intel NPU SSTV tone screener",
            "role": "Bounded 1200 Hz synchronization tone screening",
            "reason": "No verified NPU SSTV kernel: "+str(exc)[:180],
            "provider": "openvino-npu",
        }
    return {
        "available": True,
        "name": "OpenVINO Intel NPU (real MatMul inference)",
        "provider": "openvino-npu",
        "device": "NPU",
        "role": "8-channel PCM frequency screening before CPU/GPU Robot36 reconstruction",
        "auto_beneficial": kernel["auto_beneficial"],
        "benchmark_cpu_ms": kernel["benchmark_cpu_ms"],
        "benchmark_npu_ms": kernel["benchmark_npu_ms"],
        "note": "Real NPU inference, not entire decoder. Not supported by Hailo/Apple ANE.",
    }


def scan_real_npu_tones(raw: bytes, sample_rate: int) -> dict:
    """Run actual Intel NPU inference on an entire bounded real PCM section.

    The returned evidence can guide manual review. Never decide that a
    spacecraft transmitted, skip CPU sync, or create a PNG from inference
    outputs alone. Traces and original samples are not uploaded.
    """
    kernel = _build_npu_kernel(sample_rate)
    np, compiled = kernel["np"], kernel["compiled"]
    if len(raw) % 2:
        raise ValueError("Odd PCM sample byte count")
    data = np.frombuffer(raw, dtype="<i2").astype(np.float32)/32768.0
    w = kernel["window_samples"]
    hop = max(1, int(sample_rate*NPU_HOP_MS/1000))
    if data.size < w:
        raise ValueError("Insufficient real PCM for NPU tone scan")
    nwin = (data.size-w)//hop + 1
    channels = np.zeros(len(TONES), dtype=np.int64)
    processed = 0
    batch = np.zeros((NPU_BATCH, w), dtype=np.float32)
    for start in range(0, nwin, NPU_BATCH):
        count = min(NPU_BATCH, nwin-start)
        ix = (np.arange(start, start+count)[:, None]*hop +
              np.arange(w)[None, :])
        batch.fill(0.0)
        batch[:count] = data[ix]
        out = np.asarray(compiled({compiled.input(0): batch})[compiled.output(0)])
        if out.shape != (NPU_BATCH, 16) or not np.isfinite(out).all():
            raise RuntimeError("NPU returned invalid computed frequency energies")
        energy = (out[:count].reshape(count, 8, 2)**2).sum(axis=2)
        # Ignore near-zero input; a silent recording cannot become RF evidence.
        active = np.max(energy, axis=1) > 0.002
        ids = np.argmax(energy, axis=1)
        channels += np.bincount(ids[active], minlength=8)
        processed += count
    return {
        "status": "real_npu_dft_completed",
        "device_used": "NPU",
        "provider": "openvino-npu",
        "model": "static-128x8-channel-audio-DFT-matmul",
        "window_samples": w,
        "window_hop_ms": round(hop*1000/sample_rate, 3),
        "windows_processed": processed,
        "frequency_bins_hz": list(TONES),
        "dominant_tone_windows": channels.astype(int).tolist(),
        "sync_tone_1200_window_count": int(channels[TONES.index(1200.0)]),
        "image_or_iss_verified": False,
        "note": "Tone-channel screening only; CPU still validates repeated Robot36 line sync and pixels.",
    }
