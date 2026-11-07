# TIHULU TV Center — Native Debian/Pi + Pages companion

**Status: experimental v0.1, untested on actual Raspberry Pi 5 and not a finished stable release.**

A standalone, native Qt Widgets + MPV DVB-T/T2 television frontend for **Debian, Ubuntu,
Pop!_OS COSMIC and 64-bit Raspberry Pi OS on Raspberry Pi 5**. The native receiver runs locally.
The GitHub Pages companion can request optional WebUSB permission for the specific Hauppauge
USB ID, but **does not yet implement a browser DVB-T2 tuner driver or live video decoder**.
Real TV, live captions, scan controls and Teletext use a token-free same-origin
local web companion, started on 127.0.0.1:8768 when the native desktop opens.
WebGPU/WebAssembly capability detection is included, but browser AI inference is not yet implemented.

The project lives beside the existing TEXT CENTER services. TV and offline AI workers
reuse the already implemented `textcenter.speech`, `textcenter.compute` and
`textcenter.transcripts` modules. Existing Flight Radar/readsb, Satellite Center,
NooElec NESDR and protected RTL-SDR allocations are not touched.

## Verified from the user's previous Linux tests (not retested by this new app)

- Hauppauge WinTV-soloHD USB `2040:8268`; `em28xx`, `Si2168-D60`, firmware
  `dvb-demod-si2168-d60-01.fw`; `/dev/dvb/adapter0`.
- Successful `dvbv5-scan` channel files: `~/tv-538-channels.conf` (ZDF/KiKA),
  `~/tv-586-channels.conf` (Phoenix/NDR), `~/tv-626-channels.conf` (RTL, often encrypted).
- Kaffeine sometimes embedded video only under `QT_QPA_PLATFORM=xcb`; libVLC had
  VDPAU allocation failures, AAC-LATM issues and significant UCB / TS continuity errors.
- KiKA Teletext subtitles actually displayed; ARTE Teletext page 100 was readable,
  but automatic subtitle selection and page 150 were unreliable.
- RF reception must be improved: this app cannot repair missing DVB frames.

## One-line installation

**Debian / Ubuntu / Pop!_OS / Raspberry Pi OS (ARM64)** — experimental development build.

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/feature/tv-center-native-teletext-asr-2026-11-07/tv_center/install.sh | bash
```

Git clone + local installer (same source):

```bash
git clone --depth 1 --branch feature/tv-center-native-teletext-asr-2026-11-07 https://github.com/Tihulu/TIHULU-TEXT-CENTER.git ~/tihulu-tv-dev && bash ~/tihulu-tv-dev/tv_center/install.sh --local
```

The script installs Debian packages including w-scan-cpp, builds an unsigned dev .deb and installs the native app. Review the script before running. Model downloads are never automatic.

## Kaffeine-style reception, scanning and playback UI (experimental)

The native desktop now uses a clearer **channel list → selected DVB source →
live scan → real MPEG-TS player** workflow. This is an original Qt Widgets
interface informed by Kaffeine's DVBv5 scan/source architecture, not a copy of
Kaffeine source code or visual assets.

- **Watch TV:** search channels by name/frequency and filter by all, favorites,
  television, radio or free-to-air. Favorites and included/excluded choices
  remain in the owner preferences file. Historical imports are explicitly
  unverified until a real scan or tune confirms them.
- **Source / channel scan:** select the real USB DVB adapter and delivery type,
  run a full w_scan_cpp sweep or explicitly select an existing local DVBv5
  regional frequency file (the same model of scan source used in Kaffeine).
  Both methods use the actual tuner; a tuning table is never presented as
  a discovered signal. Failure retains the prior successful channel list.
- **Live scan diagnostics:** the monitoring dialog shows only frequencies and
  lock/CNR/signal/UCB values reported by the real scanner, plus confirmed
  services. No fake progress percentage or invented station names.
- **Watch selected channel:** dvbv5-zap now receives a *single-service*
  temporary DVBv5 file selected by frequency and SERVICE_ID, so duplicate
  display names cannot silently tune the wrong multiplex. The file retains
  modulation and PLP parameters from the original scan. MPV input is
  explicitly MPEG-TS; PAT/PMT validation remains required.
- **Reception diagnostics:** distinct tuner/TS statuses and persistent
  playback errors, plus a one-click X11 compatible-renderer retry and
  bounded native dvbv5-zap/MPV log viewer. Settings and caption AI occupy
  a separate tab; the actual video area is larger.

**Hardware acceptance is still required.** A detected WinTV-soloHD is not
proof of DVB-T2 RF lock. If no transport packets arrive, verify the tuned
transmitter, antenna placement, signal strength, BER/UCB and whether Kaffeine
can lock the *same* multiplex on this USB dongle. No internet/DVB stream is
substituted for the local antenna.

## Country-aware full automatic scanning

Select Germany (DE) or Türkiye (TR), choose antenna (DVB-T/T2) or cable (DVB-C), then click **Scan all local frequencies**. The app runs w_scan_cpp for real frequency discovery followed by dvbv5-scan for service names/IDs, including radio and encrypted service discovery. The **Cancel running scan** button stops it. Earlier results are preserved if a new scan finds no channels. Previously saved 538/586/626 MHz entries remain labeled as historical imports until refreshed.

Reception depends on local transmitter availability, antenna quality, broadcaster standards and frontend compatibility. The country choice selects a search plan; it does not invent channels.


## Built-in Whisper + translator starter bundle

The **standard one-line installer now provisions the offline AI starter** in
addition to the native TV app (requires internet and available disk during
installation). It builds a user-owned CPU-only whisper.cpp runtime from a
verified upstream tag, downloads the SHA-256-verified multilingual **Whisper
Tiny ~78 MB**, creates an isolated Argos Python runtime, and installs
**German ↔ English** and **English ↔ Turkish** translator packs so DE↔TR can
work via English where the Argos runtime supports pivot translations.

After initial provisioning both engines operate offline. Caption processing
remains idle unless you choose Live transcription / Teletext fallback. The
built-in **Subtitles & AI → AI MODEL MARKET** includes a one-click
**Install / Repair complete starter bundle** action, Tiny/Small models,
individual translator language packs, model activation/removal, external SSD
storage and Auto/CPU/GPU/NPU *capability checks*. Detecting an NPU does not
prove inference compatibility. GPU/NPU are never silently required.

If first-time model installation cannot finish (network, disk, build tools,
PyPI or upstream packages), the TV app remains installed, and the Market
displays which pieces are missing. Retry with `tihulu-tv-center ai install`.
`tihulu-tv-center ai status` shows exact readiness. For a smaller
TV-only install run the installer with `--tv-only`; AI packages can always
be removed from the marketplace independently of TV or channel lists.

## Run native (development checkout)

Install distro dependencies (nothing in the install process is silently downloaded by the app):

```bash
sudo apt update
sudo apt install python3 python3-pyqt5 dvb-tools w-scan-cpp mpv ffmpeg psmisc
# In repository root:
python3 -m tv_center doctor
QT_QPA_PLATFORM=xcb python3 -m tv_center
```

On Raspberry Pi 5 use the 64-bit Raspberry Pi OS / Debian packages. Video output
may require a compatible X11/XWayland session. The default MPV hardware
decoder is OFF to avoid repeating Kaffeine's NVIDIA VDPAU failure; for Pi 5,
try `auto-safe` explicitly if installed GPU codecs are confirmed. The Pi 5's
real-world HEVC 1080p decode/transcoding and Whisper performance are **not verified**.

You can also build a Debian package using `bash tv_center/packaging/build-deb.sh`;
this creates an `Architecture: all` package. The architecture-neutral Python
package does not imply tested ARM64 video acceleration.

## Tune and scan

The application automatically lists existing `~/tv-*-channels.conf` files, so
your previously verified frequencies and channel list are reused without rescanning.
It runs `dvbv5-zap -a 0 -c ... -p -P -r "Channel name"`, reads only
`/dev/dvb/adapter0/dvr0`, and feeds the live MPEG transport stream to embedded MPV
using the DVB service ID. Other DVB owners (Kaffeine/Tvheadend) must be stopped first.

The **Scan with DVBv5 regional source file** action accepts an existing
local initial frequency table, runs the same real tuner via dvbv5-scan,
then atomically saves its results as
`~/.config/tihulu-tv-center/channels-DE-t.conf` (or the selected
country/delivery profile). Old scans remain intact when no services decode.
Country-aware full auto-scanning is implemented for DE/TR and DVB-T/T2 or DVB-C with
w-scan-cpp. EPG service indexing and hardware acceptance remain incomplete.

## Captions, Teletext and installable languages

Choose **Off**, **Broadcast Teletext**, **Live transcription**,
**Teletext first → ASR fallback**, or **Teletext page viewer**. Enter page
100–899 directly; ARTE/ARD commonly use 150, while ZDF captions may use 777.
The application captures only short (up to 12-second, max 24-MiB) temporary
MPEG-TS segments while a subtitle mode is enabled. FFmpeg with **libzvbi**
decodes actual broadcaster Teletext into text; page rendering is text-only
in this preview, not full colored Level 1 Teletext graphics.

For spoken transcription, the app needs a **locally installed multilingual**
`whisper.cpp` CLI and a user-selected GGML Whisper model. No model is bundled.
`textcenter.speech` may choose a supported local CPU/GPU backend; GPU/NPU
is never inferred just because a device is present. Chunk sizes and model
speed mean subtitles are delayed, not word-by-word zero-latency.
Translation is performed by existing offline Argos, with **Turkish, German,
English** selectable independently as source and target. Install
`argostranslate` in an environment that can import PyQt5 (e.g. a venv with
`--system-site-packages`) and use the **Install local .argosmodel** button.
Missing language pairs show a real error; no invented translations.

This experimental decoding path selects Teletext/audio streams using the selected
program's service ID when available, so neighboring multiplex services should
not be mistaken for the current channel. Real-stream PID changes, DVB subtitle
formats and audio mapping still require hardware acceptance testing.

## Web companion / GitHub Pages

The static site lives in `tv_center/web/`. On GitHub Pages it should be
published at `https://tihulu.github.io/TIHULU-TEXT-CENTER/tv_center/`
**after** the repo's Pages build includes that directory (do not replace
the existing TEXT CENTER, Flight Radar or Satellite pages).

The native desktop starts the local web companion on **127.0.0.1:8768**
automatically. Open **http://127.0.0.1:8768/** directly, or choose
**Open Local TV** on GitHub Pages. There is **no token or PIN to enter on
the same computer**. The browser uses the same-origin TV API; it is never
publicly exposed. The Pages site may only query the non-sensitive
`/api/health` endpoint for a connection hint,
and exposes real read-only status/captions plus an explicit Teletext page
request. Browser localhost/private-network protections may prevent the
connection. To access a Pi across the LAN, a separate authenticated TLS
reverse proxy with owner isolation is required; it is NOT bundled.

**Video playback in the public GitHub Pages companion is not implemented.**
WebUSB permission is only detection: raw DVB MPEG-TS/HEVC is not reliably supported
by ordinary browser media elements, nor can WebGPU substitute for the missing
DVB tuner driver. The experimental separate native LAN/HLS modules require
further UI integration, pairing/stream testing and Pi hardware validation
before they can be described as a supported remote TV solution.

## Acceptance criteria and current gaps

Unit tests run without RF hardware. Real DVB-T2 lock, service selection,
Teletext page extraction, French subtitles, subtitles on video, model
latency, Pi 5 acceleration, all scanners, EPG and the Pages local
connection must be verified on real devices before a stable release.

No background tuner activity, no auto RF or AI sessions, no network or
model download without user action, no automatic SDR preemption.

## Satellite dishes, custom channel lists and model marketplace (development preview)

**DVB-S/S2:** Select `Satellite dish · DVB-S/S2` with a real dedicated Linux DVB-S2
receiver. Türksat 42°E is available, plus Hot Bird 13°E, Astra 19.2°E and
Eutelsat 7°E profiles. Choose the right Universal LNB and optional DiSEqC port.
The existing Hauppauge WinTV-soloHD DVB-T2/C tuner cannot receive a dish.
**Never connect LNB coax to Raspberry Pi GPIO or any Pi port directly.**
Read [Satellite / Pi 5 connection guide](docs/SATELLITE_PI5_DISH.md).

**Full scan:** A live scan monitor shows real scanner logs, newly discovered
services and, where available, frontend lock/C/N/UCB. Progress is indeterminate
until the hardware scanner completes; unavailable signal readings are shown as
unavailable, never invented. TV/radio services, encrypted status, favorites,
inclusion/exclusion and manual reordering live in **Channel Manager**. On a
rescan, new channels await explicit review and previous selections survive.

**Settings → Model Market:** ASR and translation default OFF and are individually
optional. A curated multilingual Whisper Tiny/Small GGML list uses verified
SHA-256 integrity during explicit downloads; user-selected local models may
also be used. Argos DE/EN/TR pack catalog refresh/install/removal requires the
Argos Python runtime and explicit consent. Models can live on an external SSD.
Compute selection is Auto/CPU/GPU/NPU; only an actually compatible runtime
and installed model are treated as ready. Disabling the feature stops its
related worker but does not uninstall system-level inference libraries.

### Optional Argos runtime install / removal

The Settings model store also offers an explicit **Install Argos engine**
operation. This creates a user-owned virtual environment at
`~/.local/share/tihulu-tv-center/ai-runtime` and downloads the Python
`argostranslate` package from PyPI after confirmation. Restart TV Center to
switch the launcher to the optional runtime. The installer includes
`python3-venv` for this purpose; ordinary TV does not need the AI environment.
Use **Remove managed AI runtime** (from an instance started with system Python)
or close the app and run `tihulu-tv-center remove-runtime` to uninstall it.
Model files and TV channels stay untouched. This feature is opt-in and not
hardware-validated on Raspberry Pi 5.

### Install / remove optional whisper.cpp CPU engine

In **Settings → Model Market**, use **Install CPU Whisper engine (source build)**
to explicitly clone official `ggml-org/whisper.cpp` release `v1.9.5`, verify
the expected release commit prefix and compile a CPU-only `whisper-cli` in
`~/.local/share/tihulu-tv-center/whisper-runtime`. This is **not performed
by the one-line installer**. Requires `git`, `cmake`, and a C++ compiler;
install missing build tools yourself, for example
`sudo apt install git cmake g++`. Raspberry Pi 5 compilation and runtime
performance remain unverified. The **Remove managed Whisper engine** control
deletes the managed build and leaves downloaded Whisper models untouched.

GPU and NPU need their own compatible, independently installed backends and
models (CUDA faster-whisper, Intel OpenVINO or supported Hailo runtime); the
presence of an accelerator alone does not imply inference is ready.

## Troubleshooting: "Error in input stream" (MPV)

The native TV player now rewrites the MPEG-TS PAT for the selected DVB service,
including a valid CRC-32/MPEG-2, rather than forwarding a multiplex PAT that
advertises discarded programs. This prevents one possible player demux failure.
It does **not** cure physical DVB reception errors or guarantee that MPV will
decode every broadcaster's video/audio codec.

If the video still displays `Error in input stream`, check the new persistent
playback logs (the files are overwritten at each tune):

```bash
tail -n 80 ~/.cache/tihulu-tv-center/mpv.log
tail -n 60 ~/.cache/tihulu-tv-center/dvbv5-zap.log
tihulu-tv-center doctor
```

If MPV exits early, the UI points to its log rather than only reporting an
unexplained input-stream failure. If no TS packets arrive for 15 seconds, or
the saved `SERVICE_ID` cannot be found in PAT/PMT, the native app reports
that specific condition. Check lock/C/N/UCB in the signal monitor. A stable
DVB lock and near-zero **new** UCB errors are preferable to raw signal power.
Try `x11-compat` if the GPU/XWayland output fails.

The original `~/tv-*-channels.conf` files and Kaffeine settings are not
changed by this fix. Do not reset the antenna or rescan unless actual lock
or service information proves that is necessary.

## Browser TV functionality (November 2026 development preview)

The static GitHub Pages client now includes a fully opt-in `Browser AI Studio`
using multilingual `onnx-community/whisper-tiny` or `whisper-small` through
Transformers.js 3.8.1. It requests microphone or shared-tab audio (when the
browser exposes an audio track), processes approximately 10-second chunks,
performs local Whisper transcription using WebGPU or WASM fallback, and can
translate via additional local ONNX models. First use downloads model weights
from Hugging Face, with explicit confirmation. Model caching is managed by the
browser, and a cache-clearing control is provided. DE↔EN and TR→EN models are
published; EN→TR uses an experimental community export that may not work in
all browsers. Native Argos translation remains the reliable alternative.

**No WebUSB DVB driver:** WebUSB can request permission for Hauppauge USB
2040:8268 but cannot yet tune demodulators, load firmware or extract a TV
transport stream. WebGPU and WASM do not provide missing USB protocol
semantics. Native Linux DVB remains required for *real* TV tuning and scanning.

For real DVB viewing on a phone, explicitly enable **Allow phone / tablet on
trusted Wi-Fi** in the native Settings panel. The host shows a six-digit PIN
and a local `http://HOST:8769/` URL; navigate to that URL on the phone,
pair, then optionally enable the CPU-intensive **Share live H.264/AAC video**
checkbox. iPhone Safari can use HLS; Android typically needs hls.js.
The same authenticated mobile interface exposes scanned TV/radio channels,
favorites/inclusion/order, starting and cancelling a country/satellite scan,
real signal and scan logs, subtitle mode and Teletext. Native source files
and channel preferences are preserved when scans yield no services.

GitHub Pages now shows the same panels, but privileged native control remains
on the dedicated **token-free same-origin local TV app** at
`http://127.0.0.1:8768/`. Pages exposes a one-click link; its only remote
probe is non-sensitive `/api/health`. This avoids relying on fragile browser
Private Network Access workarounds and keeps arbitrary web sites from issuing
tuner commands. The local site can play explicitly enabled H.264/AAC HLS;
the public GitHub Pages copy cannot. Phones use the separately enabled
PIN-paired LAN app and never receive anonymous tuner access.
Do not forward port 8769 to the public Internet: HTTP pairing cookies and
live TV are not encrypted, and local Wi-Fi still requires care.

All above integrations are experimental and subject to real DVB tuner, browser,
codec, Pi 5 throughput and security acceptance testing before release.

## Direct WebUSB EM28178 transport laboratory

The **2040:8268 Hauppauge WinTV-soloHD** is mapped to
`EM28178_BOARD_PCTV_292E` with a **bulk USB transport** in the Linux kernel
`em28xx` driver. The new Pages tab implements actual WebUSB operations
for this exact VID/PID, with explicit permission and no device auto-opening:

- Inspect USB configurations, interfaces, alternates, endpoint type and size.
- Explicitly open a device and read the **EM28xx chip-ID register 0x0A**
  using a single vendor **IN** control transfer, as the Linux driver does.
- Explicitly attempt claiming the bulk **IN** endpoint at the current
  configuration/alternate 0. This may fail when Linux `em28xx` owns the
  interface; the browser deliberately **does not detach it** or reset USB.
- Optionally request **one** bounded bulk-IN transfer (max 16 KiB) and
  classify actual 188-byte MPEG-TS packets with a parser that checks
  sync, continuity, CRC32/MPEG-2, PAT service IDs, PMT and codec/PIDs.
- Load a user-selected existing `.ts` recording into the same
  in-browser analyzer, reading at most 2 MiB, without uploading it.
- Export a device/transport diagnostic JSON without USB serial numbers.

**THIS IS NOT YET A WORKING DIRECT WEBUSB DVB-T2 RECEIVER.** USB descriptors,
a chip-ID read and even a valid transport packet do not demonstrate
successful tuner configuration or RF reception. The following are still
unimplemented in WebUSB: EM28xx digital mode and GPIO sequencing, robust
I2C controller, Si2168 (including correctly licensed firmware) and Si2157
tuner initialization, delivery-system modulation setup, frequency and lock
monitoring, continuous packet acquisition, service discovery with full DVB
tables, A/V demux and HEVC/AAC playback. WebAssembly can help with
decoding/demultiplexing but cannot replace missing hardware controls.

Do not blacklist, unload or detach `em28xx` to run these browser tests.
On the user's Linux machine, native DVB via `/dev/dvb` remains the
safe, tested driver path. For browser-based real TV and scanning use the
opt-in native loopback bridge or PIN-paired LAN HLS stream.

Primary implementation references:
- https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/f4cdf7ca9a1fdcca413157df19753f388a5a224e/drivers/media/usb/em28xx/em28xx-cards.c
- https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/f4cdf7ca9a1fdcca413157df19753f388a5a224e/drivers/media/usb/em28xx/em28xx-dvb.c
- https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/e5c91aac491def6ab3f90c4cc246e3fcb0f8f058/drivers/media/usb/em28xx/em28xx-core.c


## Tokenless local web TV (current implementation)

**Start `tihulu-tv-center`, then visit `http://127.0.0.1:8768/`.**
The desktop starts a lightweight HTTP server automatically, only on
127.0.0.1. The local browser requires **no token, login or PIN**. It can
request native live channels, favorite/update lists, full RF scans,
Teletext/subtitle modes, and an optional HLS web player when a genuine
free-to-air broadcast is tuned. HLS is CPU intensive and must be
explicitly enabled by the user from the browser, never silently started.
A checkbox in the desktop UI can stop/re-enable the local server.

The public GitHub Pages URL remains useful for direct WebUSB hardware
diagnostics and browser-local WebGPU/WASM Whisper. It only tests
`/api/health` to show whether the local app is available, and links
to the local address. It never obtains a DVB control permission just
because an origin matches. Some browsers block cross-origin health
checks; clicking **Open Local TV** works without that probe.

**Security boundaries:** the local companion rejects invalid Host
headers (DNS-rebinding prevention), foreign Origin and cross-site
requests on all privileged endpoints. No wildcard CORS and no LAN
listener. The only CORS exception is the non-sensitive health check
for `https://tihulu.github.io`. The separate mobile/Pi LAN server
on port 8769 stays OFF by default and continues requiring an explicit
six-digit PIN pairing with a trusted Wi-Fi host. Do not port-forward
either port to the Internet.

The browser's independent WebUSB EM28178 experiment still lacks a
complete Si2168/Si2157 DVB-T2 tuner driver. Running the local Linux
bridge does not pretend that direct WebUSB video works.
