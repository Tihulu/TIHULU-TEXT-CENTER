# TIHULU Phase 3 — isolated zero-regression test entry plan

**Status:** PROPOSED; DOCUMENTATION-ONLY; tests NOT created or run as part of this plan. Date: 2026-11-12.

## Baseline and immutable inputs

All six initial independent source audits have been received and source-reviewed. Three focused second-pass source-preservation audits were also received. Existing app feature equivalence, real hardware acceptance, original native build parity, new standalone installations and release/rollback are **not** accepted. The 17 cross-workstream gates remain OPEN. A green GitHub Text Center software test matrix is **not** equivalent to full native or SDR acceptance.

| Workstream | Original source | Second-pass report and pinned head | Relevant gates |
|---|---|---|---|
| Media WS01 | Unmerged original #65 → #66 → #67, #67 SHA `4e62e21cd5252df8a04f9ceadc429f4b116412ce` | [Draft #83](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/83), head `91a877f08c94fa9afe26e92dd86dd4477cc8d41b` | REG-01, REG-03, REG-14, REG-16 |
| Flight WS02 | Canonical Flight main `059b391280635d9aa4d2ac73c7318af9e135ebf5`; unmerged #7 `4ef8245b87fc78cec6cc4f5f9043d68e08cf45d3`; #13 `950f8278a625ce13a9a3c7e21bf9bf76d4b5888e` | [Draft #84](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/84), head `9db6fb96a249992214ec93e1888a88e3228427ac` | REG-03, REG-04, REG-05 |
| Text WS05 | Original retained Text `main` `1fffb711bfbb7c4abaf55299fa9240e5db3e1cde`; archived source snapshot `470eefa12dc4b2d41ecaef7cd422fb9d52abd546` | [Draft #87](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/87), head `3dbcbf658029ad213d985a5eef8227a244d3c045` | REG-02, REG-10, REG-16 |

Do not turn the archival snapshots or missing upstream commits into a supposed new canonical source. Original Text main stays canonical; Flight main stays independent; old Media #67 commits and original links stay available. Baseline source identities are acceptance inputs, not instructions to merge or overwrite.

## Authorized NOW: documentary test design only

- Preserve full reproducible, pinned source/test evidence and plan test fixtures, independent of the user's Pop!_OS services and USB radio/TV equipment.
- Record limitations, potential expected failures, current-vs-draft behavior differences and exact outcome categories (not-run / expected negative control / pass / failure / skipped).
- Track per-test environment, input, expected result, touched paths, cleanup and SHA. Use short-lived synthetic data and temporary databases, not recordings, personally stored files, network accounts or live receiver streams.
- Keep each original worker audit branch limited to its own two report/evidence files until separately authorized; coordinator updates remain under apps/_coordination only.

## Stage A — proposed first test-only authorization

**Explicit user authorization required before implementation** of even test-only files. When approved, use separately reviewable test-only branches/PRs, exact-path allowlist, no app-code writes and no merge. Prefer existing hosted CI runner and mocks/fakes; no actual systemd, sudo, network, SDR/USB, /dev/dvb, device handles, user settings or external services. Negative controls must deliberately fail with an identifiable error and must not mask unrelated failures. Do not run untrusted downloaded models.

### Priority 1 — Text Center imports and independence (WS05)

**Question:** Can current canonical Text Center be imported and started in a clean Text-only environment with `tv_center` deliberately absent, and can a *pinned archived-only* negative control demonstrate the documented coupling?

- Use temporary clean modules/paths with controlled `sys.path`/subprocess isolation; guard against ambient `tv_center` leakage.
- Verify imports of main `textcenter` CLI, HTTP, speech and transcripts, using no actual receiver and no implicit GPU downloads. This is a **target to verify**, not a preexisting pass.
- For archival snapshot, expect at least `transcripts.py` top-level `tv_center.language_codes` import failure and `compute.detect_devices` `tv_center.pi_hailo` dependency. Report each expected negative separately; never 'fix' by copying all Media modules into Text silently.
- Verify **reverse** archived Media CUDA `--serve` import of `textcenter.compute.LANGUAGES` without shipping a CUDA model; no GPU initialization needed for static import validation.
- Extend later fixtures to sample-rate WAV (32k→16k with exact duration), Argos direct/English-pivot/no-pack and source `auto` vs complete pipeline validation. Retain original captions/timestamps and EN(default)/TR/DE UI target as a distinct gate.
- Source matrix: WS05 `SI-01` to `SI-13`. Minimal Stage-A evidence: import graph, stderr/return codes, fixture provenance and confirmed network/device inactivity. **No implementation of decoupling in this phase.**

### Priority 2 — Flight Radar readsb/tar1090 ownership (WS02)

**Question:** Does the main/PR #7 control logic preserve pre-existing services on Exit, and do Start/Stop/Restart/failed actions match the documented branch-specific contracts?

- Monkeypatch subprocess/service runner and/or use an inert fake service manager; no actual systemctl/sudo calls, no sudoers writes, no real receiver.
- Test table: preexisting readsb; app-started readsb; tar1090 separately owned; explicit Stop versus Exit preference; double-click Start; queued Start+Exit; cancelled/restarted operation; permission error; app force close; cleanup idempotency.
- Validate PR #7's **separate** integration risks: main persisted exit preference, old sudoers single-service stop allowance, old Qt constructor and pending action race. The PR #7 implementation must **not** be declared ready to cherry-pick from green mocks.
- RF model fixtures separately cover exactly 3 vs 4 **unique genuine RF ICAOs**, duplicates, Internet-only fixes, 10-minute/X-hour/session history, five UI layer switches and infeasible geometric constraints. These model areas are **not** measured receiver GPS/MLAT, range/TOA or physical accuracy.
- Source matrix: WS02 `L01–L18`, `R01–R11`. Minimal Stage-A evidence: fake process/service call log per scenario; no real service process, RF device or network activity.

### Priority 3 — Media #67 subtitle export and preserved history (WS01)

**Question:** Are all 20 unmerged #67 commits and eight changed source/test paths accounted for, and do no-overwrite and caption export functions behave correctly in synthetic/temporary-file tests?

- Keep original #65→#66→#67 source and tests pinned; no cherry-pick/migration. Contract map includes TXT/SRT/VTT/ASS/JSON, conditional LRC, FFmpeg MKV mux, MP4 subtitle-burn, native Qt/CLI version contract and source clock/timestamp provenance.
- First use temporary SRT samples, Unicode and malformed cues, silent/mock FFmpeg argv capture, existing-output/O_EXCL checks, `--mode live` semantics and failure cleanup. **Fix no test/source fixture without separate explicit test-only approval**.
- Specifically cover `P67-GAP-01` literal-backslash-n optional real FFmpeg fixture and `P67-GAP-02` ineffective constant-only `-n` test; detect provenance and assertion weakness before claiming passing FFmpeg hardware mux/burn.
- Any later opt-in real FFmpeg (still sandboxed) requires explicit environment and runner approval; old native Kaffeine/welle.io CI failures were upstream APT/DNS or cancelled before compile. A passing Python runner cannot certify native Qt, live DAB/DVB reception or timed captions.
- Source matrix: WS01 `P67-GAP-01…10`, original CI and 20-SHA path ledger. Minimal Stage-A evidence: deterministic fixtures, no output overwrite and precise skip/failure classification.

## Stage B — secondary, separately scoped gates

- **Satellite WS03**: original PR #37 source-vs-Pages eight-asset mismatch and 1.024 vs 2.048 MS/s Meteor decoder path; no claims of decoded image. Define pure source/manifest and synthetic samplerate validation before any approved live satellite reception. Do not deploy Pages as part of test planning.
- **Geolocation WS04**: absent calibrated multi-receiver timebase, RF localization not GPS; mock propagation/source-age checks only, not a fabricated physical fix.
- **QA WS06**: five PNG SHA256 provenance, original PR #72–74 review/timeline gaps, dual Pages URLs, remote developer matrices, EN(default)/TR/DE runtime UI test plan, OS installer/rollback and no-background default. Do not copy private chats or fabricate original reviews.

## Exit criteria for Stage A

Only consider a test path **done** when: (1) exact input source SHAs and test branch are recorded; (2) tests run in a documented isolated environment without accessing host devices/services or user files; (3) test results, skips and expected negative controls are disambiguated; (4) CI URL, job, Python/Node/runtime version and reproducible command are pinned; (5) all other source/installer/logo/main/Pages/old-PR paths are proven unchanged by diff; (6) reported counts distinguish **test execution** from hardware and release acceptance. Tests-only success does **not** close all 17 gates.

## Stop conditions / permission boundary

**Not authorized by this document:** changing application source, settings, installers, unit/service startup, user SDR/DVB hardware, original version control heads, workflow behavior, approved logos, URLs/Pages, empty destination repos, initial commits, repo renames, merges, releases, migration or any model/hardware installation. Native hardware tests and application decoupling fixes require distinct approvals and separately scoped work.

No false ETA: estimated remaining hours/minutes are **unknown** until runner provisioning, test scope and measured work are available. Owner-facing coordination can be Turkish; all engineering documents and test descriptions stay English, UI en(default)/tr/de.
