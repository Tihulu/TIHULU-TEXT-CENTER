# Satellite Center — Earth & Sky tracking maps

The browser-only frontend now contains two connected views using the **same
operator-refreshed or manually imported CelesTrak TLEs** as the pass calendar.
These views are independent from WebUSB, so Firefox can display the maps even
though Firefox cannot directly open RTL-SDR USB devices.

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
