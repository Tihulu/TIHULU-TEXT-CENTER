# RQ-098 / EXIT-01 — Full application shutdown, model unload, RAM/VRAM and device release

**Owner request:** 2026-11-12 | **Priority:** P0 cross-application | **Status:** NEW / NOT IMPLEMENTED OR ACCEPTED | **Change type:** Additional owner requirement, separate from the initial 97 source-audited requirements.

**One-sentence user contract:** When a TIHULU application is fully quit, it and every process/resource it owns must finish, its locally loaded AI models must be unloaded, its RAM/VRAM/NPU memory allocations and open hardware resources must be released, and no application-owned AI worker, local server, capture job or background task may continue. Existing third-party or independently owned shared services must NOT be killed or disrupted.

This requirement is **not** evidence that current applications already meet it. Existing software CI and a window closing do not establish memory/resource release.

## Coverage

Applies to the TIHULU Survival Kit shell, Flight Radar, Media Center, Text Center, Satellite Center, RF Geolocation Center, AI Tools / Model Manager, and any bundled or future TIHULU component (including GPU host pairing, local inference, model marketplace and Jan-style integration). Scope includes native desktop, Raspberry Pi 5 / AI HAT+ 2, Windows x64, Debian/Ubuntu/Pop!_OS on x64/ARM64, macOS Apple Silicon, and web/PWA where the browser lifecycle permits control. App-initiated workers in other languages and embedded/native bridges are included regardless of which UI started them.

Platform/runtime resources to release when *app-owned*:

- **RAM:** Local LLM/Whisper/embedding/translation model objects and caches, inference contexts, tensor buffers, in-memory audio/video buffers, streaming frame queues, decoded TV/radio image caches, worker heaps and temporary memory mappings. Shut down workers/OS processes to release allocations; in-process `gc.collect()` alone is insufficient proof.
- **GPU/VRAM:** CUDA/ROCm, Vulkan, DirectML and Apple Metal/MPS model allocations, inference sessions/contexts, CUDA streams and buffers, PyTorch/ONNX/TensorRT/llama.cpp backends as applicable. Terminate app-owned GPU processes and dispose their contexts; a framework-specific `empty_cache()` or equivalent can be a **supplemental** cleanup but is NOT proof that the entire model or GPU context is gone.
- **NPU/AI accelerators:** Hailo-10H/AI HAT+ 2 and other NPU or vendor runtime contexts, buffers, device handles, IPC channels, model mappings and worker processes.
- **Hardware:** App-owned RTL-SDR, DVB-T2/USB tuner, audio/video devices, file descriptors, TCP/WebSocket/HTTP listeners, RF capture processes, recording timers and exclusive device locks. Close receivers and release locks **only for owned sessions**. Preserve user recordings and intentionally persisted metadata.
- **Background:** Stop app-owned `readsb` direct children, SatDump/ffmpeg/Whisper/asr translation jobs, model servers, HTTP/Tauri/Qt bridges, preview encoders, schedulers and subprocess trees when the user issues **Quit application**. Ensure no auto-restart or hidden tray-only process remains after a full Quit.
- **Model manager / marketplace:** Integrating another app's model must preserve that app's original files/permissions/path and leave the model loaded by the **external** app alone. A model shared by multiple TIHULU sessions must use ownership/refcounts/leases and unload only after the last owning client. Local exit must never terminate an unrelated remote inference server or externally owned GPU host.
- **Persistent data:** Flushing transactional recordings, queued saves and database writes is required; a Hard Stop may cancel work but cannot delete previous user media, exports, downloaded model files or authorized settings. Temporary app-owned caches may be removed after ownership verification.

## User-facing exit semantics

- **Close application / Quit** means a *real full shutdown* on every supported native platform: terminate all app-owned background and model workers and release all app-owned RAM/VRAM/NPU/hardware resources. If the window close control normally minimizes to tray in some platform, provide a **clearly separate Quit** control and ensure the user can select true termination; do not silently keep inference processes running.
- **Hard Stop** means immediate best-effort cancellation of all app-owned jobs/device capture without terminating unrelated apps or deleting recordings. It does not automatically force-quit the whole GUI unless expressly requested; **Quit** then completes full cleanup.
- **Stop Module** unloads that module's models/streams/workers and releases its device lease, while keeping unrelated TIHULU modules working.
- **Background / Always-on modes** are opt-in modes during app runtime only; the explicit full Quit takes precedence and ends that app's owned work. A separately installed, independently managed service/daemon must be treated as a distinct product with explicit ownership and a separate user-controlled Stop/Quit semantics; do not silently leave it behind under the app's name.
- On any failure to release an app-owned process/device, show an **actionable warning** while the UI is still able to report it, or write a private bounded local shutdown report. Do not falsely show "all resources freed" after an incomplete cleanup.

## Required teardown ordering

1. Transition into `STOPPING` state; reject further Start, auto-schedule, inference and reconnection. Capture a snapshot of **app-owned** child process IDs, device leases, worker sessions, temporary paths and active model sessions, with generation IDs to prevent PID reuse/race-induced kills.
2. Cancel polling, auto schedules, network loops and callbacks; stop admitting new jobs. Drain or safely cancel pending export/recording operations while preserving committed user data.
3. Request **graceful** model-worker shutdown and close IPC/HTTP/WebSocket streams; dispose local model instances, GPU/NPU inference contexts and CUDA/Metal/DirectML/Vulkan resources in their owning processes. Wait for bounded timeouts, log incomplete cleanup.
4. Stop/terminate only **verified child processes in the app's ownership tree or cgroup/Windows Job Object**. Use constrained escalation after timeout and verify the process identity (PID + creation time or OS-held handle); never global `pkill -f`, `killall`, GPU reset, `sudo systemctl stop` of externally owned services or driver unload.
5. Release app-owned receiver handles, cross-module SDR leases, model-manager reference counts, local port listeners and lock files using owner IDs; do not unlink or overwrite another app's lock. Clean only owned temporary output files that are safe to discard.
6. Verify owned-process count = 0, owned GPU/NPU sessions = 0, owned RF leases = 0, owned sockets = 0; record before/after RAM and per-process GPU allocated memory (if available). Report `STOPPED` only after verifying; otherwise `STOP_FAILED_PARTIAL` with concrete remaining resource IDs and user action. OS page cache, driver cache and memory still used by other apps are **not leaks** and must not be "freed" by system-wide destructive actions.

Crash/restart path: use a persistently identifiable session/lease registry to detect orphaned **app-owned** jobs without touching unrelated PIDs; clean on next launch only after identity/ownership checks. Avoid model downloads, access to USB or real services in automatic CI.

## Cross-platform implementation contracts

- **Rust/native shell/Tauri:** central `ResourceSupervisor`/RAII ownership registry; async task cancellation + join; process-group or equivalent scoped child handles; deterministic `Drop`/explicit shutdown (do not rely on `Drop` alone for async GPU/worker lifetime); OS signals and forced-close path. Keep shutdown ordering invariant in both native and headless launch.
- **Linux (Pop!_OS, Ubuntu/Debian, Pi):** scoped child process group/cgroup as appropriate; verify `/proc` identity before bounded terminate; `nvidia-smi` per-process memory only as a supplemental sensor. Respect independently launched `readsb.service`/`tar1090.service`, welle.io, Gqrx and other third-party services. No host-level GPU reset, kernel module removal or sudo.
- **Windows:** owned child process Job Object / tracked process handles, DirectML/CUDA sessions, USB/COM handles; ensure user Exit is not tray minimization; do not close external Windows Services.
- **macOS Apple Silicon:** close owned Metal/MPS/CoreML contexts and inference subprocesses; cooperative shutdown followed by owned-process termination, not a blanket `killall`.
- **Raspberry Pi 5 + AI HAT+ 2:** close app-owned Hailo runtime/VDevice, stream pipeline, HEF/NPY memory maps and buffers; leave other Hailo consumers untouched.
- **Web/PWA:** best-effort worker/controller cleanup and revoke WebUSB/stream leases that the page owns when it receives lifecycle events, with explicit Stop buttons and visibility-state handling; **browser-tab close/crash cannot guarantee native-style teardown**. Do not promise reliable post-tab-close cancellation of other native programs. Dedicated native supervisor is the authoritative cleanup boundary when present.
- **Remote AI host:** local app quit revokes only **its own** remote inference lease/session if the remote API supports it; never shut down a paired independent GPU host or another app's sessions.

## P0 synthetic acceptance matrix — proposed, NOT YET RUN

| ID | Case | Required outcome |
|---|---|---|
| EXIT-01-A | GUI Quit with locally loaded CPU LLM + Whisper + local translation | All three app-owned model sessions disposed; app child count zero, RAM allocations released on worker exit |
| EXIT-01-B | GUI Quit during CUDA inference | Cancel queue, close owned CUDA context/worker, per-process GPU allocation falls to zero after process termination; external GPU clients unaffected |
| EXIT-01-C | Apple Metal/MPS/Windows DirectML exit mid-stream | No model-worker processes or GPU sessions remain; user media intact |
| EXIT-01-D | Pi 5 Hailo NPU inference + Exit | Owned Hailo workers/buffers and device lease released, other users unaffected |
| EXIT-01-E | Multi-module shared model | Closing one module decrements refcount; complete Quit unloads when no other TIHULU client holds it |
| EXIT-01-F | External Jan/LLM model path or remote GPU host | Original app/host and model bytes remain unchanged; only own bridge/session closes |
| EXIT-01-G | Flight external readsb/tar1090 already running | App Quit does not stop either external service; user sees accurate receiver ownership |
| EXIT-01-H | Own SDR/SatDump/ffmpeg in recording | Cancel/complete safely, close device and owned child; no partial export mislabeled as completed; saved files preserved |
| EXIT-01-I | Delayed worker Start racing with Quit | STOPPING prevents late respawn, stale callbacks cannot relaunch a daemon |
| EXIT-01-J | Worker refuses shutdown / timeout | Bounded scoped termination of owned child only; explicit partial-failure report if not released |
| EXIT-01-K | Repeated Stop, Quit and crash/restart | Idempotent; no double-free, PID reuse kills, dangling locks or revived workers |
| EXIT-01-L | Background ON / Always-On selected but explicit Quit issued | All app-owned jobs end; no tray or hidden model server left |
| EXIT-01-M | Module-only Stop | Release only that module's model/device lease; other modules remain operational |
| EXIT-01-N | Web/PWA tab close | Best-effort cleanup with documented browser limits; no unsupported full-clean guarantee |
| EXIT-01-O | Linux, Windows, macOS, ARM64 installed app acceptance | Compare before/after owned PID, open handles, GPU/NPU memory and receiver ownership with bounded residuals and unchanged external apps |

**Acceptance definition:** "0 owned live workers/models/device sessions after full Quit" is a process/ownership contract. Total system RAM/VRAM usage need not read literal **0 MB** since OS/driver caches and other applications can retain allocations. Explicit GPU/NPU measurement is collected only on supported installed targets, after separately approved real-device testing; CI mocks cannot certify real VRAM cleanup.

## Workstream assignment and blockers

- **WS01 Media:** native Qt/FFmpeg/Whisper/NLLB/CUDA subprocess shutdown, recording flush, timed sidecars, GPU/CPU/translation buffers. References REG-01, REG-03, REG-16.
- **WS02 Flight:** safe exit ownership with new Draft #15 and old Draft #14 XFAIL, direct readsb child, local map/bridge processes, no external service kill. References REG-03, REG-14.
- **WS03 Satellite:** scheduler cancel, RTL-SDR/SatDump subprocess, decoder/image caches, RF lease, capture source preservation. References REG-06, REG-07, REG-09, REG-14.
- **WS04 Geolocation:** RF worker/device locks and timers, advertised model state; never imply calibrated location. References REG-03, REG-05.
- **WS05 Text:** direct RF/DVB workers, optional offline AI speech/translation CPU/GPU/NPU, local HTTP, worker/stream buffer cleanup, standalone Media independence. References REG-02, REG-03, REG-10.
- **WS06 QA:** 15-case matrix plus native installed OS acceptance and safe rollback, observability, leak regression and multi-app interference. References REG-13, REG-14, REG-17.
- **AI Tools / Survival Kit coordination:** Rust model registry, model loading/import/marketplace, shared GPU-host sessions, per-application leases and cross-platform supervisor. Needs its own engineering implementation scope and independent release gate; there is no source audit or software-test proof here yet.

**New requirement accounting:** baseline 97/97 source audits remain intact. RQ-098 is **one additional owner-requested requirement awaiting source mapping**. EXIT-01 is **one new proposed P0 acceptance gate** to be formally integrated later into the original 17-gate registry; the original 17/17 OPEN count must not be silently replaced or incorrectly credited.

## Permission / evidence boundary

This document records owner intent and acceptance requirements. It **does not** authorize automatically changing app source, installers, default runtime services, background settings, hardware, release, original PRs or main. A later dedicated feature branch and isolated synthetic CI are needed per app; physical GPU/NPU/SDR and installed app acceptance requires explicit owner-run scope. No existing claim that RAM/VRAM cleanup works today, no merges or migrations.
