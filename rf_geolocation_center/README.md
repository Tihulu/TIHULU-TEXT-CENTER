# TIHULU RF Geolocation Center (experimental independent application)

**Source:** `Tihulu/TIHULU-TEXT-CENTER/rf_geolocation_center/`. Do not merge other Tihulu applications or overwrite Satellite Center PR #9. Desktop and mobile friendly web app for modern browsers.

## Run

From the repository root:

```sh
python3 -m http.server 8760 --bind 127.0.0.1
```

Open http://127.0.0.1:8760/rf_geolocation_center/ (for local tests). HTTPS GitHub Pages target, only after deployment and URL verification: https://tihulu.github.io/TIHULU-TEXT-CENTER/rf_geolocation_center/

The web application supports standalone static hosting without a native backend. Mobile browsers can use maps, import local data, access device location with permission and install as a PWA where supported. Desktop Chromium browsers may support Web Serial NMEA GNSS receivers and WebUSB **permission selection only**; no SDR IQ or GNSS RF decoder is currently implemented. Firefox and Safari cannot directly use the RTL-SDR through WebUSB.

## Implemented in experimental branch

- Entire GNSS catalog: GPS, Galileo, GLONASS, BeiDou, QZSS, NavIC and SBAS. *Catalog visibility does not imply actual RF acquisition.*
- Opt-in browser/device geolocation. Without genuinely authenticated receiver observations, map defaults to Cologne, Germany as a **reference**, not your position. Imported aircraft JSON remains an unverified map reference even if it claims an ADS-B observation; future trusted Flight Radar adapters may implement the aircraft-centered fallback after verifying the observation and position.
- Precise-orbit SP3 file import, geometry-only Earth and polar sky plotting, explicit epochs and elevation mask. No extrapolated live position claims, and no satellite visibility implies RF reception.
- On-demand OpenStreetMap tile loading, without bulk offline tile caching. Otherwise show own coordinate/map overlay.
- Dedicated GNSS NMEA GGA/RMC logs with checksum validation and explicitly labeled historical import.
- Optional Web Serial GNSS live NMEA read on supported desktop browsers. Fresh receiver fixes expire after 90 seconds.
- Source-attributed station/aircraft reference import, experimental local 2D measured-range trilateration, and synchronized TDOA hyperbola constraints (not a TDOA position fix).
- Real device/receiver in-memory position history and JSON, GeoJSON, CSV, GPX, KML exports.
- Hard Stop releases only this application's serial receiver; it does not terminate readsb, Gqrx or other Tihulu receiver jobs.
- Offline application shell service worker; no automatic RF/background fetching and no telemetry.

## Not yet implemented / acceptance pending

Native .deb/.exe/.app installers, Raspberry Pi native receiver backend, actual SDR GNSS L1/Galileo/GLONASS/BeiDou acquisition and tracking, pseudorange PVT, multi-constellation clock bias correction, antenna/bias-tee management, actual MLAT fix, live ADS-B integration, real GNSS-SDR backend, empirical antenna acceptance tests and cross-platform native package checks.

The Nooelec NESDR SMArt v5 may tune to many GNSS L-band frequencies but frequency coverage **is not decoder capability** and requires suitable antenna, filtering/LNA and powered active antenna arrangement (SMArt v5 has no built-in bias tee). S-band NavIC reception is outside its 1750 MHz upper limit.

## Tests

```sh
node --test rf_geolocation_center/tests/*.test.mjs
node --check rf_geolocation_center/web/app.mjs
node --check rf_geolocation_center/sw.js
```

Use real, source-attributed measurements for positioning; test fixture synthetic values must not be presented as received data. Actual browser or SDR hardware acceptance must be documented separately.

## Future Survival Kit integration

Use an authenticated `/geolocation/` route inside the Kit's TLS local portal and existing hardware lease broker. Allow mobile clients to view authorized Raspberry Pi receiver data over the local network. Do not expose unrestricted network-facing receiver controls. Keep this module independent until reviewed.

## Python localhost source launcher (no native SDR decoder)

Run from the repository root with Python 3.11+:

```sh
python3 -m rf_geolocation_center doctor
python3 -m rf_geolocation_center serve --port 8794
```

Open http://127.0.0.1:8794/ (on the same computer). The server binds to loopback only, serves an explicit app-asset allowlist and does not open any RTL-SDR, decode GNSS RF, expose a LAN receiver API or package a native desktop binary. Python source compatibility on CI is not physical Raspberry Pi or Apple Silicon verification. See [architecture and scientific gates](docs/ARCHITECTURE_AND_RELEASE_GATES.md) and [platform matrix](docs/PLATFORM_TEST_MATRIX.md).

Current SP3 parser checks the declared GPS/UTC time system and converts supported GPS epochs to UTC using leap seconds through 2026. Other time systems are blocked pending verified handling, rather than silently mislabeling their timestamps. Browser NMEA file import is historical; it is not a current live fix.


## Map-first automatic GNSS discovery (2026-11-06)

The first dashboard now includes an immediately visible **OpenStreetMap Earth Map** and **SGP4 navigation-satellite sky plot**. It makes one bounded CelesTrak \`GROUP=gnss\` TLE request on launch (at most once per 24h per client when cache is fresh) and refreshes sky geometry every minute while the page is visible. The public CelesTrak endpoint, version-pinned \`satellite.js\` browser module, and OSM map require internet on first load. Network/CORS errors must be shown as failures; they never generate synthetic satellites. A 7-day fallback cache is available, with stale orbit warnings. Automatic orbital discovery **does not scan or acquire RF satellites**.

**Find My Location** uses a current validated serial GNSS fix when available, otherwise prompts for browser/device geolocation. Published aircraft and station positions are only reference locations and cannot establish an observer fix without independent measured ranges/timing. If no real location source exists, the map is explicitly labeled *Cologne reference, not your position*.

**Connect USB SDR** on compatible HTTPS desktop Chromium browsers now requests the RTL2832U USB device with a user gesture, loads the version-pinned browser driver, claims the tuner at 1575.420 MHz where OS permissions and other applications permit, and offers a bounded two-second **Scan GNSS L1** of relative raw digital sample level. It **does not decode** GPS/Galileo/BeiDou navigation signals, estimate C/N0, or produce a GNSS PVT fix. **Release USB** and **Hard Stop** only close this page's own WebUSB and NMEA serial handles; they do not stop \`readsb\`, Gqrx or any unrelated process. No automatic RF scanning on app launch.

The embedded OSM map makes normal viewport requests immediately when the page loads; users should expect their browser's network address and viewed region to reach the map provider. No device geolocation is requested until the user clicks the location button.
