# TIHULU Satellite Center — standalone companion v0.2.3

> **v0.2 cross-platform / GitHub Pages bridge:** This module now also has a
> static Pages client with local pairing, portable Windows/macOS/Raspberry Pi
> runtime, and one-line installers. Read [WEB_AND_INSTALL.md](WEB_AND_INSTALL.md).
> The static UI is staged on the same repository's dedicated **gh-pages** branch;
> a live website still depends on GitHub Pages deployment settings. Windows,
> macOS and Raspberry Pi hardware reception remains unverified.


This is the **new `satellite_center/` directory** intended to be placed at the root of `Tihulu/TIHULU-TEXT-CENTER`. It does **not** alter Text Center routes, UI, recordings or the Survival Kit. Integration can be decided later.

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
WebUSB is released on stop, visibility hide or page exit. Browser-only
Meteor LRPT imaging, ISS APRS text decoding and SSTV decoding are **not
implemented yet**; real raw IQ may be decoded later in external tools.

**The old local-companion application remains optional** for modes using
installed SatDump/multimon-ng and for scheduling while the browser tab is
closed but the companion runs. It is not the required path for the
browser-only capture mode. A physical Nooelec test is still pending.

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
- No RF transmission, no fabricated satellite detections or images, no all-band hidden background scans, no auto-deletion of raw recordings. Limits: 1 GiB per IQ file; max scheduled capture 480 sec; max manual capture 240 sec; 24 pending passes.
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
