"""Read-only assertions for six TIHULU parallel audit workspaces.

These tests validate planning metadata only, never open/edit application source,
receiver services, installed apps, external repositories, images or hardware.
"""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "apps" / "_coordination"

def load(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))

class SixParallelWorkstreamGates(unittest.TestCase):
    def test_six_unique_draft_pr_branches_and_issues(self):
        idx = load("WORKSTREAM_HANDOFF_INDEX.json")
        workers = idx["workers"]
        self.assertEqual(len(workers), 6)
        self.assertEqual({w["n"] for w in workers}, set(range(1,7)))
        for k in ("issue", "pr", "branch", "allowed_edit_root", "task_url"):
            self.assertEqual(len({w[k] for w in workers}), 6, k)
        self.assertEqual([w["issue"] for w in workers], [76,77,78,79,80,81])
        self.assertEqual([w["pr"] for w in workers], [83,84,85,86,87,88])
        for w in workers:
            self.assertTrue(w["allowed_edit_root"].endswith(f"/{w['n']:02d}/"))
            self.assertTrue(w["branch"].startswith(f"audit/ws{w['n']:02d}-"))
            self.assertIn(f"/pull/{w['pr']}", w["draft_pr_url"])
            self.assertIn(f"/issues/{w['issue']}", w["issue_url"])
            self.assertIn(f"/workstreams/{w['n']:02d}/TASK.md", w["task_url"])
            self.assertIn("NOT automatically launched", w["status"])
        self.assertEqual(sum(w["total"] for w in workers), 97)

    def test_no_runtime_release_or_rename_permission(self):
        idx = load("WORKSTREAM_HANDOFF_INDEX.json")
        progress = load("PROGRESS.json")
        self.assertFalse(idx["allow_runtime_change"])
        self.assertFalse(idx["allow_empty_destination_repo_init"])
        self.assertFalse(idx["allow_silent_merge"])
        self.assertEqual(idx["internal_language"], "en")
        self.assertEqual(idx["user_interface_locales"], ["en","tr","de"])
        self.assertEqual(idx["started_chats"], 0)
        self.assertEqual(idx["worker_audits_completed"], 0)
        self.assertIsNone(idx["eta_hours"])
        self.assertIsNone(idx["eta_minutes"])
        self.assertTrue(progress["release_gates"]["no_runtime_changes_in_all_six_worker_prs_verified"])
        self.assertEqual(progress["workstreams"]["worker_pr_numbers"],
                         [83,84,85,86,87,88])
        # Handoff-index started_chats=0 is an immutable bootstrap snapshot.
        # Live progress is independent and can advance after worker evidence.
        live = progress["workstreams"]
        self.assertTrue(0 <= live["started_by_other_chats"] <= len(idx["workers"]))
        self.assertTrue(0 <= live["completed_audits"] <= live["started_by_other_chats"])
        self.assertEqual(len(live.get("worker_audit_source_scope", {})),
                         live["completed_audits"])
        self.assertFalse(progress["release_gates"]["feature_acceptance_verified"])
        self.assertFalse(progress["release_gates"]["hardware_device_acceptance_verified"])
        self.assertIsNone(progress["time_remaining"]["hours"])
        self.assertIsNone(progress["time_remaining"]["minutes"])
        self.assertTrue((BASE/"WORKSTREAM_LAUNCH_GUIDE.md").is_file())

if __name__=="__main__":
    unittest.main()
