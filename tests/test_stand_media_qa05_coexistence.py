"""QA-05 isolated Media identity, ledger, same-HOME and crash tests.

Only synthetic git trees, fake Kaffeine launchers and temporary user homes.
No network, apt, dpkg, hardware, installed media, models or system services.
The original QA-03 and #105/#108 tests are not modified or skipped.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from kaffeine_next import media_standalone_guard as guard

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    p = subprocess.run(["git", *args], cwd=root, capture_output=True,
                       text=True, check=True, timeout=20)
    return p.stdout.strip()


class IndependentHomeFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="stand-qa05-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "HOME"
        self.home.mkdir()
        # Stable-first/legacy paths are NEVER adopted or read by this ledger.
        self.stable = {
            ".config/TIHULU/KaffeineRadio.conf": b"legacy-radio-user-language=de\n",
            ".config/TIHULU/KaffeineCaptionAppearance.conf": b"stable-caption-theme\n",
            ".config/tihulu-media-centerrc": b"stable-kconfig-user-settings\n",
            ".local/share/tihulu-media-center/channels.db": b"stable-channels\n",
            ".local/share/tihulu-media-center/native/install_welle.sh": b"stable-aux\n",
            ".local/opt/tihulu-media-center/current": b"stable-old-app\n",
            "Videos/TIHULU Recordings/recording.ts": b"stable-private-video",
            "external-ssd/whisper/ggml-small.bin": b"private-model",
        }
        for name, data in self.stable.items():
            file = self.home / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        self.stable_sha = self.hash_stable()
        self.source = self.root / "repo"
        for f in ("kaffeine_next/patch_upstream.py",
                  "kaffeine_next/media_standalone_guard.py",
                  "kaffeine_next/assets/tihulu-media-center.svg",
                  "tv_center/__main__.py"):
            dest = self.source / f
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("pinned fake source\n")
        git(self.source, "init", "-q")
        git(self.source, "config", "user.email", "ci@invalid.example")
        git(self.source, "config", "user.name", "CI Isolated Fixture")
        git(self.source, "add", ".")
        git(self.source, "commit", "-qm", "Synthetic Media only")
        self.rev = git(self.source, "rev-parse", "HEAD")
        self.artifact = self.root / "artifact"
        for name, data in {
            "bin/kaffeine": b"fake-native-player",
            "share/tv_center/__main__.py": b"standalone Python",
            "aux/install_welle.sh": b"no-sudo-welle",
            "aux/dvb_diagnostics.sh": b"read-only DVB",
            "setup/launcher": b"#!/bin/sh\nexit 0\n",
            "setup/desktop": b"[Desktop Entry]\nStartupWMClass=tihulu-media-standalone\n",
            "setup/cli": b"#!/bin/sh\nexit 0\n",
            "setup/icon": b"<svg/>",
        }.items():
            path = self.artifact / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if name in ("setup/launcher", "setup/cli", "bin/kaffeine"):
                path.chmod(0o755)
        (self.artifact / "bin/tihulu-media-standalone").symlink_to("kaffeine")

    def hash_stable(self):
        return {x: hashlib.sha256((self.home / x).read_bytes()).hexdigest()
                for x in self.stable}


class CoexistenceTests(IndependentHomeFixture):
    def test_negative_same_home_stable_files_are_unchanged_across_install_and_rollback(self):
        before = self.hash_stable()
        self.assertEqual(guard.preflight(self.home, self.source, self.rev)["owner"],
                         "tihulu-media-standalone")
        self.assertEqual(before, self.hash_stable())
        installed = guard.activate(self.home, self.source, self.rev, self.artifact)
        self.assertEqual(installed["phase"], "active")
        self.assertEqual(before, self.hash_stable())
        self.assertTrue(guard.layout(self.home)["launcher"].is_file())
        self.assertEqual(guard.validate_rollback(self.home, self.rev)["package_action"],
                         "none")
        self.assertEqual(guard.rollback(self.home, self.rev)["phase"], "rolled_back")
        self.assertEqual(before, self.hash_stable())
        self.assertEqual(guard.rollback(self.home, self.rev)["repeat"], True)

    def test_plan_and_foreign_destination_fail_without_home_mutation(self):
        before = sorted(str(x) for x in self.home.rglob("*"))
        plan = guard.preflight(self.home, self.source, self.rev, dab=True, ai=True)
        self.assertEqual(plan["system_package_operations"], [])
        self.assertFalse(plan["legacy_import"])
        self.assertEqual(before, sorted(str(x) for x in self.home.rglob("*")))
        foreign = guard.layout(self.home)["desktop"]
        foreign.parent.mkdir(parents=True)
        foreign.write_bytes(b"FOREIGN DESKTOP KEEP")
        with self.assertRaisesRegex(guard.Hold, "unowned"):
            guard.preflight(self.home, self.source, self.rev)
        self.assertEqual(foreign.read_bytes(), b"FOREIGN DESKTOP KEEP")
        self.assertEqual(self.hash_stable(), self.stable_sha)

    def test_modified_launcher_refuses_full_rollback_before_any_write(self):
        guard.activate(self.home, self.source, self.rev, self.artifact)
        launch = guard.layout(self.home)["launcher"]
        launch.write_bytes(b"USER EDIT - NO OVERWRITE")
        with self.assertRaisesRegex(guard.Hold, "change before rollback"):
            guard.validate_rollback(self.home, self.rev)
        with self.assertRaises(guard.Hold):
            guard.rollback(self.home, self.rev)
        self.assertEqual(launch.read_bytes(), b"USER EDIT - NO OVERWRITE")
        self.assertTrue(guard.layout(self.home)["current"].is_symlink())
        self.assertEqual(self.hash_stable(), self.stable_sha)

    def test_verified_same_commit_second_install_is_idempotent(self):
        guard.activate(self.home, self.source, self.rev, self.artifact)
        before = self.hash_stable()
        self.assertTrue(guard.preflight(self.home, self.source, self.rev)["already_active"])
        self.assertTrue(guard.activate(self.home, self.source, self.rev, self.artifact)["repeat"])
        self.assertEqual(before, self.hash_stable())

    def test_interrupted_activation_with_partial_owned_staging_recovers_without_legacy_damage(self):
        proposed = guard.proposed(self.home, self.rev, self.artifact)
        pending = guard.layout(self.home)["releases"] / (".pending-" + self.rev[:12])
        pending.parent.mkdir(parents=True)
        (pending / "setup").mkdir(parents=True)
        (pending / "setup/icon").write_bytes(b"<svg/>")
        journal = {"owner": guard.APP, "sha": self.rev, "phase": "prepared",
                   "prior": None, "new": proposed, "pending": str(pending)}
        guard.write_journal(self.home, self.rev, journal)
        plan = guard.validate_rollback(self.home, self.rev)
        self.assertEqual(plan["package_action"], "none")
        self.assertEqual(guard.rollback(self.home, self.rev)["phase"], "rolled_back")
        self.assertFalse(pending.exists())
        self.assertEqual(self.hash_stable(), self.stable_sha)

    def test_interrupted_partial_staging_foreign_file_fails_closed(self):
        proposed = guard.proposed(self.home, self.rev, self.artifact)
        pending = guard.layout(self.home)["releases"] / (".pending-" + self.rev[:12])
        pending.mkdir(parents=True)
        (pending / "foreign").write_bytes(b"DO NOT DELETE")
        guard.write_journal(self.home, self.rev, {"owner": guard.APP,
            "sha": self.rev, "phase": "prepared", "prior": None,
            "new": proposed, "pending": str(pending)})
        with self.assertRaisesRegex(guard.Hold, "Pending copy modified"):
            guard.rollback(self.home, self.rev)
        self.assertEqual((pending / "foreign").read_bytes(), b"DO NOT DELETE")

    def test_missing_build_source_and_symlinked_owner_are_rejected(self):
        (self.source / "untracked-code.py").write_text("x=1\n")
        with self.assertRaisesRegex(guard.Hold, "Dirty"):
            guard.preflight(self.home, self.source, self.rev)
        (self.source / "untracked-code.py").unlink()
        dest = guard.layout(self.home)["launcher"]
        dest.parent.mkdir(parents=True)
        foreign = self.root / "foreign"
        foreign.write_bytes(b"FOREIGN")
        dest.symlink_to(foreign)
        with self.assertRaisesRegex(guard.Hold, "unowned"):
            guard.preflight(self.home, self.source, self.rev)
        self.assertEqual(foreign.read_bytes(), b"FOREIGN")


class NativeIdentityContracts(unittest.TestCase):
    def test_native_app_and_every_radio_caption_recording_namespace_diverges(self):
        patcher = (ROOT / "kaffeine_next/patch_upstream.py").read_text()
        radio = (ROOT / "kaffeine_next/native_radio_tab.h").read_text()
        captions = (ROOT / "kaffeine_next/captions_overlay.py").read_text()
        player = (ROOT / "kaffeine_next/native_media_panel.h").read_text()
        recorder = (ROOT / "kaffeine_next/native_unified_recorder.h").read_text()
        self.assertIn('setApplicationName("tihulu-media-standalone")', patcher)
        self.assertIn("org.mpris.MediaPlayer2.tihulu_media_standalone", patcher)
        self.assertIn("TIHULUStandalone", patcher)
        self.assertNotIn('QLatin1String("KaffeineRadio")', radio)
        self.assertIn('QLatin1String("KaffeineStandaloneRadio")', radio)
        self.assertIn('QLatin1String("StandaloneMediaPlayer")', player)
        self.assertIn('QLatin1String("StandaloneRecordings")', recorder)
        self.assertIn("StandaloneKaffeineCaptionAppearance", captions)
        self.assertIn("StandaloneKaffeineSpeakerLabelNames", captions)
        self.assertIn("StandaloneKaffeineTVFileCaptionDefaults", captions)
        self.assertIn("tihulu-standalone-dvb-", captions)

    def test_no_untrusted_global_installer_package_and_no_legacy_import(self):
        source = (ROOT / "kaffeine_next/media_standalone_install.sh").read_text()
        self.assertNotIn("sudo apt-get", source)
        self.assertNotIn("apt-get install -y", source)
        self.assertNotIn("dpkg -i ", source)
        self.assertNotIn("cp -n", source)
        self.assertIn("media_standalone_guard.py", source)
        self.assertIn("TIHULU_MEDIA_STANDALONE=1", source)
        self.assertIn("StartupWMClass=tihulu-media-standalone", source)
        self.assertIn("tihulu-media-standalone-cli", source)


if __name__ == "__main__":
    unittest.main()
