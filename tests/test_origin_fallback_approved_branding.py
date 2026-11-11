"""Read-only audit of approved artwork and rename-resistant source gaps.

This test does not modify any installed application, download models, create
GitHub objects, read private chats, install icons, or access RF devices.
"""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps"
IDS = ("media-center", "satellite-center", "geolocation-center",
       "text-center", "flight-radar")


class OriginAndApprovedBrandingTests(unittest.TestCase):
    def test_coverage_ledger_is_explicitly_incomplete_but_source_linked(self):
        coverage = json.loads((APP / "_archives" / "HISTORY_COVERAGE_AUDIT.json").read_text())
        self.assertEqual(coverage["source_repository"]["id"], 1447637221)
        self.assertEqual(len(coverage["entries"]), 67)
        self.assertEqual(len(coverage["issues"]), 4)
        self.assertFalse(coverage["archive_native_reviews_complete"])
        self.assertEqual(len({p["original_number"] for p in coverage["entries"]}), 67)
        for p in coverage["entries"]:
            self.assertTrue(p["original_url"].startswith(
                "https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/"))
            self.assertEqual(p["body_status"], "description_archived_in_snapshot")
            self.assertTrue((ROOT / p["body_source"]).is_file())
            self.assertEqual(p["reviews"], "not_exported_or_unverified")
            self.assertIsNone(p["future_destination_pr_url"])
            self.assertEqual(p["native_github_identity"],
                "cannot_recreate_original_ids_or_native_approvals_with_standard_pr_creation")
        for item in coverage["issues"]:
            self.assertTrue((ROOT / item["description_archive"]).is_file())
            self.assertIsNone(item["future_destination_issue_url"])

    def test_all_apps_have_origin_pointers_and_crosslinked_matrices(self):
        reg = json.loads((APP / "registry.json").read_text())
        self.assertEqual(len(reg["apps"]), 5)
        self.assertFalse(reg["all_five_logos_installed_in_running_apps"])
        for app in reg["apps"]:
            id = app["id"]
            with self.subTest(app=id):
                origin = APP / id / "ORIGIN.md"
                self.assertTrue(origin.is_file())
                self.assertIn("1447637221", origin.read_text())
                snapshot_origin = APP / id / "source" / "ORIGIN.md"
                self.assertEqual(snapshot_origin.is_file(), id != "flight-radar")
                self.assertEqual(app["migration_state"]["state"], "not_started")
                for reference in ("history_gap_index", "approved_branding_manifest"):
                    self.assertTrue((ROOT / app[reference]).is_file())
                gaps = json.loads((ROOT / app["history_gap_index"]).read_text())
                self.assertEqual(gaps["app_id"], id)
                self.assertEqual(gaps["origin_id"]["github_repository_numeric_id"],
                                 1447637221)
                self.assertFalse(gaps["new_repository_created_by_this_record"])
                for file in ("FEATURE_MATRIX.json","COMPONENT_MATRIX.json","MODEL_MATRIX.json"):
                    matrix=json.loads((APP/id/file).read_text())
                    links=matrix["portable_repository_links"]
                    self.assertTrue((ROOT/links["incompletely_transferred_topics_and_origin_urls"]).is_file())
                    self.assertTrue((ROOT/links["approved_application_logo"]).is_file())
                    self.assertTrue(matrix["approved_logo_not_yet_installed"])

    def test_five_logos_approved_but_not_misrepresented_as_vector_or_installed(self):
        manifest = json.loads((APP / "BRANDING_APPROVED_MANIFEST.json").read_text())
        self.assertTrue(manifest["approved_by_user_in_conversation"])
        self.assertEqual({a["id"] for a in manifest["apps"]}, set(IDS))
        self.assertFalse(manifest["origin_logo"]["genuine_editable_svg_received"])
        self.assertFalse(manifest["new_binary_assets_committed_in_this_pr"])
        self.assertFalse(manifest["existing_app_icons_changed"])
        for app in manifest["apps"]:
            with self.subTest(app=app["id"]):
                self.assertRegex(app["master_sha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(app["master_format"], "image/png")
                self.assertEqual(len(app["approved_logo_pack_relative_icons"]), 4)
                self.assertFalse(app["runtime_icon_replaced"])
                data = json.loads((APP / app["id"] / "APPROVED_BRANDING.json").read_text())
                self.assertEqual(data["approved_png_master_sha256"], app["master_sha256"])
                self.assertFalse(data["asset_binary_in_git"])
                self.assertFalse(data["actual_vector_svg_available"])

    def test_no_rename_and_no_extra_model_install(self):
        identity=json.loads((APP / "REPOSITORY_IDENTITY.json").read_text())
        self.assertTrue(identity["repository_rename_pending"])
        self.assertEqual(identity["origin_repository_id"],1447637221)
        dev=json.loads((APP / "DEVELOPMENT_AGENT_MATRIX.json").read_text())
        self.assertFalse(dev["model_install_required"])
        self.assertFalse(dev["binary_logos_committed_in_current_repo"])


if __name__ == "__main__":
    unittest.main()
