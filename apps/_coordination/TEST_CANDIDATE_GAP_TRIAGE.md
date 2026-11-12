# TIHULU Coordinator: Missing Test-Candidate Triage (2026-11-11)

**Document-only audit, no source changes.** This file classifies the 11 initial requirement IDs with no test-file candidate in `apps/_coordination/REQUIREMENT_SOURCE_TEST_CANDIDATES.json`; it does **not** prove that tests are absent from all branches, nor that any feature is unimplemented. The 86/97 mapped items likewise are only *candidate* tests, not executed acceptance results.

**Frozen source inventory references:**
- Canonical Flight Radar source: `Tihulu/tihulu-flight-radar@059b391280635d9aa4d2ac73c7318af9e135ebf5`
- Origin source inventory: `Tihulu/TIHULU-TEXT-CENTER@803529ba90f43a6cb1fb977869c650ddf5db448a`
- Candidate map: `apps/_coordination/REQUIREMENT_SOURCE_TEST_CANDIDATES.json` (blob `0dde8a66ce16efa1e23688e7893eebebf36ca2f4`)
- Requirement text: `apps/_coordination/MASTER_REQUIREMENTS.json`
- Original source remains canonical until a separately approved cutover; do not infer an audit-branch source tree is the latest Media #67 branch.

## Workstream 02 — Flight Radar: 2 P0 mapping gaps (Issue #77, Draft PR #84)

| Requirement | Candidate source paths at pinned Flight SHA | Next verification evidence to collect (NOT performed) |
|---|---|---|
| `FLIGHT-016` | `AGENTS.md`; `docs/FEATURE_PARITY_AND_SURVIVAL_KIT_GATE.md` | Verify which root Claude/DeepSeek instructions and FEATURE/COMPONENT/MODEL/DEVELOPMENT_AGENT matrices exist in **Flight Radar's own** repo, not only origin snapshots. Design a read-only path/JSON validation matrix; no files in Flight repo may be edited by this worker. |
| `FLIGHT-017` | `AGENTS.md`; `docs/SURVIVAL_KIT_FLIGHT_RADAR_HANDOFF_2026-11-05.md` | Pin Flight repo ID, origin repo ID, original PR links and missing history pointers; separately inspect original and current review/comment links and `TRANSFER_GAPS` behavior. Plan a link-consistency check that does not rewrite history or publish private chat content. |

## Workstream 03 — Satellite Center: 3 mapping gaps (Issue #78, Draft PR #85)

| Requirement | Priority | Candidate source paths at pinned origin SHA | Next verification evidence to collect (NOT performed) |
|---|---|---|---|
| `SAT-005` | P0 | `satellite_center/browser/sstv_capture_diagnostics.mjs`; `satellite_center/native_robot36_results.py` | Locate negative/error-path tests for empty CADU, missing analog telemetry, PLL unlock, unsupported decoders and **zero-image** results; verify they never claim successful image decode. Run a fixture test only if safe and available; do not claim live Robot36/Meteor images. |
| `SAT-006` | P1 | `satellite_center/browser/pass_protocol_catalog.mjs`; `satellite_center/native_protocols.py` | Reconcile documented amateur/CubeSat/Iridium reception bands against actual supported protocol profiles. Distinguish supported tuners/decoders from catalogue entries and provide offline fixture validation; do not invent RX capability. |
| `SAT-008` | P1 | `satellite_center/capture_naming.py`; `satellite_center/browser/iq_analysis.mjs`; `satellite_center/planning_store.py` | Inspect frequency, sample-rate, sample format, capture duration and provenance metadata preservation; propose round-trip fixture checks and offline pass/TLE availability checks without changing IQ recordings or scheduling semantics. |

## Workstream 06 — Cross-app history and QA: 6 mapping gaps (Issue #81, Draft PR #88)

These are predominantly **policy/provenance acceptance gates**, where direct evidence may be manual inventories, checked links and negative checks rather than unit tests. Do not invent dummy unit tests solely to make the mapped number reach 97/97.

| Requirement | Priority | Candidate source paths at pinned origin SHA | Required evidence type (NOT verified) |
|---|---|---|---|
| `CROSS-006` | P0 | `apps/REPOSITORY_RENAME_LINK_POLICY.md`; `apps/REPOSITORY_IDENTITY.json` | Build a before/after link inventory for original GitHub repo ID, alias redirects, Pages/PWA scope, raw scripts, workflows and PR anchors; **no rename is authorized**. |
| `CROSS-009` | P0 | `apps/_coordination/PROGRESS.json`; `apps/_coordination/COORDINATION_PROTOCOL.md` | Audit sample CI/fixture/static claim labels and enforce physical NooElec/Hauppauge hardware evidence as a separate, currently missing category. |
| `CROSS-010` | P0 | `apps/_coordination/PR_ANCESTRY_AUDIT.json`; `apps/_archives/HISTORY_COVERAGE_AUDIT.json` | Inspect immutable SHA ancestry of origin #65–#74 and Flight #7/#13, original discussions/reviews, main refs and 0.3.1 rollback; do not merge or replace old PRs. |
| `CROSS-011` | P0 | `apps/MIGRATION_PROTOCOL.md`; `apps/_coordination/MASTER_PLAN.md` | Produce a signed-off **proposed** gate matrix for migration, empty-repo first commits, icons, releases, renames and installer repoints. No authorization to execute those actions. |
| `CROSS-012` | P0 | `apps/_coordination/PROGRESS.json` | Verify that counts distinguish started audits vs blocked intakes, docs vs semantic test vs real hardware; hours/minutes remain UNKNOWN until per-worker scoped estimates exist. |
| `CROSS-014` | P2 | `apps/_coordination/MASTER_PLAN.md` | Compare external Survival Kit News/Emergency/AI request boundaries against the five-app scope; preserve their references without importing or implementing those features here. |

## Coordinator evidence rules

1. A file path `exists_at_ref=true` is **not** implementation or acceptance proof. Workers should cite file/line or function evidence plus exact commit SHA and test command/log, separating `source-inspected`, `fixture-tested`, `CI-tested`, `physical hardware-tested` and `not verified`.
2. A test-file candidate gap is not necessarily a test suite defect, especially for approvals, source history, Pages rename risks and private evidence.
3. Worker branches may create only `REPORT.md` and `EVIDENCE.json` under their own `apps/_coordination/workstreams/NN/`. This coordinator document does not authorize any additional app changes or cross-worker writes.
4. Shared hardware acceptance remains unverified; do not mark browser mock tests as native USB SDR/DVB passes.
5. English technical records and EN(default)/TR/DE UI targets remain unchanged. The original five approved logos, source histories, live installations and old Draft PRs remain untouched.
6. Audits have **not** been completed, and a six-worker ETA cannot be stated reliably from these inventory records. Remaining hours/minutes: **UNKNOWN**.
