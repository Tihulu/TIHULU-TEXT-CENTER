# TIHULU Satellite Center — Native Qt / Browser Feature Parity

Last source audit: 2026-11-07. Development branch: `feature/satellite-auto-discovery-integrated-2026-11-06` (PR #18). **Do not merge into `main` as an untested hardware release.**

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
| Three primary steps | Overview → Auto Schedule & Capture, Analyze Recordings, Extract / Save Results | Implemented, real Qt navigation |
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
| User protocol catalog | Up to 32 NORAD/24–1750 MHz/image/audio/text/video references, Qt editor, import/export same web JSON | Implemented as **unverified reference only** |
| Custom receiver/decoder execution | Custom saved profiles do not automatically start arbitrary hardware or unknown decoders | Intentionally limited for data integrity |
| CPU/GPU/NPU selection | Qt ISS Robot36 and native Auto reception compute menus offer Auto, CPU, CPU+GPU, CPU+NPU, CPU+GPU+NPU; capability resolver checks actual backend | UI/policy implemented; do not claim accelerated throughput without backend/device proof |
| Browser direct WebUSB/PWA lifecycle | Separate web-only capability; native desktop uses OS RTL-SDR tools instead | Different transport by design, not a missing native WebView |
| Google Play/Windows/macOS installers | Not supplied by the Linux native `.deb` | **Not yet native-release parity** |
| Physical Nooelec long capture / live ISS and Meteor | Requires user-owned SDR hardware and real pass tests | **Unverified** |

## Debian / Pop!_OS

Install the latest successful PR #18 **Satellite Center native Debian package** GitHub Actions artifact.
Run `sudo apt install ./tihulu-satellite-center_0.3.0~preview5_all.deb`,
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
