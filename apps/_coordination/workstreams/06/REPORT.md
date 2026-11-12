# TIHULU Workstream 06 — Cross-App Provenance, Branding and QA Audit

**Scope:** Source-backed audit and documentation only.  
**Assigned Draft PR:** [#88](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/88) — branch `audit/ws06-provenance-qa-2026-11-11`  
**Assigned Issue:** [#81](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/81)  
**Central coordinator:** [#75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75)  
**Detailed machine-readable results:** [EVIDENCE.json](EVIDENCE.json)  
**Original repository identity:** `Tihulu/TIHULU-TEXT-CENTER`, GitHub numeric ID **1447637221** (original HTML URLs are preserved).

## 1. Scope and results

This worker read [TASK.md](TASK.md), both issues, the 97-ID master requirements and candidate-map documents, historical PR and Issue metadata, original comment/review endpoints, five-app matrix/localization files, branding and migration policies, six selected test source files and two optional remote-processing source files. No application source, installer, settings, release, icon or receiver was modified. No old PR was merged or rebased, no destination repository was initialized and no user device was opened.

| Measure | Observed result |
|---|---:|
| CROSS requirements reviewed | **15 / 15** |
| Requested/policy-only; not implementation-proven | **11** |
| Partial draft source/docs/infrastructure found; not accepted | **4** |
| Unit-verified / device-verified / released by this audit | **0 / 0 / 0** |
| Assigned IDs with a candidate test file | **9 / 15** |
| Assigned IDs with no identified candidate test file | **6 / 15** |
| Distinct candidate test source files directly inspected | **6** |
| Test commands run / real receiver tests run | **0 / 0** |
| Old app PRs checked for reviews, threads and top-level comments | **12** |
| Original PR #13 comments with preserved public permalinks | **8** |
| Additional original Issue #20/#21 comments linked in this audit | **11** |
| App FEATURE/COMPONENT/MODEL/LOCALIZATION files found at source | **20** |
| Approved logo master hash entries / byte-recomputed hashes | **5 / 0** |
| Empty destination app repositories observed | **3** |
| Evidence-based hours/minutes remaining | **unknown** |

**State interpretation:** `requested` means recorded requirement/policy, not working functionality. `draft-coded` means partial files, executable code or coordination infrastructure were found, not that any full acceptance criterion or test passed. There are **no** `unit-verified`, `hardware-verified` or `released` requirements certified here.

## 2. Per-requirement source/test audit

All source candidate links are pinned to the coordinator map's origin commit [`803529ba90f43a6cb1fb977869c650ddf5db448a`](https://github.com/Tihulu/TIHULU-TEXT-CENTER/commit/803529ba90f43a6cb1fb977869c650ddf5db448a). The matching exact source paths, test source blob SHAs and non-destructive proposed tests are in EVIDENCE.json. **No tests were executed**, and code path existence is not an implementation claim.

| ID | Classification | Direct source/audit finding | Test source inspected or gap |
|---|---|---|---|
| CROSS-001 | requested | Zero-regression stop rule documented in coordination protocol; physical/installed baseline not compared. | `test_master_zero_regression_coordination.py` — static checks, NOT RUN |
| CROSS-002 | requested | English internals and en(default)/tr/de UI contract documented; all-five runtime UI locale coverage not audited. | `test_verified_destination_repos_and_red_logos.py` — static, NOT RUN |
| CROSS-003 | requested | Five approved PNG SHA-256 entries are **recorded**, but no PNG bytes or ZIP were obtained for independent hash verification; no genuine SVG. | `test_origin_fallback_approved_branding.py` — asserts metadata shape, NOT RUN |
| CROSS-004 | requested | Live GitHub repository metadata confirms three 0-KB empty destination shells; Text Center retained; Flight Radar already separate. | `test_text_center_retained_canonical.py` — static, NOT RUN |
| CROSS-005 | requested | 67 historical PR links/four Issue description links, incomplete review/timeline exports; 19 comment permalinks linked without bodies; missing PR #72–#74 ledger coverage. | `test_origin_fallback_approved_branding.py` — static, NOT RUN |
| CROSS-006 | requested | Rename link policy and original ID exist; redirects, Pages/PWA, raw installer and workflow links untested; no rename performed. | **No test candidate** |
| CROSS-007 | draft-coded | Origin contains app metadata; canonical Flight main has `AGENTS.md` but lacks `CLAUDE.md`, `DEEPSEEK_START.md` and central developer matrix file. | `test_development_agent_entrypoints.py` — origin static, NOT RUN |
| CROSS-008 | draft-coded | Six non-overlapping audit PR/Issue assignments exist. Their status is not evidence of six independently completed audits. | `test_master_zero_regression_coordination.py` — static, NOT RUN |
| CROSS-009 | requested | Static/source contract, fixture/mock and synthetic RF test types are distinguished; no hardware acceptance proven. | **No test candidate** |
| CROSS-010 | requested | Media #67 contains **20 commits not in worker/docs branch**; old source/Flight PRs and rollback must remain intact. | **No test candidate** |
| CROSS-011 | requested | First repo commits, import, icon integration, merges, releases and rename are explicitly owner-gated. | **No test candidate** |
| CROSS-012 | draft-coded | `PROGRESS.json` tracks partial counts and null ETA. Coordinator branch has advanced independently; no worker rebase. | **No test candidate** |
| CROSS-013 | draft-coded | `tv_center/remote_gpu.py` contains opt-in TLS endpoint/token code, but no paired host or hardware acceptance. | `test_tv_ai_profiles_remote_startup.py` — fixture/mock/unit source, NOT RUN |
| CROSS-014 | requested | Survival Kit News/Emergency/AI remain out of five-app cutover; separate full inventory not verified. | **No test candidate** |
| CROSS-015 | requested | Requirements retain explicit unknown/unverified states; cannot promote from candidate source/test paths alone. | `test_master_zero_regression_coordination.py` — static, NOT RUN |

Six unique inspected source-test blobs (not execution results):
- `tests/test_master_zero_regression_coordination.py` — blob `d1cff865d479121f09ff56f6c2ce73a6e9e2c8ca`
- `tests/test_verified_destination_repos_and_red_logos.py` — blob `a56ad63c08ea942619867293bd36da27c3cdd6c6`
- `tests/test_origin_fallback_approved_branding.py` — blob `fd7752514666a525472d501f05a8b57e286ea550`
- `tests/test_text_center_retained_canonical.py` — blob `1796c882bf1ef95adad7d251d973019713edf500`
- `tests/test_development_agent_entrypoints.py` — blob `a76587b19fcc73d49463df0f290567baca259d61`
- `tests/test_tv_ai_profiles_remote_startup.py` — blob `ee85652f77759414f8f277a7b4ff50ac6b0e41b9`

The last tests' code contains mock-based remote-policy assertions and source-side paths; these do **not** verify real GPU pairing or data handling on the user's equipment.

## 3. Original PR / Issue history and review coverage

### Public original GitHub records

- Text Center source PRs [#65](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/65) through [#74](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/74): each Issue/PR metadata endpoint was retrieved, preserving author `Tihulu`, original creation timestamp, number and URL (all ten rows in EVIDENCE.json). For these ten PRs the connector returned **0 top-level comments, 0 review submissions, 0 inline review threads**. Zero observed is **not** evidence of missing approvals or unavailable history elsewhere.
- Canonical Flight Radar [PR #7](https://github.com/Tihulu/tihulu-flight-radar/pull/7) and [PR #13](https://github.com/Tihulu/tihulu-flight-radar/pull/13), repo ID **1447534043**: 0 review submissions and 0 inline review threads were returned for each. PR #13 has **8 original public top-level comments**: original numeric IDs, author and created/updated timestamps remain linked via `apps/_coordination/PR_COMMENT_LINK_INDEX.json`. No copied comment body or manufactured review was made.
- Original source Issues [#2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/2), [#20](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/20), [#21](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/21), [#34](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/34) were retrieved. Issues #20 and #21 expose **5 + 6 original public comments**. EVIDENCE.json links all eleven distinct `#issuecomment-...` permalinks with source author only. The connector did **not** return their comment creation timestamps, so those are `null` rather than fabricated.
- `apps/_archives/HISTORY_COVERAGE_AUDIT.json` and `PORTABLE_HISTORY_LINK_MAP.json` currently contain **67 PR link entries and four Issue description entries**. Neither 67-entry PR list includes newer source PRs **#72, #73 or #74**. That is a concrete archive-coverage gap, not proof original GitHub objects were lost.
- Review/approval transfer, issue event timelines, original full discussions, independent archived snapshots and user-approved private chat export remain incomplete. Native historical GitHub approvals cannot be recreated as if originally made in a new repository.

### Verified ancestry and branch drift

`#65 → #66 → #67` is the source branch lineage described by [PR ancestry audit](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/803529ba90f43a6cb1fb977869c650ddf5db448a/apps/_coordination/PR_ANCESTRY_AUDIT.json). A fresh comparison of the actual Media PR #67 source SHA `4e62e21cd5252df8a04f9ceadc429f4b116412ce` with the original WS06 branch head `22d80141ea00f13a502a589bb615dafedf8062cc` found **diverged, worker ahead 45, behind 20, merge base `20379152be2751e5d89a8bdbac85fb15fc6b3c4e`**. Copying coordinator/WS06 app snapshots as the complete Media implementation would omit the #67 branch work. It is a **preservation risk**, not a demonstrated textual merge conflict.

The WS06 branch and updated coordinator branch also diverged at `a00b8d97ce04e6279c6edc1035656a86924cc101` (WS06 ahead 1, behind 4, before these report commits). The worker did not merge, rebase, cherry-pick or change the coordinator-owned source of truth.

## 4. Approved artwork and language policy

The [approved branding manifest](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/803529ba90f43a6cb1fb977869c650ddf5db448a/apps/BRANDING_APPROVED_MANIFEST.json) declares exactly five 1254×1254 PNG masters: Media, Satellite, RF Geolocation, Text and Flight. It records individual SHA-256 values and pack SHA-256 `49eeccd46ab8b6e630b5567b4e08c0580f22430696de8e215b80d21a52043f84`, but the master PNG bytes and ZIP are not in the source Git tree and were not available for recalculation by this worker. The static test only validates manifest structure and stored values. **Approval recorded ≠ independently byte-hash verified, staged asset imported or production icon activated.** Genuine editable SVG assets remain future work.

Technical development files and agent instructions target English. Each of the five `apps/<app>/LOCALIZATION_CONTRACT.json` documents `en` default with `tr` and `de`, fallback, persistence and future locale tests; runtime UI coverage is explicitly marked not audited. The original source repo contains five app-local FEATURE, COMPONENT, MODEL and LOCALIZATION documents (**20 verified file paths**). Actual destination canonical matrix coverage is not established: three destination repositories remain empty, and independent Flight Radar `main` lacks root `CLAUDE.md` and `DEEPSEEK_START.md` even though its `AGENTS.md` exists. This is a documentation/navigation gap, not permission to add files now.

## 5. Cross-app, non-destructive regression and release gates

Every acceptance ID has a specific future test in EVIDENCE.json. These tests require separate task approval before they change installed software or invoke devices.

| Gate | Required independent verification before any approved cutover |
|---|---|
| App parity and state | Hash-pinned file trees, installed binary behavior, settings/data/recordings unchanged; no silent new background work or SDR device acquisition; real hard stop and receiver release |
| Media source preservation | Preserve #65 lyrics/Teletext/captions and #67 recording/export; source-branch comparison, timed subtitles, existing audio/video, no overwrites, FFmpeg mux, native DVB/DAB/Hauppauge/NooElec if permitted |
| Flight and localization | Flight's separate canonical sources, two Pages, I/R provenance, legacy 0.3.1 rollback; explicit English/Turkish/German UI keys, locale switch, fallback, saved preference and responsive accessibility across all five |
| Satellite/Geolocation/Text | Noninvasive fixtures then separately approved real SDR/decoder/GNSS/DVB test sessions; no fabricated Meteor images, calibrated RF claims or live signal-success assertions |
| Branding | Byte-for-byte approved pack/master PNG SHA-256, visual comparator, legal provenance, native/PWA icon assets, accessibility and rollback; no replacement in this audit |
| History/rename | Export missing PR #72–#74 links, preserve all original comment/review identifiers, inspect authorized timelines, test old PR/Issue URLs and Pages/PWA/raw installer/CI redirects after a separately authorized rename |
| Native standalone/release | Per-OS installer/upgrade/rollback, offline dependency closure, model opt-in/TLS token security, independent CI and real device tests, approved original-data recovery |
| Authorization | Owner approval **separately** for destination first commits, source import, runtime icon switch, merges, installer repoint, production release, any original repo rename |

## 6. Open blockers and handoffs

1. **CRITICAL — Media ancestry omission:** Workstream [#76](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/76) must preserve the 20 unmerged #67 commits rather than using coordinator/docs snapshots as the canonical Media source.
2. **HIGH — Historical archive completeness:** Workstream #81 / coordinator [#75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75) must reconcile #72–#74, the 11 public original #20/#21 comments and original reviews/timelines with author/time, while maintaining privacy and original IDs.
3. **HIGH — Flight agent onboarding:** Workstream [#77](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/77) must record source-backed missing canonical `CLAUDE.md`/`DEEPSEEK_START.md` and test matrix portability without changing its active repository now.
4. **HIGH — Satellite issue provenance:** Workstream [#78](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/78) needs original #20/#21 comment links and preservation of native/web/decoder test expectations.
5. **HIGH — Binary hash, runtime locales and device acceptance:** exact approved logo PNG bytes unavailable to this worker; no all-five runtime EN/TR/DE verification; no physical RF, native installer or rollback tests performed.
6. **MEDIUM — Cross-branch synchronization:** Coordinator moved ahead of WS06; preserve independent audit branch and request coordination instead of rebasing or overwriting owner files.
7. **UNKNOWN — External Survival Kit inventory:** Separate News/Emergency/AI complete requirement/source audit was not attempted in this five-app workstream.

## 7. Completion state and estimation

**Source audit records produced: 15/15.** This is a completed first source/evidence pass, **not a full cross-app feature or history certification**.

- Tests inspected: **6** distinct relevant test source files; **0 executed**, **0 physical device tests**.
- PR review submissions/threads: **12 PR endpoints checked** (all returned zero nodes); PR comment endpoint checks yielded 8 Flight PR #13 originals; issue source checks yielded 11 additional Issue comment links.
- Unresolved test candidates: **CROSS-006, CROSS-009, CROSS-010, CROSS-011, CROSS-012, CROSS-014**.
- Runtime, settings, icons, installed apps, migrations, merges and main changes by this worker: **none**.
- **Estimated remaining HHh MMm: unknown.** Reliable scope is blocked by the complete historical timeline/export census, owner-authorized hardware test availability, five-app independent migration/installer gates and cross-worker task estimates. No artificial countdown is offered.
- Keep [Issue #81](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/81) open and [Draft PR #88](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/88) unmerged until coordinator review. All further engineering documentation in English; all future end-user applications preserve **EN(default)/TR/DE**.

### Source pointers and provenance boundaries

[Master requirements](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/803529ba90f43a6cb1fb977869c650ddf5db448a/apps/_coordination/MASTER_REQUIREMENTS.json) · [Candidate test/source map](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/803529ba90f43a6cb1fb977869c650ddf5db448a/apps/_coordination/REQUIREMENT_SOURCE_TEST_CANDIDATES.json) · [History coverage](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/803529ba90f43a6cb1fb977869c650ddf5db448a/apps/_archives/HISTORY_COVERAGE_AUDIT.json) · [Original comment index](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/803529ba90f43a6cb1fb977869c650ddf5db448a/apps/_coordination/PR_COMMENT_LINK_INDEX.json) · [Media #67 preserved unmerged source](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/803529ba90f43a6cb1fb977869c650ddf5db448a/apps/_coordination/UNMERGED_MEDIA_EXPORT_PROVENANCE.json) · [Test quality audit](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/803529ba90f43a6cb1fb977869c650ddf5db448a/apps/_coordination/TEST_EVIDENCE_QUALITY.md)

All source paths/SHAs are documentary provenance, not proof of shipping, comprehensive tests, approved migration, installed hardware or user-data access. No private chat transcript, token, personal sensor serial or original comment body is reproduced.

---

## 8. Phase 4 continuation — immutable source history and zero-regression release review (2026-11-12)

**Assignment:** [Latest Issue #81 Phase 4 instruction](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/81#issuecomment-6811788707), [PHASE_4_PARALLEL_WORK_DIVISION.md](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/PHASE_4_PARALLEL_WORK_DIVISION.md), and central [Issue #75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75). This follow-up preserves the preceding 15/15 CROSS source-review rows. Exact machine-readable origin PR identities, paths, blob SHAs, test-only PR refs, QA checks and 12 still-open gates have been appended under `phase_4` in [EVIDENCE.json](EVIDENCE.json). **No software, test, logo, installer, history ledger, Pages, workflow, `main`, migration or release edits are authorized or made.**

### 8.1 Git ancestry, immutable history and archived ledger reconciliation — REG-01 / REG-11

Source compare at exact original GitHub refs:

| Original source relationship | Base | Head | Ahead / behind | Interpretation |
|---|---|---|---|---|
| [Media #65](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/65) → [#66](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/66) | `20b0417aa7edba2f86b297e7cabdd062e9b24291` | `20379152be2751e5d89a8bdbac85fb15fc6b3c4e` | **3 / 0** | Integration source descends from Media baseline |
| Media [#66](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/66) → [#67](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/67) | `20379152be2751e5d89a8bdbac85fb15fc6b3c4e` | `4e62e21cd5252df8a04f9ceadc429f4b116412ce` | **20 / 0** | Latest unmerged recording/export source **not** included by the WS06/docs branch |
| [#72](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/72) → [#73](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/73) | `5e036603a8cbe1f22ed0d0d13306c9ddd3007d42` | `424656fc36e16a4d5b87d13b5824fd36243d66e4` | **4 / 0** | Straight ancestry; no independent merge required to explain descendants |
| [#73](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/73) → [#74](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/74) | `424656fc36e16a4d5b87d13b5824fd36243d66e4` | `a27e84a283b37c9014dfe21efbc496f5da5a7c65` | **6 / 0** | Retained Text Center topology follows #73 |

**Eight changed files in the 20-commit Media #66→#67 range**, each directly fetched from the exact #67 head to record its current Git blob identity:

| Original #67 changed path | Status | Exact Git blob SHA |
|---|---|---|
| `kaffeine_next/RECORDING_EXPORT_V2_DRAFT.md` | added | `3418010eb2448879d4b8cd582e2857e64fea2857e` |
| `kaffeine_next/captions_overlay.py` | modified | `3081be75998464e758427ea12c66071924b6e69d` |
| `kaffeine_next/native_media_panel.h` | modified | `7b8f2f756025a8aec5169e86b52ec589dc769aca` |
| `kaffeine_next/native_radio_tab.h` | modified | `1aaac1b9b2c08f2ae4981d17dbd1f6029a2ad831` |
| `kaffeine_next/native_unified_recorder.h` | modified | `65ceedc5e99534a2f348b83f5c31467b55cd237f` |
| `tests/test_recording_export.py` | added | `1b8039aa5f78449ebd7c5ef19eb0f9470bfb0cf8` |
| `tv_center/__main__.py` | modified | `c5ea50700ef8d32eae4970ce9a962dc5795c4f00` |
| `tv_center/recording_export.py` | added | `084ac92aa787b1e81f2a2dab861eb0af6041eade` |

**History coverage remains incomplete:** both existing original archives `apps/_archives/HISTORY_COVERAGE_AUDIT.json` (blob `f8ceefe6a944a8a4bc21cf06c7ac7c6e72474112`) and `apps/_archives/PORTABLE_HISTORY_LINK_MAP.json` (blob `2f32fbc976bf25637afbbb23eea331a7a6fd6dc9`) contain **67 original PR records** and omit original PRs **#72, #73, #74**. The coordinator has separately preserved their metadata in [ORIGIN_PR72_74_ANCESTRY_ADDENDUM.json](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/ORIGIN_PR72_74_ANCESTRY_ADDENDUM.json) (blob `d84133429c38085e659ce982591a17e8e8000862`). **Neither original archive was edited by this worker**. The PR #74 ancestry is independent of the extra #67 feature commits; it cannot be used as a substitute for them.

Original PR metadata recovered and rechecked: #72 created `2026-11-11T17:03:05Z`, #73 `2026-11-11T18:16:02Z`, #74 `2026-11-11T18:27:38Z`; original author `Tihulu`, original repo ID **1447637221**, original URLs above, all currently open Draft. For each of these three PRs, the accessible review-submission, inline-thread and top-level-comment endpoints returned **zero nodes**. That is a bounded observation, **not** a statement that all original reviews, issue timelines, author decisions or private chat discussions were archived. Native PR object IDs not provided through these checks remain **null**; neither original native approvals nor timestamps were invented.

Previous source-linked references remain intact: eight original Flight PR #13 public comment permalinks (with author/timestamp metadata preserved in the prior index) and eleven original Satellite Issue #20/#21 public comment permalinks. The Issue-comment endpoint did not return timestamps for the latter, which remain `null`. Future review must include complete accessible event timeline, attachments, external private decisions only with source approval, and original-id→destination-alias verification, without reconstructing native approvals.

**Required historical gate:** reconcile full old PR/Issue/link counts, pin original commit trees and SHA maps, verify review author/time/immutable URLs and preserve failed/unavailable status explicitly **before** any future owner-approved repo transfer. Do not edit active historical ledgers, transfer chat content or call the origin archive complete in this phase.

### 8.2 Three isolated test-only PRs: software CI is not physical acceptance — REG-01 / REG-02 / REG-03 / REG-15 / REG-16

All three exact PR refs were independently inspected: each is **one commit ahead, zero behind** its named source baseline and changes exactly one test file. PRs remain open/unmerged. All original source and workflow paths are unchanged in these particular diffs.

| Test-only Draft PR | Exact head and tested source base | New test source / observed CI | What it **does not** establish |
|---|---|---|---|
| [Text #89](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/89) | `e1a1382e415e053a2ee939a15751413559ede1df` from Text `main` `1fffb711bfbb7c4abaf55299fa9240e5db3e1cde` | [`tests/test_textcenter_cleanroom_import.py`](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/e1a1382e415e053a2ee939a15751413559ede1df/tests/test_textcenter_cleanroom_import.py), blob `4535f36d91300382b9ffc12968c52230bc1a930e`; 2 isolated tests. [GitHub Actions 43133732602](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43133732602): **success** at exact head. | Cleanroom copied **current** Text main with no `tv_center` and mocked CPU discovery. It does not prove archived `compute.py/speech.py/transcripts.py` independence, GPU, OS installs, locale UI or physical tuner |
| [Media #90](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/90) | `15d704f2624264d9bc346248d89373188d82d597` from original unmerged #67 `4e62e21cd5252df8a04f9ceadc429f4b116412ce` | [`tests/test_recording_export_stage3_isolated.py`](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/15d704f2624264d9bc346248d89373188d82d597/tests/test_recording_export_stage3_isolated.py), blob `9d09059904f7022fc7f8206ab4a00149d669dad6`; 5 synthetic tests. [GitHub Actions 43133737755](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43133737755): **success**. | FFmpeg args/file guard are mocked, SRT/TXT fixtures synthetic; no actual FFmpeg mux or burn, no native Qt/DVB/Whisper/GPU synchronization or end-to-end recording integrity; original optional real FFmpeg case may skip |
| [Flight #14](https://github.com/Tihulu/tihulu-flight-radar/pull/14) | `b6a7510466efd5978b1724b5ce88830c1ecf9d71` from Flight main `059b391280635d9aa4d2ac73c7318af9e135ebf5` | [`tests/test_stage3_isolated_receiver_ownership.py`](https://github.com/Tihulu/tihulu-flight-radar/blob/b6a7510466efd5978b1724b5ce88830c1ecf9d71/tests/test_stage3_isolated_receiver_ownership.py), blob `311eb49a69825c34d8e7876efa210282abaf96ce`; 8 tests, **1 strict XFAIL**. [Cross-platform Actions 43133741667](https://github.com/Tihulu/tihulu-flight-radar/actions/runs/43133741667) and [ARM64 preview 43133741622](https://github.com/Tihulu/tihulu-flight-radar/actions/runs/43133741622): both **success**. | The strict XFAIL is an **unfixed P0** external readsb/tar1090 ownership error on Exit when release enabled. All service actions mocked, no systemctl/sudo, installed Qt, SDR or physical Stop/Exit validation |

These CI run **conclusions were checked at the pinned heads** using GitHub Actions metadata. The exact added test sources were read. They do not mean this worker executed tests: **WS06 test commands run = 0; WS06 native receivers opened = 0**. A strict XFAIL is a known limitation, not a passing behavioral acceptance. The cross-app release regression gates remain OPEN.

### 8.3 Five approved TIHULU logos: recorded identifiers are not verified binary bytes — REG-13

The [approved manifest](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/803529ba90f43a6cb1fb977869c650ddf5db448a/apps/BRANDING_APPROVED_MANIFEST.json), blob `dbb53390593e262c8a3ab36c1fe7daa2fd0b4688`, pins precisely **five** 1254×1254 PNG master SHA-256 values, with approved ZIP SHA-256 `49eeccd46ab8b6e630b5567b4e08c0580f22430696de8e215b80d21a52043f84`. See EVIDENCE.json `phase_4.branding` for each full master hash. The associated **actual PNG bytes and ZIP were unavailable to this auditor**; **0 master hashes and 0 pack hashes were independently recalculated**. Manifest assertions and the earlier chat-side verification statement cannot be promoted to this worker's byte-level proof. Binary asset import is not completed and no editable genuine SVG is certified. Do not select new substitute artwork.

Later **separately approved** gate: obtain the five exact approved binaries and ZIP from the authorized original source, compute SHA-256, compare visual previews/permissions/licenses, stage only identical master assets and test native icon generation/PWA cache/rollback on separate reviewed branches. **No brand asset or installed icon changed here.**

### 8.4 English engineering / en(default), tr, de installed UI — REG-13 / REG-17

All five app-local `LOCALIZATION_CONTRACT.json` files were read on the coordinator source branch and all five say `current_coverage: not_audited_no_runtime_translation_claim` and `translation_files_created_in_this_pr: false`. They require English (default), Turkish and German, safe English fallback, offline bundles, persistent locale selection and compatibility with saved user settings, not changes in the ongoing audit. **This is a policy target, not verified shipped UI.**

Later tests must inventory *user-facing* labels, dialogs, accessibility, Notifications, errors, menus, native desktop, Pages/PWA and mobile width; assert 100% required keys for `en,tr,de`, translation placeholders, locale switch/fallback/persistence, DE/TR text expansion and no default changes. Whisper/Teletext/audio translation is **not** a substitute for UI localization. Canonical Flight main has substantive `AGENTS.md` but lacks standardized root `CLAUDE.md`, `DEEPSEEK_START.md` and independent developer matrix paths; three future destination repos remain empty. The source monorepo's 20 app matrix/localization files are not proof canonical Flight or future target repositories contain those files. **REG-17 open.**

### 8.5 Dual public Pages, source-revision, PWA, old URLs and Satellite parity — REG-08 / REG-12

The two intended Flight Radar public browser origins are:

- Standalone: `https://tihulu.github.io/tihulu-flight-radar/`
- Text Center mirror: `https://tihulu.github.io/TIHULU-TEXT-CENTER/flight_radar/`

The **directly read GitHub `gh-pages` branches** have matching `source-revision.json` blob `8a5408ebd338ce8557a92f56e5af4c7383174417`, both declaring `source_ref=main`, `source_sha=059b391280635d9aa4d2ac73c7318af9e135ebf5`. Four additional directly compared asset pairs have identical Git blob SHAs: `index.html` (`38721a1ea2db2dfcad6833eafd27c48677102190`), `app.js` (`589bb5ebaf83e8a079ab4bed7a39d6c1fd420c71`), `sw.js` (`984b9e4e567104b3ecce8afa009f401e2e5f66e9`), and `adsb_worker.mjs` (`2702f30a77de7c7f9cdcdca7c9b5362b51fd5a43`). Prior WS02 also compared a broader seven-asset selected set. Both source service workers declare `tihulu-flight-radar-shell-v16`; cache paths and permissions are per origin and base path. **Matching Git files do not prove public CDN deployment, PWA update, HTTP response, offline cache, browser USB permission, or future redirects.**

Read-only retrieval of both live public origin pages and their public `source-revision.json` URLs was **unavailable in this audit environment**. Public HTTP status, live revision and old-link redirect checks were therefore **not verified**; do not infer working public URLs from GitHub repo trees. A future rename of origin repo ID **1447637221** requires separately authorized testing of Pages paths, PWA service-worker scopes/caches, both site mirrors, original PR/Issue URLs and `raw.githubusercontent.com` one-line installer links, with an explicit recovery plan. Never assume that GitHub repository redirects automatically repair Pages project URLs.

For Satellite, original PR [#37](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/37) at `670e0ddcf029c8fcc9b0cef403bf76cf37613fcb` has separate historical [Actions run 42559046861](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/42559046861) **FAILED** Pages/source parity for eight assets: `browser/index.html`, `auto_mission.mjs`, `auto_reception_ui.mjs`, `browser.js`, `browser.css`, `location_search.mjs`, `satellite_maps.mjs`, `compute_selector.mjs`. This source-backed WS03 gate is **not superseded** by successful unrelated isolated software CI; no Pages publish was attempted here.

### 8.6 Independent native installers / Flight 0.3.1 rollback — REG-14

| App | Source evidence found | Required future release proof still missing |
|---|---|---|
| **Media** | Linux APT `kaffeine_next/install.sh`, `tv_center/install.sh`, draft `tv_center/packaging/build-deb.sh` | Full independently versioned source/Qt/Kaffeine/GPL dependency closure, macOS/Windows/native pathways if supported, installer upgrade/data preservation/rollback, actual DVB/audio/RF |
| **Satellite** | `satellite_center/install/install.sh` (Linux/Pi/macOS) and `install.ps1` (Windows x64) in original branch | Target repo still empty; validated user-local native installer and driver ownership on each OS, Pages/native asset parity, physical capture correctness and rollback |
| **Geolocation** | `rf_geolocation_center/native.py` is a **localhost static launcher**, expressly not a native SDR/GNSS decoder; searched `install/install.sh` and `install/install.ps1` paths absent at pinned source | Independent native GNSS/RF backend, installer/CI, serial/USB permissions, measurements and rollback on OS matrix |
| **Text Center** | Current retained Text `main` Python `textcenter/__main__.py` CLI and local/browser source | Preserve active `main`, three stale archive blob deviations, offline dependency behavior, native package/upgrade/rollback and real FM/DAB/DVB permissions without silent Media imports |
| **Flight Radar** | Canonical `scripts/install-linux.sh`, `scripts/popos-version-switch.sh`, and `.github/workflows/build.yml` describing Linux/Windows/macOS previews | Physically validated installed app packages/Qt, real Linux service ownership, Windows/macOS/Pi startup, user settings/recordings, complete safe cross-platform rollback |

Flight [`legacy/v0.3.1`](https://github.com/Tihulu/tihulu-flight-radar/tree/legacy/v0.3.1) currently resolves exactly to the pinned legacy source `67280cd84feb89faec6a80f5fe2a55ce5f7b89e6` (**identical** by compare). The current `preview/v0.3.2-dev4` branch now resolves to `ed7fc0d591fcb34f0fb8c4ccf56d7201f3ba514e`, **6 commits ahead, 0 behind** the preview ref `def7a62ff6951951bc3a432b93da3251c7ea4162` selected by the pinned version switcher. This is **branch drift, not necessarily a defect**: the Bash script explicitly downloads the installer at an exact SHA and passes `TIHULU_REF`; it uses `pipx install --force` and verifies the reported installed version. The switcher's source blob is `dbde80f991583276fed13df89eb603f4b8f5832b`.

**No switcher, installer, sudo/systemctl, pipx modification, user settings backup, physical 0.3.1 rollback or reverse-preview reinstatement was executed by WS06.** A successful script syntax/CI check is not assurance that existing receiver services, user recordings, old app icons, USB permissions, or current local source identity will survive. Later explicit approval requires preinstall metadata backup, exact legacy binary provenance, staged OS/package validation and recoverable rollback; protect current services and the on-demand receiver ownership contract.

### 8.7 Phase 4 unresolved QA checklist — ALL OPEN

The [cross-workstream gate graph](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/CROSS_WORKSTREAM_DEPENDENCIES.json) assigns WS06 to **12 of 17** broad release gates. Documentation-only evidence has expanded, but **0/12 gates are closed**:

| Gate | Proposed next read-only / separately approved acceptance boundary |
|---|---|
| **REG-01 P0** | Reconcile complete Media #65/#66/#67 eight-path blobs, recording/export and tests, then later FFmpeg/native no-overwrite and rollback |
| **REG-02 P0** | Protect Text current main `1fffb...` against archived compute/speech/transcripts divergence; do not restore snapshot source over active main |
| **REG-06 P0** | Preserve Satellite IQ rate provenance (1.024 vs 2.048 MS/s) versus SatDump 1.024 hardcode; no false decoder conclusions |
| **REG-08 P0** | Resolve original PR #37 eight-asset Pages/source mismatch and actual publication/revision checks before deployment |
| **REG-09 P1** | Keep 22 original Satellite PR #37 test sources absent from WS03 branch as explicit branch transfer gaps; no phantom test pass |
| **REG-11 P0** | Link old PR #72–#74, original review/comment IDs, original URLs and timelines; avoid original approval reconstruction |
| **REG-12 P0** | Check both live Pages URL/revision/manifest/cache, raw installers, old alias and future redirect after separate approval |
| **REG-13 P0** | Obtain exact five logo PNG binaries for real hash calculation; verify all-five en(default)/tr/de UI and offline/a11y |
| **REG-14 P0** | Native installer/upgrade/rollback per OS/app with original settings/recordings/hardware preservation; Flight 0.3.1 safe switch |
| **REG-15 P0** | Separate source/test CI, strict XFAIL, no actual RF, incomplete worker acceptance and unknown HH:MM |
| **REG-16 P0** | Teletext/Whisper/lyrics/translation timebase and Media export source parity against real AV streams only after approval |
| **REG-17 P0** | Five canonical app-specific matrix + Claude/DeepSeek document closure; Flight independent source and empty destination status |

**Safety and completion accounting:** 15/15 original WS06 CROSS IDs remain source-reviewed; 12/12 assigned Phase 4 gates evidence-reviewed; **0 release gates closed, 0 worker-run tests, 0 installed native/rollback tests, 0 physical NooElec/Hauppauge tests, 0 verified final UI locale coverage, 0 logo binary SHA recalculations, 0 Pages publishes, 0 merges/migrations/renames**. Historical three test-only PR heads have successful GitHub software workflows; that does not change these counts. Remaining hours/minutes are **unknown** pending complete history/timeline/archive evidence and owner-approved native/hardware acceptance. Keep [Issue #81](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/81) open and [Draft #88](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/88) unmerged. Engineering English, future UI en(default)/tr/de.
