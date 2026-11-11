# Checkpoint 001 — RF Geolocation Center first independent implementation

**Date:** 2026-11-06 (Europe/Berlin).  
**Repository:** Tihulu/TIHULU-TEXT-CENTER (existing).  
**Exclusive branch:** feature/rf-geolocation-center-2026-11.  
**Draft:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/16, base main, unmerged.  
**Related independent Satellite Center:** Draft PR #9, unchanged by these RF Geo commits.  
**Survival Kit and Flight Radar:** untouched and unmerged.  
**GitHub Pages gh-pages branch:** untouched; target URL not yet deployed or verified.

## Owner instructions implemented as tested/prototype source

- Standalone directory rf_geolocation_center/ with responsive English UI, index, app CSS and JavaScript, fixed PWA assets. Dashboard, Earth coordinate map and opt-in visible OSM tiles; sky azimuth/elevation visualized only from actual user-imported SP3 orbit positions.
- Shared JS scientific core: 7 constellation family registry (GPS/Galileo/GLONASS/BeiDou/QZSS/NavIC/SBAS), corresponding frequencies/hardware limits, WGS84/ECEF transformations, bounded SP3 sampling/interpolation and NMEA GGA/RMC checksum processing. The NavIC registry includes recent L1, L5 and 2498.028 MHz S-band (not receivable on nominal RTL-SDR 1750 MHz upper band).
- Measured-only local 2D range trilateration with unvalidated calibration label, physically constrained synchronized TDOA hyperbolas (NO TDOA PVT fix), user-imported station/aircraft reference points, real browser location and NMEA GNSS receiver source metadata, in-memory track exports JSON/CSV/GeoJSON/GPX/KML.
- Browser Web Serial GNSS support when available. WebUSB device SELECTION ONLY; it does NOT claim the Nooelec USB interface, sample RF, correlate satellites, track C/N0 or calculate SDR PVT.
- Hard Stop releases only this page's opened serial device. No other process or protected radio recording touched.
- Optional Python 3.11+ standalone source launcher, explicit localhost-only asset allowlist, strict Host and path checks, no receiver API. Native command: python3 -m rf_geolocation_center serve --port 8794 (repository root), then http://127.0.0.1:8794/; doctor command available. Portable launcher tests on Linux/Windows/macOS in Actions, not signed native installers.
- PWA service worker caches same-origin static shell assets ONLY; no downloaded private orbit/IQ/positions, telemetry or OSM tile cache.

## Scientific integrity adjudications

- SP3 standard time system is NOT always UTC. Header %c GPS or UTC must be present, GPS epochs are shifted to UTC using the maintained leap-second chronology (Nov 2026 GPS-UTC = +18 seconds); unsupported systems and dates after maintained conversion validity fail closed. Synthetic test verifies GPS-vs-UTC input and unsupported TAI. Official format/IERS refs: https://gnss-x.ac.cn/docs/sp3c.pdf, https://gssc.esa.int/education/library/standards-and-data-formats/file-formats/sp3/, https://www.nist.gov/pml/time-and-frequency-division/time-realization/leap-seconds.
- An untrusted reference JSON could set observedByReceiver:true and trigger an aircraft-centered map fallback. This was an invalid evidence elevation; corrected in source at bff78bc4720512ea586a2882b34497f28333c2b7. Uploaded aircraft positions remain clearly marked as references and do NOT become verified receiver observations. No trusted Flight Radar adapter exists yet. Without a legitimate device/receiver position and verified receiver-observed aircraft, map defaults to Cologne rather than inventing observer position.
- The browser NMEA file route labels the imported file as historical; actual Web Serial data is separately labeled and expires as fresh after ~90 seconds. Browser permission-based location never becomes SDR-measured fix.
- All imported source positions and experimental radio math are independent from actual RF acquisition status. No official emergency warning or accuracy metric is invented.

## Checkpoints/CI, explicitly distinguished

- Node core/SP3/NMEA/NavIC tests + syntax + Python loopback source launcher tests on GitHub Actions. At source commit 4eafd02b076d80644908b6565fc41b3b7612c72b, [run 42172141706](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/42172141706) PASS: Linux, Windows and macOS launcher tests AND Node web scientific tests. This does not certify M-series native binaries or Raspberry Pi ARM.
- Original Text Center suite has run independently on main/this feature branch and passed on multiple commits, no test changes or source modifications to its textcenter/ or web/ code.
- Later commits add docs and an aircraft-provenance regression test; inspect latest GitHub Actions runs for exact current HEAD PASS, not only historical PASS.

## Unimplemented and BLOCKED, by requested phases

- **True GNSS SDR:** real L1/E1 acquisition, tracking C/N0, navigation message decode, time-system clock biases, pseudorange PVT, actual installed GNSS-SDR backend, FFT/PCAP/QPSK correlator, suitable antenna/LNA/bias tee, physical Nooelec/OS driver validation. None done.
- **Radio station positioning:** real calibrated range/RTT and at least four synchronized TDOA stations and resulting real MLAT fix untested. Current 2D geometry math only, no measured uncertainty accuracy.
- **Formats:** raw RINEX requires genuine observations, IQ capture requires real bounded receiver run, neither is implemented.
- **UI/device:** real macOS Apple Silicon app/menu icon, Windows x64 executable, Debian/Pop!_OS .desktop package, Pi ARM64/ARM32, Android/iOS/iPadOS browser visual QA and hardware compatibility tests. No native packaged releases.
- **GitHub Pages:** source ready at the intended directory but deployment to https://tihulu.github.io/TIHULU-TEXT-CENTER/rf_geolocation_center/ is NOT verified/merged because existing gh-pages branch must be protected.
- **Integration:** authenticated /geolocation/ route, Kit receiver broker, Satellite Center/Flight Radar data adapter and shared hardware Hard Stop not yet connected. No writes to other repositories.

## Follow-up development order

1. Pass new source provenance regression and full GitHub CI at final candidate SHA; review browser UI on phone/tablet and real imported SP3.
2. Separate input hardware backend with genuine GNSS receiver NMEA and actual USB permission tests; real SDR RF only after global receiver leasing with protected readsb/welle/Gqrx ownership.
3. Supported GNSS-SDR configuration and verified acquisition/tracking/positioning for specific signals, with real measurements and no synthetic passing claims.
4. Authentic station ranging/TDOA datasets, uncertainty/clock synchronization and interactive geometric overlays.
5. Signed native installers on explicitly verified architecture/OS versions, Pi measurements, reviewed additive Pages deployment, and authenticated API integration contract.
6. Review Draft PR #16; do not merge into main without separate approval. Preserve all ongoing Satellite Center PR9 and source main features.
