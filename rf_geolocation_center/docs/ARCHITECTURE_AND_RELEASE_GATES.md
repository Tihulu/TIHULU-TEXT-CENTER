# TIHULU RF Geolocation Center — architecture, science and release gates

2026-11-06. Isolated existing-repository feature branch: feature/rf-geolocation-center-2026-11. Draft PR #16. Only the rf_geolocation_center directory and its dedicated CI have been changed. Existing Satellite Center PR #9, Text Center main, Survival Kit and standalone Flight Radar remain unchanged and unmerged.

## Existing runnable pieces

The independent browser-first module works from an HTTPS static host or trusted 127.0.0.1 localhost. The core scientific logic is under core/gnss.mjs and core/positioning.mjs, shared with Node unit tests; web/app.mjs, web/style.css and index.html provide the responsive multi-section UI. web/maps.mjs and web/receivers.mjs are isolated browser adapters. The PWA manifest/service worker caches only fixed same-origin shell files; the original user observation files, OSM tiles and private coordinates are not cached as public sample observations.

Start from repository root: python3 -m rf_geolocation_center serve --port 8794. Open http://127.0.0.1:8794/ . Doctor: python3 -m rf_geolocation_center doctor. The optional Python 3.11+ localhost launcher serves a fixed allowlist of application assets and does NOT expose a receiver-control API, public network listener or native SDR decoder.

The hosted GitHub Pages target is https://tihulu.github.io/TIHULU-TEXT-CENTER/rf_geolocation_center/ . Source is ready for static hosting; the shared existing gh-pages deployment remains untouched. The URL is NOT claimed live or validated until separately reviewed publication.

## Provider and source distinctions

- Browser / Device Location: explicitly permissioned browser coordinates and OS-reported accuracy, never calculated by SDR.
- Dedicated GNSS NMEA: checksum-verified GGA/RMC data from an actual imported log or explicit Web Serial connection; receiver-reported fix, not browser or RTL-SDR pseudorange processing.
- SP3: user-supplied, actual dated orbit positions, interpolated only within covered epochs. Earth/sky geometry is PREDICTED and not RF acquisition, tracking, navigation clock, C/N0 or current reception.
- Terrestrial source positions: imported references have attribution but are not independently validated as observed or the user's location.
- 2D radio trilateration: only user-supplied measured:true ranges; uncertainty remains uncalibrated and results are experimental. Raw RSSI is insufficient for precise ranging.
- TDOA: measured synchronized receiver time differences and baseline plausibility check yield hyperbolic range-difference constraints, not a guaranteed multilateration position fix.
- WebUSB permission: selected compatible RTL-SDR may be named, but its USB RF interface is NOT opened and no signal is sampled. A dedicated GNSS receiver via Web Serial is the only optional live external observation input.

System registry groups GPS, Galileo, GLONASS (FDMA frequency caveat), BeiDou, QZSS, NavIC with recent L1, and documented SBAS operators. Frequency catalog presence does not mean the current Nooelec antenna, tuner clock or software can decode the signal.

## SP3 scientific time conversion

ESA GSSC and the official IGS SP3-c specification state the header time system applies to all epochs. Common GPS-time epochs are not UTC; the file does not supply leap-second conversion. This module requires a declared %c time-system header, accepts only supported GPS or UTC tags for now, applies a maintained historical GPS-to-UTC leap-second table through 2026, and blocks unsupported time systems or future dates without a verified update. On 6 November 2026 the GPS scale is 18 seconds ahead of UTC, consistent with NIST/IERS and USNO public notices. SP3 source interpolation does NOT compute GNSS navigation pseudoranges, receiver clock biases or a precise radio position fix.

References:
- https://gssc.esa.int/education/library/standards-and-data-formats/file-formats/sp3/
- https://gnss-x.ac.cn/docs/sp3c.pdf
- https://igs.org/acc/resources/
- https://www.nist.gov/pml/time-and-frequency-division/time-realization/leap-seconds
- https://maia.usno.navy.mil/products/leap-second

## Shared receiver ownership, hard stop and integration

This application has no autonomous RF process, does not send or record radio traffic, and must not take over the single Nooelec from readsb, Gqrx, welle.io, rtl_433, Satellite Center or Text Center. Hard Stop acts only on this application's own serial reader/session, not on unrelated processes; browser-wide permission revocation is managed in browser settings. A future real native GNSS-SDR/RTK backend MUST adopt the existing Kit global SDR broker, protected recordings and fully tested Stop acknowledgment rather than relying only on advisory locks.

Future Survival Kit authenticated route: /geolocation/ and versioned API under /geolocation/api/v1/ after source-provenanced identity, TLS, CSRF, rate limiting, source registry and full Kit storage/power policy validation. Never deploy an unrestricted receiver control API on public LAN or Internet. Standalone Flight Radar aircraft coordinates are references, not the observer's location, without defensible range measurements.

## Outstanding phases and truth in reporting

Phase 1 source architecture, isolated branch, source preservation and draft PR: implemented.
Phase 2 browser GNSS registry, SP3 input, coordinate/sky maps, browser location, responsive navigation, source-labelled import/export, opt-in OSM: implementation exists, real browser mobile visual QA pending.
Phase 3 dedicated Web Serial NMEA: implementation exists, physical GNSS serial hardware pending; direct WebUSB only selects device; real SDR GNSS RF acquisition/tracking/PVT unavailable.
Phase 4 GNSS-SDR signal correlation, navigation decode, clock and multi-constellation PVT: NOT IMPLEMENTED; no satellite lock claim.
Phase 5 measurement-based 2D trilateration and TDOA constraints: implemented as experimental mathematics; genuine calibrated multi-receiver dataset and MLAT fix pending.
Phase 6 Python localhost launcher with Linux/Windows/macOS test matrix: source implementation; real signed native packages, macOS M-series package, Raspberry Pi ARM32/ARM64 tests, GitHub Pages publication pending.
Phase 7 Kit integration contract: documented only; do not merge or modify existing projects.

No real GNSS RF acquisition, hardware accuracy/antenna test, RINEX raw observation output or IQ recording is claimed. External SP3 and NMEA file compatibility tests, browser layouts, native platform releases and power/memory profiles remain future acceptance gates.
