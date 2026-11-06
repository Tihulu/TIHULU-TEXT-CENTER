# Satellite Center — CPU / GPU / NPU compute backend controls

## What is actually accelerated

The **Signal Intelligence** and **Satellite Images & Data** screens offer **Auto · optimized for this device** (default) or **Custom** multi-select CPU, GPU and NPU.

- **CPU**: always available and mandatory for real recording I/O, FFT/spectrum, protocol/line synchronization, Robot36 pixel reconstruction and ZIP. NumPy accelerates the native 1 ms tone trace when installed; standard Python fallback remains.
- **GPU**: the current acceleration target is Robot36 *audio-to-tone-frequency trace*, **not all stages**. Browser/PWA uses a real WebGPU compute shader with a GPU buffer, command dispatch and mapped result, when the browser exposes a working compute adapter. Native uses an actually working CUDA/CuPy runtime if installed; audio PCM is explicitly transferred to VRAM, then the result returns to CPU. GPU is never just a UI label.
- **NPU (genuine native inference, Intel OpenVINO)**: when a supported Intel NPU driver plus optional NumPy/OpenVINO runtime is installed, the companion compiles an **actual static MatMul SSTV 8-tone DFT model on the literal `NPU` device** and runs a 1200 Hz test tone on it. Only successful compilation/inference enables this target. During reception the NPU evaluates real recorded PCM tone windows and reports frequency-bin evidence. CPU (and optional GPU) still perform accurate Robot36 synchronization, pixel reconstruction and PNG writing. The benchmark allows automatic NPU selection only if actual NPU inference beats a comparable CPU matrix operation; custom CPU+NPU or CPU+GPU+NPU works when supported. Hailo AI HAT, Apple Neural Engine and browser-only WebGPU do **not** run this Intel backend and remain unavailable pending validated provider-specific implementations.
- **Multi-select**: CPU+GPU, CPU+NPU and CPU+GPU+NPU are supported only when those exact real kernels pass capability checks. NPU runs SSTV tone-bin screening, GPU zero-crossing trace, and CPU sync/pixels. Unsupported devices are reported and never simulated.
- **Auto**: probes actual devices; CPU for short audio, compatible GPU on longer recordings, and Intel OpenVINO NPU on long WAVs only when its measured DFT inference beats equivalent CPU MatMul. Explicit custom selection errors rather than silently running an unavailable backend. Auto can fall back to CPU and records the reason.

## What this does not mean

CU8 frequency metadata is unknown unless provided by acquisition or user input. A real GPU trace does not prove an ISS transmission or decode an entire satellite dataset. Robot36 needs 1200 Hz synchronization from genuine FM audio. The generic CU8 FFT and RF spectrum remain CPU-processing, even when GPU is selected for the image part; the UI explicitly states which stage uses which backend. No background local GPU/NPU service or unapproved driver installation is performed.

The public 9–16 November 2026 ARISS Series 35 event uses **437.550 MHz FM (± Doppler) / Robot36**, not 145.800 MHz. It is a future scheduled event as of 6 November, with start/end UTC times TBD. A 60-second receiver clip may be entirely silent given a 36 s on / 120 s off cycle.

## Validation, acceptance and security

Run `python -m unittest discover -s tests -p 'test_satellite_*.py' -v`, `node --test tests/test_satellite_compute_backends.mjs`, cross-platform CI and hardware tests. The new tests verify default selection, custom combinations, unavailable NPU rejection and CPU vectorization equivalence on artificial audio. The tests do not prove actual GPU hardware on macOS/Windows/Linux, physical ISS reception or a successful NPU kernel.

For **Intel NPU** install only supported OpenVINO and NumPy packages in the optional local companion environment (e.g. `python -m pip install 'openvino>=2026.1' numpy`), with the Intel NPU driver provided separately by the vendor. The program does not install system drivers or silently download inference models. See [OpenVINO NPU documentation](https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-devices-and-modes/npu-device.html).
CUDA/CuPy is an **optional explicit install**, not included automatically, and only compatible driver/CUDA/Python combinations can run it. Check your GPU's supported CUDA version and the [CuPy installation guide](https://docs.cupy.dev/en/stable/install.html) before installing a compatible wheel into the companion virtual environment. Avoid system-wide driver changes. WebGPU depends on a secure context, browser support and GPU driver.

Source files: `satellite_center/compute_backends.py`, `satellite_center/browser/compute_backends.mjs`, `compute_selector.mjs`. All outputs retain source and decoder provenance.
