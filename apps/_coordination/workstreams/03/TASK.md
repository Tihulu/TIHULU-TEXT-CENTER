# Workstream 03 — Satellite Center — Audit Only

**Designated GitHub issue:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/78  
**Central coordination:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75  
**Dedicated branch:** `audit/ws03-satellite-parity-2026-11-11`  
**Dedicated scope root:** `apps/_coordination/workstreams/03/`  
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
Audit genuine satellite pass planner, IQ record chunking, Robot36/LRPT error reporting; browser-only Pages cannot run native unattended capture/SatDump. Existing future destination remains EMPTY; do not bootstrap.

1. Inspect all assigned requirement IDs below **against exact pinned code and candidate tests**, then source branch head differences and user-request provenance.
2. For each ID write one evidence row: `requested | draft-coded | unit-verified | hardware-verified | released | unknown`; link exact source SHA/line, exact test SHA/command/result or missing evidence. Distinguish source-only/fixture/synthetic/live receiver tests.
3. List a non-destructive regression test for every current behavior, proposed new behavior, any 3-language UI gaps and native release/rollback boundaries. Do not run invasive hardware tests automatically.
4. Record missing tests, dependencies, 3+ application preservation constraints, PR ancestry, history links and any other blocked worker Issue.
5. Add `REPORT.md` and `EVIDENCE.json` **only under this branch-owned `workstreams/03/`**. Use Draft PR comments and Issue #78 to communicate (other agents do not share chat memory).
6. Report progress as source-backed counts; estimate hours/minutes **only after** you have audited work sizes and assumptions. Until then, ETA is explicitly unknown.

## Assigned requirement IDs (8)
- **SAT-001** (P0): Keep TLE orbital predictions, AOS/LOS/max elevation, Earth and sky maps, selected station and horizon orientation such as 280°.
- **SAT-002** (P1): Offer best-pass/near-zenith planning and scheduled recording, optional alerts; verify local time zones and device readiness.
- **SAT-003** (P0): Support ISS SSTV/Robot36 WAV and concurrent IQ when possible; NOAA APT; Meteor M2-3/M2-4 LRPT IQ workflows.
- **SAT-004** (P0): Handle long RF captures and browser recording segment limits without losing frames, bytes or source time.
- **SAT-005** (P0): Report empty CADU, analog telemetry missing, PLL unlock, unsupported decoder, zero-image output instead of claiming images.
- **SAT-006** (P1): Keep wideband satellite/ham frequencies, amateur CubeSats, Iridium and per-pass capture profiles as supported, not invented.
- **SAT-007** (P0): Keep SDR native desktop hardware, exclusive lease, Start/Stop, automatic decode/export ZIP/audio/visual products when verified.
- **SAT-008** (P1): Keep exact IQ/sample-rate/frequency metadata, offline TLE/map planning and source provenance.

## Initial source/test candidates — existence only

| Requirement | Existing candidate code | Candidate test source | Verification |
|---|---|---|---|
| `SAT-001` | `satellite_center/browser/pass_candidates.mjs`, `satellite_center/native_orbit.py` | `tests/test_tv_satellite_ai.py` | Not verified |
| `SAT-002` | `satellite_center/browser/satellite_calendar.mjs`, `satellite_center/browser/schedule_controller.mjs` | `tests/test_tv_satellite_ai.py` | Not verified |
| `SAT-003` | `satellite_center/browser/sstv_robot36.mjs`, `satellite_center/native_analysis.py` | `tests/test_postprocess.py` | Not verified |
| `SAT-004` | `satellite_center/browser/chained_capture.mjs`, `satellite_center/capture_budget.py` | `satellite_center/browser/usb_diagnostics.test.mjs` | Not verified |
| `SAT-005` | `satellite_center/browser/sstv_capture_diagnostics.mjs`, `satellite_center/native_robot36_results.py` | **MISSING TEST CANDIDATE** | Not verified |
| `SAT-006` | `satellite_center/browser/pass_protocol_catalog.mjs`, `satellite_center/native_protocols.py` | **MISSING TEST CANDIDATE** | Not verified |
| `SAT-007` | `satellite_center/native_signal_tools.py`, `satellite_center/bridge.py` | `satellite_center/browser/usb_diagnostics.test.mjs` | Not verified |
| `SAT-008` | `satellite_center/capture_naming.py`, `satellite_center/browser/iq_analysis.mjs` | **MISSING TEST CANDIDATE** | Not verified |

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
