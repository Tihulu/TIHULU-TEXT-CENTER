# Workstream 02 — Flight Radar — Audit Only

**Designated GitHub issue:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/77  
**Central coordination:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75  
**Dedicated branch:** `audit/ws02-flight-standalone-2026-11-11`  
**Dedicated scope root:** `apps/_coordination/workstreams/02/`  
**Source of truth:** `Tihulu/tihulu-flight-radar`  
**Auditor status:** NOT STARTED (branch and draft planning task prepared by coordinator; no independent conversation is running).

## Guardrails: non-negotiable
- The owner requested **NO CHANGES to any currently working program feature, behavior, setting, device lifecycle, native installer, model, icon, saved data or user-visible interface**. This branch is **documentation and read-only test-planning only**.
- Do not merge, rebase, cherry-pick or close old Draft PRs; do not commit to `main`; do not initialize the three empty user-created app repositories; do not rename original repos or assume GitHub Pages redirects automatically.
- ALL coding-agent instructions, GitHub messages, source and technical documentation **English**. End-user GUI must support `en` default, `tr`, `de`; user may prefer Turkish conversation.
- The only approved badges are the original FIVE user-approved red-black-white TIHULU mascot logos. Do not change current runtime icons or claim PNGs are fully vector SVGs.
- Use original GitHub numeric ID and full PR/Issue permalinks for all migrated history, report missing review/comment bodies instead of inventing or copying confidential chats.
- Re-check full `apps/_coordination/MASTER_REQUIREMENTS.json` and `REQUIREMENT_SOURCE_TEST_CANDIDATES.json` on parent coordinator branch before claiming completeness. A source file candidate is NOT proof of the requested implementation and a listed test file is NOT proof of execution.
- Do not modify any other workstream's root and do not edit coordinator-owned `MASTER_REQUIREMENTS.json`, `PROGRESS.json`, `ISSUES.json`, source history or canonical topology. Cross-workstream dependencies go to the other worker's Issue and central #75.

## Specific first tasks
Canonical Flight Radar code lives in its OWN repo; this workstream branch in Text Center contains audit REPORTS ONLY. Do not edit its canonical source or PR #7/#13. Audit its standalone CLAUDE/DeepSeek and matrices, and old PR #13 original eight comment URLs, source revision of TWO Pages sites and future original repo rename.

1. Inspect all assigned requirement IDs below **against exact pinned code and candidate tests**, then source branch head differences and user-request provenance.
2. For each ID write one evidence row: `requested | draft-coded | unit-verified | hardware-verified | released | unknown`; link exact source SHA/line, exact test SHA/command/result or missing evidence. Distinguish source-only/fixture/synthetic/live receiver tests.
3. List a non-destructive regression test for every current behavior, proposed new behavior, any 3-language UI gaps and native release/rollback boundaries. Do not run invasive hardware tests automatically.
4. Record missing tests, dependencies, 3+ application preservation constraints, PR ancestry, history links and any other blocked worker Issue.
5. Add `REPORT.md` and `EVIDENCE.json` **only under this branch-owned `workstreams/02/`**. Use Draft PR comments and Issue #77 to communicate (other agents do not share chat memory).
6. Report progress as source-backed counts; estimate hours/minutes **only after** you have audited work sizes and assumptions. Until then, ETA is explicitly unknown.

## Assigned requirement IDs (17)
- **FLIGHT-001** (P0): Keep genuine ADS-B/Mode-S via readsb and optional internet, with I/R/I-R attribution and per-ICAO deduplication.
- **FLIGHT-002** (P0): Keep internet providers separate (adsb.lol, adsb.fi, OpenSky and policy-gated sources) with independent layer selection and rate limits.
- **FLIGHT-003** (P0): Use the real upstream tar1090 view and license attribution, not a lookalike; function even without antenna with real internet traffic.
- **FLIGHT-004** (P1): Keep Köln default, map drag, nearest-aircraft focus, receiver focus, fit/follow, icons, legends, mobile list and popups.
- **FLIGHT-005** (P1): Provide genuine departure/arrival route, origin/destination/time when a verified radio or internet source supplies it; unknown otherwise.
- **FLIGHT-006** (P1): Show separate Radio Load and Internet Load, receiver/pairing status and correct hard stop semantics; do not claim SD R when missing.
- **FLIGHT-007** (P1): Preserve geographic country/region/city search DE/TR and saved location/manual coordinates, with offline fallback.
- **FLIGHT-008** (P1): Keep aircraft detail overlays, multiple selected model layers, natural resize, controls not covering overlays.
- **FLIGHT-009** (P0): RF On enables/disables localization only, not ADS-B/Internet tracking; optional Location Circles default on with RF.
- **FLIGHT-010** (P0): Keep independent Aircraft/Location/LIVE Fit/BEST Fit circles, persistence/recomputation and explicitly labeled uncertainty.
- **FLIGHT-011** (P0): Use true received packets and honest horizon/PSF/Gaussian bounds; do not invent precise TOA/MLAT location from one SDR.
- **FLIGHT-012** (P1): Keep incremental bounded History, cache and performance limits, original evidence timestamps.
- **FLIGHT-013** (P0): Protect legacy/v0.3.1 and current releases, pinned versions and one-line restore path; reconcile open Draft PR #7 and #13.
- **FLIGHT-014** (P0): Keep native RTL-SDR/readsb separate from optional browser WebUSB and never stop externally managed services.
- **FLIGHT-015** (P0): Keep canonical standalone Pages and Text Center-generated mirror in source-SHA sync; verify both after any rename.
- **FLIGHT-016** (P0): Add feature/component/model/developer-agent matrices, root CLAUDE.md and DeepSeek guide to Flight Radar's own repo.
- **FLIGHT-017** (P0): Carry own PR history plus original Text Center source links and history gaps by immutable GitHub repository IDs.

## Initial source/test candidates — existence only

| Requirement | Existing candidate code | Candidate test source | Verification |
|---|---|---|---|
| `FLIGHT-001` | `tihulu_flight_radar/core.py`, `tihulu_flight_radar/web/adsb_worker.mjs` | `tests/browser_adsb.test.cjs`, `tests/test_core.py` | Not verified |
| `FLIGHT-002` | `tihulu_flight_radar/network_sources.py`, `tihulu_flight_radar/web/multi_sources.js` | `tests/test_multi_sources.py`, `tests/multi_sources.test.cjs` | Not verified |
| `FLIGHT-003` | `scripts/build-web-tar1090.sh`, `tihulu_flight_radar/web/tar1090-adapter.js` | `tests/tar_full_browser.test.cjs`, `tests/pages_tar.test.cjs` | Not verified |
| `FLIGHT-004` | `tihulu_flight_radar/web/app.js`, `tihulu_flight_radar/map_focus.js` | `tests/map_focus.test.cjs`, `tests/test_tar_focus_sdr_exit.py` | Not verified |
| `FLIGHT-005` | `tihulu_flight_radar/web/app.js`, `tihulu_flight_radar/web/multi_sources.js` | `tests/aircraft_popup_rf_coverage.test.cjs` | Not verified |
| `FLIGHT-006` | `tihulu_flight_radar/control.py`, `tihulu_flight_radar/native.py` | `tests/test_control.py`, `tests/test_tar_focus_sdr_exit.py` | Not verified |
| `FLIGHT-007` | `tihulu_flight_radar/web/location_search.mjs`, `tihulu_flight_radar/web/flight_location_ui.mjs` | `tests/location_selector.test.cjs`, `tests/test_search_location.py` | Not verified |
| `FLIGHT-008` | `tihulu_flight_radar/web/app.js`, `tihulu_flight_radar/web/style.css` | `tests/aircraft_visuals.test.cjs`, `tests/tar_layers_regression.test.cjs` | Not verified |
| `FLIGHT-009` | `tihulu_flight_radar/web/receiver_coverage.js`, `tihulu_flight_radar/web/rf_timing_lab.js` | `tests/aircraft_popup_rf_coverage.test.cjs`, `tests/rf_timing_lab.test.cjs` | Not verified |
| `FLIGHT-010` | `tihulu_flight_radar/web/receiver_coverage.js`, `tihulu_flight_radar/web/app.js` | `tests/aircraft_popup_rf_coverage.test.cjs` | Not verified |
| `FLIGHT-011` | `tihulu_flight_radar/web/rf_timing_lab.js`, `tihulu_flight_radar/web/receiver_coverage.js` | `tests/rf_timing_lab.test.cjs` | Not verified |
| `FLIGHT-012` | `tihulu_flight_radar/web/rf_timing_lab.js`, `tihulu_flight_radar/web/app.js` | `tests/rf_timing_lab.test.cjs` | Not verified |
| `FLIGHT-013` | `scripts/popos-version-switch.sh`, `scripts/install-linux.sh` | `tests/test_version_switch.py`, `tests/test_linux_installer.py` | Not verified |
| `FLIGHT-014` | `tihulu_flight_radar/control.py`, `tihulu_flight_radar/web/browser_usb.mjs` | `tests/test_control.py`, `tests/webusb_sampleblock.test.cjs` | Not verified |
| `FLIGHT-015` | `docs/DUAL_GITHUB_PAGES.md`, `.github/workflows/pages.yml` | `tests/release_main.test.cjs`, `tests/pages_tar.test.cjs` | Not verified |
| `FLIGHT-016` | `AGENTS.md`, `docs/FEATURE_PARITY_AND_SURVIVAL_KIT_GATE.md` | **MISSING TEST CANDIDATE** | Not verified |
| `FLIGHT-017` | `AGENTS.md`, `docs/SURVIVAL_KIT_FLIGHT_RADAR_HANDOFF_2026-11-05.md` | **MISSING TEST CANDIDATE** | Not verified |

## Existing audit and coordination documents
- [Master Plan](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/MASTER_PLAN.md)
- [97 requirements](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/MASTER_REQUIREMENTS.json)
- [Candidate mapping](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/REQUIREMENT_SOURCE_TEST_CANDIDATES.json)
- [Early ancestry audit](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/PR_ANCESTRY_AUDIT.json)
- [Test-quality categories](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/TEST_EVIDENCE_QUALITY.md)
- [Original history audit](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/PR_COMMENT_LINK_INDEX.json)
- [Protocol](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/COORDINATION_PROTOCOL.md)

## Completion report format
```md
Audit completion: <audited IDs>/17
Implementation verified: <n>; source-only/draft: <n>; unknown: <n>
Tests checked: <n>; executed with evidence: <n>; hardware tests: <n>
Missing test cases / review-comment archives: <links>
Exact source refs: <SHAs and file links>
Cross-team handoffs: <issue links>
Estimated remaining work: <HHh MMm + assumptions, or unknown>
Safety: 0 active program/installer/device/feature changes; 0 unapproved merges.
```
