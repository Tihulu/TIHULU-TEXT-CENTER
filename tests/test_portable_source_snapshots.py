"""Read-only acceptance checks for TIHULU portable app preservation.

No network, LLM, GPU, RF/DVB/SDR device access, model install, or app runtime.
Compare each active source tree with its frozen snapshot at every file path.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"
IDS = ("media-center", "satellite-center", "geolocation-center",
       "text-center", "flight-radar")
SOURCE_TREES = {
    "kaffeine_next": "4be76ef898a4adcc779c96052341fffdef0658a3",
    "tv_center": "73aa1e74465f48d33103424b4a1072d93c57d1cc",
    "textcenter": "dfc5fefbedba31f133f5a9ee34667961f3c3ef14",
    "web": "2f1e1d4b240076ff0a4490e7e259ddb1b3d165bc",
    "satellite_center": "41d5a38c6c5382d205ea98fd98648b8c7c9c2275",
    "rf_geolocation_center": "7be22e93b0138de1efbe6a27b43c8143ead76c49",
}


def file_index(folder: Path):
    """Compare files/symlinks by relative path, content and execute bits."""
    entries = {}
    for path in folder.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            continue
        if not (path.is_file() or path.is_symlink()):
            continue
        relative = path.relative_to(folder).as_posix()
        if path.is_symlink():
            contents = os.readlink(path).encode("utf-8")
            kind = "symlink"
        else:
            contents = path.read_bytes()
            kind = "file"
        entries[relative] = (kind, hashlib.sha256(contents).hexdigest(),
                             bool(path.lstat().st_mode & 0o111))
    return entries


class PortableSourceTests(unittest.TestCase):
    def test_all_exact_source_copies_exist_and_are_not_runtime_paths(self):
        reg = json.loads((APPS / "registry.json").read_text())
        self.assertEqual(reg["status"], "embedded_in_monorepo_no_migration")
        self.assertTrue(reg["snapshot_policy"]["original_runtime_paths_untouched"])
        self.assertFalse(reg["snapshot_policy"]["all_dependency_closures_verified"])
        copies = 0
        for app in reg["apps"]:
            with self.subTest(app=app["id"]):
                package = json.loads(
                    (APPS / app["id"] / "PORTABLE_PACKAGE.json").read_text())
                self.assertEqual(package["dependency_closure_status"], "unverified")
                self.assertFalse(package["new_repository_created"])
                self.assertFalse(package["main_branch_changed"])
                self.assertTrue(package["not_currently_executed"])
                self.assertEqual(app["migration_state"]["state"], "not_started")
                self.assertIsNone(app["migration_state"]["target_repository"])
                for tree in app["portable_source_snapshot"]["trees"]:
                    source = ROOT / tree["active_root"]
                    snapshot = ROOT / tree["snapshot_path"]
                    self.assertTrue(source.is_dir())
                    self.assertTrue(snapshot.is_dir())
                    self.assertEqual(tree["git_tree_sha"],
                                     SOURCE_TREES[tree["active_root"].rstrip("/")])
                    self.assertEqual(file_index(source), file_index(snapshot))
                    copies += 1
        self.assertEqual(copies, 7)

    def test_all_original_pr_and_issue_links_are_preserved_without_fake_migration(self):
        identity = json.loads((APPS / "REPOSITORY_IDENTITY.json").read_text())
        self.assertEqual(identity["origin_repository_id"], 1447637221)
        self.assertEqual(identity["origin_repository_node_id"], "R_kgDOVkkw5Q")
        self.assertTrue(identity["repository_rename_pending"])
        ledger = json.loads(
            (APPS / "_archives" / "PORTABLE_HISTORY_LINK_MAP.json").read_text())
        self.assertEqual(len(ledger["pr_links"]), 63)
        self.assertEqual(len(ledger["issue_links"]), 4)
        self.assertEqual(len({q["origin_pr_number"] for q in ledger["pr_links"]}), 63)
        for item in ledger["pr_links"]:
            self.assertTrue(item["origin_pr_url"].startswith(
                "https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/"))
            self.assertIsNone(item["destination_pr_url"])
            self.assertFalse(item["copied_native_approvals"])
            self.assertTrue((ROOT / item["source_body_part"]).is_file())
        for app_id in IDS:
            links = json.loads((APPS / app_id / "HISTORY_LINKS.json").read_text())
            self.assertFalse(links["pr_comments_review_timeline_complete"])
            self.assertFalse(links["chat_requests_export_complete"])

    def test_en_internal_and_en_tr_de_ui_requirements_do_not_claim_implementation(self):
        for app_id in IDS:
            with self.subTest(app=app_id):
                contract = json.loads(
                    (APPS / app_id / "LOCALIZATION_CONTRACT.json").read_text())
                self.assertEqual(contract["engineering_language"], "en")
                ui = contract["user_facing_language_policy"]
                self.assertEqual(ui["required"], ["en", "tr", "de"])
                self.assertEqual(ui["default"], "en")
                self.assertFalse(contract["translation_files_created_in_this_pr"])
                self.assertEqual(contract["current_coverage"],
                                 "not_audited_no_runtime_translation_claim")

    def test_all_matrices_point_to_history_locales_and_rename_identity(self):
        for app_id in IDS:
            for filename in ("FEATURE_MATRIX.json", "COMPONENT_MATRIX.json",
                             "MODEL_MATRIX.json"):
                with self.subTest(app=app_id, matrix=filename):
                    matrix = json.loads((APPS / app_id / filename).read_text())
                    refs = matrix["portable_repository_links"]
                    self.assertEqual(matrix["app_id"], app_id)
                    self.assertFalse(matrix["snapshot_is_active_runtime"])
                    self.assertEqual(matrix["target_engineering_language"], "en")
                    self.assertEqual(matrix["required_ui_languages"], ["en", "tr", "de"])
                    for field in ("repository_identity",
                                  "historical_pr_and_issue_links",
                                  "global_original_to_future_pr_map",
                                  "future_repo_locator", "source_snapshot",
                                  "ui_localization"):
                        self.assertTrue((ROOT / refs[field]).is_file(),
                                        str(refs[field]))


if __name__ == "__main__":
    unittest.main()
