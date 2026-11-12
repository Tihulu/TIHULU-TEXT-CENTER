# Satellite Center WebUSB / PWA UI recovery — owner screenshot acceptance

**Date:** 2026-11-12
**Request:** Restore the reported broken public Satellite Center web UI and make it visually/functionally equivalent to the owner's 0.3.0 preview10 native-Qt screenshot, with **WebUSB** instead of Linux native receiver calls.
**Priority:** P0 owner-requested website repair; separate from EXIT-01 source shutdown.
**Current state:** OWNED WEB BRANCH EXISTS but no source delta verified at coordinator checkpoint; **NOT IMPLEMENTED / NOT TESTED / NOT DEPLOYED**.
**Work branch:** `feature/satellite-webusb-ui-parity-2026-11-12` in `Tihulu/TIHULU-TEXT-CENTER`, forked from original Satellite PR #37 head `670e0ddcf029c8fcc9b0cef403bf76cf37613fcb`; compare returned 0 ahead, 0 behind and 0 files at checkpoint.
**Source-only reference:** original Draft [#37](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/37), branch `fix/satellite-native-scheduler-modes-2026-11-08`.
**Immutable separate native/EXIT-01 scope:** native shutdown Draft [#92](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/92); the web worker may READ native source as reference but must NOT change `satellite_center/__main__.py`, `desktop.py`, `native_web_shell.py`, or #92.
**Tracker:** [Satellite Issue #78](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/78) and [central #75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75).

## Actual baseline inspected, not presumed broken for one specific reason

- The native screenshot already visually resembles the `satellite_center/browser/index.html` HTML: dark navy header, blue logo, headline and preview badge, four-tab navigation, a capabilities strip, a three-step Auto-Capture & Decode card, ISS WAV/CU8 checkboxes, and four action buttons.
- Browser-source banner currently says **Web / PWA 0.3.0 preview6** vs screenshot's **Native desktop 0.3.0 preview10**. Their runtime capabilities differ: do **not** cosmetically label the website as a tested preview10 native or copy text saying Linux native SDR into WebUSB mode. Keep separate, accurate runtime status.
- The existing WebUSB page has real driver permissions and USB lifecycle code, `browser.js`, `auto_reception_ui.mjs`, `usb_diagnostics.mjs`, recording-file workflow, TLE maps, saved-file analysis and cached/offline assets. Start by locating **specific** current website failure (network/asset/cache JS runtime, import path, broken DOM event, duplicate/obsolete assets, release drift) via deterministic repro. Do not rewrite the entire page or fabricate device samples.
- Publishing parity CI checks bytes of a source-selected list against `gh-pages`; previous runs identified eight different source files, **not necessarily the cause of broken UI**: `index.html`, `auto_mission.mjs`, `auto_reception_ui.mjs`, `browser.js`, `browser.css`, `location_search.mjs`, `satellite_maps.mjs`, `compute_selector.mjs`. Keep this gate honest.
- Existing `capture_duration.mjs` supports **128 MiB memory IQ cap**, default 60-second browser clips for simple flow, and **optional explicit foreground Chromium File System Access disk streaming** with up to **2,000,000,000 bytes / 900 seconds** subject to rate and format. Do **not** erase that capability based solely on old UI prose that says every WebUSB part is 60 seconds. Validate disk-stream lifecycle, backpressure, file picker permissions, run-time and no-memory-overflow before advertising any >60-second success; otherwise offer safe 60-second segments and accurate discontinuity notes. Distinguish 1.024 vs 2.048 MS/s budgets.
- Original page warns no verified RF from TLE, no guaranteed ISS SSTV, no full Meteor LRPT from brief browser snippets, no WebUSB in Firefox/Safari. These scientific/safety limitations must remain visible.

## Screenshot-derived design contract

**Desktop screenshot canvas:** ~1350 x 900 with a dark navy page, a hero header, pill preview badge, intro, optional local receiver link, then four blue-tab navigation controls. Capability/status info strip below navigation; main card with heading **Satellite Auto-Capture & Decode — three steps**. Fields: Auto-target group, Auto capture length, Length unit, Recording goal. A bordered **ISS recording files — choose WAV, CU8, or BOTH** area contains 2 checkboxes, separate data-file explanation and 4 horizontally arranged steps: 1. Schedule RF passes, 2. Analyze Recordings, 3. Extract Results, Cancel native auto-jobs.

**Web adaptation:** Mirror layout/hierarchy/spacing/icon/color and functional states, but use truthful **Web / PWA / WebUSB** labels and `Schedule WebUSB capture` / `Cancel web-owned jobs` text, not `direct native OS SDR`, `native app` or WebChannel. Keep existing ISO/local time zone handling and short/long segment semantics. On mobile controls stack safely, no horizontal overflow; disabled states, keyboard focus and screen-reader status remain usable.

**Navigation destinations to preserve:** `index.html` Receiver & planner, `reception.html` Satellite Images & Data, `#satellite-tracking-maps` Earth / Sky, `#iq-analysis` Signal analysis. No dead anchors/assets, no duplicate event listeners, no broken URL with nested GitHub Pages base path.

## Runtime / hardware contract

| Runtime | RF transport | User-visible capability |
|---|---|---|
| Installed native Qt (existing) | Native Station/rtl_sdr through Qt WebChannel or direct native helpers | Separate native owner. Web worker reads but must not modify it. |
| Hosted HTTPS web / PWA in supported Chromium | **Permission-gated WebUSB RTL-SDR** after a direct user gesture; site context secure | Real IQ only after device claim + sample read, truthful signal/no-signal diagnostics. Do not silently call local native server. |
| Firefox/Safari / missing WebUSB | No direct USB access | Pass planner, sky maps, offline file inspection, downloaded archives; clear support note. |
| Optional user-started localhost companion | Explicit separate opt-in and owned lifecycle | Should remain optional; hosted website must work with its own WebUSB without `http://127.0.0.1:8791`. |

**Safety:** Never use `sudo`, `modprobe`, driver unbind, global `pkill` or `systemctl stop` to get USB; never shut down a borrowed readsb/tar1090/Gqrx/welle.io service; do not force a WebUSB claim while another program owns the tuner. WebUSB device selection is voluntary, by gesture. Closing browser/tab is best-effort, **not guaranteed**. The page has explicit Cancel, Stop, Disconnect; after STOPPING, block late device admission or capture callbacks. Mark incomplete release honestly; preserve data and external owners.

## Website repair / WebUSB evidence checklist (all OPEN)

| Test | Required proof before deployment |
|---|---|
| WEB-01 | Screenshot-relative desktop view matches hierarchy; page identifies itself as WebUSB, not native |
| WEB-02 | Responsive tablet/mobile navigation and controls do not overflow; four tabs navigate correctly |
| WEB-03 | HTTPS GitHub Pages nested base-path loads every referenced JS/CSS/icon/manifest and dynamic import, no 404 or runtime exception |
| WEB-04 | Real browser console/navigation smoke: no syntax/import/DOM errors on first and repeat load |
| WEB-05 | PWA install/offline shell and service-worker cache update recover stale bundles while preserving settings |
| WEB-06 | Unsupported browser shows planner/map/file analysis without offering fake USB access |
| WEB-07 | WebUSB chooser permission cancellation, denied access, driver-busy/claim errors have distinct actionable status, no OS changes |
| WEB-08 | Mock device open/claim/tune/read/release validates bytes from actual mock read, no sample fabrication, no false pass-transmission assertions |
| WEB-09 | WAV/CU8/BOTH record selections produce only truly supported output paths; no fake Robot36/APRS/Meteor image |
| WEB-10 | Memory capture <=128 MiB, short capture <=60 seconds per simple segment; optional explicitly tested disk streaming limits <=2 GB and <=900s, rate-specific |
| WEB-11 | Device Disconnect/Hard Stop/Cancel and Start-Quit races leave zero browser-owned workers/interfaces, with truthful browser-close limitations |
| WEB-12 | Separate native Qt source and EXIT-01 PR #92 untouched; external SDR services and user IQ/WAV/data remain unchanged |
| WEB-13 | Eight differing source/Pages assets are identified with exact SHA and minimal semantic delta; no parity-test suppression |
| WEB-14 | Browser UI PR has its own Draft branch from original #37, scoped to `satellite_center/browser/**` + browser-only tests/docs |
| WEB-15 | CI names, run URLs, passing/failing jobs and a safe *proposed* publishing plan documented; no actual deployment |

**Acceptance count: 0/15 WEB items independently verified at this checkpoint**. The agent's new feature-branch creation is not a completed feature or successful preview. UX screenshot matching cannot prove RF works. A later **explicit owner approval** is required for gh-pages publish, not implied by this document.

## Handoff order

1. Reproduce actual live website issue on static preview/PR build; record precise console/network failure and screenshot before fixes.
2. Patch browser-only source. Preserve native reference data and approved scope.
3. Verify deterministic browser mock CI, PWA asset fetches, WebUSB secure-context/manual user-gesture gating, capture budgets, data preservation and no-foreign-owner kills.
4. Prepare screenshots desktop/tablet/mobile of the repaired browser page and compare to native screenshot. Explain intentional runtime-label differences.
5. Open **new stacked Draft PR**, publish **no** site. Report PR/CI + exact hash parity evidence to Issue #78 referencing #75.
6. QA separately signs WEB-01..15, and the owner makes a later publication decision.

**Project-wide:** existing RQ-098/EXIT-01 installed RAM/VRAM/SDR acceptance **0/15** and original 17 broad release gates still open; this new website task cannot quietly close them.
