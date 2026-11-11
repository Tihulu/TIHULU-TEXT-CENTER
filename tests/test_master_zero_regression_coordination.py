"""Static contract for TIHULU six-workstream English audit planning.

No network calls, model installs, SDR access, application source changes or
GitHub issue creation are performed by this test.
"""
import json
from collections import Counter
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "apps"
PLAN = BASE / "_coordination"


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class ZeroRegressionCoordinationTests(unittest.TestCase):
    def test_initial_inventory_is_classified_but_not_claimed_implemented(self):
        manifest = load("apps/_coordination/MASTER_REQUIREMENTS.json")
        records = manifest["records"]
        self.assertEqual(manifest["total_initial_requirements"], 97)
        self.assertEqual(len(records), 97)
        self.assertEqual(len({r["id"] for r in records}), len(records))
        self.assertEqual(dict(Counter(r["app"] for r in records)),
                         manifest["count_by_app"])
        for requirement in records:
            self.assertEqual(requirement["engineering_language"], "en")
            self.assertEqual(requirement["ui_locales"], ["en","tr","de"])
            self.assertEqual(requirement["implementation_state"],
                             "unknown_requires_source_and_pr_audit")
            self.assertEqual(requirement["verification_state"],
                             "not_verified_in_current_inventory")
            self.assertEqual(requirement["release_state"], "not_claimed")

    def test_progress_has_evidence_based_issues_and_unknown_eta(self):
        progress=load("apps/_coordination/PROGRESS.json")
        self.assertEqual(progress["requirements"]["registered"], 97)
        self.assertEqual(progress["workstreams"]["issue_numbers"],
                         [76,77,78,79,80,81])
        self.assertEqual(progress["workstreams"]["master_issue"], 75)
        self.assertEqual(progress["workstreams"]["completed_audits"], 0)
        self.assertEqual(progress["workstreams"]["started_by_other_chats"], 0)
        self.assertIsNone(progress["time_remaining"]["hours"])
        self.assertIsNone(progress["time_remaining"]["minutes"])
        self.assertFalse(progress["new_repo_source_import_performed"]
                         if "new_repo_source_import_performed" in progress else False)

    def test_six_english_prompts_and_github_message_bus(self):
        ids=load("apps/_coordination/ISSUES.json")
        self.assertEqual(len(ids["entries"]), 7)
        self.assertEqual(ids["entries"][0]["issue"], 75)
        self.assertEqual([x["issue"] for x in ids["entries"][1:]],
                         [76,77,78,79,80,81])
        for i, task in enumerate(ids["entries"][1:]):
            prompt=ROOT/task["prompt"]
            self.assertTrue(prompt.is_file())
            self.assertIn("English ONLY", prompt.read_text(encoding="utf-8"))
            self.assertIn("Do not implement fixes", prompt.read_text(encoding="utf-8"))
            self.assertEqual(task["status"], "issue_created_worker_not_started")

    def test_canonical_topology_and_no_runtime_changes(self):
        x=load("apps/CANONICAL_REPOSITORY_TOPOLOGY.json")
        self.assertEqual(len(x["app_canonicals"]),5)
        self.assertEqual(sum(bool(a["move_required"]) for a in x["app_canonicals"]),3)
        text=next(a for a in x["app_canonicals"] if a["app_id"]=="text-center")
        self.assertEqual(text["source_repo_id"],1447637221)
        self.assertFalse(text["move_required"])
        p=load("apps/_coordination/PROGRESS.json")
        self.assertTrue(p["release_gates"]["zero_runtime_changes"])
        self.assertTrue(p["release_gates"]["no_merges"])
        self.assertTrue(p["release_gates"]["no_repo_rename"])
        self.assertEqual(p["release_gates"]["ui_languages_target"],["en","tr","de"])


if __name__ == "__main__":
    unittest.main()
