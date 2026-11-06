import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "textcenter", *map(str,args)],
                              cwd=ROOT, text=True, capture_output=True, timeout=10)

    def test_missing_import_prints_help_without_traceback(self):
        with tempfile.TemporaryDirectory() as path:
            result = self.run_cli("import-text", "--file", Path(path) / "missing.json")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Import file not found", result.stderr)
            self.assertIn("make-template", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_empty_template_is_not_fake_rf_data(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "decoded-pages.json"
            db = Path(temp) / "archive.db"
            created = self.run_cli("make-template", "--file", file)
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertEqual(json.loads(file.read_text()), {
                "schema_version": 1, "pages": [], "events": []
            })
            repeated = self.run_cli("make-template", "--file", file)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("Refusing to overwrite", repeated.stderr)
            imported = self.run_cli("import-text", "--db", db, "--file", file)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertEqual(json.loads(imported.stdout), {"pages":0,"events":0})
            doctor = self.run_cli("doctor", "--db", db)
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            report = json.loads(doctor.stdout)
            self.assertEqual(report["counts"]["pages"], 0)
            self.assertEqual(report["rf_decoder"], "not_bundled")


if __name__ == "__main__":
    unittest.main()
