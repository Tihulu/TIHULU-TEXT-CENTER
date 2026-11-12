"""Canonical Text CLI cleanroom acceptance without Media, hardware or LAN.

Python isolated mode copies only textcenter/, never tv_center/. Each test runs
in a new child process; actual server start, device probing, downloads,
radio/TV and any unapproved external process are prohibited by guards.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "textcenter"

CLI_RUNNER = r"""
import builtins
import importlib.util
import json
import runpy
import socket
import subprocess
import sys
from pathlib import Path
from unittest import mock

root = Path(sys.argv[1])
scenario = sys.argv[2]
sys.path.insert(0, str(root))
assert importlib.util.find_spec("tv_center") is None, "Unexpected Media installation"
args = {
    "help": ["--help"],
    "nonloopback": ["serve", "--host", "0.0.0.0"],
    "template": ["make-template", "--file", str(root / "empty-export.json")],
}[scenario]
sys.argv = ["textcenter"] + args

original_import = builtins.__import__
def disallow_media(name, *a, **kw):
    if name == "tv_center" or name.startswith("tv_center."):
        raise AssertionError("Text CLI unexpectedly depends on Media: " + name)
    return original_import(name, *a, **kw)

def exercise():
    try:
        runpy.run_module("textcenter", run_name="__main__", alter_sys=False)
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 1
    return 0

with mock.patch("builtins.__import__", side_effect=disallow_media), \
     mock.patch.object(socket, "socket", side_effect=AssertionError("CLI network access")), \
     mock.patch.object(subprocess, "Popen", side_effect=AssertionError("CLI process spawned")):
    status = exercise()
    expected = {"help": 0, "nonloopback": 2, "template": 0}[scenario]
    assert status == expected, (scenario, status, expected)
    if scenario == "template":
        dest = root / "empty-export.json"
        payload = json.loads(dest.read_text(encoding="utf-8"))
        assert payload == {"schema_version": 1, "pages": [], "events": []}, payload
        original = dest.read_bytes()
        # Existing data must never be overwritten by a second invocation.
        assert exercise() == 2
        assert dest.read_bytes() == original, "Second CLI invocation overwrote user data"

assert "tv_center" not in sys.modules
print("TEXT_CLI_ISOLATED_" + scenario.upper() + "_OK")
"""


class TextCLIStandaloneSmokeTests(unittest.TestCase):
    def child(self, scenario):
        with tempfile.TemporaryDirectory(prefix="tihulu-text-cli-") as work:
            root = Path(work)
            shutil.copytree(SOURCE, root / "textcenter")
            result = subprocess.run(
                [sys.executable, "-I", "-c",
                 textwrap.dedent(CLI_RUNNER), str(root), scenario],
                cwd=str(root),
                capture_output=True, text=True, timeout=25, check=False,
            )
            self.assertEqual(
                result.returncode, 0,
                f"{scenario} failed without Media, services or receiver.\n"
                + result.stdout[-800:] + result.stderr[-1600:],
            )
            return result.stdout

    def test_help_without_media_or_hardware(self):
        self.assertIn("TEXT_CLI_ISOLATED_HELP_OK", self.child("help"))

    def test_nonloopback_host_rejected_without_opening_socket(self):
        self.assertIn("TEXT_CLI_ISOLATED_NONLOOPBACK_OK",
                      self.child("nonloopback"))

    def test_empty_template_and_no_overwrite_without_media(self):
        self.assertIn("TEXT_CLI_ISOLATED_TEMPLATE_OK", self.child("template"))


if __name__ == "__main__":
    unittest.main()
