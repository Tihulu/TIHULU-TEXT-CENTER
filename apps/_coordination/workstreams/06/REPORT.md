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
