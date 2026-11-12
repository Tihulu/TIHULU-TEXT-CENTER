# Phase 4 — parallel work division and no-regression handoff

**2026-11-12 | Status: coordinator assignments prepared; not autonomous execution.**

## Verified input state

The following source-based audit PRs and first isolated test-only PRs are still **OPEN/DRAFT**; do not merge or rewrite them as part of a workstream review.

| Track | Existing audit / discussion | Test-only PR, real source base | Verified CI evidence |
|---|---|---|---|
| Media | [WS01 Draft #83](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/83), [Issue #76](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/76) | [Media isolated Draft #90](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/90), original PR #67 head `4e62e21cd5252df8a04f9ceadc429f4b116412ce` | [43133737755](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43133737755): success; 5 new synthetic tests, one old real FFmpeg test skipped |
| Flight | [WS02 Draft #84](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/84), [Issue #77](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/77) | [Flight isolated Draft #14](https://github.com/Tihulu/tihulu-flight-radar/pull/14), canonical Flight main `059b391280635d9aa4d2ac73c7318af9e135ebf5` | [43133741667](https://github.com/Tihulu/tihulu-flight-radar/actions/runs/43133741667): 4 platform jobs successful; inspected Ubuntu **79 passed / 1 xfailed**; Pi preview [43133741622](https://github.com/Tihulu/tihulu-flight-radar/actions/runs/43133741622) successful |
| Text | [WS05 Draft #87](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/87), [Issue #80](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/80) | [Text isolated Draft #89](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/89), canonical Text main `1fffb711bfbb7c4abaf55299fa9240e5db3e1cde` | [43133732602](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43133732602): success; 2 cleanroom import/CPU discovery tests passed |

Original coordinator Draft #82 remains on branch `chore/master-requirements-zero-regression-coordination-2026-11-11`; six baseline source audits and three focused preservation reports are complete; 17 original functional/history/hardware/release gates are **OPEN**. No source migration or merge occurred.

## Parallel isolation rule (non-overlapping write ownership)

- **WS01 — Media export test adequacy and gap triage:** Read the *actual* new PR #90 test file and original #67 `tv_center/recording_export.py`, `tests/test_recording_export.py`, original CI. Identify missing no-overwrite race, invalid SRT and translation, live/complete mode, mock FFmpeg subprocess, cross-platform path escaping and atomic sidecar-on-failure checks. Track P67-GAP-01..10 and separate **verified passing synthetic tests** from **skipped real FFmpeg/native Qt**. Save any extra read-only evidence **only** to `apps/_coordination/workstreams/01/{REPORT.md,EVIDENCE.json}` on its already assigned audit branch; post a findings comment to #76 and link central #75. Do not edit #90 or old #67. Deliver: prioritized missing-tests matrix, no source patch.
- **WS02 — Flight P0 external-service ownership contract:** Read the *actual* new Flight Draft #14 tests against canonical main and separate unmerged #7 + #13. Verify strict XFAIL is an accurate regression oracle for **external readsb/tar1090** and that explicit Stop vs passive Exit remain distinct. Propose a source-review-level minimal safe fix, specifically covering `_service_started_by_app`, persisted exit preference, sudoers, Qt constructor, Start/Stop/Restart concurrency and remote/direct modes; **do not implement any production fix or cherry-pick old #7**. Save only `apps/_coordination/workstreams/02/{REPORT.md,EVIDENCE.json}` on assigned branch and comment #77 referencing #75. Deliver: exact behavior contract and required passing-but-not-yet-run test matrix; **REG-03 stays OPEN**.
- **WS05 — Text canonical/archived independence contract:** Read the *actual* new isolated Draft #89 test and previous 13 `SI-` proposal gates; classify what its green canonical main cleanroom import **does and does not** verify. Specify safe negative control fixtures for archived unguarded `tv_center.language_codes`, `tv_center.pi_hailo`, and reverse Media GPU `textcenter.compute.LANGUAGES` dependency without copying archived modules into active main. Propose later test-only addenda and independent package-level import semantics; no runtime/GPU/model/hardware actions. Save only `apps/_coordination/workstreams/05/{REPORT.md,EVIDENCE.json}` on existing audit branch and comment #80 referencing #75. Deliver: cleanroom matrix with named target refs and observed/expected distinction.

**Coordinator / QA (this chat, not a worker code branch):** independently compare the three submitted report/evidence pairs to pinned source SHAs and test-only PR heads, check relevant CI on exact latest heads, inventory file diffs and update central `PROGRESS.json` plus #75 only. Reject changes outside allowed audit workstream roots. The coordinator may prepare separately reviewable test-only changes within the already owner-authorized scope, but **no production source changes** or merges without a new explicit owner instruction.

## Test-only execution boundary

Previously authorized isolated test-only work may expand later **only on explicitly identified independent test-only branches**, never by silently adding test edits to the workers' docs-only branches. New tests must use synthetic input, temporary files, mocked system services and network isolation; no user's Pop!_OS host, real `sudo/systemctl/readsb/tar1090`, USB SDR or Hauppauge, model downloads, live external APIs or microphone. A known source defect may be marked **strict XFAIL with source evidence**; never convert it to a false successful acceptance or pretend it has been fixed. Actual production fixes are a separate owner-gated engineering phase.

The workers are independent conversations. **GitHub comments do not start or wake them.** The owner must send each prompt to its existing chat; once worker source-audit evidence is committed, the coordinator can collect it in a later user turn. No background process/agent/ETA is claimed.

## Acceptance for parallel second-stage review

Every worker must provide: (a) new PR head and tested source base; (b) exact changed paths and inspected original tests; (c) mapping to REG and SI/L/R/P67-GAP IDs; (d) missing/expected negative cases without fabricated outcomes; (e) test-run vs CI-historical vs hardware acceptance distinctions; (f) forbidden source/service actions confirmed not performed; (g) an Issue handoff comment referencing central #75. **Three parallel reviews may complete in any order**, with coordinator reconciliation after evidence is present.

Engineering and GitHub documentation language: **English**. User-visible app interface target: **EN(default)/TR/DE**, not yet validated by hardware or installed package. Feature-equivalence and release acceptance are not claimed. ETA unknown.
