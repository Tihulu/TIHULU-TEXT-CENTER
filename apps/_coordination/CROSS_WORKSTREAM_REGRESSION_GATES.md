# TIHULU — Cross-Workstream Zero-Regression Gate Plan

**Checked:** 2026-11-12 · **Status:** documentation-only review and proposed regression closure · **Source of truth:** [Issue #75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75) and [PR #82](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/82). Machine-readable companion: [CROSS_WORKSTREAM_DEPENDENCIES.json](./CROSS_WORKSTREAM_DEPENDENCIES.json).

This document **does not implement features, certify release, schedule autonomous work or authorize merges.** Six separate source-based worker reports cover **97/97 initial requirement IDs**, but none completed feature-by-feature equivalence or physical NooElec/Hauppauge device acceptance. All six worker PRs #83–#88 remain open and Draft. The worker audits did not execute tests themselves; GitHub Actions and previous feature branch CI are separate claims. Initial requirement completeness and test-path gaps still require reconciliation. Leave current apps, installed settings, existing CI workflows, Pages, installers, logos, `main` and three empty destination repositories unchanged.

## Safe execution order

**Stage A — documentation-only (currently authorized):** retain immutable Media #67 source and active Text main baselines (REG-01/02), consolidate hardware ownership and Flight/Geo semantic contracts (REG-03–05), document Satellite sample-rate/recording/Pages/test provenance (REG-06–09), distinguish Text direct RF from delegated playback (REG-10), finish historical origin and URL inventories (REG-11/12), inventory locale/logo evidence (REG-13). Preserve original worker branches; no automatic rebase. Each proposed follow-up must be done with a newly directed worker chat or explicit user-initiated Work session; GitHub comments alone do not trigger workers.

**Stage B — separately owner-approved isolated testing/integration:** after gate-specific approval, run targeted fixture and platform regression/hardware validation with exact environment, SHA and user-data backup; no source edits without a distinct feature PR. Protect all user services and recordings.

**Stage C — separately owner-approved repo migration/release:** only after gate closure and review, authorize initial writes to the three empty repositories, tested source selection, branding/localization if authorized, release/rollback and optionally a later original Text Center rename. **There is no authorization for Stage B or C in this report.**

## Coordinator gate inventory

| Gate | Severity | Owner workstreams | Source-backed risk | Next permitted step |
|---|---|---|---|---|
| **REG-01** | P0 | WS01, WS06 | Preserve Media stacked #65→#66→#67 source history | Documentation/verification design; no changes to apps |
| **REG-02** | P0 | WS05, WS06 | Protect current Text Center main against three stale archive blobs | Documentation/verification design; no changes to apps |
| **REG-03** | P0 | WS01, WS02, WS05, WS04 | Exclusive receiver and external readsb ownership | Documentation/verification design; no changes to apps |
| **REG-04** | P0 | WS02, WS04 | Resolve Flight three-versus-four RF aircraft draft semantics | Documentation/verification design; no changes to apps |
| **REG-05** | P0 | WS04, WS02 | Scientific gate for independent geolocation, timestamps and confidence | Documentation/verification design; no changes to apps |
| **REG-06** | P0 | WS03, WS06 | Resolve Satellite recording-rate versus Meteor decoder rate | Documentation/verification design; no changes to apps |
| **REG-07** | P0 | WS03 | Make long Satellite chained-capture gaps explicit | Documentation/verification design; no changes to apps |
| **REG-08** | P0 | WS03, WS05, WS06 | Satellite Pages/source deployment parity failure | Documentation/verification design; no changes to apps |
| **REG-09** | P1 | WS03, WS06, WS02 | Satellite independent branch test provenance and 11-item candidate gap correction | Documentation/verification design; no changes to apps |
| **REG-10** | P0 | WS05, WS01 | Text Center native DVB/FM/DAB claims versus passive relays and missing Journaline | Documentation/verification design; no changes to apps |
| **REG-11** | P0 | WS06, WS01, WS02, WS03, WS05 | Immutable GitHub history and provenance gaps | Documentation/verification design; no changes to apps |
| **REG-12** | P0 | WS05, WS02, WS03, WS06 | Dual GitHub Pages, PWA, raw installers and rename-safe links | Documentation/verification design; no changes to apps |
| **REG-13** | P0 | WS06, WS01, WS02, WS03, WS04, WS05 | EN(default)/TR/DE runtime UI and five approved logo binary evidence | Documentation/verification design; no changes to apps |
| **REG-14** | P0 | WS01, WS02, WS03, WS04, WS05, WS06 | Native installs, portable packages and versioned rollback across five apps | Documentation/verification design; no changes to apps |
| **REG-15** | P0 | WS06 | Evidence quality and truthful completion/ETA accounting | Documentation/verification design; no changes to apps |
| **REG-16** | P0 | WS01, WS05, WS06 | Media Teletext/Whisper/lyrics and GPU caption-timing no-regression | Documentation/verification design; no changes to apps |
| **REG-17** | P0 | WS02, WS06, WS01, WS03, WS04, WS05 | Canonical developer-agent and feature/component/model matrix parity | Documentation/verification design; no changes to apps |

## Gate-by-gate evidence and acceptance contract

### REG-01 — Preserve Media stacked #65→#66→#67 source history

- **Priority / owners / requirement IDs:** P0; WS01, WS06; `MEDIA-036`, `MEDIA-038`, `MEDIA-039`, `CROSS-010`.
- **Observed evidence (not acceptance):** The documentation branch descends from #66 but the unmerged #67 recording/export head contains 20 additional commits and source/test files. The overlap of three source paths is not proof of a textual conflict.
- **Read-only next action:** Create an immutable eight-path PR #67 delta inventory with blob SHA, test and original discussion links. Cross-reference Media #65/#66 ancestry and expected export modes without copying app code.
- **Later acceptance evidence required:** Later separately approved integration must show selected code+tests retain #67 recording/export capability and old Media features, compare rollback and FFmpeg output on isolated sample recordings, and prevent accidental overwrite of user files.
- **Separate owner approval required before:** Selecting a migration source tree, resolving or applying code changes, merging or writing to new Media repository.
- **Dependency gate(s):** none; can be investigated independently.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/10fd5ef9c51df2c330c8c5823ce789e31db519b2/apps/_coordination/workstreams/01/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/e69c2b6eac7deeca313925bf99af31f8c9434f34/apps/_coordination/workstreams/06/REPORT.md), [3](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/67).

### REG-02 — Protect current Text Center main against three stale archive blobs

- **Priority / owners / requirement IDs:** P0; WS05, WS06; `TEXT-001`, `TEXT-007`, `CROSS-001`.
- **Observed evidence (not acceptance):** Retained main source differs from the old audit snapshot for textcenter/compute.py, textcenter/speech.py and textcenter/transcripts.py. A snapshot is not an authoritative current Text Center baseline.
- **Read-only next action:** Pin current main and worker SHA/blob pairs, map behavioral/contract differences and distinguish historical snapshots from active source. No restore, rebase or cherry-pick.
- **Later acceptance evidence required:** Later isolated comparison of current active UI/API/transcript output, files, settings and URLs; preserve unchanged main unless a distinct authorized feature PR passes parity.
- **Separate owner approval required before:** Any change to current main, Text Center runtime or archive replacement.
- **Dependency gate(s):** none; can be investigated independently.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/5a772fd399c2d743207adb69dc33bd9922fee068/apps/_coordination/workstreams/05/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/commit/1fffb711bfbb7c4abaf55299fa9240e5db3e1cde).

### REG-03 — Exclusive receiver and external readsb ownership

- **Priority / owners / requirement IDs:** P0; WS01, WS02, WS05, WS04; `MEDIA-004`, `MEDIA-016`, `FLIGHT-014`, `TEXT-005`, `GEO-006`.
- **Observed evidence (not acceptance):** Flight main close(release_local_service=True) may stop pre-existing shared readsb; Draft Flight PR #7 instead tracks app ownership. RF-only OFF behavior in Geolocation does not prove device lease release. A global Hard Stop contract is not verified.
- **Read-only next action:** Write a cross-app device-owner state table for external/app-started/direct receivers, RF On/Off, explicit Stop, application close, failure, service restart and sudo-denied outcomes.
- **Later acceptance evidence required:** On an owner-approved isolated Pop!_OS SDR session, record pre/post active readsb/tar1090/gqrx/welle processes, RTL-SDR lease and safe failure outcomes. Non-owned services must remain running; on-demand default preserved.
- **Separate owner approval required before:** Hardware session that changes live services, runtime receiver lifecycle code, privileged setup or shared installations.
- **Dependency gate(s):** `REG-02`.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/1253f55604b1401927f3a1b7a661c7f9b1fa8386/apps/_coordination/workstreams/02/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/b62ba58287ef9e76d42ca807829b26da68177e18/apps/_coordination/workstreams/04/REPORT.md), [3](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/10fd5ef9c51df2c330c8c5823ce789e31db519b2/apps/_coordination/workstreams/01/REPORT.md), [4](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/control.py#L233-L262), [5](https://github.com/Tihulu/tihulu-flight-radar/blob/4ef8245b87fc78cec6cc4f5f9043d68e08cf45d3/tihulu_flight_radar/control.py#L239-L260).

### REG-04 — Resolve Flight three-versus-four RF aircraft draft semantics

- **Priority / owners / requirement IDs:** P0; WS02, WS04; `FLIGHT-010`, `FLIGHT-011`, `GEO-005`, `GEO-008`.
- **Observed evidence (not acceptance):** Flight canonical main models an upper-bound feasible area with >=3 RF ICAOs; Draft PR #13 requires >=4 independent ICAOs and five distinct history models. Neither is a precise receiver GPS fix.
- **Read-only next action:** Record user-facing observed main vs draft contract in a decision table: 3 vs 4, independent ICAO validity, LIVE10/LIVE-X/BEST/HISTORY/HISTORY BEST, uncertainty and RF provenance; propose tests per mode.
- **Later acceptance evidence required:** Only after a separately approved specification and review, compare real RF records with replayed/synthetic geometry, including Internet spoof exclusion, permutation invariance, no center-as-GPS, expected persistence and fallback.
- **Separate owner approval required before:** Changing algorithm thresholds, model UI, histories or promoting Draft #13 to released behavior.
- **Dependency gate(s):** `REG-03`.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/1253f55604b1401927f3a1b7a661c7f9b1fa8386/apps/_coordination/workstreams/02/REPORT.md), [2](https://github.com/Tihulu/tihulu-flight-radar/blob/059b391280635d9aa4d2ac73c7318af9e135ebf5/tihulu_flight_radar/web/receiver_coverage.js#L89-L106), [3](https://github.com/Tihulu/tihulu-flight-radar/blob/950f8278a625ce13a9a3c7e21bf9bf76d4b5888e/tihulu_flight_radar/web/rf_history_models.js#L1-L43).

### REG-05 — Scientific gate for independent geolocation, timestamps and confidence

- **Priority / owners / requirement IDs:** P0; WS04, WS02; `GEO-002`, `GEO-003`, `GEO-005`, `GEO-008`, `FLIGHT-011`.
- **Observed evidence (not acceptance):** ADS-B aircraft coordinates and RSSI radius hypotheses do not provide independent receiver self-location, calibrated TDOA, GNSS-SDR pseudorange PVT or statistically validated PSF/Gaussian covariance.
- **Read-only next action:** Inventory required independent receiver stations, hardware timebase/synchronization, timestamps, measured ranges, calibration datasets, uncertainty model and confidence provenance. Mark unavailable conditions explicitly.
- **Later acceptance evidence required:** Independent calibrated measurement corpus with ground-truth receiver location, timing provenance, uncertainty calibration and no false location claims; native GNSS acquisition/PVT separately verified if available.
- **Separate owner approval required before:** New positioning implementation, hardware capture, location-accuracy claims or installation of native GNSS backend.
- **Dependency gate(s):** `REG-04`.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/b62ba58287ef9e76d42ca807829b26da68177e18/apps/_coordination/workstreams/04/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/1253f55604b1401927f3a1b7a661c7f9b1fa8386/apps/_coordination/workstreams/02/REPORT.md).

### REG-06 — Resolve Satellite recording-rate versus Meteor decoder rate

- **Priority / owners / requirement IDs:** P0; WS03, WS06; `SAT-003`, `SAT-005`, `SAT-008`.
- **Observed evidence (not acceptance):** Native scheduling permits sample_rate 1024000 or 2048000, but decode_meteor() forwards fixed SatDump --samplerate 1024000 for the recording. No lossless 2.048 MS/s decode acceptance is proved.
- **Read-only next action:** Record capture metadata contract (Hz, CU8, duration, UTC, original path) and SatDump argv across each supported rate; propose fixture tests for correct-rate forwarding, unsupported-rate rejection and preservation of input data.
- **Later acceptance evidence required:** Reproducible known-rate IQ fixture and owner-approved real Meteor dataset demonstrate decoder receives correct sample rate, no fabricated images, original IQ preserved and correct empty-CADU/error classification.
- **Separate owner approval required before:** Decoder argument changes, real receiver collection, sample conversion or decoder installation.
- **Dependency gate(s):** none; can be investigated independently.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/284944e1dc167f6b60bf762889a3c75bf28f47e2/apps/_coordination/workstreams/03/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/803529ba90f43a6cb1fb977869c650ddf5db448a/satellite_center/__main__.py#L881-L894), [3](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/803529ba90f43a6cb1fb977869c650ddf5db448a/satellite_center/__main__.py#L1778-L1797).

### REG-07 — Make long Satellite chained-capture gaps explicit

- **Priority / owners / requirement IDs:** P0; WS03; `SAT-002`, `SAT-003`, `SAT-004`, `SAT-008`.
- **Observed evidence (not acceptance):** Browser segmented capture defaults to a 6-second interpart budget and native chains reserve 21–60-second restart windows. A separate bounded native single-file capture path exists; there is no proof all chained captures are gapless.
- **Read-only next action:** Specify manifest-level segment start/end UTC, missing-sample/coverage flag, rate, loss boundaries and no-overwrite ownership; compare browser and native semantics.
- **Later acceptance evidence required:** After approval, safe fixture file-segment checks and physical recording verify uninterrupted intervals only where actually supported; UI must disclose gaps, never claim lossless chained reception by default.
- **Separate owner approval required before:** Changing capture scheduler, hardware device acquisition, browser/WebUSB behavior or existing recording files.
- **Dependency gate(s):** `REG-06`.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/284944e1dc167f6b60bf762889a3c75bf28f47e2/apps/_coordination/workstreams/03/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/803529ba90f43a6cb1fb977869c650ddf5db448a/satellite_center/browser/chained_capture.mjs#L1-L53).

### REG-08 — Satellite Pages/source deployment parity failure

- **Priority / owners / requirement IDs:** P0; WS03, WS05, WS06; `SAT-001`, `SAT-008`, `TEXT-008`, `CROSS-006`.
- **Observed evidence (not acceptance):** The original satellite PR #37 CI run 42559046861 failed a Pages/source parity check for eight browser assets, despite separate portable synthetic jobs succeeding.
- **Read-only next action:** Preserve eight failing asset names and source/current Pages blob SHA manifest, differentiate review branch vs public URLs and capture intended deployment/rollback steps as a future checklist.
- **Later acceptance evidence required:** Post-approval review of all expected hashes, public Pages HTTP paths, PWA/service worker cache, URLs, offline operation and source revision markers at both retained and new publication sites.
- **Separate owner approval required before:** Any Pages publish, workflow/source write, CDN/PWA change, repo rename or installer URL repoint.
- **Dependency gate(s):** none; can be investigated independently.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/284944e1dc167f6b60bf762889a3c75bf28f47e2/apps/_coordination/workstreams/03/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/42559046861).

### REG-09 — Satellite independent branch test provenance and 11-item candidate gap correction

- **Priority / owners / requirement IDs:** P1; WS03, WS06, WS02; `SAT-005`, `SAT-006`, `SAT-008`, `FLIGHT-016`, `FLIGHT-017`, `CROSS-007`, `CROSS-009`, `CROSS-015`.
- **Observed evidence (not acceptance):** Initial coordinator index identifies 11 without local test-file candidates. Satellite PR #37 contains 22 relevant test sources absent from the WS03 starting branch; presence there does not mean tested or transferred. Flight 016/017 lack direct candidates.
- **Read-only next action:** Publish a branch-aware source/test provenance index distinguishing baseline candidates, PR #37 additional tests, executed CI, hardware tests, policy gates and actual absence. Avoid overwriting initial candidate map without a documented reconciliation.
- **Later acceptance evidence required:** Each gap labeled either source/test linked with SHA plus genuine execution, future test required, or policy/manual gate; never infer 97 tested from 97 mapped.
- **Separate owner approval required before:** Copying test source into active branches, workflow changes, implementing tests that write to application trees or source migrations.
- **Dependency gate(s):** none; can be investigated independently.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/284944e1dc167f6b60bf762889a3c75bf28f47e2/apps/_coordination/workstreams/03/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/e69c2b6eac7deeca313925bf99af31f8c9434f34/apps/_coordination/workstreams/06/REPORT.md), [3](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/TEST_CANDIDATE_GAP_TRIAGE.md).

### REG-10 — Text Center native DVB/FM/DAB claims versus passive relays and missing Journaline

- **Priority / owners / requirement IDs:** P0; WS05, WS01; `TEXT-002`, `TEXT-003`, `TEXT-004`, `MEDIA-007`, `MEDIA-011`.
- **Observed evidence (not acceptance):** Retained Text Center has partial FM RDS and read-only welle-cli DAB metadata bridge, but Journaline is unimplemented; passive DVB diagnostic/upstream MPEG-TS relay does not demonstrate native off-air tuner/Teletext scan. Media native source is distinct.
- **Read-only next action:** Build a source-of-truth capability matrix per native Media, retained Text, external decoder, browser, actual hardware, UI claim and fallback. Preserve existing behavior without copying Media semantics into Text.
- **Later acceptance evidence required:** Later owner-authorized real Hauppauge scan/lock/Teletext and NooElec RDS/DAB DLS/MOT sessions with labels and failure outputs; include mixed TV/radio device ownership, timestamps, actual hardware path and original user settings.
- **Separate owner approval required before:** Changing source/native bridge, controlling tuner, installing dependencies, claiming Journaline or native Text TV feature completeness.
- **Dependency gate(s):** `REG-02`, `REG-03`.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/5a772fd399c2d743207adb69dc33bd9922fee068/apps/_coordination/workstreams/05/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/10fd5ef9c51df2c330c8c5823ce789e31db519b2/apps/_coordination/workstreams/01/REPORT.md), [3](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/3884cc3b0b603f7a555d1801ed12283d9df4b63f/textcenter/dab_bridge.py#L1-L12).

### REG-11 — Immutable GitHub history and provenance gaps

- **Priority / owners / requirement IDs:** P0; WS06, WS01, WS02, WS03, WS05; `CROSS-005`, `CROSS-010`, `FLIGHT-017`, `TEXT-007`.
- **Observed evidence (not acceptance):** Two 67-entry origin history ledgers omit original PRs #72–#74; eight Flight #13 PR comment permalinks and eleven satellite Issue #20/#21 comments are linked, but full review/timeline reconciliation and verified author/time details remain incomplete.
- **Read-only next action:** Prepare a per-original-record manifest by immutable repo ID and source PR/Issue/review/comment permalink; add missing #72–#74 history, preserve null timestamps, and explicitly list non-exportable or inaccessible evidence.
- **Later acceptance evidence required:** A reviewer can follow all historical links and verify original source ancestry, authors/comments/review context without false recreated approvals, without private chat dumps and with explicit transfer gaps.
- **Separate owner approval required before:** Rewriting archives in active repos, copying private content, restructuring original PRs, migrating Git history or renaming repos.
- **Dependency gate(s):** `REG-01`, `REG-02`.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/e69c2b6eac7deeca313925bf99af31f8c9434f34/apps/_coordination/workstreams/06/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/1253f55604b1401927f3a1b7a661c7f9b1fa8386/apps/_coordination/workstreams/02/REPORT.md), [3](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/5a772fd399c2d743207adb69dc33bd9922fee068/apps/_coordination/workstreams/05/REPORT.md).

### REG-12 — Dual GitHub Pages, PWA, raw installers and rename-safe links

- **Priority / owners / requirement IDs:** P0; WS05, WS02, WS03, WS06; `TEXT-008`, `FLIGHT-017`, `CROSS-005`, `CROSS-006`.
- **Observed evidence (not acceptance):** Flight standalone and Text mirror gh-pages revision blobs and seven sampled assets matched at a pinned Flight main SHA, but live HTTP/CDN/PWA parity is unverified. Origin workflow contains hardcoded previous repo URLs and satellite Pages asset drift is documented.
- **Read-only next action:** Produce a URL and immutable-source SHA checklist: current Flight independent and Text mirror Pages, every service-worker scope, old raw install URL, asset digest, OAuth/WebUSB origin boundary, archive and redirect, with before/after expected outcomes.
- **Later acceptance evidence required:** Only after separate rename/cutover approval, verify live status and redirects, 404/cache offline fallback, two-source revision equivalence, old one-line installer/0.3.1 rollback and PWA behavior under both origins.
- **Separate owner approval required before:** Rename, move, delete, republish Pages, rewrite workflows/service worker, change installer or default site.
- **Dependency gate(s):** `REG-08`, `REG-11`.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/1253f55604b1401927f3a1b7a661c7f9b1fa8386/apps/_coordination/workstreams/02/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/5a772fd399c2d743207adb69dc33bd9922fee068/apps/_coordination/workstreams/05/REPORT.md), [3](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/284944e1dc167f6b60bf762889a3c75bf28f47e2/apps/_coordination/workstreams/03/REPORT.md).

### REG-13 — EN(default)/TR/DE runtime UI and five approved logo binary evidence

- **Priority / owners / requirement IDs:** P0; WS06, WS01, WS02, WS03, WS04, WS05; `CROSS-002`, `CROSS-003`, `CROSS-009`.
- **Observed evidence (not acceptance):** All five user-facing interfaces require English default with Turkish/German options, but full installed UI path/localization tests are not complete. Approval manifest lists five PNG SHA256 values; worker did not independently rehash binary assets. No replacement logos are authorized.
- **Read-only next action:** Inventory current UI strings, unsupported locale/default/fallback coverage, existing assets and source asset hashes without adding icons, online images or translations to application trees.
- **Later acceptance evidence required:** Under separate UI/branding approval, per-platform visual+accessibility locale switching, persistence, fallback, full RTL/non-RTL behavior and exact binary SHA256 proofs for approved assets; old UI and rollback still match.
- **Separate owner approval required before:** Adding/changing UI translations, activating/changing icons, new SVG variants, installer branding or releases.
- **Dependency gate(s):** `REG-11`.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/e69c2b6eac7deeca313925bf99af31f8c9434f34/apps/_coordination/workstreams/06/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/5a772fd399c2d743207adb69dc33bd9922fee068/apps/_coordination/workstreams/05/REPORT.md).

### REG-14 — Native installs, portable packages and versioned rollback across five apps

- **Priority / owners / requirement IDs:** P0; WS01, WS02, WS03, WS04, WS05, WS06; `CROSS-001`, `CROSS-004`, `CROSS-011`, `MEDIA-001`, `FLIGHT-014`.
- **Observed evidence (not acceptance):** Audited portable/synthetic CI is not a measured Windows/macOS/Linux/Raspberry Pi installed application parity result; Flight legacy 0.3.1, native installers, user settings/data and source histories must remain preserved. Three destination repos are not yet cut over.
- **Read-only next action:** Write a platform-by-platform proposed build/smoke/rollback/backup matrix and request explicit approval boundary for repo first commits, source staging, platform installer updates, merges and releases.
- **Later acceptance evidence required:** After separate authorization, signed version pin, build hashes, native smoke/hardware parity, settings+user-recording backup restore, rollback checks on each supported platform; no release without critical gate closure.
- **Separate owner approval required before:** First commit to empty target, original repo rename, migration, installer/release changes, merges or service permission modifications.
- **Dependency gate(s):** `REG-01`, `REG-02`, `REG-03`, `REG-08`, `REG-11`, `REG-12`.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/10fd5ef9c51df2c330c8c5823ce789e31db519b2/apps/_coordination/workstreams/01/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/1253f55604b1401927f3a1b7a661c7f9b1fa8386/apps/_coordination/workstreams/02/REPORT.md), [3](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/284944e1dc167f6b60bf762889a3c75bf28f47e2/apps/_coordination/workstreams/03/REPORT.md), [4](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/b62ba58287ef9e76d42ca807829b26da68177e18/apps/_coordination/workstreams/04/REPORT.md), [5](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/5a772fd399c2d743207adb69dc33bd9922fee068/apps/_coordination/workstreams/05/REPORT.md), [6](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/e69c2b6eac7deeca313925bf99af31f8c9434f34/apps/_coordination/workstreams/06/REPORT.md).

### REG-15 — Evidence quality and truthful completion/ETA accounting

- **Priority / owners / requirement IDs:** P0; WS06; `CROSS-009`, `CROSS-012`, `CROSS-015`.
- **Observed evidence (not acceptance):** 97/97 requirements had initial source-based audits; no worker directly executed tests or physical RF/DVB sessions. Six worker PR heads had successful Text Center tests GitHub Actions, distinct from failed original satellite PR #37 Pages parity. None is a five-app installed acceptance certificate.
- **Read-only next action:** Separate source-reviewed, partial draft-coded, unit/CI executed, hardware-verified, released and original requirement-completeness claims in progress. Require reproducible run IDs, exact SHA and logs before promoting any gate.
- **Later acceptance evidence required:** Every critical gate gets evidence URL, exact SHA, reproducible result/runner/device or explicit unknown. ETA hours/minutes remain null until scoped tasks, environments, blocked dependencies and measured effort are present.
- **Separate owner approval required before:** Claiming release or changing scope, running user-host hardware tests or applying code.
- **Dependency gate(s):** `REG-03`, `REG-06`, `REG-08`, `REG-14`.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/e69c2b6eac7deeca313925bf99af31f8c9434f34/apps/_coordination/workstreams/06/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/PROGRESS.json).


### REG-16 — Media Teletext/Whisper/lyrics and GPU caption-timing no-regression

- **Priority / owners / requirement IDs:** P0; WS01, WS05, WS06; `MEDIA-007`, `MEDIA-015`, `MEDIA-018`, `MEDIA-019`, `MEDIA-021`, `MEDIA-024`, `MEDIA-027`, `MEDIA-028`, `MEDIA-031`, `CROSS-013`.
- **Observed evidence (not acceptance):** Media source paths include Teletext matching, subtitle offset scheduler, Qwen fallback, lyrics and native hardware UI. Most existing test-source contracts are static or mock/fixture; no worker ran real TV/radio, fullscreen, karaoke alignment, 10-second buffer or RTX/CPU/NPU model parity trials.
- **Read-only next action:** Construct a source-origin, timing and failure-state test contract: priority among DVB Teletext/DAB DLS/Whisper/lyrics; mismatch fallback; a single offset application; silence/music handling; local full-file prepass and video/audio player persistence; optional GPU/remote fallback never masks spoken text.
- **Later acceptance evidence required:** Later explicit approval to run isolated timed speech/lyrics fixtures, then native TV/radio and user-provided sample media playback with traceable word/cue clocks, synchronized offset, independent karaoke/manual controls and no repeated buffering, cross-language subtitle fallback and safe model selection. Separate real hardware evidence required.
- **Separate owner approval required before:** Editing timing, alignment, model/backend selection, translation, receiver selection, installed local AI dependencies or user playback settings.
- **Dependency gate(s):** `REG-01`, `REG-03`.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/10fd5ef9c51df2c330c8c5823ce789e31db519b2/apps/_coordination/workstreams/01/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/TEST_EVIDENCE_QUALITY.md).

### REG-17 — Canonical developer-agent and feature/component/model matrix parity

- **Priority / owners / requirement IDs:** P0; WS02, WS06, WS01, WS03, WS04, WS05; `FLIGHT-016`, `CROSS-002`, `CROSS-007`, `CROSS-010`.
- **Observed evidence (not acceptance):** Flight main has substantive AGENTS.md but not independently canonical root CLAUDE.md, DEEPSEEK_START.md or FEATURE/COMPONENT/MODEL/DEVELOPMENT_AGENT JSON matrices and original source-gap documents. Origin-side matrix snapshots must not be mistaken for Flight-owned files.
- **Read-only next action:** Inventory expected and actually present agent entrypoints and matrices in each of five canonical code bases, with owning repository ID and branch SHA; document schema validity, cross-agent instructions, English engineering policy and explicit origin history-fallback gaps.
- **Later acceptance evidence required:** After separate authorization, each canonical app repo includes accurate machine-checkable matrices and Claude/DeepSeek routing docs with links to actual app source/test SHA; JSON schema/path validations pass without touching working runtime defaults.
- **Separate owner approval required before:** Committing new developer files to active Flight repo or three empty destinations; changing repository ownership, source exports or release docs.
- **Dependency gate(s):** `REG-11`.
- **Evidence:** [1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/1253f55604b1401927f3a1b7a661c7f9b1fa8386/apps/_coordination/workstreams/02/REPORT.md), [2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/e69c2b6eac7deeca313925bf99af31f8c9434f34/apps/_coordination/workstreams/06/REPORT.md).

## Current coordinator CI — OPEN failure, not an application regression certificate

[Run 43119633429](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43119633429) failed on the coordinator head `d3f9dffd85b5e9e89f043a5c9b5ea26888783134`. Python 3.11/3.12/3.13 jobs failed the offline unit-test step. Python 3.12 log recorded **696 tests, 2 failures**: `test_master_zero_regression_coordination.py` expects `completed_audits == 0`, and `test_six_parallel_workstream_gates.py` expects `started_by_other_chats == 0`; both are now **6**, supported by the six committed reports and JSON evidence files. These fixed initial-state test assertions are stale; **do not falsify the progress counts** or call the coordinator PR green. This documentation phase does not modify Python test sources. Proposed narrowly scoped test maintenance and proof requirements: [COORDINATION_CI_CONTRACT_DRIFT.md](./COORDINATION_CI_CONTRACT_DRIFT.md). Other worker-head CI successes and Satellite PR #37 Pages parity failure remain separate.

## Explicit stop conditions

1. **No feature/source drift:** Do not merge Media #67 or Flight #7/#13 or any other old PR, cherry-pick feature commits, rebase another worker's branch, change Text current main, or silently replace existing user installs.
2. **No false physical proof:** Green offline/static/fixture CI is not a reception, DVB lock, automatic Journaline/Teletext or independent RF location validation. Preserve real failure outputs and original IQ/media.
3. **No hidden service ownership change:** Never stop external `readsb`, `tar1090`, `gqrx`, `welle` or tuner processes on the user's system in an audit.
4. **No unsafe URL/brand/locale rewrite:** No live GitHub Pages/workflow/PWA/installer repoints, original repository rename, substitute logos or user-facing language changes without separate approval.
5. **No fabricated progress or ETA:** Initial source audit completion (97/97) is not an implementation percent. Remaining hours and minutes are **unknown** until test environments, code reconciliation, owner approvals and platform/hardware workloads are measured. English technical record; user-facing apps' target locales remain `en` default, `tr`, `de`.

## Worker handoff contract

Open or update the *existing* worker child Issue matching the gate owner (WS01 [#76](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/76), WS02 [#77](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/77), WS03 [#78](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/78), WS04 [#79](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/79), WS05 [#80](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/80), WS06 [#81](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/81)). Workers may commit only to their own report/evidence directory and must keep Draft PRs unmerged. The coordinator owns this shared gate plan and overall progress only.
