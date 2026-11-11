# Workstream 02 — Flight Radar source, test and preservation audit

**Scope:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/84 · [Worker Issue #77](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/77) · [Central Issue #75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75)  
**Worker-owned branch:** `audit/ws02-flight-standalone-2026-11-11`  
**Deliverables:** this `REPORT.md` and sibling [`EVIDENCE.json`](./EVIDENCE.json) only.  
**Audit boundary:** read-only GitHub source/test/PR/CI/Pages-branch inspection; **no worker-executed tests, releases, installers, runtime changes, SDR acquisition, merges or migrations**. Engineering documentation is English; all five user interfaces target **EN (default), TR, DE**.

## Executive result

- **17/17 assigned requirement IDs inspected and evidence-indexed**, against exact immutable repository commits and source/test lines. This is **not** 17 implemented features or 17 acceptance passes.
- Flight Radar is already independently canonical at `Tihulu/tihulu-flight-radar` (numeric repository ID **1447534043**), `main` SHA `059b391280635d9aa4d2ac73c7318af9e135ebf5`. Text Center stays canonical at `Tihulu/TIHULU-TEXT-CENTER` (numeric ID **1447637221**). Neither repository was modified in this audit.
- **15/17** requirements have at least one inspected existing test *candidate*; **FLIGHT-016 and FLIGHT-017 have none**. Tests inspected are source/static assertions, fixtures, synthetics and mocked lifecycles, not a physical NooElec receiver acceptance run.
- **0 new worker test executions; 0 verified device tests; 0 installed-version acceptance proofs.** Existing GitHub Actions jobs are reported separately, not misrepresented as new execution.
- **Draft PR #7 and #13 remain unmerged.** Draft #13 is 316 commits ahead of canonical main and changes 44 files. Draft #7 changes 5 files, but diverged from current main (10 ahead / 485 behind at comparison time). They share zero identical changed paths; **semantic and lifecycle conflict clearance is NOT established**.
- **Seven inspected published Git blob pairs match** between standalone and Text Center-mirror `gh-pages` trees (including `index.html`, `app.js`, `sw.js` and `adsb_worker.mjs`). Both revision stamps point to main SHA `059b391280635d9aa4d2ac73c7318af9e135ebf5`. This is repository publication parity **only**, not live URL, CDN cache or PWA validation.
- **Remaining work estimate: unknown.** Inventory, external API terms, device access, cross-platform and release gates prevent defensible HH:MM until the coordinator establishes acceptance workload and test environment.

## Critical preservation findings

### P0-A: RF model minimum changed between main and Draft #13

Current `main` [`web/receiver_coverage.js` L89–L95](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/web/receiver_coverage.js#L89-L95) allows a modeled candidate region when **three** genuinely RF-sourced ICAOs are available. The [main test](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/aircraft_popup_rf_coverage.test.cjs#L33-L47) also positively asserts that three aircraft can yield a region. Draft #13 [`rf_history_models.js` L7–L38](https://github.com/Tihulu/tihulu-flight-radar/blob/950f8278a625ce13a9a3c7e21bf9bf76d4b5888e/tihulu_flight_radar/web/rf_history_models.js#L7-L38) demands **four distinct ICAOs** and adds five model types: LIVE 10-minute, variable LIVE, BEST session, HISTORY and HISTORY BEST. Therefore, the requested four-aircraft/five-model acceptance is **not equivalent to current main behavior**. Do not silently replace main, claim a released fix, or report a centroid as a GPS measurement.

### P0-B: Existing main receiver-close permission is not ownership tracking

The [current main `control.py` close path](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/control.py#L233-L262) can stop a previously active shared `readsb.service` when `release_local_service=True`. That explicit preference is distinct from “stop only what this application started.” Draft #7 [reworked close path](https://github.com/Tihulu/tihulu-flight-radar/blob/4ef8245b87fc78cec6cc4f5f9043d68e08cf45d3/tihulu_flight_radar/control.py#L230-L263) tracks app-started service ownership, avoids stopping pre-existing readsb on exit and requires a carefully scoped sudoers policy. It has not been merged. Confirm user-controlled explicit Stop, automatic close, failed sudo, tar1090 service independence and other SDR app ownership on a real Pop!_OS host **before** approving any lifecycle change. Do not change `readsb` or `tar1090` as part of this audit.

### P0-C: Do not promote Draft #13 aircraft/UI/history work into released status

Source files exclusive to the pinned Draft #13 include `flight_route_lookup.py`, `flight_journey.js`, `flight_journey_ui.js`, `rf_history_models.js`, `rf_history_client.js`, `rf_history_ui.js`, `rf_history_store.py`, `offline_maps.py`, `aircraft_panel_resize.js` and `map_motion.js`. Their presence plus green draft CI is evidence of a **draft-coded candidate**, not a published feature or device acceptance. Route lookup requires real provider provenance; adsbdb callsign origin/destination does **not** prove flight-specific timetable. The RF history heuristics are geometric bounds, **not measured PSF/MLAT range, confidence or single-SDR GPS**.

### P0-D: Independent developer contracts and historical provenance are not yet canonical

Canonical main contains substantive [`AGENTS.md`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/AGENTS.md#L1-L78) and [feature-parity guidance](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/docs/FEATURE_PARITY_AND_SURVIVAL_KIT_GATE.md#L1-L54) but lacks the following independent files:

```
CLAUDE.md
DEEPSEEK_START.md
DEVELOPMENT_AGENT_GUIDE.md
architecture/FEATURE_MATRIX.json
architecture/COMPONENT_MATRIX.json
architecture/MODEL_MATRIX.json
architecture/DEVELOPMENT_AGENT_MATRIX.json
history/ORIGIN_LINK_MAP.json
history/TRANSFER_GAPS.json
```

The coordinator's copy of `apps/flight-radar/ORIGIN_FALLBACKS.json` **does not install** these files into the independent Flight repo. A separately approved **documentation-only Flight-repository PR** should ultimately add feature/component/model/developer matrices with source/test paths, EN/TR/DE coverage and accurate agent navigation for Claude Code and DeepSeek; no additional installed AI model is required merely to read instructions. Keep old original repo IDs and permalinks, export permitted review/comment evidence with explicit gaps; never fabricate approvals or copy private conversations.

## Source traceability by requirement

Evidence links below are pinned to **exact commit SHAs and line ranges**; each test link identifies inspected test *source*, not an automatically asserted acceptance result. The full structured file records all additional refs and per-ID gaps.

| Requirement | Present state / preservation distinction | Source anchor | Test source |
|---|---|---|---|
| `FLIGHT-001` | Main source: partial | [`core.py` lines 24–75](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/core.py#L24-L75) | [`browser_adsb.test.cjs`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/browser_adsb.test.cjs#L16-L36) |
| `FLIGHT-002` | Main source: partial | [`network_sources.py` lines 18–35](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/network_sources.py#L18-L35) | [`test_multi_sources.py`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/test_multi_sources.py#L20-L84) |
| `FLIGHT-003` | Main source: partial | [`build-web-tar1090.sh` lines 2–24](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/scripts/build-web-tar1090.sh#L2-L24) | [`tar_full_browser.test.cjs`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/tar_full_browser.test.cjs#L39-L54) |
| `FLIGHT-004` | Main source: partial | [`app.js` lines 6–11](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/web/app.js#L6-L11) | [`map_focus.test.cjs`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/map_focus.test.cjs#L8-L42) |
| `FLIGHT-005` | Draft #13 only | [`flight_route_lookup.py` lines 1–6](https://github.com/Tihulu/tihulu-flight-radar/blob/950f8278a625ce13a9a3c7e21bf9bf76d4b5888e/tihulu_flight_radar/flight_route_lookup.py#L1-L6) | [`aircraft_journey_routes.test.cjs`](https://github.com/Tihulu/tihulu-flight-radar/blob/950f8278a625ce13a9a3c7e21bf9bf76d4b5888e/tests/aircraft_journey_routes.test.cjs#L11-L36) |
| `FLIGHT-006` | Main partial; Draft extends | [`control.py` lines 119–166](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/control.py#L119-L166) | [`test_control.py`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/test_control.py#L7-L31) |
| `FLIGHT-007` | Main source: partial | [`location_search.mjs` lines 2–57](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/web/location_search.mjs#L2-L57) | [`location_selector.test.cjs`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/location_selector.test.cjs#L15-L45) |
| `FLIGHT-008` | Main partial; Draft extends | [`app.js` lines 17–80](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/web/app.js#L17-L80) | [`aircraft_visuals.test.cjs`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/aircraft_visuals.test.cjs#L22-L46) |
| `FLIGHT-009` | Draft semantics; main unconfirmed | [`app.js` lines 75–88](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/web/app.js#L75-L88) | [`rf_circles_layers.test.cjs`](https://github.com/Tihulu/tihulu-flight-radar/blob/950f8278a625ce13a9a3c7e21bf9bf76d4b5888e/tests/rf_circles_layers.test.cjs#L18-L42) |
| `FLIGHT-010` | Main/Draft behavior mismatch | [`receiver_coverage.js` lines 89–95](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/web/receiver_coverage.js#L89-L95) | [`aircraft_popup_rf_coverage.test.cjs`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/aircraft_popup_rf_coverage.test.cjs#L33-L47) |
| `FLIGHT-011` | Main partial; Draft extends | [`rf_timing_lab.js` lines 2–29](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/web/rf_timing_lab.js#L2-L29) | [`rf_timing_lab.test.cjs`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/rf_timing_lab.test.cjs#L13-L38) |
| `FLIGHT-012` | Main partial; Draft extends | [`rf_timing_lab.js` lines 6–7](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/web/rf_timing_lab.js#L6-L7) | [`rf_timing_lab.test.cjs`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/rf_timing_lab.test.cjs#L30-L38) |
| `FLIGHT-013` | Main source: partial | [`popos-version-switch.sh` lines 1–27](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/scripts/popos-version-switch.sh#L1-L27) | [`test_version_switch.py`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/test_version_switch.py#L16-L46) |
| `FLIGHT-014` | Main ownership risk; Draft #7 | [`control.py` lines 201–226](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/control.py#L201-L226) | [`test_control.py`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/test_control.py#L58-L95) |
| `FLIGHT-015` | Pages branch parity | [`DUAL_GITHUB_PAGES.md` lines 1–45](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/docs/DUAL_GITHUB_PAGES.md#L1-L45) | [`release_main.test.cjs`](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tests/release_main.test.cjs#L14-L25) |
| `FLIGHT-016` | Missing in Flight main | [`AGENTS.md` lines 1–78](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/AGENTS.md#L1-L78) | **No direct test candidate** |
| `FLIGHT-017` | Missing in Flight main | [`AGENTS.md` lines 64–91](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/AGENTS.md#L64-L91) | **No direct test candidate** |

### Verified CI evidence and limits

- Canonical main [standalone Pages workflow #43114895525](https://github.com/Tihulu/tihulu-flight-radar/actions/runs/43114895525) completed successfully at `059b391280635d9aa4d2ac73c7318af9e135ebf5`. Its `verify-deploy` job reports successful browser validation, pinned tar1090 bundle, source stamp and `gh-pages` push. The workflow's checked-in script invokes Node regression tests. A green workflow validates only what its steps exercised, **not real aircraft APIs, WebUSB permissions, physical SDR, deployed CDN health, a local Qt session or the user's installed binary**.
- Draft #13 SHA `950f8278a625ce13a9a3c7e21bf9bf76d4b5888e` has three observed successful workflow runs: [ARM64 #42736953985](https://github.com/Tihulu/tihulu-flight-radar/actions/runs/42736953985), [web #42736954183](https://github.com/Tihulu/tihulu-flight-radar/actions/runs/42736954183) and [build #42736954076](https://github.com/Tihulu/tihulu-flight-radar/actions/runs/42736954076). Linux/Debian Qt smoke and macOS/Windows build and unit-test CI steps succeeded; the draft web **deploy** job was skipped. None supplies Pop!_OS + actual RTL-SDR acceptance.
- Draft #7 at `4ef8245b87fc78cec6cc4f5f9043d68e08cf45d3` had a successful observed CI run [#42162086928](https://github.com/Tihulu/tihulu-flight-radar/actions/runs/42162086928), but still lacks verified current-main integration and physical receiver lifecycle.
- `get_commit_combined_status` returned no legacy status contexts for main/draft; GitHub Actions run/job inspection supplied the CI observations instead. No new CI run was triggered by this worker.

### Dual-Pages and rename-proof source

Canonical and mirrored branch files:
- [Standalone gh-pages `source-revision.json`](https://github.com/Tihulu/tihulu-flight-radar/blob/gh-pages/source-revision.json)
- [Text Center gh-pages `flight_radar/source-revision.json`](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/gh-pages/flight_radar/source-revision.json)

Both have identical blob SHA `8a5408ebd338ce8557a92f56e5af4c7383174417` and declare `source_ref=main` at `059b391280635d9aa4d2ac73c7318af9e135ebf5`. Also byte-identical Git blobs for seven selected main frontend assets: `index.html`, `app.js`, `tar1090-adapter.js`, `sw.js`, `multi_sources.js`, `receiver_coverage.js` and `adsb_worker.mjs`.

Current browser addresses remain [standalone](https://tihulu.github.io/tihulu-flight-radar/) and [Text Center mirror](https://tihulu.github.io/TIHULU-TEXT-CENTER/flight_radar/). Direct retrieval of these live URLs was unavailable to this audit, so live HTTP status, all assets, cache/SW scopes, WebUSB permissions and actual page rendering **remain unverified**. The [Text Center mirror workflow](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/a00b8d97ce04e6279c6edc1035656a86924cc101/.github/workflows/sync-flight-radar-pages.yml) follows Flight `main`. Any future Text Center repo rename requires separately approved checks for both URLs, Pages project path, PWA scope, source-revision parity, raw one-line installer URLs, aliases and the original numeric repository identity; **do not assume permanent redirect**.

### Original discussion and review preservation

- Original Flight Draft [#7](https://github.com/Tihulu/tihulu-flight-radar/pull/7) and [#13](https://github.com/Tihulu/tihulu-flight-radar/pull/13) preserved in their own repository. This audit found 0 normalized discussion comments on #7 and **8 original top-level #13 comment permalinks** (not copied bodies): [#1](https://github.com/Tihulu/tihulu-flight-radar/pull/13#issuecomment-6749307903) · [#2](https://github.com/Tihulu/tihulu-flight-radar/pull/13#issuecomment-6749887901) · [#3](https://github.com/Tihulu/tihulu-flight-radar/pull/13#issuecomment-6751149528) · [#4](https://github.com/Tihulu/tihulu-flight-radar/pull/13#issuecomment-6751162119) · [#5](https://github.com/Tihulu/tihulu-flight-radar/pull/13#issuecomment-6754467663) · [#6](https://github.com/Tihulu/tihulu-flight-radar/pull/13#issuecomment-6754887278) · [#7](https://github.com/Tihulu/tihulu-flight-radar/pull/13#issuecomment-6755221713) · [#8](https://github.com/Tihulu/tihulu-flight-radar/pull/13#issuecomment-6756436995).
- Checked #7 and #13 review submissions: 0; checked #13 inline review threads: 0. This observation is scoped to those endpoints and **does not certify complete historical coverage**.
- Original Text Center candidate PRs [#12](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/12), [#68](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/68), [#69](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/69), [#70](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/70) and [#71](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/71) remain partly linked through `apps/flight-radar/ORIGIN_FALLBACKS.json` in the original repository. Historical author/time, inline discussion, issue timelines, approvals and chat provenance are **not certified fully exported**.
- Never overwrite original PRs, original author/timestamps, old repo numeric IDs, source-tree SHAs or old branch pointers. A moved/recreated PR cannot carry an original GitHub-native review approval as if it were new.

## Required read-only and later authorized regression matrix

The tests below are **proposed acceptance gates only**. No invasive receiver, installer, CI deployment or live provider tests were run by this worker. Preserve stable main behavior and draft alternatives without silent cutover.

- **FLIGHT-001:** Replay controlled real captured /run/readsb and valid Internet provider snapshots; independently inspect identical ICAO R/I/I-R without duplicates, stale expiry and physical readsb hardware.
- **FLIGHT-002:** With provider permission and rate limits, independently toggle adsb.lol/adsb.fi/OpenSky/IntelSky; test 429/backoff/stale/ICAO dedup on current APIs, not synthetic coordinates.
- **FLIGHT-003:** Build upstream GPL payload; exercise full standalone/native/browser Pages without USB with real Internet feed and without changing readsb ownership; verify attribution and origin controls.
- **FLIGHT-004:** Exercise Köln/default, map drag, RF 4-plane focus, nearest/fit/follow, small viewport list/legend and selected aircraft persistence without GPS-like jumps.
- **FLIGHT-005:** Test callsign mismatch, unknown route/times, provider license/rate limits and verified departure/arrival fields; never infer schedule from ADS-B timestamp.
- **FLIGHT-006:** Verify paired/absent/failed bridge, accurate Radio Load and Internet Load, stop/fail close behavior, and physical SDR release on native desktop.
- **FLIGHT-007:** Offline DE/TR region/city/manual GPS search, saved place across relaunch, optional MBTiles local import and no implicit antenna activation.
- **FLIGHT-008:** Resize desktop and mobile panels, open popups/Circles, keyboard focus, overlays and simultaneous model/aircraft selection without occlusion.
- **FLIGHT-009:** Toggle RF On OFF while simultaneous local readsb and Internet aircraft are streaming; assert ONLY localization models stop, aircraft count and receiver ownership do not.
- **FLIGHT-010:** At least four distinct genuine independently positioned RF ICAOs, arbitrary order and successive epochs; test LIVE10/LIVE-X/BEST/HISTORY/HISTORY-BEST separately.
- **FLIGHT-011:** Reject Internet/copy-derived RF constraints, do not expose range or accuracy; compare feasible-area model to independent surveyed position without promoting centroid to GPS.
- **FLIGHT-012:** Run long synthetic and opt-in recorded sessions, bounded disk/eviction/pagination/restart, RF-only provenance with original times, no background capture.
- **FLIGHT-013:** User-approved test only: backup settings, exact pin restore to 0.3.1, rerun 0.3.2.dev4, preserve RF services and Pages, then explicitly compare #7/#13 without merging.
- **FLIGHT-014:** On physical Linux, pre-existing readsb vs app-started readsb vs direct child, close with both preferences and failed sudo; verify external readsb/tar1090 never accidentally terminated.
- **FLIGHT-015:** For BOTH public site URLs check HTTP, generated source_sha, selected assets, service worker scope, offline cache, per-origin WebUSB and redirect after separately approved rename.
- **FLIGHT-016:** Future separate Flight repo PR: create English-only matrix schema and Claude/DeepSeek entry links, validate machine-readable paths and EN(default)/TR/DE UI gap matrix without app behavior changes.
- **FLIGHT-017:** Inventory exact numeric repo IDs, PR issue/review/comment URLs/timestamps, transfer gaps and rename alias checks in future docs-only authorized Flight PR; never alter original GitHub artifacts.

## Cross-worker handoffs and blockers

1. **[Issue #75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75)** — central coordinator: mark Flight main vs Draft #13 **3- vs 4-ICAO region behavior** and #7 **readsb ownership** as explicit release gates; no shared manifest edits from WS02.
2. **[Issue #80](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/80)** — Text Center worker: dual Pages `source_sha` matched in `gh-pages` branches but rename/CDN/PWA validation remains a shared blocker.
3. **[Issue #81](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/81)** — provenance/QA worker: standard Flight agent matrix documents and exact historical Text Center-to-Flight review/comment gaps remain missing in the canonical Flight repository.
4. **[Issue #76](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/76)** — Media worker: shared NooElec SDR/readsb lifecycle and exclusive ownership must be acceptance-tested jointly before any PR merges or new installation; never stop externally managed services during audit.

## Status and stop rules

**Audit result:** **17/17 requirement IDs source-traced**; baseline or draft source was found for 15 behavior groups, while required native agent/history documents remain missing for FLIGHT-016/017. No claim of full requirements completeness, source-to-user-history completeness, per-requirement integration tests, hardware acceptance or installation release is made.

**Progress:** docs-only evidence and report on the dedicated Draft #84 branch. **Remaining ETA: unknown** until there is a defensible task-by-task test/CI/hardware workload and permitted acceptance hardware. Keep Draft #84, #7 and #13 open; no merges, releases, application edits, settings changes, logos, installers, migrations, active site updates or main modifications.
