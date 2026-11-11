"""Verify the owner-approved TIHULU topology without changing application code.

Text Center stays in the original GitHub repository; only three embedded apps
will migrate later, after separate approval. This test needs no network, model,
radio receiver, native GUI or installer access.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"
SOURCE = "Tihulu/TIHULU-TEXT-CENTER"
ID = 1447637221
THREE = {
    "media-center": ("Tihulu/tihulu-media-center", 1454318539),
    "satellite-center": ("Tihulu/tihulu-satellite-center", 1454319572),
    "geolocation-center": ("Tihulu/tihulu-rf-geolocation-center", 1454320329),
}


class CanonicalTopologyTests(unittest.TestCase):
    def test_five_apps_have_five_repos_without_new_text_center(self):
        x = json.loads((APPS / "CANONICAL_REPOSITORY_TOPOLOGY.json").read_text())
        self.assertTrue(x["origin_repository"]["rebrand_rename_allowed_later_with_explicit_approval"])
        self.assertTrue(x["no_repositories_renamed"])
        self.assertTrue(x["no_existing_app_code_moved"])
        self.assertEqual(x["origin_repository"]["repository_id"], ID)
        items = {a["app_id"]: a for a in x["app_canonicals"]}
        self.assertEqual(len(items), 5)
        self.assertEqual(sum(bool(a["move_required"]) for a in items.values()), 3)
        for app_id, (target, repo_id) in THREE.items():
            item = items[app_id]
            self.assertEqual(item["target_repo"], target)
            self.assertEqual(item["target_repo_id"], repo_id)
            self.assertTrue(item["target_created_empty"])
            self.assertFalse(item["cutover_complete"])
        text = items["text-center"]
        self.assertEqual(text["current_source_repo"], SOURCE)
        self.assertEqual(text["target_repo"], SOURCE)
        self.assertEqual(text["target_repo_id"], ID)
        self.assertFalse(text["move_required"])
        self.assertTrue(text["continuing_active_development_here"])
        self.assertEqual(items["flight-radar"]["target_repo"],
                         "Tihulu/tihulu-flight-radar")
        self.assertFalse(items["flight-radar"]["move_required"])

    def test_registry_and_agent_routes_keep_text_center_in_place(self):
        reg = json.loads((APPS / "registry.json").read_text())
        self.assertTrue(reg["text_center_retained_in_origin_repository"])
        self.assertFalse(reg["text_center_dedicated_repository_creation_required"])
        self.assertEqual(set(reg["three_new_app_migrations_only"]), set(THREE))
        a = {x["id"]: x for x in reg["apps"]}
        t = a["text-center"]
        self.assertEqual(t["canonical_repository"], SOURCE)
        self.assertIsNone(t["proposed_destination_repository"])
        self.assertEqual(t["repository_migration_policy"],
                         "stay_in_origin_repository")
        self.assertEqual(t["source_roots"], ["textcenter/", "web/"])
        self.assertTrue(t["can_continue_development_in_current_repository"])
        self.assertEqual(t["migration_state"]["state"], "not_started")
        for app_id in THREE:
            self.assertEqual(a[app_id]["canonical_repository"], SOURCE)
            self.assertEqual(a[app_id]["migration_state"]["state"], "not_started")
        agents = json.loads((APPS / "DEVELOPMENT_AGENT_MATRIX.json").read_text())
        d = {x["id"]: x for x in agents["apps"]}["text-center"]
        self.assertTrue(d["continue_development_in_current_repo"])
        self.assertFalse(d["separate_destination_required"])
        self.assertEqual(d["verified_destination_repository"], SOURCE)

    def test_text_center_source_trees_stay_active_and_preserved(self):
        self.assertTrue((ROOT / "textcenter" / "__init__.py").is_file())
        self.assertTrue((ROOT / "web" / "index.html").is_file())
        self.assertTrue((APPS / "text-center" / "source" / "textcenter" / "__init__.py").is_file())
        self.assertTrue((APPS / "text-center" / "source" / "web" / "index.html").is_file())
        manifest = json.loads((APPS / "text-center" / "manifest.json").read_text())
        self.assertFalse(manifest["separate_repository_required"])
        self.assertIsNone(manifest["proposed_future_destination"])
        pkg = json.loads((APPS / "text-center" / "PORTABLE_PACKAGE.json").read_text())
        self.assertFalse(pkg["repository_migration_required"])
        self.assertEqual(pkg["final_canonical_repository"], SOURCE)
        self.assertTrue(pkg["source_snapshots_remain_read_only"])
        self.assertFalse(pkg["main_branch_changed"])

    def test_app_language_and_logo_guards_still_hold(self):
        topology = json.loads((APPS / "CANONICAL_REPOSITORY_TOPOLOGY.json").read_text())
        self.assertEqual(topology["language_policy"]["developer"], "en")
        self.assertEqual(topology["language_policy"]["user_interface"], ["en","tr","de"])
        self.assertFalse(topology["language_policy"]["coverage_verified"])
        logo = json.loads((APPS / "text-center" / "APPROVED_BRANDING.json").read_text())
        self.assertFalse(logo["asset_binary_in_git"])
        self.assertFalse(logo["runtime_icon_changed"])
        self.assertEqual(logo["canonical_app_repo"], SOURCE)


if __name__ == "__main__":
    unittest.main()
