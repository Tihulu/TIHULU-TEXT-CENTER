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
- Opt-in browser/device geolocation. Nearest verified observed aircraft (when explicitly imported), then Cologne as clearly labeled map-only fallbacks. Aircraft position is never reported as the user's location.
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
