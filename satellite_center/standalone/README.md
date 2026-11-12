# STAND-SAT-PACKAGING-01 — pinned, isolated native and WebUSB packaging preflight

**Status: DRAFT / SOURCE-AND-MOCKS ONLY / NOT AN INSTALLER.** This directory is deliberately independent from the existing `satellite_center/install/` and Debian packaging scripts. No executable package install, system command, copy, migration, rollback, GitHub Pages deployment, user file edit or hardware operation is performed by the preflight. Owner acceptance of a manifest is **not** acceptance of an installed application.

Tracking: [Satellite Issue #78](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/78), [coordinator #75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75), [STAND-01..12](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/STANDALONE_APPLICATION_ACCEPTANCE.md). Original Satellite Draft [#37](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/37); EXIT-01 native [#92](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/92); WebUSB Edition [#95](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/95); PWA cache [#101](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/101); earlier standalone tests [#104](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/104); Pages atomic manifest [#107](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/107). **No protected head was modified.**

## Two independent deliverables: never silently combine sibling PRs

| Proposed deliverable | Immutable source | What would be included | Acceptance |
| --- | --- | --- | --- |
| Native Qt desktop | [#92 exact commit `4e35bf27abba8a4eee7ac27f9c099ea51ede711c`](https://github.com/Tihulu/TIHULU-TEXT-CENTER/commit/4e35bf27abba8a4eee7ac27f9c099ea51ede711c) | `satellite_center/*.py`, bundled **native snapshot** `browser/**` + `assets/**`, `native_desktop_bridge.js`, `index.html`, README; existing `.deb` builder is separately pinned but NOT copied into installed runtime | **HOLD** on clean installed QtWebEngine/USB, receiver lease, source-only SHA verification of full native browser and historical user data; versioned real installer/rollback absent |
| Chromium WebUSB / PWA | [#101 exact commit `558dcb359b13eedafdc303fa9f321deab9d3ae94`](https://github.com/Tihulu/TIHULU-TEXT-CENTER/commit/558dcb359b13eedafdc303fa9f321deab9d3ae94) | **All 50** audited `satellite_center/browser/*` files in the unchanged [#107 atomic Pages inventory](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/9383c5fb208d345548df53a2b8ee05ffcee4cadf/satellite_center/browser/PAGES_ATOMIC_ASSET_MANIFEST_2026-11-12.json); SW v2, icons, map data, local ESM imports | **HOLD** on live HTTPS staged browser/old-cache update, real WebUSB and screenshot parity. No `gh-pages` deployment |

**Important source fork:** #92 and #95 are sibling changes atop original #37; #101 stacks on #95. The native package must retain its own #92 bundled browser view, while the **separate** WebUSB/PWA package uses the #101 browser view. This preflight does **not** produce a merged native+web UI or verify both under a single installed Qt profile. A later separate authorized, conflict-reviewed combination and CI is mandatory before claiming a unified deliverable.

### Files in this Draft PR

- `native_desktop_manifest.json`: exact #92 SHA plus **32 individually measured Git blob SHA-1** for native entrypoints, key modules, assets and Debian builder; dynamic pinned-Git-tree enumeration includes *every* extra `satellite_center/*.py`, `browser/**` and `assets/**` file, rather than silently losing source.
- `webusb_pwa_manifest.json`: exact #101 SHA and #107 inventory blob hash. Static publication inventory contains all **50** individual Git SHA pairs #95/#101 and old `gh-pages`, strict 31-file classification and 50-order copy stages.
- `rollback_policy.json`: protected installed/data/foreign roots, no wildcard deletions, no shared service/receiver kill, only manifest-owned old code restore after approval.
- `preflight.py`: **read-only** Python standard-library SHA-pinned verifier and plan emitter. It checks existing Git checkout HEAD, clean tree, all Git tree blob IDs, actual file bytes, symlinks, directory escapes, nonregular modes and critical files; no fetch, external app import, Qt/USB, shell install, package output, file copy or data deletion.
- `tests/test_satellite_standalone_packaging.py`: independent mock/negative source contracts, 50-asset validation, no-Text roots and rollback rules.

## Read-only dry run: commands for a **future reviewer** (not executed here)

Both input directories must be **preexisting, clean, top-level, independent Git worktrees**, each at its exact pinned Git commit. The preflight does not download, initialize or update either of them.

```bash
# Run in the NEW review branch with the exact committed manifests.
python3 -m satellite_center.standalone.preflight \
  --mode native --source-root /path/to/already-existing-clean-PR92-checkout

python3 -m satellite_center.standalone.preflight \
  --mode webusb --source-root /path/to/already-existing-clean-PR101-checkout
```

The stdout contains an independent `tihulu-stand-sat-dry-run-plan-v1` JSON object for each profile: a verified file-by-file Git blob/size list and **future-only** stage plan + bounded rollback ownership rules. A head mismatch, dirty checkout, missing file, changed byte, extra unexpected source mode, absent ESM, stale Pages index or escaped symlink returns **STAND-SAT HOLD**, exit 2. It has **no `--install`, `--uninstall`, `--merge` or `--publish` functionality**. The command does not claim an output installer. No real user machine or radio tools were accessed in this task.

The expected manifest-generated plan is source-independent of all other TIHULU applications: it selects *only* `satellite_center/**`, not `textcenter/`, TV, Media, Flight, RFGeo, AI Tools or Survival Kit; no mandatory process/server, model path or shared Python package is staged. Guarded optional Text imports remain in native source and are tested separately in Draft #104. **The existing Linux cooperative SDR lock lives in `~/.local/share/tihulu-text-center/.receiver-locks`; it must NOT be moved, unlinked or silently forked** until owner-approved cross-app shared lease design and busy-device tests. Simply using a separate Satellite-only lock could allow competing receivers.

## Correct profiles and paths, without migration

| Platform | Native Qt | WebUSB/PWA | Install/recordings/cache policy |
| --- | --- | --- | --- |
| Debian 12 / Ubuntu / Pop!_OS x64 | Existing `dpkg-deb` source and no-USB Debian loopback CI; QtWebEngine + NumPy + Skyfield and RTL-SDR tools declared in system package. **Not accepted as installed real receiver.** User-local script still lacks PyQtWebEngine. | Chromium HTTPS with user gesture; no Linux driver unbind or global readsb stop | Code `/usr/share/tihulu-satellite-center/` or user-local `~/.local/share/tihulu-satellite-center-app`; settings + captures `~/.local/share/tihulu-satellite-center`; OSM cache `~/.cache/tihulu-satellite-center` |
| Linux ARM64 / Pi OS | Ubuntu ARM64 source runtime CI is green. Pi OS QtWebEngine, SD/RAM/CPU, RTL-SDR permission and actual Pi build NOT proven | Chromium/WebUSB on ARM64 NOT accepted on Pi | Same app-prefixed settings/recordings; never take ownership of Text's shared lock |
| Windows x64 | **Missing native Qt installer:** existing `install.ps1` starts the `127.0.0.1:8791` companion and only installs Skyfield, not Qt desktop | Chromium may require user-administered WinUSB; browser alone cannot change OS drivers | Code `%LOCALAPPDATA%\Tihulu\SatelliteCenterApp`; settings `%LOCALAPPDATA%\Tihulu\SatelliteCenter` — independently protected |
| macOS Apple Silicon | **Missing signed native app bundle**: current user-local script lacks PyQtWebEngine; macOS portable source CI ≠ installed signed Qt support | Chromium may provide HTTPS WebUSB; real USB permission unverified | Settings `~/Library/Application Support/TihuluSatelliteCenter`; cache only under Satellite-owned paths |

No Raspberry Pi NPU/AI HAT+, Hailo, Windows/macOS RTL device or NVIDIA CUDA path is certified by these manifests. Optional CuPy/OpenVINO/AI acceleration may only be displayed when an independently verified backend supports it.

## Mandatory preserved feature and receiver contracts

Preserve existing pass planner/TLE import and cached data, Natural Earth and optional OSM tiles, station location, real IQ/CU8 capture, derived WAV, both-mode recording, Robot36 SSTV, Meteor IQ LRPT/SatDump integration, APRS, spectrum/waterfall, native pass scheduling, playback/archive, automatic decode **only when real input is available**, and all previously saved user recordings and schedules. **Source-only presence is not real hardware acceptance.**

- Native capture `1.024/2.048 MS/s`, up to ~900s / 2,000,000,000-byte raw-IQ cap when supported; **REG-06 still open** because the native SatDump decoder passes a fixed `--samplerate 1024000` even if a file was recorded at 2048000.
- Browser memory raw CU8 capped **128 MiB**; simple schedule segments ≤60s (≤32s at 2.048 MS/s), planned 6s interpart gaps; opted-in foreground streaming is conditional on File System Access and separately capped 2GB/900s. No claim of gap-free Meteor LRPT or a verified image.
- Native receiver is on-demand. On busy/unverified device state: **fail closed**. Stop/Quit kills/reaps only verified app-owned children and releases only its own device leases; never sends `systemctl stop`, kills foreign `readsb`/`tar1090`, unbinds external SDR or deletes shared lock files. EXIT-01 #92 has synthetic Quit tests, **real process/device memory measurements still missing**.
- WebUSB independently needs HTTPS Chromium permission; it must not use native Linux SDR or start a localhost service; worker v2 caches only the audited app shell, never RF data, custom recordings or third-party APIs. Browser `pagehide` cleanup is best effort.
- Text/Media/Flight/RFGeo/AI Tools/Survival Kit integration is OPTIONAL and never a package dependency. Fresh no-other-app VM is a later acceptance gate, not executed here.

## Rollback / uninstall safeguards (NO operations performed)

Before future authorized installation: archive a SHA-256 inventory of current app-owned *installed code* and separately checksum all **unchanged** captures, TLE, schedules, user profiles, paired browser storage and foreign app fixtures. On rollback restore only an exact previous package-owned code/launcher manifest, never a broad directory delete. **Always preserve** `captures/`, `*.cu8`, `*.wav`, `*.png`, `*.tle`, `schedule.json`, `hardware.json`, `pages-pairing.key`, `user_downlinks.json`, custom external SSD, `~/.cache/tihulu-satellite-center`, other TIHULU data and the shared cooperative lock. Do not touch non-Satellite .desktop entries. `rollback_policy.json` is a policy record, **not** an executable uninstaller. Recover an owned PWA service worker only within its exact Satellite scope and after owned capture is stopped; never clear all origin data.

## Publication HOLD — retain the 50-asset Pages gate untouched

[#107 exact manifest](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/9383c5fb208d345548df53a2b8ee05ffcee4cadf/satellite_center/browser/PAGES_ATOMIC_ASSET_MANIFEST_2026-11-12.json) compares source #101 against pinned `gh-pages` `854b1109c04c5f8e9a22d1ee3bb999a16d9d4b7d`: **33 matching, nine different, eight absent**. Existing strict `scripts/verify_satellite_pages_bundle.py` covers 31 assets; the other 19 still require independent hashes/path checks. Keep strict parity **RED** before release; do not waive, skip, alter checker, deploy or publish. Future release would need a separate owner-approved Pages PR, one atomic Git commit and scoped SW v1→v2 cache validation and rollback.

## Exact future clean-install smoke plan, NOT EXECUTED

1. Verify two pinned clean source roots and new manifests using this read-only tool; produce independent file-size/SHA-256 reproducibility and source-closure proof. No Text Center checkout on `PYTHONPATH`.
2. In an **authorized future** disposable OS VM, install ONLY Satellite binary/package into owner-approved paths. Leave all other TIHULU apps absent. Start native Qt and fallback Widgets with USB disconnected: verify pass planner/cached TLE, map, ISS Robot36 WAV import, local SSTV capture archive and Stop/Quit. Never make physical RF acceptance claims from source CI alone.
3. Run WebUSB/PWA alone on staging HTTPS origin (not published Pages): 50 asset integrity and MIME, all four sections/three-step UI, no localhost dependency, EN(default)/TR/DE labels, responsive native screenshot review and browser fallback. Simulate WebUSB busy/connect cancellation and SW v1→v2/offline behavior.
4. With synthetic foreign `readsb`, `tar1090` and another app-owned data/receiver file, verify NO foreign service stop, no unauthorized schedule restart and owned-only bounded Quit. Real physical SDR is separately owner-run only.
5. Future authorized versioned upgrade/uninstall/rollback must checksum pre/post user and foreign files and prove recordings/TLE/maps unchanged. Submit independent QA to #78/#75. Keep destination repo empty and all original Draft PRs protected until explicitly approved.

**Remaining blocker summary:** native #92 + web #101 combined integration not executed; default QtWebEngine missing from user-local installer; Windows and macOS native packaging absent; Pi installed support absent; legacy shared SDR lock namespace unresolved; REG-06 rate mismatch; no real USB/SatDump/cleanup evidence; Pages parity still red; no destination repo release or approved data migration. Status = **HOLD**, ETA unknown.
