"""Preservation guard for the additive, unchanged multi-app integration.

This test protects application trees imported from independent feature branches.
It makes no claims about physical SDR/DVB hardware or cross-app integration.
"""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP_TREES = {
    "satellite_center": "41d5a38c6c5382d205ea98fd98648b8c7c9c2275",
    "rf_geolocation_center": "7be22e93b0138de1efbe6a27b43c8143ead76c49",
}


class PreservedAppTreeTests(unittest.TestCase):
    def test_imported_application_trees_match_their_original_git_objects(self):
        for path, expected_tree in APP_TREES.items():
            with self.subTest(application=path):
                self.assertTrue((ROOT / path).is_dir())
                actual_tree = subprocess.check_output(
                    ["git", "rev-parse", f"HEAD:{path}"],
                    cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
                ).strip()
                self.assertEqual(
                    actual_tree, expected_tree,
                    f"{path} differs from its pre-integration source tree; "
                    "review the changes intentionally before updating the pin.",
                )


if __name__ == "__main__":
    unittest.main()
