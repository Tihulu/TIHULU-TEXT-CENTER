# STAND-RFGEO-PACKAGING-01 — source-only native installer preparation

**Status:** ISOLATED DRAFT / NOT INSTALLED / NO HARDWARE VERIFIED. **Owner consent:** source-only Linux x64/ARM64 packaging and synthetic install evidence. No production install, release, migration, Text/Flight source edit or destination repository initialization authorized.

## Provenance and exact source tree

- Coordination: [Issue #75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75), [RFGeo Issue #79](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/79), [STAND-01..12 acceptance](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/STANDALONE_APPLICATION_ACCEPTANCE.md).
- Derived from the exact [STAND RFGeo Draft #103](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/103) head `964e7f8eb4abc3e75f25d55a9bf919cac167abdd`, including unchanged REG-05 [#100](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/100) `c1fe9eb477df10309a0281910b43f0402231fed4`, EXIT-01 USB [#97](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/97) `33ba329a4b6af82e7a9f8440e4aa17f037d4ed12`, and owned-resource cleanup [#94](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/94) `772f21e11b510553b481fd483592b11cfcc3d1db`. Original RFGeo source PR #16/history is retained through this stacked lineage.
- All modifications are new `rf_geolocation_center/packaging/**`, `rf_geolocation_center/tests/test_packaging_contract.py`, and this document. Existing `native.py`, browser GNSS/locations, `web/usb_sdr.mjs`, `dvb_bridge.py`, `sw.js`, source assets, original PRs, `main`, and other TIHULU apps are unchanged.
- The planned `Tihulu/tihulu-rf-geolocation-center` destination repository stays **EMPTY**. Nothing was copied, imported or committed there.

## Portable Linux source bundle: what it IS, and what it is NOT

`rf_geolocation_center.packaging` builds a reproducible gzip+USTAR archive named `tihulu-rfgeo-0.1.0-dev-linux-python-any.tar.gz`. It contains a `bin/tihulu-rfgeo` relative source launcher, the five app-owned Python entrypoint/backend files, the exact `native.ASSETS` browser/GNSS/satellite/signal/evidence/map modules and resources, and `package-manifest.json` with per-file SHA-256, size, version, minimum Python and hardware truth flags. Neither `tests/`, `docs/`, the packaging tool itself nor any sibling application is bundled.

The **build does not execute or import** native backend modules, receiver helpers or system commands. All bundle members are regular files: fixed 0 epoch/uid/gid, sorted paths, no symlinks, canonical manifest JSON, and gzip mtime 0. The only executable member is the portable shell launcher (`0755`). Existing `scripts/usb_prepare_linux.sh` and `scripts/dvb_scan_linux.sh` stay **passive text assets with mode `0644`** to preserve source/PWA route compatibility; the packaging/installer planner never invokes them. `usb_prepare_linux.sh --release` may stop readsb or unbind the Linux driver if a person separately invokes it; **automatic invocation is expressly forbidden**.

The bundle runs the *existing* Python 3.11+ stdlib localhost browser launcher and optional, consent-gated Linux DVB bridge. It is **NOT** a compiled .deb/.rpm/AppImage/Flatpak, signed native desktop GUI, native RTL-SDR I/Q GNSS decoder, trusted multisensor position fix, system service, auto-start app, hardware permission broker or a one-line production installer. The app displays original RF/map/position evidence and independent fallback as the source does, not synthetic hardware success.

### Explicit offline preparation commands (development VM only)

From a single RFGeo source checkout, with Python 3.11+ and a pre-existing **scratch** output directory:

```sh
python3 -m rf_geolocation_center.packaging check
python3 -m rf_geolocation_center.packaging build --out-dir /absolute/temporary/artifact-dir
python3 -m rf_geolocation_center.packaging verify --archive /absolute/temporary/artifact-dir/tihulu-rfgeo-0.1.0-dev-linux-python-any.tar.gz
python3 -m rf_geolocation_center.packaging plan \
  --archive /absolute/temporary/artifact-dir/tihulu-rfgeo-0.1.0-dev-linux-python-any.tar.gz \
  --prefix /absolute/dedicated/test-install-prefix --home /absolute/test-user-home
python3 -m rf_geolocation_center.packaging rollback-review \
  --plan-json /absolute/path/to/saved-dry-run.json \
  --prefix /absolute/dedicated/test-install-prefix
```

The CLI has **no `install`, `uninstall`, `migrate`, `start-service`, `unbind-usb`, `takeover-sdr` or device scan command**. Only `build` writes a new archive exclusively into a caller-provided existing scratch directory; it refuses an existing archive. `check`, `verify`, `plan` and `rollback-review` do not write anything. No `PYTHONPATH`, global package install, external app install, network fetch or mandatory localhost Text/Flight service is used. This is installer **preparation**, not a user-facing installer.

`plan` rejects unsafe relative prefixes, symlinked parents, overlaps with reserved user-data roots and any pre-existing package payload file, even if an existing file's name looks like RFGeo. It produces sorted **future created-only file** paths/hashes and user-owned directories that must never be deleted by uninstall. `rollback-review` checks only those exact package paths, marks checksum-changed files **PROTECTED**, and never deletes them. It does not claim to restore or delete installed user files: an actual future, separately approved installer must implement atomic staging, backup, provenance, update locks, rollback execution and OS integration.

### State/data ownership contract (planned paths, NOT runtime migration)

On Linux use application-specific XDG roots, or fallback per user:

| Category | Default planned root |
|---|---|
| Config | `~/.config/tihulu/rf-geolocation-center/` |
| Cache | `~/.cache/tihulu/rf-geolocation-center/` |
| App data | `~/.local/share/tihulu/rf-geolocation-center/` |
| User recordings | `~/.local/share/tihulu/rf-geolocation-center/recordings/` |
| User exports | `~/.local/share/tihulu/rf-geolocation-center/exports/` |
| Reserved model area (no bundled model) | `~/.local/share/tihulu/rf-geolocation-center/models/` |
| Logs | `~/.local/state/tihulu/rf-geolocation-center/logs/` |

Respect absolute `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME` and `XDG_STATE_HOME` overrides. `plan` computes these paths without creating or inspecting them. Actual app version `0.1.0-dev` persists browser settings to namespaced `localStorage`; **this PR does not rewire the existing native/browser runtime** to use those XDG directories, migrate data, replace recordings, modify browser storage or claim a working uninstall. Keep existing browser/backup/recording files intact. A future installer must preserve legacy and custom paths and support non-destructive opt-in discovery.

## Platform and dependency truth matrix

| Target | What is prepared / source-supported | What is NOT accepted |
|---|---|---|
| **Linux x86_64 (Debian/Ubuntu/Pop!_OS)** | Architecture-neutral Python 3.11+ stdlib source tar and relative shell launcher, localhost UI, GNSS file import, map evidence, optional browser Web Serial/WebUSB. `dvbv5-scan` and local DVB frontend **optional and user-initiated** | Native GUI/desktop integration, package manager install/signing, installed SDR/native hardware, physical owner tests, network-free cold PWA boot |
| **Linux aarch64 / Raspberry Pi OS ARM64** | Same pure-Python/JS source archive; no x86 binary bundled | No physical Pi boot/thermal/performance/SDR/Hailo evidence, apt/Pi image artifact, hardware claim/permission test |
| **Windows x64** | Python source and relative browser assets remain theoretically portable; existing Windows CI uses Python 3.11 for launcher tests | POSIX `bin/tihulu-rfgeo` not a Windows executable, no MSIX/installer, WinUSB/USB/driver or Windows-specific data path implementation |
| **macOS ARM64 (Apple Silicon)** | Python source and web UI concept; existing macOS CI runs Python unit/localhost tests | No signed/notarized .app/.dmg, Metal/SDR entitlement, Apple Silicon installation or USB device acceptance |

Python 3.11+ is mandatory for the package launcher; no third-party Python libraries or model weights are installed. `dvbv5-scan`, `/dev/dvb`, regional profiles and Linux OS receiver permission are **optional**, never prerequisites for offline maps/import. Browser WebUSB requires Chromium-like secure context, explicit user click, compatible hardware and exclusive permission. Web Serial requires browser and receiver consent. Flight ADS-B `BroadcastChannel`, Text read-only `127.0.0.1:8787`, RFGeo local DVB `127.0.0.1:8794`, orbital/CDN resources, OSM and online aircraft sources remain **optional**. The native launcher binds loopback only if an operator explicitly launches `serve`; no background daemon.

A pure `receiver_access_preflight()` always returns `may_claim_now:false`; missing consent, unknown/external owner and unverified exclusive lease fail closed. This does not enforce an OS device lease. **No global readsb/tar1090/Gqrx/welle.io shutdown, RTL driver unbind, SDR takeover or source recording deletion is ever performed by the package tooling.** Real physical receiver coexistence must be accepted separately.

## Reproducible synthetic acceptance checks

```sh
python3 -m unittest discover -s rf_geolocation_center/tests -p 'test_*.py' -v
python3 -m unittest rf_geolocation_center.tests.test_packaging_contract -v
node --test rf_geolocation_center/tests/*.test.mjs
```

The synthetic packaging tests verify: equal archive bytes from equal sources; zero timestamps and deterministic paths; the exact Python/web/GNSS/Map/USB/PWA feature asset closure; passive non-executable Linux helper scripts; isolated extraction to `tempfile.TemporaryDirectory` and `python -m rf_geolocation_center --help` with no siblings or PYTHONPATH; Linux XDG path namespaces; zero-write dry-run and rollback review; foreign data sentinel checks; refusal to overwrite, traverse or follow symlinks; tampered manifest/asset refusal; opt-in receiver policy; explicit Windows/macOS/Linux source compatibility truth; and absence of an `install` command.

Existing `.github/workflows/rf-geolocation.yml` already triggers on `rf_geolocation_center/**` and runs Python unittest on Ubuntu/Windows/macOS and Node source tests on Ubuntu. CI is source/synthetic only: no package signing, actual installed UI screenshot, USB/DVB/RTL receiver, physical RAM/FD checks, foreign readsb session or persistent binary installer. Preserve zero regression and evaluate all failures before coordinator acceptance.

## STAND-01..12 gates after this change

| Gate | New evidence | Remaining required installed verification |
|---|---|---|
| STAND-01 | Deterministic archive and temp unpacked single-app launcher | Clean native installed single-target VM and dependency lock/signing |
| STAND-02 | Source launcher CLI and relative shell wrapper smoke in temp | Actual installed UI screenshot, browser/desktop integration |
| STAND-03 | Native allowlist closure, portable namespace, no sibling package | Full deployed origin/optional connector proof |
| STAND-04 | Preserved source/PWA/map/GNSS assets and no-device policy | Real offline browser cold boot and no receiver screenshot |
| STAND-05 | XDG namespaced **planned** roots, per-file SHA manifest and rollback review | Runtime path wiring, install/uninstall+recordings preservation |
| STAND-06 | No foreign app requirements and synthetic two-app independence | Native parallel installed runs and port conflicts |
| STAND-07 | Pure opt-in unknown-owner fail-closed policy; no helpers executed | Real exclusive receiver/BUSY and foreign service survival |
| STAND-08 | EXIT-01 app-owned source preserved; no process/service actions | Actual owned SDR/worker/FD/resource teardown measurements |
| STAND-09 | Flight/Text optional static dependencies retained | Versioned connector OFF/ON and separate-origin acceptance |
| STAND-10 | Archive build, version/hashes and dry-run/rollback contract | Actual .deb/AppImage/installer/icon, update/uninstall, OS signing |
| STAND-11 | Existing SW asset paths retained, bundled shell parity | HTTPS nested path/offline cache update/real PWA smoke |
| STAND-12 | Synthetic test vs real release distinction documented | Independent QA / hardware owner approval |

**Verdict: HOLD — 0/12 independently installed STAND gates signed off.** Archive and mock CI can validate source packaging preparation but never prove real RF positioning, GNSS pseudorange fixes, Gaussian/PSF confidence, verified multi-station TDOA, installed native UI or correct physical USB/resource release. No defendable rollout ETA without separately approved platform/hardware acceptance.
