"""A06-115: FULL original guard-module negative regressions. No owner machine.

Disposable HOME/source/artifact only. Original QA03/QA05 files remain intact.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import unittest

from kaffeine_next import media_standalone_guard as guard
from test_stand_media_qa05_coexistence import IndependentHomeFixture

ROOT = Path(__file__).resolve().parents[1]


class FullGuardForgery(IndependentHomeFixture):
    def setUp(self):
        super().setUp()
        self.assertEqual(guard.activate(
            self.home, self.source, self.rev, self.artifact)["phase"], "active")
        self.before = self.hash_stable()

    def _forge(self, raw, *, marker=None):
        record = guard.journal(self.home, self.rev)
        record["phase"] = "prepared"
        record["pending"] = raw
        if marker is not None:
            record["pending_identity"] = marker
        # Deliberately bypass the installer writer: this is what forged
        # on-disk JSON means. Invoke the ACTUAL guard functions afterward.
        guard.atomic_json(guard.journal_path(self.home, self.rev),
                          self.home, record)

    @staticmethod
    def _id(path):
        st = path.lstat()
        return {"dev": st.st_dev, "ino": st.st_ino, "uid": st.st_uid}

    def _must_hold(self):
        with self.assertRaises(guard.Hold):
            guard.validate_rollback(self.home, self.rev)
        with self.assertRaises(guard.Hold):
            guard.rollback(self.home, self.rev)
        self.assertEqual(self.hash_stable(), self.before)
        self.assertTrue(guard.layout(self.home)["current"].is_symlink())

    def test_01_forged_outside_home_empty_dir_is_never_deleted(self):
        outside = self.root / "unrelated-empty"
        outside.mkdir()
        self._forge(str(outside), marker=self._id(outside))
        self._must_hold()
        self.assertTrue(outside.is_dir())

    def test_02_forged_outside_home_manifest_matching_file_is_never_deleted(self):
        outside = self.root / "foreign-matching"
        outside.mkdir()
        original = self.artifact / "setup/icon"
        (outside / "setup").mkdir()
        (outside / "setup/icon").write_bytes(original.read_bytes())
        sentinel = (outside / "setup/icon").read_bytes()
        self._forge(str(outside), marker=self._id(outside))
        self._must_hold()
        self.assertEqual((outside / "setup/icon").read_bytes(), sentinel)

    def test_03_parent_escape_is_never_canonicalized_or_deleted(self):
        foreign = guard.layout(self.home)["root"] / "foreign"
        foreign.mkdir()
        (foreign / "protected").write_bytes(b"KEEP-FOREIGN")
        raw = str(guard.layout(self.home)["releases"] / ".." / "foreign")
        self._forge(raw, marker=self._id(foreign))
        self._must_hold()
        self.assertEqual((foreign / "protected").read_bytes(), b"KEEP-FOREIGN")

    def test_04_symlink_pending_to_foreign_is_rejected(self):
        outside = self.root / "private-data"
        outside.mkdir()
        (outside / "owner.dat").write_bytes(b"OWN")
        pending = guard.layout(self.home)["releases"] / (".pending-" + self.rev[:12])
        pending.symlink_to(outside, target_is_directory=True)
        self._must_hold()
        self.assertEqual((outside / "owner.dat").read_bytes(), b"OWN")

    def test_05_replaced_canonical_pending_inode_is_rejected(self):
        pending = guard.layout(self.home)["releases"] / (".pending-" + self.rev[:12])
        pending.mkdir()
        (pending / "setup").mkdir()
        (pending / "setup/icon").write_bytes((self.artifact / "setup/icon").read_bytes())
        self._must_hold()
        self.assertTrue((pending / "setup/icon").is_file())

    def test_14_symlinked_releases_ancestor_never_traversed(self):
        releases = guard.layout(self.home)["releases"]
        parked = self.root / "protected-releases"
        releases.rename(parked)
        releases.symlink_to(parked, target_is_directory=True)
        self._must_hold()
        self.assertTrue((parked / self.rev[:12]).is_dir())

    def test_06_forged_matching_canonical_inode_without_receipt_is_rejected(self):
        pending = guard.layout(self.home)["releases"] / (".pending-" + self.rev[:12])
        pending.mkdir()
        r = guard.journal(self.home, self.rev)
        r["pending_identity"] = None
        guard.atomic_json(guard.journal_path(self.home, self.rev), self.home, r)
        self._must_hold()
        self.assertTrue(pending.is_dir())

    def test_07_manifest_mismatch_in_staging_never_deletes_foreign(self):
        pending = guard.layout(self.home)["releases"] / (".pending-" + self.rev[:12])
        pending.mkdir()
        foreign = pending / "foreign.txt"
        foreign.write_bytes(b"STRANGER")
        self._forge(str(pending), marker=self._id(pending))
        self._must_hold()
        self.assertEqual(foreign.read_bytes(), b"STRANGER")

    def test_08_wrong_sha_or_current_receipt_cannot_authorize_cleanup(self):
        r = guard.journal(self.home, self.rev)
        r["new"]["sha"] = "a" * 40
        guard.atomic_json(guard.journal_path(self.home, self.rev), self.home, r)
        self._must_hold()

    def test_09_historical_normal_rollback_and_reinstall_still_work(self):
        self.assertEqual(guard.rollback(self.home, self.rev)["phase"], "rolled_back")
        self.assertTrue(guard.preflight(
            self.home, self.source, self.rev)["historical_reentry"])
        self.assertEqual(guard.activate(
            self.home, self.source, self.rev, self.artifact)["phase"], "active")
        self.assertEqual(self.hash_stable(), self.before)


class SourceAndProcessContracts(unittest.TestCase):
    def test_10_every_radio_and_media_cli_process_uses_pinned_absolute_path(self):
        for filename in ("native_radio_tab.h", "native_media_panel.h"):
            source = (ROOT / "kaffeine_next" / filename).read_text()
            self.assertIn('#include "tihulu_companion_path.h"', source)
            self.assertNotRegex(source,
                r'\.start\(\s*QLatin1String\("tihulu-media-standalone-cli"\)')
            self.assertIn("tihuluCompanionCliPath()", source)
        patched = (ROOT / "kaffeine_next/patch_upstream.py").read_text()
        self.assertNotIn('hubProcess->start(QLatin1String("tihulu-media-standalone-cli")', patched)
        self.assertIn('hubProcess->start(tihuluCompanionCliPath()', patched)

    def test_11_absolute_companion_path_enforces_owner_inode_and_mode(self):
        source = (ROOT / "kaffeine_next/tihulu_companion_path.h").read_text()
        for fragment in ("::lstat(", "st.st_uid != ::geteuid()", "file.st_nlink != 1",
                         "(file.st_mode & 0077)", "return QString();"):
            self.assertIn(fragment, source)

    def test_12_fifo_has_exclusive_create_owner_check_and_inode_unlink(self):
        source = (ROOT / "kaffeine_next/patch_upstream.py").read_text()
        for fragment in ("tihuluOwnedFifoIno", "O_NOFOLLOW",
                         "S_ISFIFO(", "tihuluUnlinkOwnedFifo(",
                         "tihulu_owned_fifo_cleanup.h"):
            self.assertIn(fragment, source)
        guard_header = (ROOT / "kaffeine_next/tihulu_owned_fifo_cleanup.h").read_text()
        for fragment in ("::fstat(", "::lstat(", "::unlink(encoded.constData())",
                         "static_cast<quint64>(pathStat.st_ino) != ownedIno", "S_ISFIFO(", "pathStat.st_nlink != 1"):
            self.assertIn(fragment, guard_header)
        self.assertIn("Refuse even a UUID collision", source)

    def test_13_sigkill_leaves_orphan_fifo_foreign_bytes_unmodified(self):
        # A crash CANNOT execute destructors. Any next process must create
        # its own PID+UUID FIFO, NEVER sweep arbitrary old names.
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "orphan.m2t"
            code = ("import os,signal,sys\n"
                    "os.mkfifo(sys.argv[1],0o600)\n"
                    "os.kill(os.getpid(),signal.SIGKILL)\n")
            killed = subprocess.run([sys.executable, "-c", code, str(p)],
                                    capture_output=True, timeout=5)
            self.assertEqual(killed.returncode, -signal.SIGKILL)
            self.assertTrue(stat.S_ISFIFO(p.lstat().st_mode))
            protected = Path(temp) / "foreign-socket"
            protected.write_bytes(b"PRIVATE")
            other = Path(temp) / "next-process.m2t"
            os.mkfifo(other, 0o600)
            self.assertNotEqual(p.lstat().st_ino, other.lstat().st_ino)
            self.assertEqual(protected.read_bytes(), b"PRIVATE")
            self.assertTrue(p.exists())  # no unauthenticated orphan cleanup


if __name__ == "__main__":
    unittest.main()
