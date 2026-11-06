# TIHULU RF Geolocation Center (experimental independent application)

**Source:** `Tihulu/TIHULU-TEXT-CENTER/rf_geolocation_center/`. Do not merge other Tihulu applications or overwrite Satellite Center PR #9. Desktop and mobile friendly web app for modern browsers.

## Run

From the repository root:

```sh
python3 -m http.server 8760 --bind 127.0.0.1
```

Open http://127.0.0.1:8760/rf_geolocation_center/ (for local tests). HTTPS GitHub Pages target, only after deployment and URL verification: https://tihulu.github.io/TIHULU-TEXT-CENTER/rf_geolocation_center/

The web application supports standalone static hosting without a native backend. Mobile browsers can use maps, import local data, access device location with permission and install as a PWA where supported. Desktop Chromium browsers may support Web Serial NMEA GNSS receivers and WebUSB **real device connection and bounded uncalibrated IQ sampling** when hardware/browser permissions permit; no GNSS RF decoder or SDR position fix is currently implemented. Firefox and Safari cannot directly use the RTL-SDR through WebUSB.

## Implemented in experimental branch

- Entire GNSS catalog: GPS, Galileo, GLONASS, BeiDou, QZSS, NavIC and SBAS. *Catalog visibility does not imply actual RF acquisition.*
- Opt-in browser/device geolocation. Without genuinely authenticated receiver observations, map defaults to Cologne, Germany as a **reference**, not your position. Imported aircraft JSON remains an unverified map reference even if it claims an ADS-B observation; future trusted Flight Radar adapters may implement the aircraft-centered fallback after verifying the observation and position.
- Precise-orbit SP3 file import, geometry-only Earth and polar sky plotting, explicit epochs and elevation mask. No extrapolated live position claims, and no satellite visibility implies RF reception.
- Online OpenStreetMap tiles when requested by the map-first page; no bulk offline tile caching. Offline locally rendered WGS84 coordinate grid and range evidence remain usable without tiles.
- Dedicated GNSS NMEA GGA/RMC logs with checksum validation and explicitly labeled historical import.
- Optional Web Serial GNSS live NMEA read on supported desktop browsers. Fresh receiver fixes expire after 90 seconds.
- User-imported station/aircraft references, local experimental 2D range trilateration, **visible measured-distance circles and intersection marker** on Earth Map, separate synthetic **DEMO ONLY** explanation, and synchronized TDOA hyperbola constraints (not a TDOA position fix).
- Real device/receiver in-memory position history and JSON, GeoJSON, CSV, GPX, KML exports.
- Hard Stop releases only this application's serial receiver; it does not terminate readsb, Gqrx or other Tihulu receiver jobs.
- Offline PWA shell; locally stored last known position, imported reference stations and measured-range inputs (labeled saved/unverified), and a best-effort cached pinned SGP4 dependency. No automatic RF/background fetching or telemetry.

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


## Offline position and visually explained range rings

The app must be installed/loaded over HTTPS while online at least once so that its PWA shell and required JavaScript are cached. When offline, the main map falls back to a local coordinate grid instead of a blank OpenStreetMap frame. User-approved browser location can still work if the underlying operating system/device has **offline GNSS or another offline location provider**; this is not guaranteed for every desktop/browser. An attached dedicated serial GNSS receiver may provide a live NMEA fix without internet. The current RTL-SDR sample survey cannot decode GNSS and **cannot locate the user independently**.

Each valid device/serial fix is cached in the user's own browser storage with its UTC timestamp. If live positioning fails, the app can display an **experimental range estimate** from already imported measured distances, or the **last-known cached point**, both clearly distinguished from a fresh fix. All saved coordinates remain local to that browser origin and can be cleared from the Settings panel. Imported reference points and range observations also persist locally, up to the import limits.

On the dedicated **Earth Map** page, use the checked layers:
- **Measured radio distance rings:** solid aqua circles appear only after importing at least 3 values with \`measured:true\`, latitude/longitude, \`rangeMeters\` and ideally source/name/type metadata. Every station used appears as \`R\` (or \`A\` for a genuinely measured aircraft range); the best-fit intersection is marked \`X\`. The range residual is *not* a location accuracy estimate.
- **Show ring explanation (SIMULATED):** checked initially when there are no measured ranges. This shows three **fictional** stations, dashed amber circles and a simulated intersection marked \`D\`. These are not antenna measurements and never count as a live positioning fix.
- **Ground stations and aircraft:** imported verified/published reference coordinates are visibly distinct from measured positioning sources. A reference coordinate by itself does not yield a distance.
- **Predicted satellite ground points:** off by default to avoid hundreds of dots obscuring Earth Map. This toggles predicted satellite subpoints, not GNSS pseudorange measurements or satellites used in a decoded solution. Real GNSS pseudoranges are 3D, not two-dimensional transmitter circles.

The **Fit rings / evidence to map** control chooses a zoom around the current evidence geometry. **Clear measured ranges** removes persisted range observations and returns to the labeled simulated demonstration.

Import accepted shape (illustrative JSON schema; do not treat this as a measurement unless the distances were actually measured):
\`\`\`json
{"stations":[
  {"name":"Receiver A","type":"station","lat":51.26,"lon":7.15,"rangeMeters":4200,"measured":true,"source":"Actual calibrated range method","measuredAt":"2026-11-06T07:00:00Z"},
  {"name":"Receiver B","type":"station","lat":51.29,"lon":7.22,"rangeMeters":3800,"measured":true,"source":"Actual calibrated range method","measuredAt":"2026-11-06T07:00:00Z"},
  {"name":"Receiver C","type":"station","lat":51.22,"lon":7.19,"rangeMeters":5300,"measured":true,"source":"Actual calibrated range method","measuredAt":"2026-11-06T07:00:00Z"}
]}
\`\`\`
Those numerical values are **schema placeholders, NOT actual measured distances**. Do not import them as a real capture.

### Remaining scientific blockers

No live aircraft-based self-positioning, no calibrated terrestrial ranging from uncalibrated SDR RSSI, no synchronized multi-receiver MLAT position fix, and no RTL-SDR GPS/Galileo tracking/pseudorange solver. Supporting published transmitter or aircraft coordinates on the map does not claim the antenna currently uses them. TLE/SGP4 positions can predict sky geometry offline only when compatible orbital data and the propagation library are cached; a predicted satellite is never a received navigation fix.


## One-click real location test (2026-11-06)

Open the Dashboard or the dedicated Earth Map and click **Find My Location**. The app checks a **current** supported NMEA serial GNSS receiver fix first and otherwise requests browser/device geolocation permission. The Earth Map now lists the actual source, coordinates, receiver-reported satellite count/HDOP when available, or the browser-reported accuracy radius. A **violet dotted circle** shows browser-reported location uncertainty where available; this is **not** radio-distance trilateration. **Solid aqua circles** represent user-imported station ranges (not verified by the app), while **dashed amber circles** are explicitly synthetic explanation. Browsers can use GPS, Wi-Fi, cellular or IP-based providers and do **not** disclose which method produced the position. Treat the browser's reported accuracy estimate as a claim from the OS/provider, not as proof of satellite reception.

**Practical offline test:** Install/open the PWA over HTTPS while online at least once and grant location permission. Find your location and verify that a timestamped last-known position is saved. Switch off Internet connectivity and reopen the installed app: the local coordinate-grid map, station reference markers and measured-range overlays remain visible. Press Find My Location again. On a phone/receiver with independently working offline GNSS the device's geolocation API may still return a fresh fix; on desktops without location hardware, this may fail and the cached position remains labeled **LAST KNOWN / NOT LIVE**. PWA source code caching alone never creates offline GPS hardware.

Browser coordinates are no longer considered fresh after **five minutes** without a new geolocation observation. A new measurement requires a user action. The demo does not infer range to any nearby aircraft or radio station. RTL-SDR WebUSB currently provides short uncalibrated RF sample captures, not GPS pseudorange decoding. To attempt real SDR standalone GNSS PVT, the separate GNSS-SDR backend plus suitable GNSS antenna/front-end must first be implemented and validated.
