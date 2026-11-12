"""STAND-TEXT installer preparation: synthetic, Text-only and no real install.

Uses temporary fixtures for release activation/rollback. Never touches user
home, actual models, system services, USB, TV frontend or host receivers.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "tihulu_text_installer_preflight", ROOT / "scripts" / "text_standalone.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class StandTextInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="stand-text-installer-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "text-only"
        self.source.mkdir()
        shutil.copytree(ROOT / "textcenter", self.source / "textcenter",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "web", self.source / "web")
        self.pin = installer.pin_from_file()
        self.bundle = self.root / "v1.zip"
        self.second = self.root / "v1-duplicate.zip"

    def test_exact_canonical_blob_pin_is_byte_reproducible_and_text_only(self):
        one = installer.write_package(self.source, self.bundle, self.pin)
        two = installer.write_package(self.source, self.second, self.pin)
        self.assertEqual(one["sha256"], two["sha256"])
        self.assertEqual(self.bundle.read_bytes(), self.second.read_bytes())
        self.assertEqual(one["source"], "1fffb711bfbb7c4abaf55299fa9240e5db3e1cde")
        manifest, parts = installer.inspect_bundle(self.bundle.read_bytes(), self.pin)
        self.assertEqual(manifest["version"], "0.6.0")
        self.assertEqual(len(parts), 24)
        self.assertEqual(set(parts), set(self.pin["files"]))
        self.assertFalse(any(x.startswith(("apps/", "tv_center/", "flight_radar/",
                                           "satellite_center/", "rf_geolocation_center/"))
                             for x in parts))
        self.assertTrue(any(x.startswith("web/") for x in parts))
        self.assertEqual(installer.write_package(self.source, self.bundle, self.pin)["unchanged"], True)
        (self.source / "textcenter" / "compute.py").write_text(
            (self.source / "textcenter" / "compute.py").read_text() + "\n# forbidden drift\n")
        with self.assertRaisesRegex(installer.InstallerError, "blob mismatch"):
            installer.bundle_bytes(self.source, self.pin)

    def test_symlinked_source_and_cross_app_prefix_fail_closed(self):
        original = self.source / "web" / "index.html"
        link_target = self.root / "imported.html"
        link_target.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(link_target)
        with self.assertRaisesRegex(installer.InstallerError, "Symlink"):
            installer.bundle_bytes(self.source, self.pin)
        with self.assertRaisesRegex(installer.InstallerError, "another TIHULU"):
            installer._safe_prefix(self.root / "tihulu-flight-radar" / "something")
        with self.assertRaisesRegex(installer.InstallerError, "another TIHULU"):
            installer._data_paths(self.root / "tihulu-media-center" / "data")

    def test_plan_is_read_only_and_windows_cannot_be_misreported(self):
        installer.write_package(self.source, self.bundle, self.pin)
        prefix = self.root / "uninstalled" / "tihulu-text-center"
        paths = self.root / "external-data"
        report = installer.deploy(self.bundle, prefix, paths, pin=self.pin)
        self.assertEqual(report["mode"], "DRY_RUN")
        self.assertFalse(report["automatic_service_start"])
        self.assertFalse(report["external_receiver_actions"])
        self.assertFalse(report["models_changed"])
        self.assertEqual(report["database"], str(paths / "text-center.db"))
        self.assertFalse(prefix.exists())
        self.assertFalse(paths.exists())
        not_windows = installer.support(platform_name="Windows")
        self.assertFalse(not_windows["core_launch_candidate"])
        self.assertIn("fcntl", " ".join(not_windows["notes"]))
        self.assertFalse(not_windows["installed_platform_verified"])
        with self.assertRaisesRegex(installer.InstallerError, "Unsupported core platform"):
            installer.deploy(self.bundle, prefix, paths,
                             apply=True, pin=self.pin, platform_name="Windows")
        self.assertFalse(prefix.exists())
        self.assertFalse(paths.exists())

    def test_temp_two_release_rollback_keeps_data_models_and_other_apps(self):
        installer.write_package(self.source, self.bundle, self.pin)
        # Synthetic second release exercises real rollback pointer mechanics.
        # It does NOT claim to be a genuine newer canonical source commit.
        source_b = self.root / "mock-next-text"
        shutil.copytree(self.source, source_b)
        changed_file = source_b / "web" / "index.html"
        changed_file.write_bytes(changed_file.read_bytes() + b"\n<!-- synthetic only -->\n")
        pin_b = copy.deepcopy(self.pin)
        pin_b["canonical_commit"] = "b" * 40
        pin_b["version"] = "0.6.1-synthetic"
        pin_b["files"]["web/index.html"] = installer._blob(changed_file.read_bytes())
        next_archive = self.root / "v2.zip"
        installer.write_package(source_b, next_archive, pin_b)

        prefix = self.root / "private-text" / "runtime"
        data_root = self.root / "private-text" / "data"
        foreign = self.root / "foreign-data" / "important-recording.mp4"
        foreign.parent.mkdir()
        foreign.write_bytes(b"Other application must remain untouched")
        shared_ssd_model = self.root / "external-ssd" / "whisper" / "model.bin"
        shared_ssd_model.parent.mkdir(parents=True)
        shared_ssd_model.write_bytes(b"Shared model weights are never managed")
        old_weights = hashlib.sha256(shared_ssd_model.read_bytes()).hexdigest()

        first = installer.deploy(self.bundle, prefix, data_root, pin=self.pin, apply=True)
        old_id = first["bundle_sha256"]
        self.assertIsNone(first["previous_bundle_sha256"])
        self.assertEqual((prefix / "owner.json").stat().st_mode & 0o777, 0o600)
        original_recording = data_root / "recordings" / "keep-fm.mp3"
        original_recording.parent.mkdir(parents=True)
        original_recording.write_bytes(b"Existing Text recording must remain")

        with patch.dict(os.environ, {"TIHULU_WHISPER_MODEL": str(shared_ssd_model)}):
            second = installer.deploy(next_archive, prefix, data_root, pin=pin_b,
                                      apply=True)
            next_id = second["bundle_sha256"]
            self.assertNotEqual(old_id, next_id)
            self.assertEqual(second["previous_bundle_sha256"], old_id)
            current = installer._active(prefix)
            self.assertEqual(current["bundle_sha256"], next_id)
            self.assertEqual(installer.rollback(prefix)["mode"], "DRY_RUN")
            self.assertEqual(installer._active(prefix), current)
            done = installer.rollback(prefix, apply=True)
            self.assertEqual(done["to"], old_id)
            self.assertEqual(installer._active(prefix)["bundle_sha256"], old_id)
            self.assertTrue((prefix / "releases" / next_id).exists())
            self.assertTrue((prefix / "releases" / old_id).exists())
        self.assertEqual(original_recording.read_bytes(),
                         b"Existing Text recording must remain")
        self.assertEqual(foreign.read_bytes(),
                         b"Other application must remain untouched")
        self.assertEqual(hashlib.sha256(shared_ssd_model.read_bytes()).hexdigest(),
                         old_weights)
        self.assertEqual(installer._active(prefix)["database"],
                         str(data_root / "text-center.db"))

    def test_unowned_prefix_corrupt_release_and_untrusted_bundle_refused(self):
        installer.write_package(self.source, self.bundle, self.pin)
        unowned = self.root / "unowned"
        unowned.mkdir()
        marker = unowned / "another-app.json"
        marker.write_text("must be unchanged")
        with self.assertRaisesRegex(installer.InstallerError, "no Text-owned marker"):
            installer.deploy(self.bundle, unowned, pin=self.pin, apply=True)
        self.assertEqual(marker.read_text(), "must be unchanged")
        prefix = self.root / "owned" / "runtime"
        first = installer.deploy(self.bundle, prefix, pin=self.pin, apply=True)
        with self.assertRaisesRegex(installer.InstallerError, "No prior"):
            installer.rollback(prefix, apply=True)
        original = (prefix / "releases" / first["bundle_sha256"] /
                    "textcenter" / "__main__.py")
        original.write_bytes(b"# attacker-modified source\n")
        state = installer._active(prefix).copy()
        with self.assertRaisesRegex(installer.InstallerError, "contents modified"):
            installer.deploy(self.bundle, prefix, pin=self.pin, apply=True)
        self.assertEqual(state, installer._active(prefix))
        with zipfile.ZipFile(self.root / "extra.zip", "w") as bad:
            bad.write(self.bundle, arcname="../foreign.py")
        with self.assertRaises(installer.InstallerError):
            installer.read_bundle(self.root / "extra.zip", self.pin)

    def test_preflight_optional_python_packages_and_model_paths_are_not_runnable_claims(self):
        # Pure metadata and environment inspection: no model import/inference.
        with patch.object(installer.importlib.util, "find_spec", return_value=None) as probe, \
             patch.dict(os.environ, {"TIHULU_WHISPER_MODEL":
                                      str(self.root / "external-ssd" / "not-installed.bin")}):
            status = installer.support(platform_name="Linux", version=(3, 11),
                                       lookup=lambda _: None)
        self.assertTrue(status["core_launch_candidate"])
        self.assertFalse(status["installed_platform_verified"])
        self.assertTrue(all(not v for v in
                            status["optional_python_packages_present_not_runnable"].values()))
        self.assertTrue(status["model_environment_paths_set_not_verified"]
                        ["TIHULU_WHISPER_MODEL"])
        self.assertTrue(all(not v for v in
                            status["optional_tools_present_not_live_verified"].values()))
        self.assertFalse(status["native_dvb_tuning"])
        self.assertFalse(status["journaline_decoder"])
        self.assertEqual(probe.call_count, 7)

    def test_launcher_refuses_modified_release_before_import(self):
        if sys.platform == "win32":
            self.skipTest("Canonical Unix fcntl is not available on Windows")
        installer.write_package(self.source, self.bundle, self.pin)
        prefix = self.root / "launcher-tamper" / "runtime"
        result = installer.deploy(self.bundle, prefix, pin=self.pin, apply=True)
        source = (prefix / "releases" / result["bundle_sha256"] /
                  "textcenter" / "__main__.py")
        source.write_bytes(source.read_bytes() + b"\n# altered after install\n")
        proc = subprocess.run(
            [sys.executable, str(prefix / "bin" / "tihulu-text-center"), "--help"],
            cwd=str(self.root), capture_output=True, text=True, timeout=15,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Text-only release integrity check failed", proc.stderr)
        self.assertNotIn("usage:", proc.stdout)

    def test_temp_installed_launcher_can_import_text_without_other_app(self):
        if sys.platform == "win32":
            self.skipTest("Canonical fcntl dependency blocks Windows Text native imports")
        installer.write_package(self.source, self.bundle, self.pin)
        prefix = self.root / "launcher" / "text-only-runtime"
        result = installer.deploy(self.bundle, prefix, pin=self.pin, apply=True)
        launcher = prefix / "bin" / "tihulu-text-center"
        self.assertTrue(launcher.is_file())
        clean_env = dict(os.environ)
        clean_env.pop("PYTHONPATH", None)
        clean_env.pop("TIHULU_TV_CHANNELS_FILE", None)
        proc = subprocess.run(
            [sys.executable, str(launcher), "--help"],
            cwd=str(self.root), env=clean_env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=15, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-1500:])
        self.assertIn("import-text", proc.stdout)
        self.assertIn("serve", proc.stdout)
        self.assertEqual(result["action"], "install")
        self.assertFalse((self.root / "launcher" / "text-only-runtime" /
                          "releases" / result["bundle_sha256"] / "tv_center").exists())


if __name__ == "__main__":
    unittest.main()
