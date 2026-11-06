# TIHULU Satellite Center — standalone companion v0.1

This is the **new `satellite_center/` directory** intended to be placed at the root of `Tihulu/TIHULU-TEXT-CENTER`. It does **not** alter Text Center routes, UI, recordings or the Survival Kit. Integration can be decided later.

## What works (subject to installed tools and actual RF)

- Local, mobile-responsive browser UI at **`http://127.0.0.1:8791/`** (independent from Text Center's `8787`).
- Explicit-only HTTPS downloads of current CelesTrak TLE sets for ISS (NORAD 25544), Meteor M2-3 (57166), Meteor M2-4 (59051), a bounded amateur/CubeSat selection and **Iridium NEXT**. TLE data is cached for offline use. The app never silently fetches data in the background.
- Skyfield-propagated predicted rise/peak/set (AOS/LOS), maximum elevation and opt-in recording **scheduler**. Region independent; presets for Köln, other German locations, İzmir, İstanbul, Ankara, Brussels, Paris, Rome and Stockholm. The schedule persists in the local data directory; it executes **only while this independent server remains running**. A pass is not a radio transmission guarantee.
- Safe fixed-band `rtl_power` RF surveys, `rtl_sdr` IQ recordings (`.cu8`), optional `rtl_fm`/`multimon-ng` ISS APRS text, and ISS SSTV WAV that can be decoded by an external tool such as QSSTV. Meteor-M IQ can be processed by installed SatDump with the selected LRPT pipeline; it reports the **actual** output files only. Iridium mode is **spectrum-only** and does **not** decode private satellite communications.
- No RF transmission, no fabricated satellite detections or images, no all-band hidden background scans, no auto-deletion of raw recordings. Limits: 1 GiB per IQ file; max scheduled capture 480 sec; max manual capture 240 sec; 24 pending passes.
- Uses Text Center's **cooperative RTL-SDR lock** at `~/.local/share/tihulu-text-center/.receiver-locks/rtl_fm_rds.lock`, plus existing `/proc` receiver-conflict checks. Third-party apps which ignore locks can still interfere; never run welle.io/readsb concurrently with the single RTL-SDR. A dedicated second receiver is preferable for simultaneous operation.

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
| Meteor-M2-3/M2-4 | 137.900 MHz or current published backup 137.100 MHz, LRPT / SatDump | 137 MHz V-dipole / QFH, clear sky; downlink availability changes |
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
