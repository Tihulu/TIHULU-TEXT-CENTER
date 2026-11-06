# Satellite Center — standalone satellite SDR companion

**Independent of TIHULU Text Center and the Survival Kit.** The receiver backend
lives in the [Satellite Center draft feature branch](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/9).
The public web UI is published separately on the repository's `gh-pages` branch.

**Web (primary browser-only):** https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/

**Local USB service/dashboard:** http://127.0.0.1:8791/

## Choose your ground station: GPS, offline city search or custom coordinates

In the browser-only Satellite Center under **3 · Satellite pass planner**:

- **Search as you type:** a bundled offline database includes 7,104
  German and 980 Turkish cities/towns (8,084 records). Suggestions show
  region and country, so you can distinguish similarly named places.
  Accents are optional: `koln` can find Köln, and `izmir` can find İzmir.
  The static city database does not require an external API or key.
- **Use device location (GPS / Wi-Fi):** asks for browser location permission
  *only when pressed*. Firefox can use this Geolocation API too, even
  though its browser does not support WebUSB radio reception. Browser
  locations can be coarse and have an estimated accuracy radius.
- **Search worldwide online:** explicitly consults Open-Meteo's
  GeoNames-backed Geocoding API, and shows candidate results for user
  confirmation. Online suggestions *while typing* are separately opt-in
  and disabled by default; only search text is sent, not your GPS
  coordinates. Free API usage is non-commercial.
- **Custom coordinates:** directly enter any latitude/longitude in
  world bounds. No city, browser location permission or Internet
  connection is required.

Changing station invalidates old predicted pass results. Press
**Calculate passes** again to recalculate for the new observer; Earth/Sky
maps also use the same station location. Nothing triggers an SDR capture
automatically. Data: [GeoNames-derived DE/TR directory](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/feature/satellite-center-standalone-2026-11-06/satellite_center/browser/CITY_DATA_LICENSE.md)
under ODbL 1.0, and [Open-Meteo](https://open-meteo.com/en/docs/geocoding-api)
for optional worldwide lookup.


## Satellite Images on GitHub Pages and all installed platforms (v15)

**In GitHub Pages:** open **7 · Satellite Images**. You can explicitly
request official **NASA DSCOVR EPIC** full-disk Earth images or NASA's
historical **ISS Earth photography**. The page labels source/observation
time and is not pretending to receive these images over USB. NASA's
CORS/rate-limit policies may prevent image downloads; an official
source link remains available. Official **EUMETSAT**, **NOAA GOES**
and **NASA Worldview** satellite-imagery viewers are linked for
Germany, Türkiye and worldwide interest.

**Images actually decoded from your antenna:** during an active
ARISS SSTV transmission, an antenna and compatible receiver can record
a 36-second Robot36 session. After suitable narrowband-FM demodulation,
the browser has an experimental Robot36 audio/WAV image decoder. It can
also attempt to convert actual CU8 SDR samples to FM audio first,
then decode Robot36 on a user click; no image is fabricated without
a detected repeating synchronization train. Current ARISS SSTV
frequency and mode must always be checked against the dated event:
some 2026 events used **437.550 MHz Robot36**, while **145.800 MHz**
is not an always-on SSTV image channel.

For **Meteor-M2-3/M2-4**, collect valid 137 MHz LRPT baseband IQ and
choose **Decode Meteor LRPT 72k / 80k with SatDump** in the native
companion (requires SatDump installed separately). Only real SatDump
output PNG/JPEG is saved and displayed. This is not decoded inside
a standalone Pages-only WebUSB tab. Photos from other tools can be
imported as **user-supplied** and are not implicitly verified.

**Saved capture filename:** e.g.,
`TIHULU_ISS-SSTV-CANDIDATE_20261106T101500Z_437550000Hz_1024000SPS_IQ.cu8`
or actual decoder output
`TIHULU_METEOR-M2-4-CANDIDATE_20261106T101500Z_137900000Hz_LRPT-IMAGE-01.png`.
`CANDIDATE` is intentional: TLE pass and tuning are not proof of a
spacecraft's transmitted signal.

**Same code across platforms:** the source-branch native companion
on Debian, Ubuntu, Pop!_OS, Raspberry Pi OS, macOS Apple Silicon and
Windows x64 now provides **Open live map and Satellite Images**,
embedding the same `/browser/index.html` JS source as GitHub Pages.
That includes the 1-second LIVE clock, Pause, Sky, Earth, photo gallery
and local CU8 FFT tools. The iframe starts on user request, not at
companion startup, and it must not open an RTL-SDR simultaneously with
the native receive process. Existing local installations need to be
updated from the source branch. Cross-platform CI is synthetic; real
radio SSTV/LRPT reception and platform-specific hardware compatibility
are not guaranteed until physically tested.

## Continuous live satellite animation (browser v14)

Press **Now / live** in the Earth/Sky tracking view to propagate the
loaded satellite TLE orbital geometry against the real wall clock once
per second. Both OpenStreetMap ground markers and the local world/sky
plots update while the tab is visible. Orbital tracks spanning ±45 minutes
are recalculated about every 15 seconds, but the satellite markers and
coverage positions move each second. This animation uses cached TLEs,
does not poll CelesTrak every second, and does **not** access WebUSB
or capture RF.

**Pause** freezes the displayed time. Dragging the time slider shows
a frozen predicted snapshot at the selected relative time. Press
**Now / live** again to return immediately to actual time and resume.
**Follow selected satellite while LIVE** optionally pans the map to
the chosen spacecraft; it is off by default. When the browser tab
is hidden, live drawing stops; when the tab becomes visible again,
the display jumps to the current wall clock (no replay/backlog).
Closing the page clears the clock timer. TLE positions, tracks,
and coverage remain predicted geometry rather than observed RF signals.

Regression tests for this mode and incremental Leaflet map updates
are in `tests/test_satellite_live_clock.mjs`; changes are developed
in [PR #9](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/9).

## Satellite overlay maps and CU8 analysis (browser-only v13)

From the Earth map use **Orbit tracks → All tracked satellites** to see
each loaded satellite's predicted ±45-minute ground path. Switch
**Coverage circles → Selected satellite** to view the approximate
minimum-elevation region, or choose All / Off. Use **Show all satellites**
to fit the orbit catalog or **Focus selected satellite** to zoom to
its ground subpoint. A satellite can appear on a global map while below
the observer's horizon, and none of these traces implies reception.

The new **6 · CU8 I/Q analysis** section performs local-only complex
FFT (2048 points), sampled waterfall, relative digital-level time
history and file statistics. It can automatically inspect the latest
browser raw capture or import a prior `.cu8` from your computer and
export the report as JSON, all without local software or uploading
IQ data. To avoid large RAM usage it reads up to 32 scattered 4096-byte
blocks rather than the entire file. Raw CU8 does not embed rate or
center-frequency metadata. The user must confirm them unless they are
available from the TIHULU filename format.

This is an uncalibrated RF sample-level analysis, not Meteor LRPT image
decoding, SSTV/APRS packet decoding, Iridium private communications or
evidence that any named satellite was received. An external decoder
remains necessary for those separately supported protocols.

## Updated Earth map, sorting and scheduled RF analysis (browser-only)

- If the OSM street tiles remain blank in Brave/Chromium, select
  **Base map → World outlines**. The app automatically tries a
  **bundled public-domain Natural Earth** land-basemap after multiple tile
  errors or nine seconds without a loaded tile. Use **Load / retry
  OpenStreetMap** for a fresh attempt. This is an approximate world
  outline, not detailed street imagery. The map keeps satellite/station
  markers, predicted tracks and coverage even when external OSM tiles fail.
  OSM requires a valid Referer from the public site and can block
  third-party clients, while Brave Shields/network settings may also
  prevent loading. The site does not silently bypass browser protections.
- In **Satellite pass planner**, use **Sort potential passes → Soonest
  date/time first** or **Latest / farthest date first**. You can also
  sort by elevation, duration, name, and satellite family. The app
  retains all computed passes before display pagination, avoiding a
  misleading "latest" order from only the first 80 results. The
  map-side satellite list has its own **Next pass · soonest/latest**
  and near/far distance sorting.
- **Schedule / configure timed RF analysis** on any computed pass opens
  an explicit form for local date/hour/minute, receive-only frequency,
  duration (5–60 s), sample rate and optional raw CU8 file download.
  Confirming creates an in-memory job. The app releases an idle USB
  receiver while waiting; at the chosen minute it tries to reopen
  a **previously permitted** RTL2832U using WebUSB without a new
  permission dialog.
- **Check scheduled-scan readiness** is read-only; it reports browser
  visibility, permission grant and optional screen wake lock. Keep the
  browser tab visible and the computer awake. The browser cannot
  guarantee execution while sleeping, hidden or closed. Any missed or
  blocked scan gets an explicit status; a blocked job can be retried
  within its original pass.
- After actual USB sampling, the job reports raw byte count, number of
  measured blocks and relative digital minimum/average/maximum/variation.
  This is **not calibrated RF power, confirmed satellite identity or
  decoding of Meteor images/APRS/SSTV**. Browser downloads can be
  blocked, so the most recent raw file may be downloaded again manually.
- Changing your observer via GPS, city search or manual coordinates
  invalidates prior predictions **and cancels future armed jobs** for
  the previous station. Recalculate and confirm new times.

The scheduled time uses the **computer/browser timezone**, not
necessarily the selected ground station country's local timezone.
Actual SDR reception and unattended/browser-closed scheduling still
require hardware validation or the optional local companion,
respectively. Source and regression tests are in
[PR #9](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/9).

## Earth and sky tracking maps (new)

The public [Satellite Center browser app](https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/browser/)
now shows **OpenStreetMap ground tracks** and a **Heavens-Above-style
sky plot** for the selected observing location. Satellite dots represent
SGP4 orbital predictions from CelesTrak TLEs, **not** confirmed RTL-SDR
detections or successful weather-image reception. Filter by ISS, Meteor-M,
CubeSat and Iridium NEXT, visible elevation, or matching candidate
receiver band; select one for azimuth, elevation, approximate coverage
footprint and a safe SDR tune preset.

OSM tiles are user-initiated and attributed to OpenStreetMap contributors;
the browser sends the normal public site origin and visible map tile
requests to OSM. The sky plot does not use a third-party map service.
Heavens-Above and SatNOGS transmitter information are linked as
external references. Firefox can use both maps (but not direct WebUSB
RTL-SDR reception). Future/past slider positions are simulated.

The standalone developer documentation lives at
[Satellite Center MAPS.md](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/feature/satellite-center-standalone-2026-11-06/satellite_center/MAPS.md).

## Browser-only mode — no local app required (experimental)

**[Open Satellite Center in the browser](https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/)**.
The primary Pages link now redirects to its native
[Browser-only WebUSB view](https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/browser/).
The previous local-companion view remains available as an
[optional advanced mode](https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/companion/).

On **desktop Chrome, Edge, Brave and compatible Chromium browsers**, plug in the
Nooelec NESDR SMArt v5 RTL2832U dongle and attach a suitable antenna, open
the HTTPS page, then click **Choose RTL-SDR (WebUSB)**. Approve the USB device
permission. No Python, localhost bridge or pairing token is involved.

Current implemented browser capabilities:
- Request WebUSB permission and tune an RTL2832U/R820T-family receiver
  via a version-pinned open-source JavaScript driver when the OS permits it.
- Select an ISS, Meteor-M, CubeSat survey or Iridium L-band preset;
  collect actual raw USB IQ sample bytes, plot **relative digital sample level**
  (not dBm) and optionally save a bounded CU8 file locally (128 MiB max).
- Import TLE text or request CelesTrak HTTPS source lists and calculate
  geometric pass windows using version-pinned satellite.js in the browser.
  Internet sources may block CORS, so a local TLE file import is supported.
- Optionally arm one tab-open, user-approved pass capture while the page stays
  in the foreground and the device remains connected. Closing or hiding the
  browser ends receiver capture; Stop explicitly calls the WebUSB close method.

**Not yet available browser-only:** in-page Meteor/SSTV images or APRS text
decoding; closed-tab/passive background reception, scheduled execution after
browser exit, and automatic system-level USB driver/permission changes.
The old companion still offers optional external decoder integration and
longer-lived scheduled operation while its service runs.

**Important:** WebUSB cannot make all OS and browser combinations equally
capable. Firefox/Safari have no WebUSB; Windows may require WinUSB (Zadig)
set up for the RTL-SDR (do not change Hauppauge drivers); Linux can require
kernel-DVB driver release or udev permissions. Browser JS dependencies are
downloaded over HTTPS when the app loads. Hardware acceptance remains pending.
WebUSB driver documentation:
https://github.com/jtarrio/webrtlsdr

## What the satellite app does

- Predict potential ISS, Meteor-M, amateur CubeSat and Iridium NEXT passes
  using cached or operator-refreshed CelesTrak orbit data, with observer
  coordinates anywhere in Europe, Germany, Türkiye or elsewhere.
- Scan allowed RF bands manually using a local RTL-SDR; save bounded raw I/Q,
  ISS APRS text if `multimon-ng` is available, or FM/WAV for external SSTV
  decoder tools.
- Use installed SatDump to try converting real Meteor-M LRPT captures into
  images. Images only appear after an actual successful decoder run.
- Schedule opted-in passes while the local receiver companion remains running.
  An orbital pass is not proof of a transmission or received data.
- Track Iridium satellite positions and relative RF energy only. This does
  not decode private user traffic, authenticate Iridium transmissions or
  identify an individual satellite from an energy peak.
- Release Satellite Center's own SDR subprocesses when stopped or closed.
  It never kills `readsb`, Gqrx or other independent SDR applications.

## Optional companion install / update — ONE LINE

Run the installer as your **normal user**, after reviewing its source. The
installer clones/updates the feature branch under your home directory,
creates a Python virtual environment and installs the Skyfield orbital
library. It **does not** secretly install SDR drivers, start captures, or
enable a background network listener.

### Linux: Debian, Ubuntu, Pop!_OS; Raspberry Pi OS (ARM32/ARM64)

Requires `git`, Python 3.11+ and `python3-venv`.

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/feature/satellite-center-standalone-2026-11-06/satellite_center/install/install.sh | bash
```

Launch from Applications (**TIHULU Satellite Center**) or run:

```bash
~/.local/bin/tihulu-satellite
```

For radio hardware tools (Debian/Ubuntu/Pop!_OS/Raspberry Pi OS), install
separately:

```bash
sudo apt install rtl-sdr
```

This is a recommended explicit step, **not** a hidden dependency installed
automatically. If `readsb` is using the dongle, close/stop it manually
*only when you want to pause Flight Radar*. Satellite Center will not
preempt it. If Linux driver/udev permissions prevent opening the USB
receiver, review the OS and hardware driver setup.

### macOS: Apple Silicon (M1/M2/M3/M4) or Intel

With `git`, Python 3.11+ and `venv`, the same Bash one-liner works.
The installer creates `~/Applications/TIHULU Satellite Center.command`.
Install SDR command-line utilities separately if required, for example
`brew install librtlsdr`. A native `.app` bundle is **not** produced.

### Windows 10/11 x64 (PowerShell)

Requires Python 3.11+ available via `py` or `python`.

```powershell
irm https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/feature/satellite-center-standalone-2026-11-06/satellite_center/install/install.ps1 | iex
```

Open **TIHULU Satellite Center** via the Start menu. Windows RTL-SDR
binaries on PATH and a compatible WinUSB driver may be required for USB
access; the installer never changes drivers automatically. A standalone
signed `.exe` is not yet provided.

The current installer links to a **draft development branch**, not a stable
numbered release. If that branch is deleted, these direct URLs will need
to be replaced with a release/tag or the eventual `main` location.

## Connect USB SDR from GitHub Pages

1. Insert the **Nooelec NESDR SMArt v5** RTL-SDR into the computer's USB port.
   Connect a suitable RF antenna to the dongle's SMA antenna input.
2. Start the local companion, open `http://127.0.0.1:8791/`.
3. On the **local** page choose **Reveal GitHub Pages pairing token**.
   This is a secret **64-character hexadecimal token**, not the dongle's
   serial number, GitHub password or an antenna identifier.
4. Visit the hosted Satellite Center page on the **same computer**; paste
   the pairing token and choose **Connect to 127.0.0.1:8791**.
5. Choose **Test USB receiver (temporary access)**. This temporarily uses
   `rtl_test` to confirm receiver opening and releases it afterward;
   it does **not** prove that satellites or radio signals were detected.

For Meteor-M weather downlinks, consider a 137 MHz V-dipole or QFH antenna.
For ISS VHF signals, use an antenna suitable for about 145 MHz. Iridium
L-band around 1.6 GHz generally needs its own properly matched antenna,
often with a suitable filter/LNA. The bundled telescopic antenna is not
equally suitable for all these services.

### About Amazon ASIN B0152XLPFS

The linked **Hauppauge WinTV-soloHD 01589** is a DVB-T/T2/C television
receiver and belongs to the *TV/DVB* capability of Text Center. It is **not**
a replacement satellite SDR, not DVB-S/S2, and does not receive ISS/Meteor
or Iridium data just because it connects via USB.

## Safety and limits

- **GitHub Pages does not itself talk to USB.** Local helper is required.
- Receiver lock prevents cooperative Text Center conflicts, and known
  Linux third-party SDR process conflicts (including readsb) are rejected.
  It cannot guarantee all unrelated SDR applications will respect the lock.
- Closing the browser tab stops an owned *manual* scan; explicitly scheduled
  scans may continue while the local helper stays running. **Quit companion
  & release SDR** also stops Satellite Center's own RF child processes.
- Scheduled captures require a running local helper, no autostart daemon is
  installed by default. A phone's `localhost` is the phone, not the
  USB-connected PC. Safari and other browsers may limit cross-origin
  HTTPS-to-HTTP loopback access; the local dashboard remains available.
- No real Nooelec, Windows, macOS ARM or Raspberry Pi satellite reception
  has been certified by automated tests. Hardware behavior must be
  validated on the target device.

For implementation, current test status and open issues see
[PR #9](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/9)
and [Satellite Center WEB_AND_INSTALL.md on the feature branch](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/feature/satellite-center-standalone-2026-11-06/satellite_center/WEB_AND_INSTALL.md).

## Applications / Dock icon and Firefox on Linux

Satellite Center includes a custom **radio V-dipole / RTL-SDR / satellite** icon in SVG plus 192×192 and 512×512 PNG sizes. The browser-only page now links a web manifest with `display: standalone`; on Chromium-based desktop browsers choose **Install this site as an app** from the address bar/browser menu, then pin the installed application in the COSMIC dock. This is the no-Python-helper path, but direct USB still requires a browser with WebUSB and appropriate OS USB permissions. PWA install availability/appearance depends on the browser and OS.

On **Firefox for Linux**, orbital predictions and manual TLE import work in the hosted page but **direct USB access does not**: Firefox does not expose `navigator.usb`. There is no `about:config` switch that makes native WebUSB work. To receive RF in Firefox, use the **optional** local companion at `http://127.0.0.1:8791/`, which requires the Python helper and `rtl-sdr` utilities. Third-party experimental extensions relying on locally installed Native Messaging hosts do not satisfy zero-install requirements.

The Linux one-line installer installs/updates two separate Applications entries with the custom icon:

- **TIHULU Satellite Center:** standalone Chromium WebUSB browser window (opens only the web frontend, no Python receiver).
- **TIHULU Satellite Center (Local Companion):** optional local decoding/scheduled recording server; opens localhost in the default browser, including Firefox.

On Pop!_OS/COSMIC, open Applications, right-click the Satellite Center entry and **Pin to Dock**. If an old generic gear icon remains pinned, unpin it and pin the new browser entry. A COSMIC/Chromium window-class issue can affect live dock grouping; the static Applications icon is explicitly installed to `~/.local/share/icons/hicolor/` and can be refreshed by running the installer again. Firefox's normal windows may still appear under the Firefox dock icon.
