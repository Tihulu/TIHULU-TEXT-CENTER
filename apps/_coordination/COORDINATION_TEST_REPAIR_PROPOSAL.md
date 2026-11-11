# TIHULU coordinator CI — stage-aware test repair proposal

**Status: REVIEW PROPOSAL ONLY (2026-11-12).** This document is not a test patch. No application, CI workflow, Python test source, user service or original branch is modified. A separate explicit owner approval is needed before applying changes to any test source.

## Reproduced failure and provenance

- [Coordinator Draft PR #82](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/82) reached SHA f19fe6b2d3238f0c8e67634619c40abfe1da2b6d. [GitHub Actions run 43120118615](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43120118615): Python 3.11, 3.12, 3.13 each failed the offline test step. Inspected Python 3.12 job 130858160444: **696 tests run, 2 failed**.
- tests/test_master_zero_regression_coordination.py line 44 requires completed_audits == 0, but six completed source-based audit REPORT/EVIDENCE pairs are on independent Draft branches #83–#88 and PROGRESS.json accurately reports completed_audits = 6.
- tests/test_six_parallel_workstream_gates.py line 50 requires started_by_other_chats == 0, but PROGRESS.json accurately reports started_by_other_chats = 6.
- WORKSTREAM_HANDOFF_INDEX.json has started_chats = 0, worker_audits_completed = 0 and descriptions saying workers were not automatically launched. These fields are a **historical coordinator bootstrap snapshot**, not live counters. Leave them unchanged and continue to distinguish from live PROGRESS.json.
- The six source-audited requirement counts are 41+17+8+8+8+15 = 97. This is **not** a completed-feature, native-device or release count.

## Suggested narrowly scoped code changes (NOT APPLIED)

**Proposed replacement in tests/test_master_zero_regression_coordination.py:** replace the fixed completed_audits == 0 assertion with a stage-aware and evidence-index-aware contract; keep the original unknown-ETA, zero-import, requirements and release-protection assertions.

~~~python
workers = progress["workstreams"]
started = workers["started_by_other_chats"]
completed = workers["completed_audits"]
self.assertTrue(0 <= completed <= started <= workers["defined"] == 6)
scope = workers.get("worker_audit_source_scope", {})
self.assertEqual(len(scope), completed)
self.assertEqual(workers["worker_pr_numbers"], [83, 84, 85, 86, 87, 88])
expected = {
    "01": (83, 76, 41), "02": (84, 77, 17),
    "03": (85, 78, 8), "04": (86, 79, 8),
    "05": (87, 80, 8), "06": (88, 81, 15),
}
for key, row in scope.items():
    self.assertIn(key, expected)
    expected_pr, expected_issue, expected_count = expected[key]
    self.assertEqual(row["pr"], expected_pr)
    self.assertEqual(row["issue"], expected_issue)
    self.assertEqual(row["requirement_ids_reviewed"], expected_count)
    self.assertRegex(row["head"], r"^[0-9a-f]{40}$")
self.assertEqual(
    sum(row["requirement_ids_reviewed"] for row in scope.values()),
    progress["requirements"].get("initial_source_based_workstream_review_count", 0),
)
if completed == 6:
    self.assertEqual(set(scope), set(expected))
    self.assertEqual(progress["requirements"]["code_source_audited"], 97)
~~~

**Proposed replacement in tests/test_six_parallel_workstream_gates.py:** replace ONLY the fixed live started_by_other_chats == 0 assertion, not the original handoff snapshot assertions.

~~~python
live = progress["workstreams"]
self.assertTrue(0 <= live["started_by_other_chats"] <= len(idx["workers"]))
self.assertTrue(0 <= live["completed_audits"] <= live["started_by_other_chats"])
self.assertEqual(
    len(live.get("worker_audit_source_scope", {})),
    live["completed_audits"],
)
self.assertFalse(progress["release_gates"]["feature_acceptance_verified"])
self.assertFalse(progress["release_gates"]["hardware_device_acceptance_verified"])
self.assertIsNone(progress["time_remaining"]["hours"])
self.assertIsNone(progress["time_remaining"]["minutes"])
~~~

The suggestions above preserve the original initial snapshot while accepting legitimate staged audit progress. A reviewer must check that intermediate states remain supported and that later releases use a distinct versioned acceptance contract rather than weakening these audit-only safety gates.

## External verification cannot be simulated by offline unittests

Worker branch heads, verified directly through GitHub, are:
- WS01, Issue #76, Draft #83: 10fd5ef9c51df2c330c8c5823ce789e31db519b2 (41 initial IDs)
- WS02, Issue #77, Draft #84: 1253f55604b1401927f3a1b7a661c7f9b1fa8386 (17 initial IDs)
- WS03, Issue #78, Draft #85: 284944e1dc167f6b60bf762889a3c75bf28f47e2 (8 initial IDs)
- WS04, Issue #79, Draft #86: b62ba58287ef9e76d42ca807829b26da68177e18 (8 initial IDs)
- WS05, Issue #80, Draft #87: 5a772fd399c2d743207adb69dc33bd9922fee068 (8 initial IDs)
- WS06, Issue #81, Draft #88: e69c2b6eac7deeca313925bf99af31f8c9434f34 (15 initial IDs)

The proposed offline tests can confirm the local evidence-index structure, but cannot contact GitHub to verify remote report bytes. The reviewer must separately confirm each branch's REPORT.md / EVIDENCE.json and the unchanged workstream-only PR diff before accepting the milestone.

## Approval and acceptance checklist

1. **Separate approval first:** a test-only, coordination-specific update to the two named Python test files; do not change application, workflows, installers, main or active repositories.
2. Preserve all no-runtime, no-repo-init, no-merge, no-rename, EN engineering / en(default)-tr-de UI and unknown-ETA safety checks. Keep initial handoff snapshot facts and newly verified live progress distinct.
3. Execute the unchanged Text Center tests workflow on Python 3.11, 3.12, 3.13 against the reviewed new commit and provide run IDs, logs and test count.
4. A passing metadata CI is NOT installed hardware validation, full five-app feature parity or green Satellite feature PR #37 Pages/source parity.

**No Python test source files have been modified by this proposal.**
