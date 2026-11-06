# Satellite Center — Earth & Sky tracking maps

The browser-only frontend now contains two connected views using the **same
operator-refreshed or manually imported CelesTrak TLEs** as the pass calendar.
These views are independent from WebUSB, so Firefox can display the maps even
though Firefox cannot directly open RTL-SDR USB devices.

## Ground-station location selector (v0.5)

The same observer position now controls the pass calendar, polar sky plot
and OSM map. The default station coordinates are intentionally approximate
Cologne coordinates, **not inferred user GPS**.

1. **Offline town autocomplete** — 8,084 embedded named places: 7,104
   Germany and 980 Türkiye entries, including places such as Hürth,
   Köln and Karaburun (İzmir). The local city-name search starts after
   two characters and matches Turkish/German accent folding and common
   aliases. Choose among the named state/country suggestions to avoid
   mixing up towns with the same name. Entries are populated points,
   not street addresses or device positions.
2. **Explicit browser geolocation** — the operator presses
   **Use device location (GPS / Wi-Fi)**; only then does the browser
   call `navigator.geolocation.getCurrentPosition` and prompt for
   permission. The displayed accuracy is the browser's estimate.
   Geolocation may derive from IP/Wi-Fi rather than real GPS; it can be
   denied or time out. Denial does not silently fall back to IP location.
3. **Fully custom manual coordinates worldwide** — both latitude
   (−90..+90) and longitude (−180..+180) remain editable, and the
   user can switch to Custom mode without an account or online lookup.
   Blank/out-of-range coordinates prevent pass calculation.
4. **Optional worldwide city lookup** — a user click on
   **Search worldwide online** queries
   `https://geocoding-api.open-meteo.com/v1/search`, or users may
   opt in to online suggestions as they type (unchecked by default).
   Open-Meteo is an external service based on GeoNames, currently
   free for non-commercial use with fair-use limits. Typing city
   names offline does not contact that service. Network failures
   leave the offline library and manual coordinate method usable.
5. When a station changes, previously calculated passes are
   invalidated and must be recalculated. Earth/Sky views immediately
   use the new coordinates as their geometric reference; no USB scan
   begins automatically.

**Data attribution:** bundled `browser/cities-de-tr.json` is an ODbL
1.0 derivative of `srestre/world-countries-cities-db` and its dr5hn
upstream source. See [CITY_DATA_LICENSE.md](browser/CITY_DATA_LICENSE.md).
Online search credit: [Open-Meteo Geocoding](https://open-meteo.com/en/docs/geocoding-api)
and underlying GeoNames data. The user's browser may send a typed
online query only after explicit online search/opt-in; no device GPS
coordinate is sent to city search. No location state is persisted by
the map app or transmitted in TLE requests.

## Earth / OpenStreetMap (OSM)

- User-initiated **Load OpenStreetMap** control. Until clicked, no Leaflet
  library or OSM raster tiles are loaded; the sky plot works independently.
- Interactive map with approximate satellite ground subpoints, manual station
  marker, filter by ISS/Meteor-M/CubeSat/Iridium, current SDR band, above
  horizon, selected orbit segment (±45 minutes) and optional geometric
  line-of-sight footprint respecting the minimum elevation selector.
- Only the human-visible viewport is requested from OSM. No tile caching
  bypass, geographic prefetch, or offline tile downloads. OSM attribution is
  always present on the Leaflet map.
- The browser uses a normal origin-only HTTP Referer because OSM's tile usage
  policy prohibits `no-referrer` for hosted tiles. Thus the map provider
  receives the public website origin, browser/IP and the viewed tile extent;
  no precise browser geolocation permission is requested by this app.
- Leaflet is pinned to `1.9.4` with official published SRI hashes; OSM tiles
  use exactly `https://tile.openstreetmap.org/{z}/{x}/{y}.png`.

Official policy: https://operations.osmfoundation.org/policies/tiles/
Library: https://leafletjs.com/download.html

## Heavens-Above-style Sky view

- Original browser-rendered **polar azimuth/elevation chart**; it is NOT a
  copied Heavens-Above graphic or an embedded third-party map.
- North is up, east right, outer ring is 0° elevation (horizon), center is
  90° elevation (zenith); circles for 30° and 60°. Satellites below the
  horizon are omitted from the sky even when shown in the Earth view/list.
- The selected satellite's ±15 min approximate sky path is drawn using
  orbital propagation, not an optical visibility calculation.
- Heavens-Above is linked externally for independent pass comparison:
  https://www.heavens-above.com/

## Signals / data integrity

- Every object is labelled **TLE-derived / geometry only**. A colored pin,
  pass prediction, above-horizon indicator or spectral peak does NOT
  identify an active satellite transmitter.
- Existing WebUSB raw-IQ sampling is unchanged. The map's **Select MHz**
  control changes the receiver's preset but does not start a USB capture.
- ISS: use published live ARISS/ISS activation status, 145 MHz VHF and
  associated UHF modes when available.
- Meteor-M: candidate 137.900/137.100 MHz downlinks; LRPT images require
  a decoder, appropriate antenna and a successful recording.
- CubeSat: an amateur TLE is not a downlink frequency database. Check
  individual verified published downlinks, e.g.
  https://db.satnogs.org/transmitters/.
- Iridium: orbit positions and 1.6 GHz relative RF spectrum scanning only;
  no non-public communications decoding. L-band antenna/filter/LNA may
  be required. The current receiver's R820T band edge further limits
  reception.
- **Match current SDR band** is only a candidate category match. It cannot
  prove a satellite is actually transmitting on the tuned frequency.
- TLE epoch ages above seven days raise a warning; refresh before planning.
- A timestamp slider (−45 to +90 minutes) is simulated geometry, not a
  recording from another time. Live rendering refreshes about every 18 sec.
- Data and manual station coordinates remain in the tab for propagation;
  the Earth tile provider receives requests for the viewed map extent.
- The OSM map does not transmit to satellites or provide emergency alerts.

## Offline and browser support

Sky/ground geometry can be recalculated offline *after* the satellite.js
library and TLE data have been loaded and remain available in that tab.
The OSM tile server must not be used for bulk/offline download; an existing
browser tile cache may be honored normally. Third-party CDN failures are
reported, rather than drawing fictitious ground positions.

Firefox can use satellite maps and the pass planner; RTL2832U WebUSB
reception is unavailable in Firefox. Chrome/Brave/Edge can use both map and
WebUSB if the operating system allows the receiver to be claimed.

## Verification

- Native static browser JavaScript and map module syntax checks.
- Node unit tests for sky projection cardinal alignment, visibility footprint
  shrinkage with higher minimum elevation, longitude/date-line splitting,
  and valid observer coordinate bounds.
- No end-to-end on-device satellite reception, map tile rendering in
  Chromium/Firefox, or active downlink detection was verified by CI.


## Earth basemap failure recovery (Nov 2026)

On some browser/network/privacy-filter configurations the Leaflet satellite
markers render but the OSM raster imagery remains blank. This should **not**
be interpreted as successful map loading. The Earth view now:

1. Sets explicit `strict-origin-when-cross-origin` tile referrer policy,
   as required by OSMF's tile use policy.
2. Tracks actual `tileload` and `tileerror` events, rather than reporting
   "ready" merely because Leaflet initialized.
3. On three tile errors without any loaded tile, or nine seconds with no
   successful tile load, selects a **bundled, public-domain Natural Earth
   1:110m land outline fallback**, so Earth geography remains visible with
   the station and satellite overlays.
4. Displays the active layer and its success/failure state, provides a
   `Load / retry OpenStreetMap` button and an explicit **Base map** selector.
   A blocked tile service is never claimed to be a successful OSM layer.

If a provider returns a 200-status "blocked" image instead of the requested
map (some OSM restrictions do), Leaflet might report `tileload` even though
the content is not geographic. Switch manually to **World outlines**.
Do not disable privacy protections automatically; the user can test their
network/Brave Shields settings separately. This fallback is a coarse world
map, not street-level OSM.

Data: Natural Earth public-domain 1:110m land, mirrored and reduced from
`martynafford/natural-earth-geojson/110m/physical/ne_110m_land.json`.
Source: https://www.naturalearthdata.com/
OSM tile rules: https://operations.osmfoundation.org/policies/tiles/

## Pass and satellite sorting

- Pass-calendar selector: **soonest date/time, latest/farthest date/time,
  highest/lowest maximum elevation, longest/shortest pass and A–Z**.
- The old UI silently displayed only the first 80 entries from a truncated
  100-pass cache. The full computed pass list is now retained; the panel
  paginates 40 entries at a time with **Show more passes**. Consequently
  "latest date first" sorts over all calculated candidates.
- Right-side satellite list sorts by elevation, **next calculated pass
  soonest/latest**, slant-range near/far and name.
- A next-pass ranking requires Calculate passes first; no timestamp
  is invented for a satellite lacking a computed pass.
- Neither sorting nor filtering adjusts a pass time or a scheduled RF job.

## Browser-only scheduled receiver analysis

1. **Calculate passes**, then expand **Schedule / configure timed RF
   analysis** for a satellite.
2. Confirm exact **date + hour + minute** in the **computer/browser local
   timezone** (which may differ from the ground station timezone),
   candidate frequency, sampling rate, 5/15/30/60-second duration and
   whether to save raw interleaved `.cu8` USB IQ.
3. **Confirm scheduled RF scan**. It creates a memory-only job and
   releases any idle SDR immediately, so waiting hours does not keep
   the receiver claimed.
4. Click **Choose RTL-SDR** once to grant WebUSB if it was not already
   permitted. **Check scheduled-scan readiness** inspects prior USB
   grants read-only, without taking RF samples. An optional Screen Wake
   Lock button can reduce screen sleep risk where available.
5. At the due minute (if the page is visible and running), it tries to
   reopen **only a previously permitted RTL2832U via
   `navigator.usb.getDevices`**, then tunes to the chosen profile and
   reads actual I/Q USB bytes for the configured duration or remaining
   pass length. Jobs are sequential; competing receiver jobs wait.
6. It computes actual raw sample-level minimum/average/maximum,
   block count, size, elapsed time and variation, **not calibrated
   RF dBm or proof of a named satellite**. If raw recording was requested
   the browser download is triggered; an explicit **Download raw IQ
   again** action retains the latest recording if automatic downloads
   are blocked.
7. The job card shows **armed / due / starting / running / finished /
   blocked / missed / stopped** with date, countdown, error reason and
   measured RF report. A blocked pass can be retried *while still active*
   without changing any unrelated USB process.

**Critical limitation:** A static browser cannot guarantee background work
after tab closure, browser suspension or laptop sleep. This schedule is
**foreground-only**; the user is told to keep the tab open/visible, and
missed passes are explicitly labelled. Previous WebUSB permissions do not
prove the device is free. The app never kills `readsb`, Gqrx or welle.io.
The idle USB device is not kept claimed while waiting.

**Still not implemented in browser:** Meteor LRPT image reconstruction,
APRS packets, SSTV images or satellite-specific RF identification. The
result is honest uncalibrated sample-level analysis and optional raw IQ;
the optional local companion with SatDump/multimon-ng is needed for
external decoders and for jobs while the browser tab is closed but the
companion service runs.

No physical Nooelec scheduled-capture acceptance test has been performed
by this code-only change. Synthetic tests cover sorting, schedule minute
bounds, due/hidden/busy transitions, digital level statistics, tile
fallback thresholds and UI control presence.


## Follow-up: Earth map works independently of Leaflet (November 6, 2026)

When OSM street tiles and the earlier Leaflet fallback both appear blank,
the **Earth tab now automatically draws a world Canvas background** from the
bundled `natural-earth-land-110m.geojson` file. It does not need OpenStreetMap
servers or the Leaflet CDN for the basic world basemap.

- Built-in Canvas shows real coastlines/land, the current selected station,
  and ground subpoints of TLE-propagated satellites.
- Satellite dots are clickable to synchronize with the prediction list and
  receiver candidate profile. They do **not** claim RF reception.
- **Interactive street map (OpenStreetMap / Leaflet, optional)** is a separate
  expandable section. Missing OSM tiles can no longer prevent the Canvas
  world map from being visible.
- **Test map background** diagnoses the bundled map data, feature count,
  Canvas render status and, if loaded, the separate Leaflet SVG paths.
- Leaflet's own optional Natural Earth layer uses an explicitly assigned SVG
  renderer and a pane above raster tiles, rather than an unreliable default
  Canvas renderer below the basemap.
- The app entry point and revised map modules have cache-busting version
  identifiers to avoid using stale Pages/PWA cached JavaScript.

The Canvas map is a **global geographic overview**, not street-level tiles.
If its own Natural Earth JSON request fails, the app explicitly reports that
rather than fabricating countries or pretending OSM loaded.

## Follow-up: real WebUSB hardware test and sample shape correction

The receiver panel now has **Test real USB + RF samples (3 sec)**, which
tries to reopen a *previously permitted* RTL2832U from WebUSB, tunes to the
selected Step 2 frequency, reads true complex I/Q samples and reports
actual byte counts, unsigned sample spread and relative digital level.
It always closes its own USB session afterward and never stops
`readsb`, Gqrx or another process.

The prior browser capture code incorrectly expected `readSamples()` to
return an ArrayBuffer. In `@jtarrio/webrtlsdr` v3 it returns a
`SampleBlock` object with `frequency`, `directSampling`, and
`data: ArrayBuffer`. All three paths—manual record, timed record and
hardware test—now extract `.data` correctly. This is a functional
fix, not merely UI: the previous format mismatch could discard every
valid received sample. Verified against the upstream TypeScript interface:
https://github.com/jtarrio/webrtlsdr/blob/main/src/rtlsdr/rtldevice.ts

A passing browser test proves a USB device opened and returned samples.
It does **not** prove that the antenna is matched, calibrated signal
power was measured, or any specific satellite transmitted. Test uses
the chosen frequency, so a quiet band can still pass valid USB sampling.
No physical-device run has been performed by CI.
