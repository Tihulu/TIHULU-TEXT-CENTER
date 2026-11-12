"""STAND-RFGEO: fully synthetic package/install/rollback acceptance evidence.

No real installation, network requests, receiver/USB access, driver operations,
readsb shutdown or user data migration. All writes are inside TemporaryDirectory.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

from rf_geolocation_center.packaging import (
    APP_ID, BUNDLE_LAUNCHER, FORMAT, NAME, PackageError, _tar_bytes,
    build_bytes, build_to, compatibility_report, linux_data_roots,
    plan_install, receiver_access_preflight, review_rollback, verify_bytes,
    verify_path,
)

ROOT = Path(__file__).resolve().parents[1]


class PackagingPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload, cls.manifest = build_bytes(ROOT)

    def test_repeated_build_is_deterministic_and_arch_neutral(self):
        second, manifest = build_bytes(ROOT)
        self.assertEqual(self.payload, second)
        self.assertEqual(self.manifest, manifest)
        self.assertEqual(manifest["format"], FORMAT)
        self.assertEqual(manifest["app_id"], APP_ID)
        self.assertEqual(manifest["supported_linux_architectures"], ["aarch64", "x86_64"])
        self.assertFalse(manifest["hardware_verified"])
        self.assertFalse(manifest["native_desktop_binary"])
        self.assertGreaterEqual(len(manifest["owned_files"]), 25)
        with tarfile.open(fileobj=io.BytesIO(self.payload), mode="r:gz") as tar:
            members = tar.getmembers()
            self.assertTrue(all(member.isfile() and member.mtime == 0 and
                                member.uid == 0 and member.gid == 0 for member in members))
            self.assertEqual(tar.getmember(BUNDLE_LAUNCHER).mode, 0o755)
            self.assertEqual(tar.getmember(
                "rf_geolocation_center/scripts/usb_prepare_linux.sh").mode, 0o644)
            self.assertEqual(tar.getmember(
                "rf_geolocation_center/scripts/dvb_scan_linux.sh").mode, 0o644)
        self.assertEqual(verify_bytes(second), manifest)

    def test_payload_is_rfgeo_only_and_preserves_survey_gnss_maps(self):
        names = set(self.manifest["owned_files"])
        for required in (
            "rf_geolocation_center/__main__.py",
            "rf_geolocation_center/native.py",
            "rf_geolocation_center/radio_metadata.py",
            "rf_geolocation_center/dvb_bridge.py",
            "rf_geolocation_center/core/gnss.mjs",
            "rf_geolocation_center/core/positioning.mjs",
            "rf_geolocation_center/core/location_layers.mjs",
            "rf_geolocation_center/core/evidence.mjs",
            "rf_geolocation_center/core/rf_ranging.mjs",
            "rf_geolocation_center/web/rf_survey.mjs",
            "rf_geolocation_center/web/maps.mjs",
            "rf_geolocation_center/web/usb_sdr.mjs",
            "rf_geolocation_center/web/catalog_discovery.mjs",
            "rf_geolocation_center/web/exit_lifecycle.mjs",
            "rf_geolocation_center/index.html",
            "rf_geolocation_center/manifest.webmanifest",
            "rf_geolocation_center/sw.js",
            BUNDLE_LAUNCHER,
        ):
            self.assertIn(required, names)
        for name in names:
            self.assertTrue(name.startswith("rf_geolocation_center/") or name == BUNDLE_LAUNCHER)
            self.assertNotIn("/tests/", name)
            self.assertNotIn("/docs/", name)
            self.assertNotIn("/packaging/", name)
            self.assertNotIn("survival-kit", name)
            self.assertNotIn("text_center/", name)
            self.assertNotIn("flight_radar/", name)
        self.assertEqual(verify_bytes(self.payload), self.manifest)

    def test_synthetic_unpacked_only_app_cli_without_other_apps(self):
        with tempfile.TemporaryDirectory(prefix="rfgeo-stand-pack-") as tmp:
            root = Path(tmp).resolve()
            with tarfile.open(fileobj=io.BytesIO(self.payload), mode="r:gz") as tar:
                # Tests create only the isolated TEMP fixture; NEVER call extractall
                # with an unvalidated archive or install to a production prefix.
                verify_bytes(self.payload)
                for member in tar.getmembers():
                    target = root / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(tar.extractfile(member).read())
            self.assertEqual(sorted(path.name for path in root.iterdir()),
                             ["bin", "package-manifest.json", "rf_geolocation_center"])
            env = os.environ.copy()
            for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
                env.pop(key, None)
            env["PYTHONNOUSERSITE"] = "1"
            cli = subprocess.run(
                [sys.executable, "-m", "rf_geolocation_center", "--help"],
                cwd=root, env=env, capture_output=True, text=True,
                timeout=15, check=False,
            )
            self.assertEqual(cli.returncode, 0, cli.stderr)
            self.assertIn("serve", cli.stdout)
            self.assertIn("doctor", cli.stdout)
            # The native script is a portable relative path launcher, NOT an
            # OS desktop binary, and must never start by itself on packaging.
            self.assertTrue((root / "bin/tihulu-rfgeo").is_file())
            if os.name != "nt":
                launcher = subprocess.run(
                    ["sh", str(root / "bin/tihulu-rfgeo"), "--help"],
                    cwd=root / "rf_geolocation_center", env=env,
                    capture_output=True, text=True, timeout=15, check=False,
                )
                self.assertEqual(launcher.returncode, 0, launcher.stderr)
                self.assertIn("serve", launcher.stdout)

    def test_build_requires_explicit_directory_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="rfgeo-build-") as tmp:
            destination = Path(tmp).resolve()
            report = build_to(ROOT, destination)
            self.assertEqual(Path(report["archive"]).name, NAME)
            self.assertEqual(report["sha256"], hashlib.sha256(self.payload).hexdigest())
            self.assertEqual(verify_path(Path(report["archive"])), self.manifest)
            with self.assertRaises(PackageError):
                build_to(ROOT, destination)
            self.assertEqual((destination / NAME).read_bytes(), self.payload)

    def test_abstract_linux_user_paths_no_file_writes(self):
        with tempfile.TemporaryDirectory(prefix="rfgeo-xdg-") as tmp:
            home = Path(tmp) / "home"
            xdg = {"XDG_CONFIG_HOME": str(home / "xdg-config"),
                   "XDG_CACHE_HOME": str(home / "xdg-cache"),
                   "XDG_DATA_HOME": str(home / "xdg-data"),
                   "XDG_STATE_HOME": str(home / "xdg-state")}
            roots = linux_data_roots(home, xdg)
            self.assertEqual(len(roots), 7)
            self.assertTrue(all("tihulu/rf-geolocation-center" in Path(root).as_posix()
                                for root in roots.values()))
            self.assertEqual(roots["config"], str(home / "xdg-config/tihulu/rf-geolocation-center"))
            self.assertNotEqual(roots["data"], roots["cache"])
            self.assertNotEqual(roots["recordings"], roots["exports"])
            self.assertFalse(home.exists(), "pure path calculation wrote an OS directory")
            with self.assertRaises(PackageError):
                linux_data_roots(home, {"XDG_DATA_HOME": "relative/path"})

    def test_dry_run_records_checksums_owned_files_and_preserves_sentinels(self):
        with tempfile.TemporaryDirectory(prefix="rfgeo-plan-") as tmp:
            root = Path(tmp).resolve()
            archive = root / NAME
            archive.write_bytes(self.payload)
            home = root / "home"
            prefix = root / "candidate-rfgeo"
            foreign = root / "tihulu-flight-radar" / "saved-aircraft.json"
            foreign.parent.mkdir()
            foreign.write_bytes(b"FOREIGN DATA UNTOUCHED")
            owner_recordings = home / ".local/share/tihulu/rf-geolocation-center/recordings"
            owner_recordings.mkdir(parents=True)
            protected = owner_recordings / "old-capture.wav"
            protected.write_bytes(b"OLD USER CAPTURE")
            plan = plan_install(archive, prefix, home)
            self.assertEqual(plan["schema"], "rfgeo-install-dry-run-v1")
            self.assertEqual(plan["mode"], "DRY_RUN_ONLY")
            self.assertFalse(plan["install_executed"])
            self.assertFalse(plan["receiver_claims"])
            self.assertFalse(plan["driver_changes"])
            self.assertFalse(plan["service_changes"])
            self.assertFalse(plan["network_listeners_started"])
            self.assertEqual(plan["foreign_apps_required"], [])
            self.assertEqual(len(plan["planned_created_files"]),
                             len(self.manifest["owned_files"]))
            self.assertFalse(prefix.exists())
            self.assertEqual(foreign.read_bytes(), b"FOREIGN DATA UNTOUCHED")
            self.assertEqual(protected.read_bytes(), b"OLD USER CAPTURE")
            self.assertTrue(all(str(prefix) in entry["path"] for entry in
                                plan["planned_created_files"]))
            self.assertEqual(review_rollback(plan, prefix)["eligible_owned_unchanged_files"], [])
            self.assertEqual(protected.read_bytes(), b"OLD USER CAPTURE")

    def test_synthetic_stage_and_rollback_review_is_checksum_scoped(self):
        with tempfile.TemporaryDirectory(prefix="rfgeo-rollback-") as tmp:
            root = Path(tmp).resolve()
            archive = root / NAME
            archive.write_bytes(self.payload)
            prefix = root / "package-prefix"
            plan = plan_install(archive, prefix, root / "home")
            with tarfile.open(fileobj=io.BytesIO(self.payload), mode="r:gz") as tar:
                for member in tar.getmembers():
                    target = prefix / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(tar.extractfile(member).read())
            rollback = review_rollback(plan, prefix)
            self.assertEqual(len(rollback["eligible_owned_unchanged_files"]),
                             len(plan["planned_created_files"]))
            self.assertEqual(rollback["protected_modified_or_foreign_files"], [])
            self.assertFalse(rollback["deletion_executed"])
            user_modified = prefix / "rf_geolocation_center/index.html"
            user_modified.write_bytes(user_modified.read_bytes() + b"\nuser modification")
            changed = review_rollback(plan, prefix)
            self.assertEqual(len(changed["protected_modified_or_foreign_files"]), 1)
            self.assertIn("index.html", changed["protected_modified_or_foreign_files"][0]["path"])
            self.assertFalse(changed["deletion_executed"])
            self.assertIn(b"user modification", user_modified.read_bytes())

    def test_foreign_existing_file_or_symlinked_install_target_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="rfgeo-foreign-") as tmp:
            root = Path(tmp).resolve()
            archive = root / NAME
            archive.write_bytes(self.payload)
            prefix = root / "install"
            (prefix / "rf_geolocation_center").mkdir(parents=True)
            (prefix / "rf_geolocation_center/native.py").write_text("FOREIGN FILE", encoding="utf-8")
            with self.assertRaisesRegex(PackageError, "overwrite"):
                plan_install(archive, prefix, root / "home")
            self.assertEqual((prefix / "rf_geolocation_center/native.py").read_text(),
                             "FOREIGN FILE")
            link = root / "symlinked-prefix"
            try:
                link.symlink_to(prefix, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("OS/user cannot create symlinks")
            with self.assertRaisesRegex(PackageError, "symlink"):
                plan_install(archive, link, root / "home")

    def test_malicious_archive_with_path_escape_or_bad_checksum_is_rejected(self):
        bad = dict(self.manifest["owned_files"])
        self.assertIn("rf_geolocation_center/native.py", bad)
        with self.assertRaises(PackageError):
            verify_bytes(b"not a tarball")
        with self.assertRaises(PackageError):
            _tar_bytes({"../flight-radar/saved.json": b"unsafe"})
        with tarfile.open(fileobj=io.BytesIO(self.payload), mode="r:gz") as tar:
            existing = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
        existing["rf_geolocation_center/native.py"] += b"\n# tampered"
        with self.assertRaisesRegex(PackageError, "checksum"):
            verify_bytes(_tar_bytes(existing))
        # Rehashing a package with a missing browser module cannot trick the
        # verifier: it independently reconstructs native.ASSETS closure.
        missing_asset = {name: data for name, data in existing.items()
                         if name != "rf_geolocation_center/web/maps.mjs"}
        forged_manifest = json.loads(missing_asset["package-manifest.json"])
        forged_manifest["owned_files"] = {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            for name, data in sorted(missing_asset.items())
            if name != "package-manifest.json"
        }
        missing_asset["package-manifest.json"] = (
            json.dumps(forged_manifest, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True) + "\n"
        ).encode("utf-8")
        with self.assertRaisesRegex(PackageError, "asset closure"):
            verify_bytes(_tar_bytes(missing_asset))

    def test_package_does_not_grant_receiver_rights_or_stop_foreign_services(self):
        for consent, owner, lease, expected in (
            (False, "known-free", True, "CONSENT_REQUIRED"),
            (True, "unknown", True, "BUSY_OR_UNKNOWN_EXTERNAL_OWNER"),
            (True, "external", True, "BUSY_OR_UNKNOWN_EXTERNAL_OWNER"),
            (True, "app-owned", False, "EXCLUSIVE_LEASE_NOT_VERIFIED"),
            (True, "app-owned", True, "POLICY_ONLY_NOT_A_RECEIVER_CLAIM"),
        ):
            outcome = receiver_access_preflight(
                explicit_consent=consent, owner_classification=owner,
                verified_exclusive_lease=lease,
            )
            self.assertEqual(outcome["status"], expected)
            self.assertFalse(outcome["may_claim_now"])
            self.assertFalse(outcome["device_opened"])
            self.assertFalse(outcome["driver_unbound"])
            self.assertFalse(outcome["readsb_or_other_service_stopped"])

    def test_linux_targets_are_source_eligible_others_not_native_verified(self):
        for arch in ("x86_64", "AMD64", "aarch64", "arm64"):
            state = compatibility_report("Linux", arch, (3, 11))
            self.assertTrue(state["linux_portable_source_eligible"])
            self.assertFalse(state["native_gui_binary_installed"])
            self.assertFalse(state["receiver_ownership_verified"])
        for system, arch, version in (
            ("Linux", "i686", (3, 11)),
            ("Linux", "x86_64", (3, 10)),
            ("Windows", "AMD64", (3, 12)),
            ("Darwin", "arm64", (3, 12)),
        ):
            state = compatibility_report(system, arch, version)
            self.assertFalse(state["linux_portable_source_eligible"])
            self.assertFalse(state["native_gui_binary_installed"])

    def test_planner_cli_is_read_only_and_has_no_install_verb(self):
        with tempfile.TemporaryDirectory(prefix="rfgeo-cli-plan-") as tmp:
            root = Path(tmp).resolve()
            archive = root / NAME
            archive.write_bytes(self.payload)
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            check = subprocess.run(
                [sys.executable, "-m", "rf_geolocation_center.packaging", "check"],
                cwd=ROOT.parent, env=env, capture_output=True, text=True,
                timeout=15, check=False,
            )
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertFalse(json.loads(check.stdout)["native_gui_binary_installed"])
            bad = subprocess.run(
                [sys.executable, "-m", "rf_geolocation_center.packaging", "install"],
                cwd=ROOT.parent, env=env, capture_output=True, text=True,
                timeout=15, check=False,
            )
            self.assertNotEqual(bad.returncode, 0)
            self.assertFalse((root / "installed").exists())


if __name__ == "__main__":
    unittest.main()
