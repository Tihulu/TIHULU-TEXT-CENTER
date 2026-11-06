# Satellite Center — standalone satellite SDR companion

**Independent of TIHULU Text Center and the Survival Kit.** The receiver backend
lives in the [Satellite Center draft feature branch](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/9).
The public web UI is published separately on the repository's `gh-pages` branch.

**Web (primary browser-only):** https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/

**Local USB service/dashboard:** http://127.0.0.1:8791/

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
