# TIHULU — Coordinator CI Contract Drift (2026-11-12)

**Status:** OPEN, documentation-only diagnosis. Do **not** relabel GitHub Actions as successful, change verified progress from six to zero, merge worker branches, alter CI workflows, or modify application/test code in this audit-only step.

## Verified failing run

- Coordinator Draft PR [#82](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/82), head SHA `d3f9dffd85b5e9e89f043a5c9b5ea26888783134` when observed.
- [GitHub Actions Text Center tests run 43119633429](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43119633429): **completed, failure**.
- Matrix jobs: Python 3.11 job `130856485702`, 3.12 job `130856485683`, 3.13 job `130856485771`: each **failure** in the "Run offline unit and loopback HTTP tests" step.
- Inspected Python 3.12 job logs: **696 tests run; 2 failed**, both fixed initial-coordinator-state expectations. The same test suite runs on all three Python versions; do not infer an application hardware failure or unverified identical stack traces from the other job logs.

## Actual mismatches observed directly in logs and source

1. `tests/test_master_zero_regression_coordination.py` — `ZeroRegressionCoordinationTests.test_progress_has_evidence_based_issues_and_unknown_eta`, line 44:
   ```python
   self.assertEqual(progress["workstreams"]["completed_audits"], 0)
   ```
   Current `apps/_coordination/PROGRESS.json` value is **6** because six worker report/evidence pairs were actually committed and fetched on their own Draft branches, each source reviewing its assigned initial IDs. This is a completed **first source audit**, not acceptance/release completion. Log: `AssertionError: 6 != 0`.
2. `tests/test_six_parallel_workstream_gates.py` — `SixParallelWorkstreamGates.test_no_runtime_release_or_rename_permission`, line 50:
   ```python
   self.assertEqual(progress["workstreams"]["started_by_other_chats"], 0)
   ```
   Current value is **6** after the owner launched six separate ChatGPT chats and each committed its own report/evidence. Log: `AssertionError: 6 != 0`.

The `WORKSTREAM_HANDOFF_INDEX.json` includes historical coordinator-created bootstrap fields such as `started_chats=0` and `worker_audits_completed=0`, and initial `TASK.md` descriptions. Treat these explicitly as **initial snapshot data**; they are not current milestone counters. Current progress must remain source-backed in `PROGRESS.json`.

## Honest interpretation

- The regression is in **the audit metadata's static test assumptions**, not a verified program behavior regression. It is still a **real failing CI result** that must remain visible and block claims of a green coordinator PR.
- Six independent worker PR heads each had a successful `Text Center tests` GitHub workflow run at their own respective SHAs; those results are not the same as the coordinator's later failing head and not physical hardware acceptance.
- Original Satellite PR #37 portable CI failure on Pages/source parity (run `42559046861`) is a **separate** unresolved deployment issue and must not be hidden by any passing Text Center test.

## Proposed follow-up, NOT performed or authorized as an application change

A **separate narrowly reviewed coordination-test maintenance step**, if expressly approved, should:
- Replace fixed `0` expectations with staged, verifiable workstream progress checks; distinguish historical bootstrap index fields from live milestone values.
- Assert the six report/evidence file pairs, assigned branch refs, requirement counts, and per-worker SHA/Issue/PR provenance before allowing `started_by_other_chats=6` and `completed_audits=6`.
- Preserve non-negotiable assertions: **zero runtime/installer/feature changes**, no merges, no first commits in the three empty destinations, no repo rename or release, missing hardware acceptance and `time_remaining.hours/minutes = null`.
- Re-run all three Python matrix jobs against the exact reviewed head and attach logs. A test pass then would still be software CI only, **not** five-app parity.

**Actions in this step:** only this coordinator document and a truthful progress/Issue status update. No Python test source, GitHub workflow, application source, server/receiver state, installer, logo, PR base, release, `main`, rename or repository migration modified. Engineering English; future UI locales en(default), tr, de.
