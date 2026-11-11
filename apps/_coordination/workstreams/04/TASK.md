# Workstream 04 — RF Geolocation Center — Audit Only

**Designated GitHub issue:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/79  
**Central coordination:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75  
**Dedicated branch:** `audit/ws04-rf-geolocation-2026-11-11`  
**Dedicated scope root:** `apps/_coordination/workstreams/04/`  
**Source of truth:** `Tihulu/TIHULU-TEXT-CENTER`  
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
Check RF evidence honesty, PSF/Gaussian, 3+ aircraft hypotheses, circles, native GNSS-SDR unimplemented/experimental and ensure no false triangulation from one receiver. Future destination remains EMPTY.

1. Inspect all assigned requirement IDs below **against exact pinned code and candidate tests**, then source branch head differences and user-request provenance.
2. For each ID write one evidence row: `requested | draft-coded | unit-verified | hardware-verified | released | unknown`; link exact source SHA/line, exact test SHA/command/result or missing evidence. Distinguish source-only/fixture/synthetic/live receiver tests.
3. List a non-destructive regression test for every current behavior, proposed new behavior, any 3-language UI gaps and native release/rollback boundaries. Do not run invasive hardware tests automatically.
4. Record missing tests, dependencies, 3+ application preservation constraints, PR ancestry, history links and any other blocked worker Issue.
5. Add `REPORT.md` and `EVIDENCE.json` **only under this branch-owned `workstreams/04/`**. Use Draft PR comments and Issue #79 to communicate (other agents do not share chat memory).
6. Report progress as source-backed counts; estimate hours/minutes **only after** you have audited work sizes and assumptions. Until then, ETA is explicitly unknown.

## Assigned requirement IDs (8)
- **GEO-001** (P0): Preserve independent geolocation app, not only Flight Radar embedded UI; own positioning APIs and tests.
- **GEO-002** (P0): Support GNSS/NMEA, radio observations, aircraft evidence, valid TDOA/multilateration when hardware timestamps allow.
- **GEO-003** (P0): Expose PSF/Gaussian models, statistical uncertainty and source/provenance rather than fake precise coordinates.
- **GEO-004** (P1): Support large-circle performance optimization, indexing, incremental fit and bounded history.
- **GEO-005** (P0): Show source aircraft coverage rings separately from Location, LIVE Fit and BEST Fit positioning rings.
- **GEO-006** (P0): RF On enables real localized computation with optional location circle default, RF Off stops own radio computation.
- **GEO-007** (P1): Provide multiple independent map/model layers, offline maps, saved coordinate selection and map interaction.
- **GEO-008** (P0): Do not require latitude/longitude user input for verified RF 3+ aircraft region-estimation mode.

## Initial source/test candidates — existence only

| Requirement | Existing candidate code | Candidate test source | Verification |
|---|---|---|---|
| `GEO-001` | `rf_geolocation_center/core/positioning.mjs`, `rf_geolocation_center/native.py` | `rf_geolocation_center/tests/core.test.mjs`, `rf_geolocation_center/tests/test_native.py` | Not verified |
| `GEO-002` | `rf_geolocation_center/core/gnss.mjs`, `rf_geolocation_center/core/evidence.mjs` | `rf_geolocation_center/tests/evidence.test.mjs` | Not verified |
| `GEO-003` | `rf_geolocation_center/core/positioning.mjs`, `rf_geolocation_center/core/rf_ranging.mjs` | `rf_geolocation_center/tests/rf_ranging.test.mjs` | Not verified |
| `GEO-004` | `rf_geolocation_center/core/positioning.mjs`, `rf_geolocation_center/core/location_layers.mjs` | `rf_geolocation_center/tests/location_layers.test.mjs` | Not verified |
| `GEO-005` | `rf_geolocation_center/core/location_layers.mjs`, `rf_geolocation_center/web/maps.mjs` | `rf_geolocation_center/tests/location_layers.test.mjs` | Not verified |
| `GEO-006` | `rf_geolocation_center/web/receivers.mjs`, `rf_geolocation_center/web/hardware_manager.mjs` | `rf_geolocation_center/tests/receiver_ux.test.mjs` | Not verified |
| `GEO-007` | `rf_geolocation_center/web/maps.mjs`, `rf_geolocation_center/core/source_catalog.mjs` | `rf_geolocation_center/tests/map_interactivity.test.mjs`, `rf_geolocation_center/tests/source_catalog.test.mjs` | Not verified |
| `GEO-008` | `rf_geolocation_center/core/positioning.mjs`, `rf_geolocation_center/core/rf_ranging.mjs` | `rf_geolocation_center/tests/rf_ranging.test.mjs` | Not verified |

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
Audit completion: <audited IDs>/8
Implementation verified: <n>; source-only/draft: <n>; unknown: <n>
Tests checked: <n>; executed with evidence: <n>; hardware tests: <n>
Missing test cases / review-comment archives: <links>
Exact source refs: <SHAs and file links>
Cross-team handoffs: <issue links>
Estimated remaining work: <HHh MMm + assumptions, or unknown>
Safety: 0 active program/installer/device/feature changes; 0 unapproved merges.
```
