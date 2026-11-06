"""Static safety checks for a single-command user-local installer.

CI must not execute an installation or open a real USB SDR.
"""
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT=Path(__file__).resolve().parents[1]


class InstallerSafetyTests(unittest.TestCase):
    def test_bash_syntax_and_non_destructive_update_contract(self):
        script=ROOT/"install.sh"
        self.assertTrue(script.is_file())
        data=script.read_text()
        self.assertIn("git -C \"$repo\" merge --ff-only FETCH_HEAD",data)
        self.assertIn("status --porcelain",data)
        self.assertIn("No RF scan, model download",data)
        self.assertIn("--update",data)
        self.assertNotIn("git reset --hard",data)
        self.assertNotRegex(data,r"(?m)^\\s*sudo\\s")
        if shutil.which("bash"):
            result=subprocess.run(["bash","-n",str(script)],
                                  capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=="__main__":
    unittest.main()
