# Workstream 06 — Historical Provenance and Cross-App QA — Audit Only

**Designated GitHub issue:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/81  
**Central coordination:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75  
**Dedicated branch:** `audit/ws06-provenance-qa-2026-11-11`  
**Dedicated scope root:** `apps/_coordination/workstreams/06/`  
**Source of truth:** `all five repo origins`  
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
Audit original PR/Issue comments, reviews, timestamps, source anchors and missing chat context WITHOUT leaking private data or forging approval records. Validate five SHA-pinned approved red TIHULU logos, proper English engineering and EN/TR/DE user UI requirements, source history and no-regression gates.

1. Inspect all assigned requirement IDs below **against exact pinned code and candidate tests**, then source branch head differences and user-request provenance.
2. For each ID write one evidence row: `requested | draft-coded | unit-verified | hardware-verified | released | unknown`; link exact source SHA/line, exact test SHA/command/result or missing evidence. Distinguish source-only/fixture/synthetic/live receiver tests.
3. List a non-destructive regression test for every current behavior, proposed new behavior, any 3-language UI gaps and native release/rollback boundaries. Do not run invasive hardware tests automatically.
4. Record missing tests, dependencies, 3+ application preservation constraints, PR ancestry, history links and any other blocked worker Issue.
5. Add `REPORT.md` and `EVIDENCE.json` **only under this branch-owned `workstreams/06/`**. Use Draft PR comments and Issue #81 to communicate (other agents do not share chat memory).
6. Report progress as source-backed counts; estimate hours/minutes **only after** you have audited work sizes and assumptions. Until then, ETA is explicitly unknown.

## Assigned requirement IDs (15)
- **CROSS-001** (P0): ZERO application feature, behavior, default, settings, recordings, data, installer, device ownership or existing icon changes in audit phase.
- **CROSS-002** (P0): English engineering internals, source docs, commits, GitHub Issue/PR and coding-agent prompts; UI languages English(default), Turkish, German in all five apps.
- **CROSS-003** (P0): Only use exact five previously approved red/black/white TIHULU mascot logo PNG masters; verify hashes and real SVG later.
- **CROSS-004** (P0): Three user-created empty repos are Media, Satellite, RF Geolocation; Text Center stays in source repo, Flight Radar remains separate canonical.
- **CROSS-005** (P0): No loss of PR comments, reviews, issue timelines, decisions, original author/time: linked old repo + explicit transfer gaps + independent permitted snapshots.
- **CROSS-006** (P0): On any future origin repo rename, preserve original GitHub URLs and repo ID; resolve aliases, test Pages/PWA, GitHub raw scripts, workflow and PR links.
- **CROSS-007** (P0): Document FEATURE, COMPONENT, MODEL and DEVELOPMENT_AGENT matrices for each app in its canonical repository, with Claude/DeepSeek navigation.
- **CROSS-008** (P0): Six independent audit workers coordinate through GitHub Issues, distinct branches and Draft PRs; no shared file edits or unapproved merges.
- **CROSS-009** (P0): Only verified source-backed test success is reported as success; distinguish unit/static CI from real NooElec/Hauppauge physical tests.
- **CROSS-010** (P0): Preserve main, all prior Draft PRs (#65–#74), Flight Radar PRs (#7/#13), open issues, legacy rollback and active installed apps.
- **CROSS-011** (P0): Set explicit user authorization gates for first commits to empty repos, importing sources, icon activation, merges, release repoints and renames.
- **CROSS-012** (P0): Track progress from audited counts and tested gates; remaining hours/minutes stay null until workload is inventoried and assumptions documented.
- **CROSS-013** (P1): Treat optional paired GPU remote processing, offline-first CPU/GPU/NPU support, models and permissions as modular nonbreaking future changes.
- **CROSS-014** (P2): Keep separate related Survival Kit News/Emergency/AI requirements inventory without silently grafting them onto these five apps.
- **CROSS-015** (P0): For each demand distinguish Requested, Draft coded, Verified in CI, Verified on device, Released; never promote from code presence alone.

## Initial source/test candidates — existence only

| Requirement | Existing candidate code | Candidate test source | Verification |
|---|---|---|---|
| `CROSS-001` | `apps/_coordination/COORDINATION_PROTOCOL.md`, `apps/_coordination/MASTER_PLAN.md` | `tests/test_master_zero_regression_coordination.py` | Not verified |
| `CROSS-002` | `apps/_coordination/MASTER_PLAN.md`, `apps/registry.json` | `tests/test_verified_destination_repos_and_red_logos.py` | Not verified |
| `CROSS-003` | `apps/BRANDING_APPROVED_MANIFEST.json`, `apps/BRANDING_APPROVED_ROLLOUT.md` | `tests/test_origin_fallback_approved_branding.py` | Not verified |
| `CROSS-004` | `apps/CANONICAL_REPOSITORY_TOPOLOGY.json`, `apps/VERIFIED_DESTINATION_REPOSITORIES.json` | `tests/test_text_center_retained_canonical.py` | Not verified |
| `CROSS-005` | `apps/_archives/HISTORY_COVERAGE_AUDIT.json`, `apps/HISTORY_ORIGIN_FALLBACK_POLICY.md` | `tests/test_origin_fallback_approved_branding.py` | Not verified |
| `CROSS-006` | `apps/REPOSITORY_RENAME_LINK_POLICY.md`, `apps/REPOSITORY_IDENTITY.json` | **MISSING TEST CANDIDATE** | Not verified |
| `CROSS-007` | `apps/DEVELOPMENT_AGENT_MATRIX.json`, `DEVELOPMENT_AGENT_GUIDE.md` | `tests/test_development_agent_entrypoints.py` | Not verified |
| `CROSS-008` | `apps/_coordination/ISSUES.json`, `apps/_coordination/prompts/README.md` | `tests/test_master_zero_regression_coordination.py` | Not verified |
| `CROSS-009` | `apps/_coordination/PROGRESS.json`, `apps/_coordination/COORDINATION_PROTOCOL.md` | **MISSING TEST CANDIDATE** | Not verified |
| `CROSS-010` | `apps/_coordination/PR_ANCESTRY_AUDIT.json`, `apps/_archives/HISTORY_COVERAGE_AUDIT.json` | **MISSING TEST CANDIDATE** | Not verified |
| `CROSS-011` | `apps/MIGRATION_PROTOCOL.md`, `apps/_coordination/MASTER_PLAN.md` | **MISSING TEST CANDIDATE** | Not verified |
| `CROSS-012` | `apps/_coordination/PROGRESS.json` | **MISSING TEST CANDIDATE** | Not verified |
| `CROSS-013` | `tv_center/remote_gpu.py`, `tv_center/hardware_status.py` | `tests/test_tv_ai_profiles_remote_startup.py` | Not verified |
| `CROSS-014` | `apps/_coordination/MASTER_PLAN.md` | **MISSING TEST CANDIDATE** | Not verified |
| `CROSS-015` | `apps/_coordination/MASTER_REQUIREMENTS.json`, `apps/_coordination/PROGRESS.json` | `tests/test_master_zero_regression_coordination.py` | Not verified |

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
Audit completion: <audited IDs>/15
Implementation verified: <n>; source-only/draft: <n>; unknown: <n>
Tests checked: <n>; executed with evidence: <n>; hardware tests: <n>
Missing test cases / review-comment archives: <links>
Exact source refs: <SHAs and file links>
Cross-team handoffs: <issue links>
Estimated remaining work: <HHh MMm + assumptions, or unknown>
Safety: 0 active program/installer/device/feature changes; 0 unapproved merges.
```
