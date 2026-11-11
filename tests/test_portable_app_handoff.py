"""Portable app registry and original source ownership checks; no network."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "apps"


class PortableAppHandoffTests(unittest.TestCase):
    def test_registry_routes_original_source_paths_without_moving_them(self):
        data = json.loads((APP_DIR / "registry.json").read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "embedded_in_monorepo_no_migration")
        self.assertEqual(data["source_repository"], "Tihulu/TIHULU-TEXT-CENTER")
        self.assertEqual(len(data["apps"]), 5)
        for app in data["apps"]:
            with self.subTest(app=app["id"]):
                self.assertTrue((APP_DIR / app["id"] / "AGENTS.md").is_file())
                self.assertTrue((APP_DIR / app["id"] / "MODEL_MATRIX.md").is_file())
                self.assertEqual(app["migration_state"]["state"], "not_started")
                self.assertIsNone(app["migration_state"]["target_repository"])
                if app["id"] != "flight-radar":
                    self.assertEqual(app["canonical_repository"],
                                     "Tihulu/TIHULU-TEXT-CENTER")
                    for source in app["source_roots"]:
                        self.assertTrue((ROOT / source).is_dir(),
                                        "Original source path moved: " + source)
                else:
                    self.assertEqual(app["canonical_repository"],
                                     "Tihulu/tihulu-flight-radar")

    def test_original_pr_descriptions_and_issue_records_are_indexed(self):
        data = json.loads((APP_DIR / "_archives" / "pr-index.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(data["number_of_prs"], len(data["prs"]))
        self.assertEqual(len(data["prs"]), 63)
        self.assertEqual(len({row["number"] for row in data["prs"]}), 63)
        self.assertTrue(all(row["url"].startswith("https://github.com/Tihulu/")
                            for row in data["prs"]))
        numbers = set()
        for part in sorted((APP_DIR / "_archives").glob("pr-body-*.json")):
            archive = json.loads(part.read_text(encoding="utf-8"))
            for row in archive["pr_records"]:
                self.assertIn("body", row)
                self.assertIn("author", row)
                self.assertNotIn(row["number"], numbers)
                numbers.add(row["number"])
        self.assertEqual(numbers, {row["number"] for row in data["prs"]})
        issues = json.loads((APP_DIR / "_archives" / "issues.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual(len(issues["issues"]), 4)

    def test_workspaces_do_not_claim_live_git_reviews_were_exported(self):
        for app_dir in APP_DIR.iterdir():
            manifest = app_dir / "manifest.json"
            if manifest.is_file():
                data = json.loads(manifest.read_text(encoding="utf-8"))
                self.assertFalse(data["history"]["comments_review_snapshot_complete"])


if __name__ == "__main__":
    unittest.main()
