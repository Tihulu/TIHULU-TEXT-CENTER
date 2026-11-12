"""STAND-RFGEO-PACKAGING: exclusively synthetic per-user install fixtures.

No USB, DVB, shell helper, systemctl, readsb, hardware, network, or real
user-home installation is started by any test in this module.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from rf_geolocation_center.packaging import standalone as pkg

ROOT = Path(__file__).resolve().parents[1]
REV_A = "964e7f8eb4abc3e75f25d55a9bf919cac167abdd"
REV_B = "a" * 40


class SyntheticPackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rfgeo-packaging-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.home = self.work / "fake-home"
        self.home.mkdir()
        self.archive = self.work / "rfgeo-a.tar.gz"

    def bundle(self, revision=REV_A, name="rfgeo-a.tar.gz"):
        path = self.work / name
        result = pkg.build_bundle(ROOT, path, revision)
        return path, result

    def test_01_reproducible_bytes_and_complete_local_source(self):
        a, left = self.bundle()
        b, right = self.bundle(name="rfgeo-b.tar.gz")
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertEqual(left["sha256"], right["sha256"])
        manifest, payload, hash_value = pkg.verify_bundle(a)
        self.assertEqual(hash_value, left["sha256"])
        self.assertEqual(manifest["app_id"], pkg.APP_ID)
        self.assertEqual(manifest["version"], "0.1.0-dev")
        self.assertEqual(manifest["source_revision_declared"], REV_A)
        self.assertTrue(pkg.REQUIRED.issubset({
            n[len("rf_geolocation_center/"):] for n in payload
        }))
        self.assertNotIn("rf_geolocation_center/tests/test_standalone_package.py", payload)
        self.assertNotIn("textcenter/", "".join(payload))
        self.assertNotIn("tihulu-flight-radar/", "".join(payload))

    def test_02_build_never_overwrites_existing_artifact(self):
        path, _ = self.bundle()
        original = path.read_bytes()
        with self.assertRaisesRegex(pkg.PackagingError, "Refuse to replace"):
            pkg.build_bundle(ROOT, path, REV_A)
        self.assertEqual(path.read_bytes(), original)

    def test_03_build_refuses_symlink_in_packaged_files(self):
        copy = self.work / "rf_geolocation_center"
        copy.mkdir()
        for item in pkg.REQUIRED:
            target = copy / item
            target.parent.mkdir(exist_ok=True, parents=True)
            target.write_text('source-placeholder')
        malicious = copy / "web" / "borrowed.mjs"
        malicious.symlink_to(self.work / "secret")
        with self.assertRaisesRegex(pkg.PackagingError, "Symlink"):
            pkg.build_bundle(copy, self.work / "bad.tar.gz", REV_A)
        self.assertFalse((self.work / "bad.tar.gz").exists())

    def test_04_build_refuses_undeclared_unrelated_app_file(self):
        copy = self.work / "rf_geolocation_center"
        copy.mkdir()
        for item in pkg.REQUIRED:
            target = copy / item
            target.parent.mkdir(exist_ok=True, parents=True)
            target.write_text('source-placeholder')
        other = copy / "textcenter"
        other.mkdir()
        (other / "speech.py").write_text("SHOULD NOT BE INCLUDED")
        with self.assertRaisesRegex(pkg.PackagingError, "Unexpected source directory"):
            pkg.build_bundle(copy, self.work / "bad.tar.gz", REV_A)
        self.assertFalse((self.work / "bad.tar.gz").exists())

    def test_05_dry_run_has_no_side_effects(self):
        archive, _ = self.bundle()
        plan = pkg.install_plan(archive, home=self.home, system="Linux", machine="x86_64")
        self.assertTrue(plan["dry_run"])
        self.assertIn("NO FOREIGN", plan["policy"])
        self.assertFalse((self.home / ".local").exists())
        self.assertFalse((self.home / ".config").exists())
        self.assertFalse((self.home / ".cache").exists())
        self.assertEqual(pkg.install_bundle(archive, home=self.home,
                                            system="Linux", machine="aarch64"), {
            **pkg.install_plan(archive, home=self.home, system="Linux", machine="aarch64")
        })
        self.assertFalse((self.home / ".local").exists())

    def test_06_explicit_sandbox_install_is_package_scoped(self):
        archive, _ = self.bundle()
        result = pkg.install_bundle(archive, apply=True, home=self.home,
                                    system="Linux", machine="x86_64")
        self.assertFalse(result["dry_run"])
        root = self.home / ".local" / "opt" / pkg.APP_ID
        self.assertTrue((root / "bin" / "tihulu-rfgeo").is_file())
        self.assertEqual(os.stat(root / "bin" / "tihulu-rfgeo").st_mode & 0o777, 0o755)
        self.assertTrue((root / "releases" / result["release"] / "rf_geolocation_center" / "index.html").is_file())
        for key, base in (("config", ".config"), ("cache", ".cache"), ("data", ".local/share")):
            self.assertTrue((self.home / base / pkg.APP_ID).is_dir())
            self.assertEqual(Path(result[key]), self.home / base / pkg.APP_ID)
        state = json.loads((root / "state.json").read_text())
        self.assertEqual(state["active"], result["release"])
        self.assertEqual(state["previous"], [])
        self.assertFalse((self.home / "textcenter").exists())
        self.assertFalse((self.home / ".local/bin/tihulu-rfgeo").exists())

    def test_07_sandbox_launcher_help_works_without_other_apps_or_pythonpath(self):
        archive, _ = self.bundle()
        result = pkg.install_bundle(archive, apply=True, home=self.home,
                                    system="Linux", machine="x86_64")
        launcher = Path(result["launcher"])
        env = dict(os.environ)
        for variable in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
            env.pop(variable, None)
        env["HOME"] = str(self.home)
        env["PYTHONNOUSERSITE"] = "1"
        completed = subprocess.run([sys.executable, str(launcher), "--help"],
                                   cwd=self.home, env=env, capture_output=True,
                                   text=True, timeout=12, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("serve", completed.stdout)
        self.assertIn("doctor", completed.stdout)

    def test_08_repeated_identical_install_cannot_overwrite_release(self):
        archive, _ = self.bundle()
        pkg.install_bundle(archive, apply=True, home=self.home,
                           system="Linux", machine="x86_64")
        root = self.home / ".local" / "opt" / pkg.APP_ID
        state = (root / "state.json").read_bytes()
        with self.assertRaisesRegex(pkg.PackagingError, "already staged"):
            pkg.install_bundle(archive, apply=True, home=self.home,
                               system="Linux", machine="x86_64")
        self.assertEqual((root / "state.json").read_bytes(), state)

    def test_09_two_versions_and_pointer_only_rollback_preserve_user_data(self):
        a, _ = self.bundle()
        b, _ = self.bundle(revision=REV_B, name="rfgeo-b.tar.gz")
        first = pkg.install_bundle(a, apply=True, home=self.home,
                                   system="Linux", machine="aarch64")
        recording = self.home / ".local" / "share" / pkg.APP_ID / "user-measurements.csv"
        recording.write_bytes(b"USER-DATA-MUST-REMAIN\x00\xff")
        config = self.home / ".config" / pkg.APP_ID / "preferences.json"
        config.write_text('{"custom":true}')
        second = pkg.install_bundle(b, apply=True, home=self.home,
                                    system="Linux", machine="aarch64")
        self.assertNotEqual(first["release"], second["release"])
        planned = pkg.rollback(home=self.home, system="Linux", machine="aarch64")
        self.assertEqual(planned["from"], second["release"])
        self.assertEqual(planned["to"], first["release"])
        self.assertTrue(planned["dry_run"])
        root = self.home / ".local" / "opt" / pkg.APP_ID
        current_before = json.loads((root / "state.json").read_text())["active"]
        self.assertEqual(current_before, second["release"])
        reverted = pkg.rollback(apply=True, home=self.home, system="Linux", machine="aarch64")
        self.assertFalse(reverted["dry_run"])
        active = json.loads((root / "state.json").read_text())["active"]
        self.assertEqual(active, first["release"])
        self.assertTrue((root / "releases" / second["release"]).is_dir())
        self.assertEqual(recording.read_bytes(), b"USER-DATA-MUST-REMAIN\x00\xff")
        self.assertEqual(config.read_text(), '{"custom":true}')
        self.assertFalse((root / ".operation-lock").exists())

    def test_10_tampered_rollback_target_refuses_changes(self):
        a, _ = self.bundle()
        b, _ = self.bundle(revision=REV_B, name="rfgeo-b.tar.gz")
        first = pkg.install_bundle(a, apply=True, home=self.home, system="Linux", machine="x86_64")
        second = pkg.install_bundle(b, apply=True, home=self.home, system="Linux", machine="x86_64")
        root = self.home / ".local" / "opt" / pkg.APP_ID
        old = root / "releases" / first["release"] / "rf_geolocation_center" / "index.html"
        old.write_text("tampered installed HTML")
        previous_state = (root / "state.json").read_bytes()
        with self.assertRaisesRegex(pkg.PackagingError, "changed"):
            pkg.rollback(home=self.home, system="Linux", machine="x86_64")
        self.assertEqual((root / "state.json").read_bytes(), previous_state)
        self.assertTrue((root / "releases" / second["release"]).exists())

    def test_11_existing_foreign_user_install_prefix_is_refused(self):
        root = self.home / ".local" / "opt" / pkg.APP_ID
        root.mkdir(parents=True)
        foreign = root / "user notes.txt"
        foreign.write_bytes(b"belongs to user")
        archive, _ = self.bundle()
        with self.assertRaisesRegex(pkg.PackagingError, "unowned install prefix"):
            pkg.install_plan(archive, home=self.home, system="Linux", machine="x86_64")
        self.assertEqual(foreign.read_bytes(), b"belongs to user")

    def test_12_symlinked_user_home_branch_is_refused(self):
        base = self.home / ".local"
        external = self.work / "foreign"
        external.mkdir()
        base.symlink_to(external, target_is_directory=True)
        archive, _ = self.bundle()
        with self.assertRaisesRegex(pkg.PackagingError, "Symlinked"):
            pkg.install_plan(archive, home=self.home, system="Linux", machine="x86_64")
        self.assertEqual(list(external.iterdir()), [])

    def test_13_active_install_lock_refuses_concurrent_operations(self):
        archive, _ = self.bundle()
        first = pkg.install_bundle(archive, apply=True, home=self.home,
                                   system="Linux", machine="x86_64")
        root = self.home / ".local" / "opt" / pkg.APP_ID
        lock = root / ".operation-lock"
        lock.mkdir()
        b, _ = self.bundle(revision=REV_B, name="rfgeo-b.tar.gz")
        with self.assertRaisesRegex(pkg.PackagingError, "lock|operation"):
            pkg.install_bundle(b, apply=True, home=self.home,
                               system="Linux", machine="x86_64")
        self.assertEqual(json.loads((root / "state.json").read_text())["active"], first["release"])

    def test_14_unsupported_platform_refused_without_writes(self):
        archive, _ = self.bundle()
        self.assertFalse(pkg.host_capabilities("Windows", "AMD64")["supported_install_target"])
        self.assertFalse(pkg.host_capabilities("Darwin", "arm64")["supported_install_target"])
        self.assertFalse(pkg.host_capabilities("Linux", "i686")["supported_install_target"])
        for system, machine in (("Windows", "AMD64"), ("Darwin", "arm64"), ("Linux", "armv7l")):
            with self.subTest(system=system), self.assertRaisesRegex(pkg.PackagingError, "Linux x64/ARM64"):
                pkg.install_plan(archive, home=self.home, system=system, machine=machine)
        self.assertFalse((self.home / ".local").exists())

    def test_15_traversal_and_symlink_archive_members_are_refused(self):
        archive, _ = self.bundle()
        manifest, assets, _ = pkg.verify_bundle(archive)
        for member_name, symlink in (
            ("rf_geolocation_center/../../foreign.txt", False),
            ("rf_geolocation_center/web/borrowed.mjs", True),
        ):
            with self.subTest(member_name=member_name):
                evil = self.work / ("link.tar.gz" if symlink else "traversal.tar.gz")
                with tarfile.open(evil, "w:gz") as tf:
                    content = b"do not extract"
                    info = tarfile.TarInfo(member_name)
                    info.type = tarfile.SYMTYPE if symlink else tarfile.REGTYPE
                    info.linkname = "../../foreign.txt" if symlink else ""
                    info.size = 0 if symlink else len(content)
                    tf.addfile(info, io.BytesIO(content) if not symlink else None)
                with self.assertRaises(pkg.PackagingError):
                    pkg.verify_bundle(evil)
        self.assertFalse((self.work / "foreign.txt").exists())

    def test_16_unknown_receivers_and_foreign_apps_are_never_contacted(self):
        # Packaging validation does not connect anything; device and foreign
        # service ownership remain UNKNOWN, requiring explicit consent later.
        archive, _ = self.bundle()
        with patch.object(subprocess, "Popen", side_effect=AssertionError("forbidden process")):
            with patch("socket.socket", side_effect=AssertionError("forbidden socket")):
                plan = pkg.install_plan(archive, home=self.home, system="Linux", machine="x86_64")
                self.assertEqual(plan["policy"],
                                 "NO DEVICE, NO DRIVERS, NO READSB, NO FOREIGN APPLICATION ACCESS")
        self.assertFalse((self.home / ".local").exists())


if __name__ == "__main__":
    unittest.main()
