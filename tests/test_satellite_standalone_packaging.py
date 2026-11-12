"""STAND-SAT packaging refusal and source integrity contracts.

All fixtures are local mock paths. No app installation, RF, SatDump,
GitHub Pages, Qt, other TIHULU runtime or global service is accessed.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from satellite_center.standalone import preflight as p


REPO = Path(__file__).resolve().parents[1]


def fixture_native(root: Path):
    """A synthetic, minimal source tree, NOT an installed Satellite package."""
    contents = {
        "satellite_center/__main__.py": b"import json\n",
        "satellite_center/bridge.py": b"def verify(): return True\n",
        "satellite_center/native_desktop_bridge.js": b"export const ok = true;\n",
        "satellite_center/index.html": b"<!doctype html><title>Mock Satellite</title>\n",
        "satellite_center/README.md": b"# Fake source for test only\n",
        "satellite_center/browser/index.html": b"<!doctype html><title>Bundled mock</title>\n",
        "satellite_center/browser/recorder.mjs": b"export const WAV = true;\n",
        "satellite_center/assets/tihulu-satellite.svg": b"<svg></svg>\n",
        "satellite_center/packaging/debian/build.sh": b"#!/bin/sh\n# Do not execute\n",
    }
    tree = {}
    for path, data in contents.items():
        dest = root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        tree[path] = ("100644", p.blob_sha(data))
    manifest = {"schema": "tihulu-stand-sat-native-manifest-v1",
                "source_commit": "a" * 40,
                "required_blobs": [
                    {"path": path, "git_blob_sha1": tree[path][1]}
                    for path in ("satellite_center/__main__.py",
                                 "satellite_center/bridge.py",
                                 "satellite_center/packaging/debian/build.sh")
                ]}
    return manifest, tree


class StandSatPackagingContracts(unittest.TestCase):
    def test_native_contract_pins_exit01_and_no_foreign_installer(self):
        m = p.load_json(p.NATIVE_MANIFEST)
        self.assertEqual(m["source_commit"],
                         "4e35bf27abba8a4eee7ac27f9c099ea51ede711c")
        self.assertEqual(m["capture_policy"]["mode"], "ON_DEMAND")
        self.assertEqual(m["source_composition"]["combined_native_plus_web_runtime_ci"],
                         "NOT_RUN_HOLD")
        self.assertGreaterEqual(len(m["required_blobs"]), 30)
        self.assertEqual(len(set(x["path"] for x in m["required_blobs"])),
                         len(m["required_blobs"]))
        self.assertTrue(all(x["path"].startswith("satellite_center/")
                            and len(x["git_blob_sha1"]) == 40
                            for x in m["required_blobs"]))
        self.assertIn("PyQt5.QtWebChannel", m["dependencies"]["runtime_required"])
        self.assertIn("HOLD", m["platform_status"]["windows-x64"])
        self.assertIn("HOLD", m["platform_status"]["raspberry-pi-os-arm64"])
        self.assertFalse(m["rollback_safety"]["delete_user_data"])

    def test_web_contract_and_exact_50_blob_source_integrity(self):
        m = p.load_json(p.WEB_MANIFEST)
        index = p.load_json(REPO / m["assets"]["index_path"])
        self.assertEqual(m["source_commit"],
                         "558dcb359b13eedafdc303fa9f321deab9d3ae94")
        self.assertEqual(m["assets"]["static_asset_count"], 50)
        self.assertEqual(m["assets"]["cache_version"],
                         "satellite-webusb-shell-20261112-v2")
        self.assertEqual(index["baseline_summary"]["diff"], 9)
        self.assertEqual(index["baseline_summary"]["absent"], 8)
        self.assertEqual(index["baseline_summary"]["match"], 33)
        self.assertEqual(p.blob_sha((REPO / m["assets"]["index_path"]).read_bytes()),
                         m["assets"]["index_git_blob_sha1"])
        tree = {}
        for row in index["files"]:
            data = (REPO / row["path"]).read_bytes()
            tree[row["path"]] = ("100644", p.blob_sha(data))
        output = p.checked_web(REPO, m, index, tree)
        self.assertEqual(len(output), 50)
        self.assertEqual(sum(bool(x["parity_31"]) for x in output), 31)
        self.assertEqual(output[-1]["path"], "satellite_center/browser/satellite-sw.js")
        self.assertTrue(all(x["action"] == "STAGE_STATIC_FILE_ONLY" for x in output))

    def test_webusb_missing_or_replaced_static_dependency_is_hold(self):
        m = p.load_json(p.WEB_MANIFEST)
        index = p.load_json(REPO / m["assets"]["index_path"])
        tree = {r["path"]: ("100644", r["source_pr101_blob_sha1"])
                for r in index["files"]}
        missing = "satellite_center/browser/pass_candidates.mjs"
        del tree[missing]
        with self.assertRaisesRegex(p.HoldError, "SHA differs"):
            p.checked_web(REPO, m, index, tree)
        tree[missing] = ("100644", "f" * 40)
        with self.assertRaisesRegex(p.HoldError, "SHA differs"):
            p.checked_web(REPO, m, index, tree)
        index = copy.deepcopy(index)
        index["files"][0]["path"] = "../textcenter/stolen.js"
        with self.assertRaises(p.HoldError):
            p.checked_web(REPO, m, index, tree)

    def test_missing_required_esm_and_parity_waiver_are_not_allowed(self):
        m = p.load_json(p.WEB_MANIFEST)
        index = p.load_json(REPO / m["assets"]["index_path"])
        tree = {r["path"]: ("100644", r["source_pr101_blob_sha1"])
                for r in index["files"]}
        index = copy.deepcopy(index)
        index["files"][2]["strict_31"] = not index["files"][2]["strict_31"]
        with self.assertRaisesRegex(p.HoldError, "31-asset parity"):
            p.checked_web(REPO, m, index, tree)
        self.assertFalse(m["publication_gate"]["parity_waiver"])
        self.assertTrue(m["publication_gate"]["must_leave_red_until_publication"])

    def test_native_fixture_plan_is_dry_only_with_rollback_preserving_data(self):
        with tempfile.TemporaryDirectory(prefix="stand-sat-native-test-") as tmp:
            root = Path(tmp)
            foreign = root / "textcenter" / "old_radio.wav"
            foreign.parent.mkdir(parents=True)
            foreign.write_bytes(b"FOREIGN-APP-DATA")
            m, tree = fixture_native(root)
            plan = p.plan("native", root, manifest_override=m,
                          tree_override=tree)
            self.assertFalse(plan["install_performed"])
            self.assertFalse(plan["release_allowed"])
            self.assertFalse(plan["destination_repo_initialized"])
            self.assertEqual(plan["file_count"], 8)
            self.assertFalse(any(x["path"].startswith("textcenter/")
                                 for x in plan["source_files"]))
            self.assertEqual(foreign.read_bytes(), b"FOREIGN-APP-DATA")
            policy = " ".join(plan["rollback_manifest"]["never_remove_or_overwrite"])
            for item in ("captures/", "*.cu8", "*.wav", "other TIHULU",
                         "cooperative Text-center"):
                self.assertIn(item, policy)
            self.assertIn("REG-06", " ".join(plan["unresolved_gates"]))

    def test_native_modified_blob_is_denied_without_write(self):
        with tempfile.TemporaryDirectory(prefix="stand-sat-blob-") as tmp:
            root = Path(tmp)
            m, tree = fixture_native(root)
            target = root / "satellite_center/bridge.py"
            target.write_bytes(b"# modified local implementation\n")
            with self.assertRaisesRegex(p.HoldError, "Unexpected source bytes"):
                p.plan("native", root, manifest_override=m, tree_override=tree)
            self.assertEqual(target.read_bytes(), b"# modified local implementation\n")

    def test_bad_source_git_hash_and_foreign_symlinks_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="stand-sat-guard-") as tmp:
            root = Path(tmp)
            m, tree = fixture_native(root)
            m["required_blobs"][0]["git_blob_sha1"] = "0" * 40
            with self.assertRaisesRegex(p.HoldError, "contract differs"):
                p.plan("native", root, manifest_override=m, tree_override=tree)
            for foreign in ("textcenter/core.py", "tv_center/settings.json",
                            "../outside.cu8", "satellite_center/../textcenter/secret",
                            "/tmp/satellite_center/a", "satellite_center\\..\\other"):
                with self.subTest(path=foreign):
                    with self.assertRaises(p.HoldError):
                        p.safe_path(foreign)

    @unittest.skipIf(os.name == "nt", "Windows cannot always create unprivileged symlinks")
    def test_synthetic_symlink_attack_is_refused_without_touching_foreign_file(self):
        with tempfile.TemporaryDirectory(prefix="stand-sat-symlink-") as tmp:
            root = Path(tmp)
            m, tree = fixture_native(root)
            original = root / "satellite_center/bridge.py"
            outside = root / "foreign.dat"
            outside.write_bytes(b"EXTERNAL")
            original.unlink()
            original.symlink_to(outside)
            with self.assertRaisesRegex(p.HoldError, "Symlink"):
                p.plan("native", root, manifest_override=m, tree_override=tree)
            self.assertEqual(outside.read_bytes(), b"EXTERNAL")

    def test_snapshot_git_ref_mismatch_fails_before_any_copy(self):
        with tempfile.TemporaryDirectory(prefix="stand-sat-git-") as tmp:
            with mock.patch.object(p, "_git", side_effect=[
                    bytes(str(Path(tmp).resolve()) + "\n", "utf8"),
                    b"0" * 40 + b"\n",
            ]):
                with self.assertRaisesRegex(p.HoldError, "Source HEAD mismatch"):
                    p.pinned_tree(Path(tmp), "a" * 40)

    def test_no_composed_integration_or_installer_arguments(self):
        with tempfile.TemporaryDirectory(prefix="stand-sat-args-") as tmp:
            with self.assertRaisesRegex(p.HoldError, "not authorized"):
                p.plan("both", Path(tmp))
            with mock.patch.object(sys, "argv", [
                    "stand-sat", "--mode", "native", "--source-root", tmp,
                    "--install"]):
                with self.assertRaises(SystemExit) as exc:
                    p.main()
                self.assertEqual(exc.exception.code, 2)

    def test_existing_native_data_and_cross_app_lock_are_not_copied_into_payload(self):
        m = p.load_json(p.NATIVE_MANIFEST)
        self.assertEqual(m["capture_policy"]["foreign_services"],
                         "NEVER_STOP_OR_UNBIND")
        self.assertTrue(m["rollback_safety"]["owned_code_only"])
        self.assertFalse(m["rollback_safety"]["delete_records"])
        self.assertIn("LEGACY_TEXT_NAMESPACE",
                      m["capture_policy"]["shared_lease_status"])
        for x in m["required_blobs"]:
            self.assertTrue(x["path"].startswith("satellite_center/"))
        self.assertIn("NOT_RUN_HOLD",
                      m["source_composition"]["combined_native_plus_web_runtime_ci"])


if __name__ == "__main__":
    unittest.main()
