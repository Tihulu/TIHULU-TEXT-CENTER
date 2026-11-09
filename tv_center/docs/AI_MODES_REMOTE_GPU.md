# TIHULU AI ready modes and remote GPU

## Native Model Market workflow

Open **TIHULU AI → Model Market → Ready modes · Install all**.

1. Choose a profile to see its exact model/runtime components, estimated disk,
   restrictions and hardware suitability.
2. **Check installed** inspects locally provisioned components. A checkpoint
   file alone is not a live performance benchmark.
3. **Install all** asks permission and installs only missing components,
   sequentially. The operation needs internet for downloads/compiles, but
   does not select a mode, access a tuner, or run on application startup.
   Rerunning safely skips already installed components. Partial successes
   remain installed; errors must not be hidden.
4. **Select mode** checks hardware and every required local model/runtime,
   then activates the backend, CPU fallback model and translator in persistent
   owner-owned settings. Live captions must be restarted for a clean session.

| Preset | Speech | Translator | Additional components | Hardware |
|---|---|---|---|---|
| Pi 5 8GB | whisper.cpp Tiny CPU | Argos DE/EN/TR | CPU build | Pi 5, >=6GB host RAM |
| Pi 5 8GB + AI HAT+ 2 | whisper.cpp Tiny **CPU** | Argos DE/EN/TR | HAT hardware required; no Hailo model install | Pi 5 + Hailo device |
| Normal PC | whisper.cpp Small CPU | Argos DE/EN/TR | CPU build | >=7.5GB RAM |
| Performance | Faster-Whisper Large-v3 Turbo CUDA | Argos DE/EN/TR | Resemblyzer + Small CPU fallback | NVIDIA >=12GB VRAM; >=16GB RAM |
| Experimental | CUDA Turbo | MADLAD-400 3B CUDA | Resemblyzer, NLLB-200 600M, Argos, CPU fallback | NVIDIA >=24GB VRAM; >=32GB RAM |

NLLB uses **CC-BY-NC-4.0 (non-commercial)**. MADLAD uses Apache-2.0.
Experimental's simultaneous model execution may still exceed a VRAM/latency
budget despite meeting these minimum checks; no real-time guarantee.

### Pi 5 + AI HAT+ 2 boundary

Hailo-10H AI HAT+ 2 has a *separate* 8GB dedicated NPU memory, not a
general-purpose 8GB host RAM upgrade. Hailo supports compiled compatible
generative models, but the existing whisper.cpp GGML and Argos Python models
are **NOT** Hailo compiled and **do not use the NPU**. The current Pi HAT+ 2
preset remains a truthful CPU fallback until an actual compatible, verified
Hailo speech and translation execution pipeline is shipped.

## Remote GPU option (off by default)

This is the **speech recognition** backend only. Translation and TV playback
remain local. Only bounded 32-kHz s16le speech PCM is uploaded when the user
explicitly selects and saves **Inference engine = remote** plus **Allow sending
spoken TV audio**. No service discovery, uploads, model downloads, or LAN
server startup occurs automatically.

1. On the **GPU computer**, install the native TIHULU TV Python code and its
   separately verified managed Faster-Whisper CUDA Turbo model. Provide an
   HTTPS certificate and private TLS key for the GPU host's real DNS name.
2. Generate a distinct random token securely on the GPU computer:

   ```bash
   python3 -c 'import secrets; from tv_center.remote_gpu import save_token; save_token(secrets.token_hex(32)); print("Private token generated")'
   ```

   Transfer that secret to the viewing computer **only over a secure
   channel**; do not paste it into public issues, repository files or logs.
3. Start the server **manually** on the GPU computer. By default it listens
   on loopback only; for use over a trusted network set the host bind address
   explicitly and restrict access with your firewall/VPN:

   ```bash
   python3 -m tv_center.remote_gpu_server \
     --host 127.0.0.1 --port 8443 \
     --cert /path/to/server.crt --key /path/to/server.key \
     --token-file "$HOME/.config/tihulu-tv-center/remote-gpu-token"
   ```

   For direct LAN access, use an explicitly approved network bind address,
   a valid certificate matching your GPU host name, and restricted
   firewall/VPN access. Self-signed certificates must be trusted by the
   **client OS**; TLS verification is intentionally not disabled.
4. On the **viewing computer**, open Ready modes → Remote GPU. Enter
   `https://your-gpu-host:8443`, save the matching private token, and use
   **Test TLS · no audio**. Enable transmission and local fallback as desired.
   Go to **Speech models → Inference engine = remote**, then **Save settings**.
   Restart live captions. Without these explicit steps, no audio is uploaded.

The server's `/health` response only confirms local installed files, NOT a
real GPU speed/accuracy result. Measure on real broadcasts before relying on
remote results. All HTTP redirects and environment proxies are rejected;
the client uses system TLS certificate verification and a private token.

## Faster startup / no surprise hardware access

The native TV window and Model Market now display before NVIDIA/CUDA and
Argos package inventory probes complete. Slow discovery runs on read-only
worker threads; status updates appear afterward. Native Kaffeine now starts
without tuning the last channel by default, to avoid RF activity before the
user explicitly selects TV. To restore old behavior for a particular launch:

```bash
TIHULU_AUTOPLAY_LAST_CHANNEL=1 tihulu-media-center
```

No benchmark of first-paint duration or complete live remote inference is
claimed until tested on actual user hardware.
