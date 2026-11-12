"""STAND-RFGEO: clean single-app source closure without external TIHULU apps.

Only Python stdlib, synthetic folder copies, and static source. No network,
WebUSB, DVB devices, driver actions or system-service calls.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from rf_geolocation_center import native, radio_metadata

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ("__init__.py", "__main__.py", "native.py", "dvb_bridge.py", "radio_metadata.py")


class StandaloneSourceTests(unittest.TestCase):
    def test_all_native_asset_routes_are_owned_and_contained(self):
        self.assertGreaterEqual(len(native.ASSETS), 20)
        for route, (relative, mime) in native.ASSETS.items():
            with self.subTest(route=route):
                rel = Path(relative)
                self.assertFalse(rel.is_absolute())
                self.assertNotIn("..", rel.parts)
                self.assertTrue((ROOT / rel).is_file())
                result = native.safe_asset(route)
                self.assertIsNotNone(result)
                self.assertTrue(result[0].is_relative_to(ROOT))
                self.assertEqual(result[1], mime)
        self.assertIsNone(native.safe_asset("/textcenter/server.py"))
        self.assertIsNone(native.safe_asset("/tihulu-flight-radar/index.html"))
        self.assertIsNone(native.safe_asset("/../other-app/secrets"))

    def test_browser_static_module_graph_resolves_inside_package(self):
        modules = sorted((*ROOT.joinpath("web").glob("*.mjs"),
                          *ROOT.joinpath("core").glob("*.mjs")))
        self.assertGreaterEqual(len(modules), 18)
        # Ignore remote, pinned import() statements; they remain separately
        # disclosed OPTIONAL internet/CDN dependencies.
        expression = re.compile(r"""(?:\bfrom\s+|\bimport\s*\(\s*)['"](\.{1,2}/[^'"]+)['"]""")
        checked = 0
        for path in modules:
            source = path.read_text(encoding="utf-8")
            for ref in expression.findall(source):
                checked += 1
                asset = (path.parent / ref).resolve()
                with self.subTest(module=str(path.relative_to(ROOT)), dependency=ref):
                    self.assertTrue(asset.is_relative_to(ROOT), "foreign app/source import")
                    self.assertTrue(asset.is_file(), "missing bundled dependency")
                    self.assertIn("/" + asset.relative_to(ROOT).as_posix(), native.ASSETS)
        self.assertGreaterEqual(checked, 15)

    def test_service_worker_shell_and_html_assets_exist_in_native_allowlist(self):
        sw = ROOT.joinpath("sw.js").read_text(encoding="utf-8")
        match = re.search(r"const SHELL=\[([\s\S]*?)\];", sw)
        self.assertIsNotNone(match, "missing independent PWA shell definition")
        entries = re.findall(r"""['"](\./[^'"]+)['"]""", match.group(1))
        self.assertGreaterEqual(len(entries), 14)
        for entry in entries:
            if entry == "./":
                continue
            rel = Path(entry[2:])
            with self.subTest(cache=entry):
                self.assertTrue((ROOT / rel).is_file())
                self.assertIn("/" + rel.as_posix(), native.ASSETS)
        html = ROOT.joinpath("index.html").read_text(encoding="utf-8")
        refs = re.findall(r"""(?:href|src)=['"](\./[^'"?#]+)['"]""", html)
        self.assertGreaterEqual(len(refs), 3)
        for ref in refs:
            if ref == "./":
                continue
            with self.subTest(page_asset=ref):
                rel = Path(ref[2:])
                self.assertTrue((ROOT / rel).is_file())
                self.assertIn("/" + rel.as_posix(), native.ASSETS)
        # Personal RF, location, downloaded maps and other app resources are
        # not legal entries in the static shell precache.
        self.assertFalse(any("recording" in s or "flight-radar" in s or "textcenter" in s
                             for s in entries))

    def test_runtime_python_imports_are_local_or_standard_library(self):
        for filename in PYTHON:
            tree = ast.parse(ROOT.joinpath(filename).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        self.assertIn(node.module, ("native", "dvb_bridge", "radio_metadata"))
                        continue
                    modules = [node.module or ""]
                else:
                    continue
                for name in modules:
                    with self.subTest(path=filename, python_import=name):
                        self.assertIn(name.split(".")[0], sys.stdlib_module_names,
                                      "undeclared foreign-app/PyPI runtime dependency")

    def test_missing_text_center_radio_provider_fails_closed(self):
        # The Text Center 8787 endpoint is optional; never open a socket.
        with patch.object(radio_metadata, "_get", side_effect=ConnectionRefusedError("synthetic absent app")):
            state = radio_metadata.read_local_radio_metadata()
        self.assertEqual(state["available"], False)
        self.assertEqual(state["events"], [])
        self.assertEqual(state["rdsActive"], False)
        self.assertIsNone(state["dab"])

    def test_cli_help_starts_from_copy_containing_only_rfgeo_package(self):
        # No sibling checkouts, symlinks, altered PYTHONPATH or real devices.
        with tempfile.TemporaryDirectory(prefix="rfgeo-standalone-") as tmp:
            target = Path(tmp) / "rf_geolocation_center"
            shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "tests", "docs"))
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                             ["rf_geolocation_center"])
            env = os.environ.copy()
            for var in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
                env.pop(var, None)
            env["PYTHONNOUSERSITE"] = "1"
            result = subprocess.run(
                [sys.executable, "-m", "rf_geolocation_center", "--help"],
                cwd=tmp, env=env, capture_output=True, text=True,
                timeout=15, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("serve", result.stdout)
            self.assertIn("doctor", result.stdout)
            self.assertTrue((target / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
