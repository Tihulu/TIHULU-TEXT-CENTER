# Live Studio 420 — Continuous FM / DVB-TV, Recording and Offline Translation

**Development status:** This is an additive, reviewable candidate. CI unit tests use synthetic PCM and DVB fixture metadata; continuous streaming has NOT yet been validated on the user's Nooelec or ordered Hauppauge. Hardware/decoder/model dependencies are mandatory. No fake stations, video, subtitles or NPU execution.

## Feature summary

| Source | Playback | Optional recording | Live original subtitles | Live translation | Translate saved transcript later |
| --- | --- | --- | --- | --- | --- |
| FM radio | Single native RTL-SDR -> rtl_fm -> ffmpeg -> browser MP3 stream; stays active until stop/browser disconnect or safety limit | Source audio as MP3 (default OFF) | Multilingual faster-whisper from same PCM (default OFF) | Offline Argos EN, DE, TR (if installed models) | Yes, saved original required |
| DVB-T/T2/C television | Real DVB service -> dvbv5-zap -> /dev/dvb/adapter0/dvr0 -> FFmpeg fragmented MP4 -> browser MSE (needs compatible codecs) | Original unchanged MPEG-TS (default OFF) | Real TV audio decoded once in FFmpeg, fed to same caption worker | Offline Argos EN, DE, TR (if installed models) | Yes |

FM and DVB use **different physical tuners**. Multiple applications must not retune the same receiver. Text Center's /proc process detection + cooperative lock protect its own sessions, but a full Survival Kit installation must use the *authoritative shared Radio/TV/Flight Radar lease broker* before exposing multi-application capture.

## On Pop!_OS 24.04 — required native tools

```bash
cd ~/TIHULU-TEXT-CENTER
git fetch origin feature/continuous-av-translator-2026-11-06
git switch --track origin/feature/continuous-av-translator-2026-11-06
command -v rtl_fm
command -v ffmpeg
ffmpeg -hide_banner -encoders 2>/dev/null | grep -E 'libmp3lame|libx264|aac'
python3 -m textcenter receivers
python3 -m textcenter dvb-diagnose
python3 -m textcenter serve
```

Where necessary, and only after user approval, install distribution packages such as `ffmpeg` and `dvb-tools` using apt. The base Text Center still has no mandatory third-party Python packages and runs without AI models. Do not install a kernel PPA solely because a DVB frontend is absent; confirm actual USB VID/PID and dmesg firmware request, especially on nonstandard Pop!_OS kernels.

## Hauppauge 01589 — actual DVB channel prerequisite

WinTV-soloHD model 01589 is specified by Hauppauge for terrestrial DVB-T/DVB-T2 and DVB-C, but the product order does not prove it is already connected, unencrypted channels are present or Linux drivers are functional. Additional European firmware may be required.

First install/verify the actual hardware. Use `python3 -m textcenter dvb-diagnose`, `lsusb`, `ls -l /dev/dvb/adapter*`, `dmesg` for the real frontend/firmware. **Never assume adapter0/frontend0 is the Hauppauge until identified.**

Generate a *real* channel list with `dvbv5-scan`, using a verified local regional initial-tuning file. This is explicitly user-triggered because it retunes the DVB frontend; do not scan while a TV recording is in progress.

```bash
# Example structure; replace file paths with YOUR real verified regional scan file:
dvbv5-scan /path/to/verified-dvb-t2-initial-scan-file -o "$HOME/.local/share/tihulu-text-center/channels.conf"
export TIHULU_DVB_CHANNELS_FILE="$HOME/.local/share/tihulu-text-center/channels.conf"
python3 -m textcenter serve
```

Only services from this configured, locally scanned file appear in Live Studio's TV dropdown. `dvbv5-zap -r -p` selects the verified service PIDs (no all-multiplex default) and provides an original TS stream at `/dev/dvb/adapter0/dvr0`. Video is transcoded to H.264 baseline/AAC fragmented MP4 at a CPU-conservative resolution for MediaSource. A browser without a compatible MSE/video decoder may not play. Free-to-air channels only; nothing circumvents encryption/DRM or paid-TV entitlement.

**Safety:** a separate `dvb_frontend0.lock` is used for Text Center, plus known competing DVB-process detection. This is not a globally authoritative hardware lease; a fully integrated Survival Kit broker remains required. The optional MPEG-TS recording preserves original received packets but is subject to explicit disk quotas, transport quality and user stop.

## Offline English / German / Turkish transcription and translation

All 6 directed language pairs are supported conceptually: EN↔DE, EN↔TR, DE↔TR. Same-language original subtitles are also supported.

Prerequisites:

1. **Speech-to-text:** install `faster-whisper` in the Python environment used to launch the application. Provide an existing *multilingual CTranslate2-converted Whisper model directory* containing model.bin. Set `TIHULU_WHISPER_MODEL` to that directory. **The app never downloads a model or runs ASR automatically.**
2. **Translation:** install `argostranslate` and the offline Argos language-model packages for the selected pair. Some language pairs may be routed through English if direct packages are missing; only installed translation paths can run. The app never calls a commercial cloud translation API.
3. **CPU:** local speech and translation workers can select the detected CPU. For CUDA on NVIDIA GPUs, faster-whisper/Argos also require compatible CUDA/cuDNN/CTranslate2 libraries; GPU presence alone does not prove readiness. These are verified when a model is loaded.
4. **NPU:** the CPU/GPU/NPU list detects Hailo accelerators by device node, including Raspberry Pi AI HAT+ 2 where drivers expose it. Hailo NPU hardware detection is NOT proof that a model/runtime for Whisper/Argos is available. The NPU choice is disabled until a tested Hailo-specific ASR/translation adapter is implemented. No silent fallback is described as NPU acceleration.

Example of isolated optional environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install faster-whisper argostranslate
# Obtain compatible multilingual model and Argos language packs explicitly while online.
export TIHULU_WHISPER_MODEL="$HOME/.local/share/tihulu-text-center/models/whisper-multilingual"
python3 -m textcenter serve
```

Use a distinct path under an optional external SSD for large AI models or recordings. Radio defaults to a local recordings folder and accepts operator-defined `TIHULU_RECORDINGS_DIR`; TV recordings are stored next to the application archive unless configured otherwise. Do not alter user recordings during a software update.

**Subtitle pipeline:** real incoming 32-kHz mono PCM is broken into 8-second pieces (plus model inference time), then optionally translated, and surfaced as a time-stamped original/translated caption timeline. This is *near-live*, not zero-latency simultaneous interpretation. On low-powered CPUs, results may lag or audio segments may be skipped rather than halting playback. Video codec quality and audio channel selection can differ between broadcasters; every hardware capture needs actual testing.

**CPU/GPU device selection is separate for ASR and translation.** `nvidia-smi` reports a named GPU when available; Linux CPU and detected Hailo device names are also shown. The operator can select Automatic, an installed CPU, or a validated CUDA GPU; separate local Argos worker processes keep per-session backend settings from interfering with one another.

**Saving data:** recording and original transcript are independently optional and default OFF. Translated subtitle storage requires original transcript storage. Even when saving is OFF, the UI may show transient in-memory caption cues during that active session only. Saving original cues enables after-the-fact offline translation into a newly chosen target language, with SRT/VTT export for either original or translated layer. The audio/video recording and subtitle transcript may be saved separately. No metadata or synthetic text substitutes for genuine speech inference.

## Practical constraints / hardware gates

- One Nooelec SDR cannot simultaneously serve Flight Radar at 1090 MHz and FM at 88–108 MHz. A single tuner cannot run separate RDS + audio readers at different configurations; the continuous FM pipeline has a **single audio capture**, with shared PCM for captions. Integration with live RDS metadata from the same tuner still needs multiplex fanout rather than opening another RTL-SDR session.
- DVB uses the separate Hauppauge tuner; do not confuse the pre-existing `/dev/dvb/adapter0/frontend0` with the ordered device.
- Original MP3 audio and MPEG-TS TV archive files are explicitly opt-in; playback never starts a recording by itself. Finite clip preview remains available separately.
- FM audio is MP3 and generally browser-compatible; DVB uses fragmented MP4 and MediaSource, which requires H.264/AAC support and FFmpeg encoder availability. Full codec/hardware acceleration/closed-caption acceptance remains to be tested on desktop and mobile browsers.
- 24h defensive timeout and per-recording disk quota apply. If disk fills, streams fail rather than corrupting the user's other recordings. No unattended background scanning, cloud calls, AI inference or recording is enabled by default.
- The standalone server stays loopback-only. To use on a phone through tihulu.lan, the Survival Kit must provide authenticated TLS reverse proxy, resource leasing and per-user playback/session authorization. **Do not directly expose port 8787.**

## GitHub validation checklist

CI verifies Python 3.11–3.13 and JavaScript syntax; units use synthetic radio PCM, fixture DVB channels, local cap­tion cues and fake device inventories. It does NOT verify real Nooelec reception, an unconnected Hauppauge, uninterrupted stream under load, EN/DE/TR Argos model availability, CUDA/cudNN performance, Hailo execution, MediaSource support on every phone or real translated TV captions. Run physical acceptance checks and update implementation states accordingly before merging into the Survival Kit release.
