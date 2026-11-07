# TIHULU Satellite Center — Native Qt / Browser Feature Parity

Last source audit: 2026-11-07. Development branch: `feature/satellite-auto-discovery-integrated-2026-11-06` (PR #18). **Do not merge into `main` as an untested hardware release.**

## Preview8 · browser information architecture, native hardware transport

The **default installed desktop stays PyQt5 Qt Widgets**. The page hierarchy
now mirrors the browser's same numbered receiver-to-results sequence rather
than an unrelated engineering dashboard:

1. Automatic satellite recording (target, recording goal, auto seconds)
2. Choose USB receiver (named physical inventory, direct Connect/Test/Release)
3. Receive satellite-band samples (receiver profile, hardware mode, sample
   rate, duration, real CU8/WAV/BOTH, actual sample-level graph)
4. Satellite pass planner (city, local/online lookup and opt-in OS location,
   local TLE import, sort/family/media tags, individual schedule)
5. Scheduled reception + calendar and saved archives
6. Earth/Sky maps, OSM opt-in, time slider, selectable satellites and exports
7. Signal Intelligence and Satellite Images & Data (actual local decoders,
   NASA EPIC/ISS separate archival imagery, editable user protocols)

**Hardware presence is never called a successful connection.** A physical
`rtl_test` interface open followed by **actual nonempty CU8 bytes from
`rtl_sdr`** is the native Connect acceptance requirement. USB-only and
sample-only tests are available independently. Disconnect requests shutdown
of *this Station's* child processes, verifies their exit and its cooperative
receiver lock release, persists disabled state, and prevents scheduled RF
capture from restarting until another successful physical Connect. It does
not unpower USB, detach kernel drivers or kill unrelated receivers.

**Native-only difference:** No WebUSB, no browser/PWA memory quota, no
embedded site. IQ is written by OS `rtl_sdr` to local disk (1.024/2.048 MS/s,
strict 2 GB safety budget); when CU8+WAV is chosen, a CPU-derived **32-kHz**
FM WAV is saved *from that same physical CU8* after recording. This differs
technically from the web's real-time 48-kHz WAV writer and must not be
represented as byte-identical. One-second live IQ dBFS history comes from
genuine growing files; it is not calibrated signal strength or RF attribution.
Internet-only NASA imagery is fetched via bounded HTTPS requests on user
action; never labeled as an SDR downlink.

**Known gaps:** Native Qt Widgets replicate the web's information architecture
and essential UI/task controls but are **not an exact CSS/pixel-for-pixel DOM
render**, which would require embedding a browser (explicitly forbidden).
Some WebUSB-specific browser permissions, File System Access dialogs and PWA
lifecycle behaviors have no reason to exist in a native desktop. Exact
OrbitCanvas vs browser Leaflet gestures, optional GPS service and physical
Pop!_OS driver/access behavior require real user/host verification.

## Preview7 · native user-facing navigation parity

The web and native Qt editions still use independent technology stacks: no
Qt WebView, Electron, localhost site or browser USB API is used by the installed
desktop. The Qt primary navigation now exposes just **Home, Find satellites,
Maps & live, Auto receive, Recordings & results**. **More tools** retains
calendar, manual RF and custom profiles. Home presents three plain-language
actions. The recording workspace is split into **Choose recording → Analyze RF
→ Decode & save** rather than a single dense panel. Technical capture and map
overlays are collapsed by default and can be expanded manually.

Earth (offline by default) is the initial map view and the online OSM toggle
remains clearly visible. Pass-recording parameters are hidden until a specific
predicted pass is selected and the user presses *Plan recording for this pass*.
Automatic mission scheduling and manual pass actions give direct in-pane status.

**Acceptance:** headless Debian Qt smoke verifies guided navigation, three
analysis steps, map default, and hidden advanced panels, plus five screenshots
inside the native UI artifact. These are not a human usability study or proof
of live RF reception. Physical COSMIC Wayland acceptance remains pending.

## Main rule

The desktop application is **real PyQt5 Qt Widgets**. It does not open or embed HTML,
a localhost web page, Chromium, Electron, WebUSB, or a WebView. Map geometry
uses cached orbital elements and Skyfield; Earth/sky painting uses Qt/QPainter.
Bundled Natural Earth outlines display fully offline. **OSM raster tiles are optional,
online and explicitly enabled for the visible viewport only**; no prohibited bulk tile downloads.

A geometric pass or TLE dot is never evidence that the actual RF receiver has heard a
transmitter; no PNG/image/AX.25 message may be fabricated from orbit positions.
All real receiver operations require explicit operator action and USB ownership.

## Parity inventory

| Browser/PWA capability | Native Qt desktop implementation | Honest status |
|---|---|---|
| Browser-style seven-stage dashboard | Native Qt Home contains same seven numbered tasks with direct, functional capture/schedule/map/analysis links | Implemented in Qt, not pixel-identical HTML/CSS |
| Three primary steps | Overview → Auto Schedule & Capture, Analyze Recordings, Extract / Save Results | Implemented, real Qt navigation |
| Physical receiver open/test/disconnect | Named RTL-SDR/TV USB inventory, rtl_test access, bounded actual IQ test, persistent RF disarm and owned-process/lease release verification | Implemented in code; actual Nooelec acceptance pending |
| Website's CU8 + WAV choice | Native 1.024 / 2.048 MS/s CU8, native FM WAV or derived 32-kHz WAV from same capture, disk size caps | Implemented, WebUSB's 48-kHz live WAV differs |
| Online NASA official imagery | On-demand source-labeled EPIC & historical ISS archive, Qt local preview and source JSON sidecar | Implemented; Internet/API dependent |
| Live RF sample meter | Qt real growing-CU8 file tail relative dBFS meter, no synthetic/extra USB read | Implemented on active physical IQ recordings |
| Local TLE import and pass sorting | Local validated TLE cache import, name/elevation/duration/time sorting and family/media filtering | Implemented |
| Online worldwide cities and GPS | Explicit Open-Meteo name lookup and optional user-permitted QtPositioning source | Implemented conditionally; OS provider optional |
| City/location picker | Same bundled 8,084 Germany/Türkiye cities, custom latitude/longitude, QCompleter | Implemented offline |
| Orbital passes | Native Skyfield with cached public CelesTrak TLEs, start/LOS, max elevation, NORAD | Implemented; no RF verification |
| Image/audio/text/RF pass tags | Native media capability chips, search/filter, per-pass protocol and decoder requirements | Implemented as **candidates**, not promises |
| Earth map | QPainter offline Natural Earth world outlines, draggable map, zoom-at-cursor, fit visible TLE objects | Implemented |
| OpenStreetMap layer | Qt QNetworkAccessManager; optional HTTPS tiles for visible viewport, cache/attribution, no bulk fetching | Implemented, requires network + operator opt-in |
| Sky map | Native azimuth/elevation polar canvas with clickable TLE object pins | Implemented |
| Live tracking | 1 s TLE position updates only while Maps & Live is active; pause and ±45/90 min time slider | Implemented, **orbital prediction**, not ADS-B/RF |
| Orbital overlays | Predicted ±45 min selected or up to 12 visible paths, orbit footprint circles, horizon and family/medium filtering, follow and station center | Implemented; expensive paths throttled |
| Map exports | Rendered native map PNG, predicted orbit point/track/station GeoJSON with no-RF provenance | Implemented |
| Map→receiver integration | Select TLE pin, find next predicted pass, choose published receiver preset (no capture until click) | Implemented |
| Native 8–900 s capture | `rtl_sdr` direct CU8 to disk; `rtl_fm` actual WAV; `rtl_power` up to 180 s bounded | Implemented in code; actual USB/900 s acceptance pending |
| Image/data auto schedule | Native selected ISS/Meteor missions, 24h calendar, editable/cancellable pending jobs, disk+LOS guard | Implemented in code; transmission availability unknown |
| Full CU8 spectrum | NumPy bounded chunked sampled overview/full FFT, waterfall, peak/noise candidate discovery | Implemented, uncalibrated RF only |
| FM audio | Real CU8→PCM WAV, optional native QtMultimedia playback | Implemented; depends on real samples and optional system plugin |
| ISS SSTV | Actual saved FM WAV → Robot36 synchronization → PNG only on successful decode | Implemented conditional pipeline; physical ISS RF not yet verified |
| Meteor imagery | Actual 137 MHz IQ → externally installed SatDump decoder if usable | Supported conditionally; full successful LRPT/FEC/image not yet verified |
| Results | View imported PNG/WAV/TXT/JSON, emit spectrum PNG/CSV, selected file Save As, ZIP of real outputs with provenance | Implemented, size-limited |
| Local file format visibility | Recordings and decoded-results lists label raw CU8, PNG/JPEG/GIF/WEBP, WAV/MP3/OGG/FLAC, MP4/WebM/MOV and TXT/JSON/CSV/GeoJSON; selected audio/video plays only through installed native Qt Multimedia, image headers checked before attribution | Implemented conditionally; format signatures are not full decode or satellite proof |
| User protocol catalog | Up to 32 NORAD/24–1750 MHz/image/audio/text/video references, Qt editor, import/export same web JSON | Implemented as **unverified reference only** |
| Custom receiver/decoder execution | Custom saved profiles do not automatically start arbitrary hardware or unknown decoders | Intentionally limited for data integrity |
| CPU/GPU/NPU selection | Qt ISS Robot36 and native Auto reception compute menus offer Auto, CPU, CPU+GPU, CPU+NPU, CPU+GPU+NPU; capability resolver checks actual backend | UI/policy implemented; do not claim accelerated throughput without backend/device proof |
| Browser direct WebUSB/PWA lifecycle | Separate web-only capability; native desktop uses OS RTL-SDR tools instead | Different transport by design, not a missing native WebView |
| Google Play/Windows/macOS installers | Not supplied by the Linux native `.deb` | **Not yet native-release parity** |
| Physical Nooelec long capture / live ISS and Meteor | Requires user-owned SDR hardware and real pass tests | **Unverified** |

## Debian / Pop!_OS

Install the latest successful PR #18 **Satellite Center native Debian package** GitHub Actions artifact.
Run `sudo apt install ./tihulu-satellite-center_0.3.0~preview8_all.deb`,
then open **TIHULU Satellite Center (System)** from COSMIC's app menu.
It starts the Qt window directly. Only explicit `tihulu-satellite-center serve`
runs the old optional HTTP compatibility server. If the older user-local
Local/PWA shortcuts appear, preview `tihulu-satellite-center cleanup-shortcuts`;
then use `--apply` only after reviewing which exact per-user shortcuts it
will back up. All RF files, browser profiles and other TIHULU applications are preserved.

## Verification boundaries

Portable CI tests Python/Node app logic on Ubuntu x64/ARM64, Windows and macOS
where supported; the Debian 12 CI installs the real `.deb`, launches Qt in
offscreen mode and checks GUI map/file controls without hardware. No CI action
simulates an actual valid SSTV image, RF packet provenance or a physical
antenna-to-WAV/PNG reception. Real Pop!_OS COSMIC Wayland, USB permissions,
sustained 900-second write throughput and SatDump acceptance remain the
release checklist. PR remains Draft; `main` stays unchanged.
