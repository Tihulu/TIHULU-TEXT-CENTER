"""Static verification: exact owner-created repo IDs and approved red logo identity.

Does not call GitHub, initialize empty repos, install assets, or change runtime code.
"""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
APPS=ROOT/"apps"
EXPECTED={
"media-center":("Tihulu/tihulu-media-center",1454318539),
"satellite-center":("Tihulu/tihulu-satellite-center",1454319572),
"geolocation-center":("Tihulu/tihulu-rf-geolocation-center",1454320329),
}

class VerifiedNewRepos(unittest.TestCase):
    def test_three_created_empty_repos_not_canonical(self):
        verified=json.loads((APPS/"VERIFIED_DESTINATION_REPOSITORIES.json").read_text())
        actual={d["app_id"]:(d["full_name"],d["github_repository_id"])
                for d in verified["verified_destinations"]}
        self.assertEqual(actual,EXPECTED)
        reg=json.loads((APPS/"registry.json").read_text())
        for app in reg["apps"]:
            self.assertEqual(app["migration_state"]["state"],"not_started")
            self.assertIsNone(app["migration_state"]["target_repository"])
            if app["id"] in EXPECTED:
                self.assertEqual(app["proposed_destination_repository"],EXPECTED[app["id"]][0])
                self.assertEqual(app["canonical_repository"],"Tihulu/TIHULU-TEXT-CENTER")
                p=json.loads((APPS/app["id"]/"PORTABLE_PACKAGE.json").read_text())
                self.assertTrue(p["new_repository_created"])
                self.assertTrue(p["new_repository_empty"])
                self.assertFalse(p["application_import_completed"])
        for item in verified["verified_destinations"]:
            self.assertTrue(item["observed_empty"])
            self.assertFalse(item["has_app_source"])
            self.assertFalse(item["has_logo_binaries"])
            self.assertEqual(item["cutover_status"],"not_started")

    def test_exact_approved_red_logo_family_not_replaced(self):
        manifest=json.loads((APPS/"BRANDING_APPROVED_MANIFEST.json").read_text())
        self.assertEqual(manifest["approved_pack_sha256"],
          "49eeccd46ab8b6e630b5567b4e08c0580f22430696de8e215b80d21a52043f84")
        self.assertTrue(manifest["all_master_png_sha256_match_verified_chat_side_pack"])
        self.assertFalse(manifest["existing_app_icons_changed"])
        self.assertFalse(manifest["binary_assets_committed_to_new_repos"])
        self.assertEqual(len(manifest["apps"]),5)
        for item in manifest["apps"]:
            self.assertEqual(item["master_format"],"image/png")
            self.assertFalse(item["runtime_icon_replaced"])
            self.assertEqual(len(item["master_sha256"]),64)

if __name__=="__main__":
    unittest.main()
