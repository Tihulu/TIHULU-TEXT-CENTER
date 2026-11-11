"""Portable feature/model matrices: source-evidence and no-fake-capability checks.

Does not install models, open USB/DVB/SDR devices or modify source trees.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"
IDS = ("media-center", "satellite-center", "geolocation-center",
       "text-center", "flight-radar")


class PortableMatrices(unittest.TestCase):
    def test_every_application_has_a_portability_contract(self):
        for slug in IDS:
            with self.subTest(app=slug):
                directory = APPS / slug
                self.assertTrue((directory / "MODEL_MATRIX.md").is_file())
                self.assertTrue((directory / "PORTING_GUIDE.md").is_file())
                for filename in ("FEATURE_MATRIX.json", "MODEL_MATRIX.json"):
                    data = json.loads((directory / filename).read_text(encoding="utf-8"))
                    self.assertEqual(data["schema_version"], 1)
                    self.assertEqual(data["app_id"], slug)
                self.assertTrue((directory / "FEATURE_MATRIX.md").is_file())

    def test_all_evidence_and_test_paths_exist(self):
        # Never invent a test or source citation in the matrix. Empty test
        # arrays are valid and honestly expose release verification gaps.
        for slug in IDS:
            features = json.loads((APPS / slug / "FEATURE_MATRIX.json").read_text())
            models = json.loads((APPS / slug / "MODEL_MATRIX.json").read_text())
            ids = set()
            for feature in features["features"]:
                with self.subTest(app=slug, feature=feature["id"]):
                    self.assertNotIn(feature["id"], ids)
                    ids.add(feature["id"])
                    self.assertTrue(feature["source_paths"])
                    self.assertTrue(feature["invariants"])
                    for value in feature["source_paths"] + feature["test_paths"]:
                        self.assertTrue((ROOT / value).is_file(),
                                        "Unverified feature source or test: " + value)
            for model in models["model_backends"]:
                with self.subTest(app=slug, model=model["engine"]):
                    self.assertEqual(model["installed_on_user_device"],
                                     "unknown_not_probed")
                    self.assertIs(model["verified_real_hardware"], False)
                    self.assertTrue(model["evidence"])
                    self.assertTrue(model["fallback"])
                    for evidence in model["evidence"]:
                        self.assertTrue((ROOT / evidence["path"]).is_file(),
                                        "Unverified model evidence: " + evidence["path"])
                    for test in model["test_paths"]:
                        self.assertTrue((ROOT / test).is_file(),
                                        "Unverified model test: " + test)

    def test_registry_has_no_unapproved_cutover(self):
        registry = json.loads((APPS / "registry.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["status"], "embedded_in_monorepo_no_migration")
        self.assertEqual({r["id"] for r in registry["apps"]}, set(IDS))
        for app in registry["apps"]:
            self.assertEqual(app["migration_state"]["state"], "not_started")
            self.assertIsNone(app["migration_state"]["target_repository"])

    def test_six_workstreams_have_prompts_and_are_read_only(self):
        folder = APPS / "_prompts"
        self.assertTrue((folder / "00-common.md").is_file())
        missions = sorted(folder.glob("0[1-6]-*.md"))
        self.assertEqual(len(missions), 6)
        for path in missions:
            prompt = path.read_text(encoding="utf-8")
            self.assertIn("No program feature", prompt)
            self.assertIn("Draft PR", prompt)
        schema = json.loads(
            (APPS / "_schemas" / "PORTABILITY_MATRIX_SCHEMA.json").read_text())
        self.assertIs(schema["policy"]["source_changes_allowed_in_this_pr"], False)


if __name__ == "__main__":
    unittest.main()
