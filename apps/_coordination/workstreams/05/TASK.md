# Workstream 05 — Text Center — Audit Only

**Designated GitHub issue:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/80  
**Central coordination:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75  
**Dedicated branch:** `audit/ws05-text-retained-2026-11-11`  
**Dedicated scope root:** `apps/_coordination/workstreams/05/`  
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
Text Center STAYS in this original GitHub repo (ID 1447637221). Keep active textcenter/ and web/ untouched; audit real FM/DAB/DVB and Pages/installer link breakage when SAME repo is eventually renamed. Never treat entire source repo as read-only after three app cutovers.

1. Inspect all assigned requirement IDs below **against exact pinned code and candidate tests**, then source branch head differences and user-request provenance.
2. For each ID write one evidence row: `requested | draft-coded | unit-verified | hardware-verified | released | unknown`; link exact source SHA/line, exact test SHA/command/result or missing evidence. Distinguish source-only/fixture/synthetic/live receiver tests.
3. List a non-destructive regression test for every current behavior, proposed new behavior, any 3-language UI gaps and native release/rollback boundaries. Do not run invasive hardware tests automatically.
4. Record missing tests, dependencies, 3+ application preservation constraints, PR ancestry, history links and any other blocked worker Issue.
5. Add `REPORT.md` and `EVIDENCE.json` **only under this branch-owned `workstreams/05/`**. Use Draft PR comments and Issue #80 to communicate (other agents do not share chat memory).
6. Report progress as source-backed counts; estimate hours/minutes **only after** you have audited work sizes and assumptions. Until then, ETA is explicitly unknown.

## Assigned requirement IDs (8)
- **TEXT-001** (P0): Keep Text Center as active canonical source in TIHULU-TEXT-CENTER, including textcenter/ and web/ paths.
- **TEXT-002** (P0): FM RDS/RadioText+, DAB DLS/DLS+, Journaline, MOT slideshow, full scans and genuine frequency/source information.
- **TEXT-003** (P0): DVB-T2 scan, channel list, Teletext, playback, live subtitles, selected channels and recording metadata remain intact.
- **TEXT-004** (P1): Keep optional NOAA APT, AIS, ACARS, RTL-433 modules truthful about hardware capability and decoding state.
- **TEXT-005** (P0): Offer independent device manager, native RF desktop operation, hard stop and default on-demand/no-background lifecycle.
- **TEXT-006** (P1): Preserve local web desktop/tablet/mobile parity, saved favorites, source selection and responsive navigation.
- **TEXT-007** (P0): Continue Text Center development after other app cutovers, retaining original historical PR archive and code provenance.
- **TEXT-008** (P0): Protect existing Pages/PWA/installer URLs against a later explicitly approved rename of the SAME repository ID.

## Initial source/test candidates — existence only

| Requirement | Existing candidate code | Candidate test source | Verification |
|---|---|---|---|
| `TEXT-001` | `textcenter/__main__.py`, `web/index.html` | `tests/test_cli.py`, `tests/test_text_center_retained_canonical.py` | Not verified |
| `TEXT-002` | `textcenter/fm_rds.py`, `textcenter/dab_bridge.py` | `tests/test_fm_rds.py`, `tests/test_dab_bridge.py` | Not verified |
| `TEXT-003` | `textcenter/dvb_hardware.py`, `textcenter/live_tv.py` | `tests/test_dvb_hardware.py`, `tests/test_live_tv.py` | Not verified |
| `TEXT-004` | `textcenter/capabilities.py`, `textcenter/receivers.py` | `tests/test_capabilities.py` | Not verified |
| `TEXT-005` | `textcenter/receivers.py`, `textcenter/conflicts.py` | `tests/test_conflicts.py`, `tests/test_receivers.py` | Not verified |
| `TEXT-006` | `textcenter/http_app.py`, `web/app.js` | `tests/test_http_app.py`, `tests/test_tv_web.py` | Not verified |
| `TEXT-007` | `apps/text-center/ORIGIN.md`, `apps/CANONICAL_REPOSITORY_TOPOLOGY.json` | `tests/test_text_center_retained_canonical.py` | Not verified |
| `TEXT-008` | `apps/REPOSITORY_RENAME_LINK_POLICY.md`, `.github/workflows/sync-flight-radar-pages.yml` | `tests/test_origin_fallback_approved_branding.py` | Not verified |

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
