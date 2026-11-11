"""No-network, no-model-install checks for coding agent onboarding."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class DevelopmentAgentGuideTests(unittest.TestCase):
    def test_entrypoints_exist_and_are_not_model_requirements(self):
        manifest = json.loads((ROOT / "apps/DEVELOPMENT_AGENT_MATRIX.json").read_text())
        self.assertEqual(manifest["type"], "coding_agent_context_not_runtime_ai")
        self.assertFalse(manifest["model_install_required"])
        self.assertFalse(manifest["gpu_npu_required_for_matrix"])
        self.assertFalse(manifest["cloud_api_required_for_matrix"])
        self.assertEqual(len(manifest["apps"]), 5)
        for client in manifest["entrypoints"].values():
            self.assertTrue((ROOT / client["file"]).is_file())
        for path in manifest["global_read_first"]:
            self.assertTrue((ROOT / path).is_file())

    def test_all_agent_references_point_to_real_contracts(self):
        manifest = json.loads((ROOT / "apps/DEVELOPMENT_AGENT_MATRIX.json").read_text())
        for app in manifest["apps"]:
            with self.subTest(app=app["id"]):
                self.assertEqual(app["migration_state"], "not_started")
                for field in ("feature_matrix", "component_matrix",
                              "runtime_ai_matrix", "instructions", "porting_guide"):
                    self.assertTrue((ROOT / app[field]).is_file(), app[field])
                self.assertEqual(json.loads((ROOT / app["feature_matrix"]).read_text())["app_id"], app["id"])
        self.assertFalse(manifest["entrypoints"]["deepseek"]["auto_read_guarantee"])

if __name__ == "__main__":
    unittest.main()
