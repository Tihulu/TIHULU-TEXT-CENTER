## Browser-only direct FM SSTV WAV recording (2026-11-06)

The [public Satellite Center browser receiver](browser/index.html) now records **real FM-demodulated SSTV audio in WAV during actual RTL2832U WebUSB sampling**; no native companion is necessary on supported secure-origin Chromium/Brave/Chrome/Edge. Select the `ISS SSTV 437.550 MHz` receiver preset: the UI defaults to `Record FM-demodulated SSTV audio (.wav)` while keeping a separate `Record raw RF (.cu8)` option. Check both to retain the original RF for later reprocessing; uncheck both for level measurements only.

The WebUSB pipeline accepts genuine unsigned interleaved CU8 I/Q from `readSamples`, decimates with continuous stream state, FM-discriminates complex samples, removes carrier DC, emits real **48 kHz mono, signed 16-bit PCM** and writes an exact RIFF/WAV header with the final number of captured samples. It is **not** a raw-CU8 file renamed .wav. Short WAV clips are downloaded from bounded memory. WAV recordings exceeding the 16 MiB memory budget are streamed to a file selected through Chromium File System Access. When both CU8 and WAV require disk streaming, one explicit directory picker selects a folder for two separately written files. Up to 900 s can be requested within RF/disk browser limits. Closing or hiding the browser tab stops browser-only capture: this is not a background service or an unattended full-pass guarantee.

Both manual receiver start and selected pass schedule entries support WAV, CU8 or both; calendar editing preserves output options. Browser-only automated ISS SSTV pass scheduling now prefers WAV. The in-page **Decode last captured FM WAV** button hands the short WAV to the existing experimental Robot36 image decoder; a longer WAV saved on disk can be explicitly re-opened via `Satellite Images & Data → Real demodulated SSTV audio (WAV)`. The raw CU8 path remains available for full spectrum analysis. The web app never claims an ISS signal or a verified picture merely because it successfully saved a WAV; real Robot36 1200 Hz synchronization is still required.

**Reception limits:** 9–16 November 2026 ARISS Series 35 was announced at 437.550 MHz FM / Robot36. The web demodulator does not currently perform automatic Doppler tracking; at UHF the Doppler shift may affect decoding, especially near pass edges. Antenna suitability, device permissions, driver ownership and a genuine transmitting ISS pass remain mandatory. Firefox does not support direct WebUSB; use the native local companion for that browser.



# TIHULU Satellite Center 0.3.0 — NATIVE desktop application

**Primary Debian / Ubuntu / Pop!_OS program: Qt Widgets — NOT a website.**
Launching from the Applications menu or running `tihulu-satellite-center`
opens a genuine Qt5 desktop window with native select boxes, controls,
calendar, capture and analysis panes. **No embedded WebView, WebEngine,
Electron, localhost server or browser** is used by the desktop UI.
The previous browser/WebUSB workflow is preserved only as an optional,
**separate web application**. Historic browser/localhost sections below
describe that separate legacy workflow, not the installed desktop app.

Install the Debian package downloaded from GitHub Actions, then run:

```bash
sudo apt install ./tihulu-satellite-center_0.3.0~preview1_all.deb
tihulu-satellite-center
```

The app provides: native receiver diagnostics, explicit CelesTrak TLE
refresh and station pass prediction, manual 8–900s planned/direct IQ
captures, optional auto-missions, an editable automatic-job schedule and
24-hour recording calendar, local file imports, actual PNG/WAV/text
preview, CPU NumPy CU8 FFT/waterfall (fast sampled or full-file streaming),
optional SatDump image decoding of Meteor captures, and ZIP export of
**only genuine analysis outputs**, with source-provenance warnings.
All receiver/time/decoder behavior still depends on physical SDR and
installed native utilities. Installation never silently acquires USB,
downloads TLEs or starts a scheduled radio recording.

Native dependencies: Debian `python3-pyqt5`, `python3-numpy`,
`python3-skyfield`, `rtl-sdr` and `xdg-utils`. `qtwayland5`
is recommended so Pop!_OS/COSMIC can use native Wayland Qt5 windows,
with XWayland as a fallback if unavailable. Legacy `serve`
is strictly opt-in: `tihulu-satellite-center serve --port 8791`.
A native Qt window can open without any browser installed.

**Validation:** Debian 12 package install and headless Qt Widgets opening
are software checks, not evidence of real Nooelec RF/SSTV/Meteor reception.

---


### Debian / Pop!_OS — native, Firefox-compatible SDR application

On the local server's `/browser/index.html`, Calculate Passes → Schedule
offers native backend scheduling without Chromium WebUSB or the 128 MiB
memory cap. Native server independently rechecks local TLE/pass geometry,
allowlisted frequency and protocol, UTC start, disk budget and receiver
conflicts. The Iridium 1620 MHz preset is RF energy recording only;
no private messages or satellite identity are decoded.


The **preferred Linux desktop launcher** is now the local RTL-SDR receiver
(`tihulu-satellite-center` from the Debian package, or `tihulu-satellite`
from the user-local source installer), not the WebUSB-only website. It
serves the existing Satellite Center UI at `http://127.0.0.1:8791/`,
which opens in your normal browser **including Firefox**. RF capture
runs through native `rtl_sdr` / `rtl_fm` tools; it does **not** depend
on Firefox's missing File System Access or WebUSB APIs.

A native Debian `.deb` (source + shared UI + icons, using Debian's own
`python3-skyfield` and `rtl-sdr` packages) is built and smoke-tested
in GitHub Actions: `.github/workflows/satellite-debian-package.yml`.
Install the downloaded artifact with `sudo apt install ./tihulu-satellite-center_*.deb`.
Open **TIHULU Satellite Center** from Applications or run
`tihulu-satellite-center`. Use **Satellite Images & Data → Auto Schedule
& Capture** for native long Meteor image candidates, or the supported
native pass scheduler for other allowlisted receive-only modes.
Use `tihulu-satellite-center doctor` to inspect installed tools
without accessing RF. Actual USB opening needs udev/device permissions;
`rtl_test -t` should succeed. User-specific recordings stay under
`~/.local/share/tihulu-satellite-center/`. No background daemon or
hardware operation is enabled by installation.

For a non-root user-local install, `install/install.sh` now defaults
to this branch's native desktop launcher; the separate web-only icon
remains available for Chromium users. Debian package is marked preview
until a physical RTL-SDR pass capture and end-to-end image decode pass.

# TIHULU Satellite Center — standalone companion v0.2.3

## One-click Satellite Auto-Capture & Decode (2026-11-06 draft)

### Adjustable recording durations, timeline, result archive

- **Actual RF sample length (Calculate Passes):** Manual per-pass scheduling now uses an editable 1–900-second number field instead of a fixed 60-second dropdown. Secure-origin Chromium browsers with File System Access can save long I/Q directly to a user-selected CU8 file, streaming individual received blocks with a 2 GB byte ceiling. A 2.048 MS/s recording has a shorter cap than 1.024 MS/s. Permission to save is obtained while explicitly scheduling the pass; the browser must remain open and visible. Firefox/Safari and unsupported browsers need a native companion for long data. Neither a geometrical pass nor a saved file proves full image reception.

- User can choose a native 8–900 second clip (or leave blank for automatic pass-fitting). Browser WebUSB remains 8–60 seconds / 128 MiB because of foreground/memory limits. Large Meteor LRPT imaging requires the local disk-streamed SDR workflow; the actual downlink, sufficient antenna reception and SatDump decoding must still succeed.
- The shared calendar hides cancelled jobs while preserving them in native audit records. Every visible job is labeled with local start–end time, actual planned clip duration, media type and estimated disk size; long jobs continue across hourly rows. Pending native tasks can edit time, protocol and recording duration.
- Step 2 analyzes existing real files, Step 3 previews decoded image candidates, audio and text/data. **Save analyzed results as ZIP** packages actual output PNG/WAV/text/evidence JSON, manifest and warnings without uploading files. A safe ZIP limit of 256 MiB applies; raw IQ files are preserved separately for download and re-analysis, not embedded in ZIP. No decoding or source authenticity is fabricated.



On **Satellite Images & Data** (`browser/reception.html`) the user has three primary actions:

1. **Auto Schedule & Capture:** select images / public ISS APRS messages /
   both, choose GPS or manual ground station, and look ahead 12/24/48 h.
   On the local native companion this single explicit click calls
   `POST /api/auto-schedule`: it obtains missing TLEs on demand,
   predicts passes, validates installed RTL-SDR/decoder tools, arms at most
   six non-overlapping pass captures, and records actual RF on the established
   scheduler. Schedules are persisted. The optional service must stay running,
   and other programs such as readsb may prevent the device lease.
   On Pages/PWA the button opens the common WebUSB scheduler with the selected
   station transferred via **same-tab session storage, not the URL**; a
   pre-authorized receiver can be silently reopened at an eligible pass.
   New USB permissions must still be granted manually in a supported Chromium
   browser. Browser-only automation lasts while its tab remains open,
   foreground and awake. Each capture is max 60 s / 128 MiB; entire Meteor
   image downlinks frequently need the longer native workflow.
   **Coverage goals:** choose full-pass (default) or an explicit quick RF sample.
   Native auto-planning can now record up to 900 s / 2 GB of streamed CU8
   per geometric pass when disk space permits (1.024 MS/s ≈ 2.048 MB/s).
   Meteor LRPT uses IQ for later SatDump analysis; native ISS SSTV/voice
   selects compact real FM WAV (~96 KB/s), and APRS uses decoder text.
   Every armed job reports planned seconds, estimated bytes, data category
   and whether the predicted visible pass is fully covered or only sampled.
   If full image reception cannot fit the receiver/disk/window, All mode
   prefers another feasible operator-selected text/audio downlink on that
   same spacecraft. A full visible-window capture does not mean all data
   aboard a spacecraft has been obtained.

2. **Analyze Recordings:** native mode scans recent actual on-disk archive files
   and attempts compatible SatDump Meteor LRPT output, CRC-unverified raw
   public packet text viewing and browser local CU8 full-FFT/audio/Robot36
   candidate discovery; only files fetched from its own localhost service.
   On Pages/PWA select a real downloaded local recording via the file chooser
   because the website cannot silently read Downloads. The receiver page
   also offers Analyze Recordings for its last captured in-memory IQ file.

3. **Extract Results:** display actual candidate images only from line-sync-
   validated Robot36 or native SatDump output, allow user-controlled PNG/audio
   and evidence JSON export, and show real APRS/text archive contents with
   honest source labels. Unsupported modulation and packet decoders never
   manufacture text, imagery or protocol matches.

**Cancel Auto Missions:** clears only this application's auto-armed pending
jobs and requests Stop for its own current automatic capture; external SDR
programs, manual jobs and existing files are preserved. A separate Stop
Analysis cancels local analysis, not arbitrary SatDump OS processes.

**Current target set:** Meteor-M2-3 / M2-4 LRPT at a candidate 137.900 MHz,
ISS SSTV 437.550 MHz Robot36 (event-only), ISS packet APRS UHF 437.825 MHz
(current mode subject to ARISS) and optional ISS public FM audio. ISS video
HamTV at 2395 MHz, retired NOAA-15/18/19 APT, NASA Internet imagery, and
unverified CubeSat protocols are **not auto-armed** with the present NESDR.
Auto-planning never claims the transmitter is active or that reception succeeded.

This is an implemented but still **draft** cross-platform workflow: CI is
synthetic (not hardware proof). Remaining gates include real ISS/Meteor
receiving tests on Linux, Pi, Windows and macOS; browser-supported unattended
full-pass Meteor decoding, broader open-format decoders, proper per-image
quality/CRC validation and multi-day background service UX. See
[Issue #21](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/21)
and [platform parity contract](FEATURE_PARITY.md).


## Satellite Images & Data — common cross-platform tab (2026-11-06)

The separate **[Satellite Images & Data tab](browser/reception.html)** is now part
of the canonical browser/PWA bundle. The same exact HTML/JS/CSS is served by
GitHub Pages at `/satellite_center/browser/reception.html` and by the optional
native companion at `http://127.0.0.1:8791/browser/reception.html` on Linux,
Raspberry Pi OS, Windows, and macOS. The native dashboard also links to the tab.

- The mission picker distinguishes **ISS Robot36 SSTV pictures** (currently
  event-dependent, check [ARISS](https://www.ariss.org/upcoming-sstv-events.html)),
  **Meteor-M2-3/M2-4 LRPT Earth-weather imagery** (requires native SatDump for
  decoding), **ISS voice/APRS public messages**, **SatNOGS public transmitter
  references**, **NASA's online EPIC and ISS archives**, and **retired NOAA APT
  recording archives**. Frequencies are candidate receive-only targets, not
  proof of an active transmitter.
- Inside the tab, the same existing experimental `satellite_images_ui.mjs`
  decoder can open real user WAV/CU8 samples and **attempt** actual Robot36
  sync-validated reconstruction. Users can save only images produced from real
  decoded audio. The NASA gallery fetches images explicitly on click and
  credits the source; these are **online**, not SDR-received images.
- A local-only file viewer supports image, audio, video, text/JSON/TLE and CU8
  evidence files. Optional frequency and sample-rate inputs remain manual;
  export is metadata only, with **user-imported/unverified** provenance. CU8
  requires separate analysis and is not a JPEG/WAV.
- **Hauppauge WinTV-soloHD 01589:** DVB-T/T2/C TV tuner, **not** a raw satellite
  SDR or a Meteo/ISS digital decoder. Keep it in the TV module. The separate
  portable TV antenna may not be adequate at 137 MHz; a properly designed
  V-dipole/QFH/weather satellite antenna is preferred. The Nooelec NESDR
  SMArt v5 is the intended VHF/UHF SDR.
- **NOAA-15, NOAA-18, NOAA-19** were decommissioned in 2025; archived
  recordings only. No scheduled capture from those inactive transmitters.
- **No background scan, RF transmit, auto USB claim, fabricated decoded image,
  RF upload, guaranteed reception or unsupported cross-browser WebUSB claim.**
  Direct USB requires a compatible Chromium browser; native local tools must
  be installed for SatDump/APRS and unattended receiver jobs.

Pending: full single-screen native receiver controls within this separate
tab; optional SatDump LRPT output attachment to the browser gallery; live
SatNOGS transmitter catalog filtering, per-satellite capabilities and
hardware acceptance on real Windows/macOS/ARM devices. Follow
[the delivery issue](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/21)
before claiming these capabilities as complete.


> **v0.2 cross-platform / GitHub Pages bridge:** This module now also has a
> static Pages client with local pairing, portable Windows/macOS/Raspberry Pi
> runtime, and one-line installers. Read [WEB_AND_INSTALL.md](WEB_AND_INSTALL.md).
> The static UI is staged on the same repository's dedicated **gh-pages** branch;
> a live website still depends on GitHub Pages deployment settings. Windows,
> macOS and Raspberry Pi hardware reception remains unverified.


This is the **new `satellite_center/` directory** intended to be placed at the root of `Tihulu/TIHULU-TEXT-CENTER`. It does **not** alter Text Center routes, UI, recordings or the Survival Kit. Integration can be decided later.

## v0.15 — Satellite Images and source-attributed recordings (2026-11-06)

**Satellite Images** in the browser-only/Pages app offers two distinct,
non-interchangeable acquisition paths:

1. **Received with user's RTL-SDR:** actual ISS **Robot36 SSTV** events
   (frequency and image mode are event-dependent; consult the
   [ARISS schedule](https://www.ariss.org/upcoming-sstv-events.html)).
   Select a locally captured demodulated FM WAV, or experiment with
   recorded unsigned CU8 → narrowband FM → 1200 Hz sync detection →
   320×240 Robot36 conversion. A decoded image is only shown if there
   are repeated, aligned audio syncs. All such decodes are experimental
   candidates, never assured ISS origin. Raw frequency power/geometry
   does not count as a received image.
2. **Meteor-M2-3/M2-4 LRPT:** locally captured CU8 can be decoded with
   the optional native SatDump CLI. The installed companion supports
   72k/80k pipeline choices and displays only real SatDump PNG/JPEG
   outputs. No unsupported promise to decode Meteor LRPT in the
   browser-only page; the in-browser RF/FM/Robot36 path is SSTV only.
3. **Online original imagery:** NASA DSCOVR EPIC Earth photographs and
   historic ISS Earth photographs from the NASA Images archive are
   requested *on demand* via official NASA APIs. The online gallery
   labels actual source and acquisition timestamps and never presents
   external NASA downloads as if they were received via the local USB
   antenna. NASA API rate limits/CORS may require opening the official
   gallery. Official EUMETSAT and NOAA weather image viewers are also
   linked for international use.

**Filename convention:** `TIHULU_<SATELLITE-CANDIDATE>_<YYYYMMDDTHHMMSSZ>_<FREQUENCY>Hz[_<SAMPLE-RATE>SPS]_<IQ|SSTV|LRPT|...>.<ext>`.
UTC avoids Windows/macOS/Linux/Raspberry Pi timezone ambiguity. Unknown
attribution is explicitly `RF-UNATTRIBUTED`; observing a TLE pass is
not proof of the transmitted signal's identity. Existing legacy raw
recordings remain openable. The most recent browser I/Q recording
is available for local FFT analysis and optional experimental SSTV
decode, without uploading samples.

**Shared cross-platform UI:** The installed Python local companion
on Debian/Ubuntu/Pop!_OS, Raspberry Pi OS, Windows x64 and macOS Apple
Silicon now exposes **Open live map and Satellite Images**, loading the
exact same browser sources as GitHub Pages from its local
`/browser/index.html` route. The 1-second LIVE TLE view, Pause, Sky,
Earth map, and image gallery thus share one implementation.
The embedded web interface is only loaded when requested and releases
its own USB session on close. Two SDR frontends cannot own the same
physical dongle simultaneously. Page-only WebUSB requires a compatible
desktop Chromium-family browser; the desktop companion uses its native
RTL-SDR tools for its own capture workflows.

**Verification limits:** Core browser JS parses, UI controls are wired,
image-naming metadata round-trips, and synthetic 240-scan-line Robot36
audio yielded a 320×240 candidate. Cross-platform CI is defined for
Ubuntu x64/ARM, Windows, and macOS, but physical SSTV/LRPT, receiving
antennas, browser CORS and native hardware remain unverified until
tested on compatible real RF data. No fabricated space imagery.

## Primary: browser-only direct WebUSB (no local installer)

[Open the public Satellite Center](https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/)
or go directly to
[Browser-only WebUSB](https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/browser/).

On desktop Chrome/Edge/other suitable Chromium browsers, press **Choose
RTL-SDR (WebUSB)**, select the locally plugged-in Nooelec NESDR SMArt v5
RTL2832U receiver and grant the browser USB permission. There is no Python
process, `127.0.0.1` connection, pairing key or OS-level local software
installation required for the **web application itself**.

The browser source is under `satellite_center/browser/`. It dynamically
loads the version-pinned `@jtarrio/webrtlsdr@3.0.7` WebUSB library,
samples real USB I/Q data, plots relative digital signal level and optionally
downloads original CU8 records of up to 128 MiB. It uses `satellite.js@6.0.1`
for browser-side geometry, on-demand CelesTrak TLE downloads (with a
two-hour per-tab refresh limit) or manual local TLE upload, and a limited
in-memory browser-open pass scheduler. No third-party SDR process is stopped.

**Limits and non-promises:** Firefox and Safari lack WebUSB; Windows may
require WinUSB installation, Linux may require DVB kernel module release
or udev permissions, and those cannot be fixed solely via browser consent.
The hosted app cannot work with USB hardware plugged into a *different*
computer. The tab must be open and foreground to schedule reliably, and
WebUSB is released on stop, visibility hide or page exit. Browser-only Meteor LRPT imaging and ISS APRS packet decoding are **not
implemented**. Experimental Robot36 SSTV reconstruction from actual local
WAV/CU8 with line-sync checks is available inside Satellite Images & Data;
the captured file and correct antenna, active event and metadata are required.

**The old local-companion application remains optional** for modes using
installed SatDump/multimon-ng and for scheduling while the browser tab is
closed but the companion runs. It is not the required path for the
browser-only capture mode. A physical Nooelec test is still pending.

## Progressive local CU8 signal discovery (draft)

The separate Signal Intelligence panel now includes full-file spectrum analysis, energy candidate selection, AM/NFM audio previews, and explicit, attempted Robot36 image synchronization from sufficiently long recordings. All actual CU8 IQ remains in the user's browser. Packet protocols including APRS and Meteor LRPT require their own verified decoders; no false image/data extraction is claimed. See [SIGNAL_INTELLIGENCE.md](SIGNAL_INTELLIGENCE.md) for evidence requirements and platform limits. The current shared browser frontend has been mirrored to the gh-pages branch; public deployment and real RF hardware validation are separate acceptance steps.

## Earth & Sky Maps (v0.4, browser-only)

The direct GitHub Pages application includes an **interactive OpenStreetMap
Earth tracker** and an original **Heavens-Above-style azimuth/elevation sky
plot**. Both use the same local/browser-refreshed TLEs as the pass planner:

- Predicted ground subpoints, real-time sky angles and range for ISS, Meteor-M,
  amateur CubeSat candidates and Iridium NEXT; filter by type, local horizon
  and selected *candidate* SDR band.
- Select a satellite on the map, in the list or on the sky plot to inspect
  azimuth/elevation, pass details, TLE age and candidate receiver frequency.
  Selecting MHz **never** starts a capture.
- Chosen orbit segment (±45 minutes), estimated contact footprint, and a
  ±45/+90 minute simulation slider that never labels past/future positions
  as live radio detections.
- **OSM tiles load only after clicking Load OpenStreetMap**, follow the
  OSMF attribution, Referer, and no-prefetch/no-offline policies. Sky-chart
  drawing needs no map tile service.
- Official Heavens-Above comparisons and SatNOGS transmitter database
  links are optional external references, not embedded feeds or evidence of
  an active transmitter.
- Firefox can display the Earth/sky maps even though its WebUSB reception
  mode is unavailable. Chromium browsers can show maps and direct USB capture.

See [MAPS.md](MAPS.md) for functionality, map/privacy policies,
geometry-only indicators, and hardware limitations. These maps do not
decode spacecraft traffic, and current reception is **not proven** merely
because a satellite is above the horizon.

## What works (subject to installed tools and actual RF)

- Local, mobile-responsive browser UI at **`http://127.0.0.1:8791/`** (independent from Text Center's `8787`).
- Explicit-only HTTPS downloads of current CelesTrak TLE sets for ISS (NORAD 25544), Meteor M2-3 (57166), Meteor M2-4 (59051), a bounded amateur/CubeSat selection and **Iridium NEXT**. TLE data is cached for offline use. The app never silently fetches data in the background.
- Skyfield-propagated predicted rise/peak/set (AOS/LOS), live-on-request geometric overhead positions (azimuth/elevation), maximum elevation and opt-in recording **scheduler**. Region independent; presets for Köln, other German locations, İzmir, İstanbul, Ankara, Brussels, Paris, Rome and Stockholm, plus manual latitude/longitude anywhere in Germany, Türkiye, the EU or elsewhere. The schedule persists in the local data directory; it executes **only while this independent server remains running**. A pass is not a radio transmission guarantee.
- Safe fixed-band `rtl_power` RF surveys, `rtl_sdr` IQ recordings (`.cu8`), optional `rtl_fm`/`multimon-ng` ISS APRS text, and ISS SSTV WAV that can be decoded by an external tool such as QSSTV. Meteor-M IQ can be processed by installed SatDump with the selected LRPT pipeline; it reports the **actual** output files only. Iridium mode is **spectrum-only** and does **not** decode private satellite communications.
- No RF transmission, no fabricated satellite detections or images, no all-band hidden background scans, no auto-deletion of raw recordings. Limits: 2 GB per IQ file streamed to local disk; max scheduled capture 900 sec (15 min); max manual capture 240 sec; 24 pending passes. The local planner estimates free storage and whether a full predicted visibility window fits; it never claims to download all satellite data.
- Uses Text Center's **cooperative RTL-SDR lock** at `~/.local/share/tihulu-text-center/.receiver-locks/rtl_fm_rds.lock`, plus existing `/proc` receiver-conflict checks. Third-party apps which ignore locks can still interfere; never run welle.io/readsb concurrently with the single RTL-SDR. A dedicated second receiver is preferable for simultaneous operation.

## One-line GitHub install or update

**Linux / Pop!_OS / Ubuntu / Debian / Raspberry Pi OS / macOS Apple Silicon**
(Requires Git, Python 3.11+ and venv; additional SDR binaries as needed):

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/feature/satellite-center-standalone-2026-11-06/satellite_center/install/install.sh | bash
```

**Windows x64 PowerShell** (Python 3.11+; RTL-SDR drivers/tools separately):

```powershell
irm https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/feature/satellite-center-standalone-2026-11-06/satellite_center/install/install.ps1 | iex
```

The local dashboard is `http://127.0.0.1:8791/`. The hosted view is
`https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/`.
Copy the **local** 64-character pairing token into the hosted view;
never use your RTL-SDR USB serial or GitHub credentials. A physical USB dongle,
its antenna and installed RTL-SDR command-line tools are still needed for
real reception. See the
[main repository's setup guide](../docs/SATELLITE_CENTER_COMPANION.md) or
the feature-specific [WEB_AND_INSTALL.md](WEB_AND_INSTALL.md).

## Install / run (Pop!_OS / Ubuntu / Debian)

From the repository root, with Python 3.11+:

```bash
python3 -m venv .venv-satellite
. .venv-satellite/bin/activate
python -m pip install 'skyfield>=1.49,<2'
# rtl_power, rtl_sdr, rtl_fm typically come from the rtl-sdr distro package.
# Optional: multimon-ng, SatDump and QSSTV, installed separately for relevant modes.
python3 -m satellite_center doctor
python3 -m satellite_center serve --port 8791
```

Without `skyfield`, radio surveys and the UI can still start; **the pass calculation clearly returns an unavailable error**. Without the RTL-SDR tools or antenna, or if another receiver owns it, acquisition fails explicitly. With no TLE cache, use the **Download fresh orbit data** button when Internet is available. Offline cached TLE may be used for 7 days, with a caution after 2 days; orbital accuracy degrades as data ages.

The application listens **only on loopback**. Do not expose port 8791 to LAN, Internet or `tihulu.lan` until a separate authenticated, CSRF-protected and TLS-enabled reverse-proxy integration is completed. Browser location permissions are not used; selectable ground-station presets are only approximate. The user's reception location does not leave the device in the TLE HTTP requests.

## Required antennas / honest limits

| Source | Typical receive mode | Antenna note |
| --- | --- | --- |
| ISS 145.800 MHz (voice or scheduled SSTV) | FM / WAV / external SSTV decoder | VHF antenna; SSTV is *not always transmitting* |
| ISS 145.825 MHz (APRS) | FM 1200-baud AX.25 via `multimon-ng` | VHF antenna; frequency and operational mode subject to current ARISS status |
| ISS 437.800 MHz repeater | UHF energy survey | UHF antenna; intermittent; 437.825 MHz APRS tests may also occur |
| Meteor-M2-3/M2-4 | 137.900 MHz primary or 137.100 MHz alternate selectable for IQ; LRPT / SatDump | 137 MHz V-dipole / QFH, clear sky; downlink availability changes |
| Amateur/CubeSat candidates | published satellite-specific VHF/UHF channels | Frequency catalog is **not** automatically resolved; generic scans do not identify satellites |
| Iridium NEXT | 1616–1626.5 MHz relative RF spectrum **only** | L-band patch/helix and suitable LNA/filter; the bundled VHF whip is usually unsuitable |

At 1.6 GHz the R820T-based receiver is near the upper end of its useful band, and an RTL-SDR's narrow instantaneous bandwidth cannot monitor the entire Iridium allocation at once. `rtl_power` sweeps are brief samples; **missing a burst does not imply no satellite**. CelesTrak's Iridium ephemeris can show candidate overhead satellites; a spectrum peak alone cannot attribute a burst to a specific satellite.

Recorded ISS WAV is an RF audio capture, **not an image** until independently decoded. SatDump output is not guaranteed even if an IQ file exists. Never label these measurements as official weather alerts or distress messages. Receive only signals you may lawfully monitor in your jurisdiction; do not capture, distribute or decode non-public Iridium user communications. Germany, Türkiye and EU countries have differing interception/privacy rules.

## Test / integration boundaries

```bash
python3 -m unittest discover -s tests -p 'test_satellite*.py' -v
python3 -m compileall -q satellite_center
```

The project code is testable without a connected RTL-SDR; neither radio reception nor live satellite decoding has been hardware-validated by this build environment. **One original file/recording must survive a failed decode.** Device locking is cooperative, not a complete interprocess SDR lease broker. Future survival-kit integration should use its central receiver broker, authenticated portal, storage quota controls and external SSD locations.

Up-to-date radio operation should be checked against [ARISS status](https://www.ariss.org/current-status-of-iss-stations.html), [CelesTrak GP documentation](https://celestrak.org/NORAD/documentation/gp-data-formats.php) and [SatDump documentation](https://docs.satdump.org/).

## Applications / Dock icon and Firefox on Linux

Satellite Center includes a custom **radio V-dipole / RTL-SDR / satellite** icon in SVG plus 192×192 and 512×512 PNG sizes. The browser-only page now links a web manifest with `display: standalone`; on Chromium-based desktop browsers choose **Install this site as an app** from the address bar/browser menu, then pin the installed application in the COSMIC dock. This is the no-Python-helper path, but direct USB still requires a browser with WebUSB and appropriate OS USB permissions. PWA install availability/appearance depends on the browser and OS.

On **Firefox for Linux**, orbital predictions and manual TLE import work in the hosted page but **direct USB access does not**: Firefox does not expose `navigator.usb`. There is no `about:config` switch that makes native WebUSB work. To receive RF in Firefox, use the **optional** local companion at `http://127.0.0.1:8791/`, which requires the Python helper and `rtl-sdr` utilities. Third-party experimental extensions relying on locally installed Native Messaging hosts do not satisfy zero-install requirements.

The Linux one-line installer installs/updates two separate Applications entries with the custom icon:

- **TIHULU Satellite Center:** standalone Chromium WebUSB browser window (opens only the web frontend, no Python receiver).
- **TIHULU Satellite Center (Local Companion):** optional local decoding/scheduled recording server; opens localhost in the default browser, including Firefox.

On Pop!_OS/COSMIC, open Applications, right-click the Satellite Center entry and **Pin to Dock**. If an old generic gear icon remains pinned, unpin it and pin the new browser entry. A COSMIC/Chromium window-class issue can affect live dock grouping; the static Applications icon is explicitly installed to `~/.local/share/icons/hicolor/` and can be refreshed by running the installer again. Firefox's normal windows may still appear under the Firefox dock icon.
