# STAND-RFGEO — Standalone native and WebUSB independence audit

**Scope/date:** 2026-11-12 · **Status:** SOURCE/CI AUDIT ONLY, 0/12 independently installed STAND acceptance gates signed off · **REG-14 P0 OPEN**  
**Pinned source:** Existing REG-05 [Draft #100](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/100) head `c1fe9eb477df10309a0281910b43f0402231fed4`, stacked on unchanged USB fix #97 (`33ba329a4b6af82e7a9f8440e4aa17f037d4ed12`) and EXIT-01 #94 (`772f21e11b510553b481fd483592b11cfcc3d1db`), original Geo #16. No source or installer changes are included in this audit.  
**Coordination:** [Issue #79](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/79) → [#75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75) · [standalone acceptance contract](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/STANDALONE_APPLICATION_ACCEPTANCE.md) · [REG-14](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/CROSS_WORKSTREAM_REGRESSION_GATES.md). Planned repository `Tihulu/tihulu-rf-geolocation-center` is EMPTY / NOT MIGRATED. Existing source is embedded in `Tihulu/TIHULU-TEXT-CENTER/rf_geolocation_center/`.

## STAND-01..12 feature and evidence matrix

Legend: **SOURCE** = code exists, not installed acceptance; **SYNTHETIC** = unit/CI only; **PARTIAL** = unmet criteria; **HOLD** = blocking independent evidence.

| Gate | Source evidence / demonstrated behavior | Remaining gaps and exact next verification | Acceptance |
|---|---|---|---|
| **STAND-01** clean single-app clone/build | `__main__.py` imports only `.native`; `native.py` imports only stdlib plus local `.dvb_bridge` and `.radio_metadata`. Entire JS import graph in `web/` + `core/` is relative/local except optional pinned CDN imports. New `tests/test_standalone_independence.py` performs a temporary folder-only copy and runs `python -m rf_geolocation_center --help` with **no other TIHULU app tree/PYTHONPATH** | No independently published/locked Python package, reproducible wheel/source-dist or clean customer install; current GitHub Actions checks out entire source repo. Run future truly clean target checkout + signed package/artifact smoke | **PARTIAL / HOLD** |
| **STAND-02** standalone UI launch | Browser `index.html` module `./web/app.mjs` and `web/style.css`. Local Python 3.11+ `python -m rf_geolocation_center serve --port 8794` binds **127.0.0.1 only** and serves an allowlisted static browser UI plus opt-in DVB backend. Existing loopback unit tests cover HTTP. Static folder can be served from any proper HTTPS/static server | **NOT a desktop GUI binary**; no .deb/.rpm/AppImage/Flatpak/MSIX/.exe/.app/DMG or Pi launcher, desktop icon/install/uninstall, signed release or UI screenshots from a clean independent installation. Python launcher is not a native RTL-SDR IQ application | **PARTIAL / HOLD** |
| **STAND-03** no required foreign imports/runtime assumptions | All `core/*.mjs` and `web/*.mjs` static relative imports are RFGeo-owned. `radio_metadata.py` has an **optional** read-only Text Center snapshot at `http://127.0.0.1:8787`; `web/catalog_discovery.mjs` optional same-origin `BroadcastChannel("tihulu.rfgeo.adsb.v1")` from Flight Radar. `web/dvb_bridge_client.mjs` optional localhost RFGeo DVB bridge at `http://127.0.0.1:8794`, not Text | **Port/origin migration blocker:** `native.py:PAGES_ORIGIN="https://tihulu.github.io"`, `dvb_bridge_client.mjs` has special Pages/local origin selection and hardcoded 8794 port; UI instructions refer to old `TIHULU-TEXT-CENTER` checkout and Flight URL. Need no-other-app clean install and alternate-origin/nested-path tests; optional bridge must not become mandatory | **SOURCE + SYNTHETIC / HOLD** |
| **STAND-04** offline/single-app behavior | `web/auto_explorer.mjs` renders an offline coordinate SVG grid if `navigator.onLine===false`; `web/app.mjs` renders local WGS84/grid, imported range rings, GNSS NMEA historical file, SP3 imports and NO POSITION FIX / cached/reference distinctly; the app loads with no Flight/Text. JS core computes without network | PWA first install requires online asset load; CelesTrak TLE, OpenSky/Overpass and OSM external maps are not available fresh offline; `https://esm.sh/satellite.js@6.0.1?bundle` cache is best effort. Offline browser/PWA cold-boot test and failed-network-with-`navigator.onLine===true` fallback needed. Missing actual RTL-SDR ≠ signal | **PARTIAL / HOLD** |
| **STAND-05** independent config/cache/data | Namespaced `localStorage` keys: `tihulu.rfgeo.last-known-position.v1`, `measured-ranges.v1`, `reference-points.v1`, `location-method-layers.v1`, `gnss-orbits.v1`, `rf-survey.v1`, `catalog.towers.v1`, `catalog.aircraft.v1`, `simple-ui-options.v1`, `native-dvb-channel-list.v1`; cache `tihulu-geolocation-shell-v23`. User exports JSON, CSV, GeoJSON, GPX and KML via browser download; no model or native recording store currently implemented. Native DVB worker uses `TemporaryDirectory(prefix="tihulu-rfgeo-dvb-")` | No XDG/AppData/Library or versioned migration/backup/restore, app-specific download directory, reinstall/uninstall foreign-file checks. `clear-local` clears only a subset of RFGeo keys; same web origin can host other apps despite namespaced keys, so a browser-wide Clear Site Data may affect them. Manual Linux DVB script writes dated config to **current directory**; prevent accidental collision/overwrite at installer stage | **PARTIAL / HOLD** |
| **STAND-06** solo plus simultaneous apps | No required Flight, Text, AI, Survival Kit, account or always-on shared daemon. Python app loopback only; optional WebUSB and Linux DVB are direct app-owned channels | No tested parallel installed Flight/Geo/Media instance or real shared lease under contention. Confirm no port/service conflict and whether hardware use is exclusive; separate receiver hardware required for concurrent direct SDR tuning | **SOURCE / HOLD** |
| **STAND-07** busy-device protection | Browser WebUSB select only after consent, specific RTL2832U ID 0bda:2838 in `web/usb_sdr.mjs`. Rejected USB driver claim reports BUSY/permission/driver diagnostic; native `DVBScanBridge` tracks per-client scan owner and rejects foreign Stop; no code automatically stops readsb/tar1090 | No cross-application RF lease broker or physical user-visible EXTERNAL OWNER proof; USB receiver **cannot** be assumed shareable while other app owns it. **Important unsafe optional manual helper:** `scripts/usb_prepare_linux.sh --release` explicitly runs `sudo systemctl stop readsb` and Linux RTL driver unbind; must NEVER be run automatically by an installer, startup, Stop or Quit. No hardware/driver action performed in this audit | **SYNTHETIC / HOLD** |
| **STAND-08** Quit / Hard Stop ownership | `web/exit_lifecycle.mjs` and `web/usb_sdr.mjs` handle scope, exactly-once app-owned close, bounded concurrent reads and STOP_FAILED_PARTIAL; Python `native.py:run_owned_server` shuts down **its own** DVB child and its localhost listener. Existing JS/Python cross-platform CI is mock-owned lifecycle, not installed RAM/VRAM | Real owned device releases, independent external readsb continuity, foreign application longevity, kernel busy, pending read timeout, native FD/process/RSS/VRAM/threads and browser tab-crash close acceptance remain unverified. `pagehide` is **best-effort** | **SYNTHETIC / HOLD** |
| **STAND-09** optional app-to-app overlays | Flight `BroadcastChannel` absent → core map remains functional; no persisted antenna-aircraft feed. Text RDS/DAB read-only snapshot unavailable → `available:false` / empty events, no tuner claim, as exercised by isolated mock; local RFGeo DVB bridge pairing is optional and guarded | ADS-B channel is origin-dependent and **not an authenticated receiver proof** (timestamps/metadata checked, not signed). Need explicit connector OFF/disconnect policy, version/permission handshake, separate-origin fallback, no source spoof or implicit shared daemon; no Flight or Text source modification authorized | **PARTIAL / HOLD** |
| **STAND-10** installers and platform docs | `README.md`, `docs/PLATFORM_TEST_MATRIX.md`, version `0.1.0-dev`, `manifest.webmanifest` and `web/icon.svg` exist; `.github/workflows/rf-geolocation.yml` exercises Node 22 JS and Python 3.11 loopback/doctor on Ubuntu, Windows and macOS | No stand-alone repo-scoped workflow/lockfile/manifest/versioned build/install/uninstaller/signing/rollback, one-line installer, complete EN(default)/TR/DE UI, Raspberry Pi hardware or ARM native package. Inherited repo-root CI must be adapted for independent target after authorization | **SOURCE / HOLD** |
| **STAND-11** self-hosted/static PWA | `manifest.webmanifest` uses relative start_url/scope `./`; `sw.js` caches only an explicit app shell and optional pinned CDN scripts, not RF recordings, personal positions, OSM tiles or cross-app data; `native.ASSETS` allowlists locally served shell and ESM. New graph tests check local files and route closure | No published standalone destination Pages or nested-path HTTPS/PWA smoke; CDN availability, browser private-network access and cache version/source hashes need network-offline and two-version updates; helper scripts are cached as static assets by shell but never executed by SW. Existing original-repo Pages URL is not a deployed new app | **SOURCE + SYNTHETIC / HOLD** |
| **STAND-12** independent acceptance / truth | Existing PR #97 CI **89/89** JS, 17/17 Ubuntu Python, Windows/macOS launchers; REG-05 PR #100 CI **97/97** JS, same synthetic native tests. Honest `NO POSITION FIX`, no GNSS SDR PVT, no RSSI GPS, and experimental range status. New isolated tests cover clean package-only CLI/static assets | **0/12 installed STAND cases signed off**; 0/15 installed EXIT-01 physical resource acceptance; real SDR shared-owner behavior, clean installer, hardware positioning, local HTTP dual-app/port, native RAM/VRAM and Pi all remain OPEN. No release decision or defensible ETA | **HOLD** |

## Exact import graph and source file inventory

**Python startup:**

```
python -m rf_geolocation_center [doctor | serve --port 8794]
  rf_geolocation_center/__main__.py -> .native
  rf_geolocation_center/native.py -> .dvb_bridge, .radio_metadata
  rf_geolocation_center/dvb_bridge.py -> Python standard library; optional Linux dvbv5-scan binary
  rf_geolocation_center/radio_metadata.py -> Python standard library; optional EXISTING Text Center HTTP 8787
```

Python 3.11+ standard modules: `argparse`, `http.server`, `pathlib`, `json`, `hmac`, `secrets`, `re`, `signal`, `urllib.parse`, `urllib.request`, `platform`, `sys`, `os`, `shutil`, `subprocess`, `tempfile`, `threading`, `time`. No PyPI production module imported, no `PYTHONPATH`/foreign-TIHULU import necessary for source launcher. An actual independently built wheel/app installation is **not** implemented.

**Browser entry and full local graph** (all paths relative to `rf_geolocation_center/`):

```
index.html -> web/app.mjs; web/style.css; manifest.webmanifest; web/icon.svg
web/app.mjs ->
  core/gnss.mjs
  core/positioning.mjs -> core/gnss.mjs
  core/scan_map.mjs
  core/evidence.mjs
  core/location_layers.mjs
  core/source_provenance.mjs
  web/auto_explorer.mjs -> core/gnss.mjs
  web/usb_sdr.mjs -> core/rf_ranging.mjs
  web/rf_survey.mjs -> core/rf_ranging.mjs
  web/catalog_discovery.mjs -> core/source_catalog.mjs
  web/simple_ui.mjs -> core/dvb_scan.mjs
  web/hardware_manager.mjs
  web/dvb_bridge_client.mjs
  web/exit_lifecycle.mjs
Additional owned JS assets not imported by current app.mjs:
  web/maps.mjs -> core/gnss.mjs
  web/receivers.mjs -> core/positioning.mjs
Standalone assets and optional helpers:
  sw.js, manifest.webmanifest, web/style.css, web/icon.svg
  scripts/dvb_scan_linux.sh, scripts/usb_prepare_linux.sh
```

**External runtime resources — optional/capability-gated:** `https://esm.sh/satellite.js@6.0.1?bundle` (SGP4), `https://esm.sh/@jtarrio/webrtlsdr@3.0.7/rtlsdr.js?bundle` (WebUSB after user permission), `https://celestrak.org/NORAD/elements/gp.php?GROUP=gnss&FORMAT=TLE`, `https://tile.openstreetmap.org/`, `https://www.openstreetmap.org/export/embed.html`, `https://overpass-api.de/api/interpreter`, `https://opensky-network.org/api/states/all`, optional same-origin Flight channel `tihulu.rfgeo.adsb.v1`, optional private RFGeo bridge `127.0.0.1:8794`, and optional Text read-only HTTP `127.0.0.1:8787`. Externally retrieved *map/site/aircraft/orbit metadata* is NEVER evidence of GNSS reception or location fix.

**Absent required future files for complete independently installed app:** package-owned `pyproject.toml`/lock/SBOM, distribution version manifest, native GUI/desktop-entry/icon integration, platform-specific package scripts/signing, clean installer/uninstaller/rollback, reproducible release artifacts with SHA-256, a standalone target-repo workflow and ownership-aware migration tests. A `package.json`/npm dependency installation is **not required** for current no-build ES module source, but if future bundling is chosen it needs a pinned manifest/lock and attribution. No source file should be assumed available from the parent Text checkout after migration.

## Platform and native dependency matrix — proposed, not installed acceptance

| Platform | No-hardware map/CLI | Optional hardware | Installation blockers |
|---|---|---|---|
| **Pop!_OS / Ubuntu / Debian x64** | Python >=3.11 standard-library loopback server; Chromium/other ES-module browser, static HTTPS Web build | Chromium WebUSB RTL2832U receiver with permissions; Web Serial NMEA; Linux DVB frontend `/dev/dvb/adapterN/frontend0`, distribution `dvbv5-scan` (`dvb-tools`), regional tuning file from `/usr/share/dvb` or user-supplied | No .deb/AppImage/Flatpak, signed launcher or rollback; Linux `usb_prepare_linux.sh` --release is **privileged and out-of-band ONLY**, not safe default |
| **Windows x64** | Python 3.11 localhost and browser static work in CI mock | Browser WebUSB where permitted, Web Serial with receiver; no Linux DVB scanner | No .exe/MSIX native wrapper, signed build, WebUSB host-driver check or installed hardware acceptance |
| **macOS Apple Silicon** | Python 3.11 localhost CI on macOS runner; no evidence of native .app | Browser USB/serial depends on supported browser/macOS permissions; Linux DVB backend unavailable | No M-series signed/notarized .app/DMG; CI does NOT confirm Apple Silicon-installed parity |
| **Raspberry Pi OS ARM64** | Source Python/browser technically portable, not tested in standalone Pi installed acceptance | Pi power/permission/driver compatibility and receiver lease must be separately verified | No Pi arm64 package/headless UI launcher/NPU or CPU test; no Pi-only receiver background service assumed |
| **Static web / PWA** | Relative HTML/CSS/ESM and offline grid with existing cached assets | WebUSB requires secure Chromium user gesture; Web Serial depends on browser; optional native DVB via separately started localhost bridge | New target Pages/site not published; first cache/CDN/OSM connectivity and CSP/permissions must be confirmed; Safari/Firefox do not provide WebUSB |

## Safe clean-build/test plan (pre-migration only)

**A. Current authorized synthetic audit:** On a new isolated branch stacked on PR #100, only test file `tests/test_standalone_independence.py` and this matrix were added. Test Python import/asset closure, manifest/service-worker preload list, HTML local assets, absence of foreign application modules, fallback when Text Center is explicitly mocked absent, and launch the CLI help from a temporary folder containing **only `rf_geolocation_center/`**, with no `PYTHONPATH` or other TIHULU sibling checkouts. No hardware, real USB, network, readsb or packages are invoked. Run existing JS 97 tests and Python native suite on Ubuntu/Windows/macOS in GitHub Actions; **not** real independent installed acceptance.

**B. Future separately authorized clean target clone:** Freeze source SHA, license and destination repo layout; create a fresh VM/user profile with only RFGeo installed. Build and launch from a pinned manifest, inspect Python/JS import graph and HTTP requests for any Text/Flight dependency, and verify offline/no-device map/import/export/NO POSITION FIX with screenshots. Prevent automatic native bridge/Flight/Text connections at cold start.

**C. Future negative integration and storage:** Disable Internet, omit Text 8787 and Flight channel entirely, then add mock providers. With two app instances, test distinct web origins/tabs, port 8794 collision, cross-app receiver claims returning BUSY without takeover, owned DVB scan lease isolation, separate browser storage/cache/uninstall/data hashes, and export/restore of actual user measurements without touching foreign locations.

**D. Future owner-approved installed hardware and shutdown:** Record pre/post processes, FD counts, native RAM and any GPU/VRAM, receiver busy status, external readsb/tar1090/welle/Gqrx uptime, and real USB claimed owner. Trigger Stop RF, Hard Stop, full Quit, delayed read, failed close, tab-crash cases; distinguish app-owned close from foreign services; verify exact data hashes after rollback. PWA crash release is not guaranteed; no global process kill or helper `--release` allowed in the app lifecycle.

**E. Separate destination repository (proposal ONLY, NO FILES CREATED THERE):**

```
Tihulu/tihulu-rf-geolocation-center/     # destination currently empty
  rf_geolocation_center/                  # retain Python package import identity
    __init__.py  __main__.py  native.py  dvb_bridge.py  radio_metadata.py
    index.html  sw.js  manifest.webmanifest
    core/*.mjs  web/*.mjs  web/style.css  web/icon.svg
    scripts/{dvb_scan_linux.sh,usb_prepare_linux.sh}
    docs/  tests/
  README.md  LICENSE  pyproject.toml       # only after approval
  .github/workflows/standalone.yml       # independent CI after approval
  packaging/{linux,windows,macos,pi}/    # native artifacts after approval
```

Define per-platform output, version hashes, EN(default)/TR/DE locale coverage, user-data roots, no implicit Flight/Text requirement, optional companion/versioning/permissions and independent one-line install/update/uninstall/rollback **before any first destination commit**.

## Final source-audit decision

**NO-GO for migration/release/standalone installed sign-off:** All **STAND-01..12 remain OPEN / NOT VERIFIED as installed**, though static import closure, clone-only Python CLI and synthetic lifecycle are testable. Also unresolved: independent native RTL-SDR implementation, no foreign-owner kill (especially the optional privileged USB helper), true browser/PWA offline nested-path acceptance, multi-app leases/port conflicts, versioned optional connectors, cross-platform native installers, archived data protection and REG-05 positioning truth. Do not interpret clean software CI as 12/12 accepted. ETA **unknown**, because real devices, installation artifacts, platform approvals and ground-truth data are not in scope or measured.

**Strict exclusion:** No direct RF/WebUSB, sudo/systemctl, driver changes, Text/Flight edits, user data manipulation, initial destination-repo commit, main merge, Pages deployment, migration, signed build or release occurred in this branch.
