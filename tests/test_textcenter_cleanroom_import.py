"""Text-only cleanroom smoke tests: no Media package, RF device or network.

Tested source is current canonical Text main, not the archived snapshot.
The archived compute/speech/transcripts import regression is separately open.
"""
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "textcenter"
# -I prevents current checkout and user-site packages from entering sys.path.
# Only the copied Text package is inserted inside the isolated child process.
CLEANROOM = """
import builtins
import importlib.util
import socket
import subprocess
import sys
from pathlib import Path
from unittest import mock

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
assert importlib.util.find_spec("tv_center") is None, "Media package leaked into Text-only runner"

original_import = builtins.__import__
def no_media(name, *args, **kwargs):
    if name == "tv_center" or name.startswith("tv_center."):
        raise AssertionError("Text-only import attempted to use Media: " + name)
    return original_import(name, *args, **kwargs)

with mock.patch("builtins.__import__", side_effect=no_media), \\
     mock.patch.object(subprocess, "Popen", side_effect=AssertionError("process started during import")), \\
     mock.patch.object(socket, "socket", side_effect=AssertionError("network opened during import")):
    import textcenter
    import textcenter.compute
    import textcenter.transcripts
    import textcenter.speech
    import textcenter.http_app
assert "tv_center" not in sys.modules
assert textcenter.compute.LANGUAGES == ("en", "de", "tr")
print("TEXT_CLEANROOM_OK")
"""

DISCOVERY = """
import importlib.util
import sys
from pathlib import Path
from unittest import mock

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from textcenter import compute
original_find = importlib.util.find_spec

def safe_find(name, *args):
    if name.startswith(("openvino", "hailo", "faster_whisper", "ctranslate2")):
        return None
    return original_find(name, *args)

with mock.patch.object(compute.importlib.util, "find_spec", side_effect=safe_find):
    result = compute.detect_devices(
        executable_lookup=lambda _: None,
        device_root=root / "empty-dev",
        model_path="",
        system="Linux",
        command_runner=lambda _: "")
assert any(device["id"] == "cpu" and device["runtime_ready"]
           for device in result["devices"]), result
assert "tv_center" not in sys.modules
print("TEXT_MOCKED_CPU_OK")
"""


class TextCleanroomTests(unittest.TestCase):
    def run_isolated(self, script):
        with tempfile.TemporaryDirectory(prefix="tihulu-text-cleanroom-") as work:
            root = Path(work)
            shutil.copytree(SOURCE, root / "textcenter")
            (root / "empty-dev").mkdir()
            result = subprocess.run(
                [sys.executable, "-I", "-c", textwrap.dedent(script), str(root)],
                cwd=str(root), capture_output=True, text=True, timeout=25,
                check=False,
            )
            self.assertEqual(result.returncode, 0,
                             "Text-only process failed; no installed Media allowed.\n"
                             + result.stdout[-1000:] + result.stderr[-3000:])
            return result.stdout

    def test_current_main_imports_without_media_or_side_effects(self):
        self.assertIn("TEXT_CLEANROOM_OK", self.run_isolated(CLEANROOM))

    def test_cpu_discovery_does_not_need_media_or_devices(self):
        self.assertIn("TEXT_MOCKED_CPU_OK", self.run_isolated(DISCOVERY))


if __name__ == "__main__":
    unittest.main()
