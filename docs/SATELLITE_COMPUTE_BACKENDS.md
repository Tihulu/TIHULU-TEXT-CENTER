# Satellite Center — CPU / GPU / NPU compute backend controls

## What is actually accelerated

The **Signal Intelligence** and **Satellite Images & Data** screens offer **Auto · optimized for this device** (default) or **Custom** multi-select CPU, GPU and NPU.

- **CPU**: always available and mandatory for real recording I/O, FFT/spectrum, protocol/line synchronization, Robot36 pixel reconstruction and ZIP. NumPy accelerates the native 1 ms tone trace when installed; standard Python fallback remains.
- **GPU**: the current acceleration target is Robot36 *audio-to-tone-frequency trace*, **not all stages**. Browser/PWA uses a real WebGPU compute shader with a GPU buffer, command dispatch and mapped result, when the browser exposes a working compute adapter. Native uses an actually working CUDA/CuPy runtime if installed; audio PCM is explicitly transferred to VRAM, then the result returns to CPU. GPU is never just a UI label.
- **NPU**: shown as a separate target but disabled with an explanation until there is a validated and compatible DSP kernel or trained signal classifier for that NPU. An installed Hailo AI HAT or Windows NPU alone is not support. No virtual NPU, NPU model download or hidden inference.
- **Multi-select**: CPU+GPU can run the real GPU tone trace plus CPU synchronization/assembly. GPU-only selection still requires CPU housekeeping and the UI says so. CPU+NPU or CPU+GPU+NPU is available as a *configuration concept*, but attempts to use NPU are blocked until a supported implementation exists rather than silently pretending success.
- **Auto**: probes usable hardware, favors CPU for short SSTV audio, CPU+WebGPU when at least 50 seconds of browser audio can benefit, and CPU+native CUDA/CuPy for native WAVs of 120+ seconds. If automatic GPU execution fails, use a truthful CPU fallback with a recorded reason. Explicit custom GPU failure is reported instead of silently switching.

## What this does not mean

CU8 frequency metadata is unknown unless provided by acquisition or user input. A real GPU trace does not prove an ISS transmission or decode an entire satellite dataset. Robot36 needs 1200 Hz synchronization from genuine FM audio. The generic CU8 FFT and RF spectrum remain CPU-processing, even when GPU is selected for the image part; the UI explicitly states which stage uses which backend. No background local GPU/NPU service or unapproved driver installation is performed.

The public 9–16 November 2026 ARISS Series 35 event uses **437.550 MHz FM (± Doppler) / Robot36**, not 145.800 MHz. It is a future scheduled event as of 6 November, with start/end UTC times TBD. A 60-second receiver clip may be entirely silent given a 36 s on / 120 s off cycle.

## Validation, acceptance and security

Run `python -m unittest discover -s tests -p 'test_satellite_*.py' -v`, `node --test tests/test_satellite_compute_backends.mjs`, cross-platform CI and hardware tests. The new tests verify default selection, custom combinations, unavailable NPU rejection and CPU vectorization equivalence on artificial audio. The tests do not prove actual GPU hardware on macOS/Windows/Linux, physical ISS reception or a successful NPU kernel.

CUDA/CuPy is an **optional explicit install**, not included automatically, and only compatible driver/CUDA/Python combinations can run it. Check your GPU's supported CUDA version and the [CuPy installation guide](https://docs.cupy.dev/en/stable/install.html) before installing a compatible wheel into the companion virtual environment. Avoid system-wide driver changes. WebGPU depends on a secure context, browser support and GPU driver.

Source files: `satellite_center/compute_backends.py`, `satellite_center/browser/compute_backends.mjs`, `compute_selector.mjs`. All outputs retain source and decoder provenance.
