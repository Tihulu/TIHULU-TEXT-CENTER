"""STAND-MEDIA PR114 P1/P2 remediation: real disposable guard/child process QA.

No real hardware, sudo, system packages, owner installation, models or services.
Original QA05 tests remain unmodified.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from kaffeine_next import media_standalone_guard as guard
from test_stand_media_qa05_coexistence import IndependentHomeFixture

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "kaffeine_next/media_standalone_install.sh"
PATCHER = ROOT / "kaffeine_next/patch_upstream.py"
RADIO = ROOT / "kaffeine_next/native_radio_tab.h"


def heredoc(source, marker):
    opener = "<<'" + marker + "'\n"
    assert source.count(opener) == 1, marker
    return source.split(opener, 1)[1].split("\n" + marker, 1)[0] + "\n"


class RemediationGuard(IndependentHomeFixture):
    def stable_same(self):
        self.assertEqual(self.hash_stable(), self.stable_sha)

    def test_01_first_install_rollback_reinstall_identical_release(self):
        a = guard.activate(self.home, self.source, self.rev, self.artifact)
        self.assertEqual(a["phase"], "active")
        original = guard.items(guard.release_path(self.home, self.rev))
        self.assertEqual(guard.rollback(self.home, self.rev)["phase"], "rolled_back")
        self.assertTrue(guard.preflight(self.home, self.source, self.rev)["historical_reentry"])
        result = guard.activate(self.home, self.source, self.rev, self.artifact)
        self.assertEqual(result["phase"], "active")
        self.assertEqual(guard.items(guard.release_path(self.home, self.rev)), original)
        self.assertEqual(guard.rollback(self.home, self.rev)["phase"], "rolled_back")
        self.stable_same()

    def test_02_reinstall_uses_verified_old_bits_not_new_stage_rebuild(self):
        guard.activate(self.home, self.source, self.rev, self.artifact)
        guard.rollback(self.home, self.rev)
        expected = guard.items(guard.release_path(self.home, self.rev))
        (self.artifact / "bin/kaffeine").write_bytes(b"NONREPRODUCIBLE TEMP REBUILD")
        guard.activate(self.home, self.source, self.rev, self.artifact)
        self.assertEqual(guard.items(guard.release_path(self.home, self.rev)), expected)
        self.stable_same()

    def test_03_hash_tamper_after_rollback_is_manual_hold(self):
        guard.activate(self.home, self.source, self.rev, self.artifact)
        guard.rollback(self.home, self.rev)
        foreign = guard.release_path(self.home, self.rev) / "my-private-data"
        foreign.write_bytes(b"NEVER DELETE")
        with self.assertRaisesRegex(guard.Hold, "hash mismatch"):
            guard.preflight(self.home, self.source, self.rev)
        self.assertEqual(foreign.read_bytes(), b"NEVER DELETE")
        self.stable_same()

    def test_04_foreign_state_is_not_adopted(self):
        foreign = guard.layout(self.home)["state"] / "unrelated-user"
        foreign.parent.mkdir(parents=True)
        foreign.write_bytes(b"MY UNRELATED DATA")
        with self.assertRaises(guard.Hold):
            guard.preflight(self.home, self.source, self.rev)
        self.assertEqual(foreign.read_bytes(), b"MY UNRELATED DATA")
        self.stable_same()

    def test_05_unknown_release_after_rollback_blocks_reentry(self):
        guard.activate(self.home, self.source, self.rev, self.artifact)
        guard.rollback(self.home, self.rev)
        foreign = guard.layout(self.home)["releases"] / "FOREIGN"
        foreign.mkdir()
        (foreign / "data").write_bytes(b"DO NOT DELETE")
        with self.assertRaises(guard.Hold):
            guard.preflight(self.home, self.source, self.rev)
        self.assertEqual((foreign / "data").read_bytes(), b"DO NOT DELETE")
        self.stable_same()

    def test_06_real_sigkill_after_pending_copy_recover_then_reinstall(self):
        # SIGKILL an isolated Python worker AFTER it durably records
        # 'activating'; no mocks of the termination event or a live app.
        worker = "\n".join((
            "import os,signal,sys",
            "from pathlib import Path",
            "sys.path.insert(0, " + repr(str(ROOT)) + ")",
            "from kaffeine_next import media_standalone_guard as g",
            "original=g.write_journal",
            "def kill(home,sha,record,**kw):",
            "    original(home,sha,record,**kw)",
            "    if record['phase']=='activating':",
            "        os.kill(os.getpid(),signal.SIGKILL)",
            "g.write_journal=kill",
            "g.activate(Path(" + repr(str(self.home)) + "),Path(" +
                repr(str(self.source)) + ")," + repr(self.rev) + ",Path(" +
                repr(str(self.artifact)) + "))",
        ))
        p = subprocess.run([sys.executable, "-c", worker],
                           env={**os.environ, "HOME": str(self.home),
                                "PYTHONDONTWRITEBYTECODE": "1"},
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(p.returncode, -signal.SIGKILL, p.stderr)
        self.assertEqual(guard.journal(self.home, self.rev)["phase"], "activating")
        self.assertEqual(guard.rollback(self.home, self.rev)["phase"], "rolled_back")
        self.assertTrue(guard.preflight(self.home, self.source, self.rev)["historical_reentry"])
        self.assertEqual(guard.activate(self.home, self.source, self.rev,
                                        self.artifact)["phase"], "active")
        self.stable_same()

    def test_07_competing_independent_processes_fail_closed_and_unlock_after_kill(self):
        worker = "\n".join((
            "import os,sys,time",
            "from pathlib import Path",
            "sys.path.insert(0, " + repr(str(ROOT)) + ")",
            "from kaffeine_next import media_standalone_guard as g",
            "with g.owner_transaction_lock(Path(" + repr(str(self.home)) + ")):",
            "    print('LOCKED',flush=True)",
            "    time.sleep(15)",
        ))
        child = subprocess.Popen([sys.executable, "-c", worker],
                                 env={**os.environ, "HOME": str(self.home)},
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "LOCKED")
            with self.assertRaisesRegex(guard.Hold, "Competing"):
                guard.activate(self.home, self.source, self.rev, self.artifact)
            self.assertFalse(guard.layout(self.home)["active"].exists())
        finally:
            child.kill()
            child.communicate(timeout=5)
        self.assertEqual(guard.activate(self.home, self.source, self.rev,
                                        self.artifact)["phase"], "active")
        self.stable_same()

    def test_08_symlinked_lock_fails_closed_without_overwrite(self):
        parent = self.home / ".local/opt"
        parent.mkdir(parents=True, exist_ok=True)
        lock = parent / guard.LOCK_NAME
        owner = self.home / "OWNER-LOCK-DATA"
        owner.write_bytes(b"PRIVATE LOCK TARGET")
        lock.symlink_to(owner)
        with self.assertRaises((guard.Hold, OSError)):
            guard.activate(self.home, self.source, self.rev, self.artifact)
        self.assertEqual(owner.read_bytes(), b"PRIVATE LOCK TARGET")
        self.stable_same()

    def test_09_hardlinked_or_permissive_lock_refused(self):
        parent = self.home / ".local/opt"
        parent.mkdir(parents=True, exist_ok=True)
        lock = parent / guard.LOCK_NAME
        lock.write_bytes(b"foreign")
        lock.chmod(0o644)
        with self.assertRaises(guard.Hold):
            with guard.owner_transaction_lock(self.home):
                pass
        lock.chmod(0o600)
        link = self.home / "other-hardlink"
        os.link(lock, link)
        with self.assertRaises(guard.Hold):
            with guard.owner_transaction_lock(self.home):
                pass
        self.assertEqual(link.read_bytes(), b"foreign")
        self.stable_same()

    def test_10_guarded_script_is_restricted_to_exact_installer(self):
        script = SHELL.read_text()
        self.assertIn("guarded-script --source", script)
        self.assertIn('TIHULU_MEDIA_TRANSACTION_FD', script)
        self.assertIn('pass_fds=(fd,)', (ROOT / "kaffeine_next/media_standalone_guard.py").read_text())
        self.assertNotIn("sudo apt-get", script)
        self.stable_same()

    def test_11_interrupted_journal_foreign_bytes_refuse_reinstall(self):
        guard.activate(self.home, self.source, self.rev, self.artifact)
        guard.rollback(self.home, self.rev)
        foreign = guard.journal_path(self.home, self.rev).parent / "keep.bin"
        foreign.write_bytes(b"OWNER UNKNOWN JOURNAL DATA")
        with self.assertRaises(guard.Hold):
            guard.preflight(self.home, self.source, self.rev)
        self.assertEqual(foreign.read_bytes(), b"OWNER UNKNOWN JOURNAL DATA")
        self.stable_same()


    def test_17_real_outer_guard_holds_fd_through_shell_and_python_child(self):
        # Two exec boundaries: Python guard -> Bash -> nested Python.
        script = self.source / "kaffeine_next/media_standalone_install.sh"
        script.write_text(
            "#!/bin/bash\nset -eu\n/usr/bin/python3 - <<'END_PY'\n"
            "import os,sys,time\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, " + repr(str(ROOT)) + ")\n"
            "from kaffeine_next import media_standalone_guard as g\n"
            "with g.owner_transaction_lock(Path.home()) as fd:\n"
            "    assert fd == int(os.environ['TIHULU_MEDIA_TRANSACTION_FD'])\n"
            "    print('INHERITED_LOCK_OK',flush=True)\n"
            "    time.sleep(1.2)\n"
            "END_PY\n")
        from test_stand_media_qa05_coexistence import git
        git(self.source, "add", ".")
        git(self.source, "commit", "-qm", "Explicit disposable guarded installer")
        self.rev = git(self.source, "rev-parse", "HEAD")
        command = [sys.executable, str(ROOT / "kaffeine_next/media_standalone_guard.py"),
                   "guarded-script", "--source", str(self.source),
                   "--sha", self.rev, "--script", str(script)]
        child = subprocess.Popen(command,
                                 env={**os.environ, "HOME": str(self.home),
                                      "PYTHONPATH": str(ROOT),
                                      "PYTHONDONTWRITEBYTECODE": "1"},
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "INHERITED_LOCK_OK")
            with self.assertRaisesRegex(guard.Hold, "Competing"):
                with guard.owner_transaction_lock(self.home):
                    pass
            out, err = child.communicate(timeout=8)
            self.assertEqual(child.returncode, 0, err)
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=5)
        with guard.owner_transaction_lock(self.home):
            pass
        self.stable_same()


class NativePackagingContracts(unittest.TestCase):
    def test_12_native_diagnostics_menu_invokes_real_installed_public_wrapper(self):
        patcher = PATCHER.read_text()
        self.assertIn('QStringList() << QLatin1String("--diagnose-tuner")', patcher)
        self.assertIn('QLatin1String("/.local/bin/tihulu-media-standalone")', patcher)
        self.assertNotIn('/.local/share/tihulu-media-standalone/native/dvb_diagnostics.sh',patcher)
        src = SHELL.read_text()
        with tempfile.TemporaryDirectory(prefix="stand-diag-") as root:
            home = Path(root)
            setup = heredoc(src,"LAUNCH")
            launcher = home / ".local/bin/tihulu-media-standalone"
            launcher.parent.mkdir(parents=True)
            launcher.write_text(setup)
            launcher.chmod(0o700)
            diag = home / ".local/opt/tihulu-media-standalone/current/aux/dvb_diagnostics.sh"
            diag.parent.mkdir(parents=True)
            diag.write_text('#!/bin/bash\nprintf "MENU_DIAGNOSTICS_OK\\n"\n')
            diag.chmod(0o700)
            result = subprocess.run(["/bin/sh", str(launcher), "--diagnose-tuner"],
                env={"HOME": str(home), "PATH": "/bin"}, capture_output=True,
                text=True, timeout=6)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("MENU_DIAGNOSTICS_OK", result.stdout)

    def test_13_transport_pipe_names_are_per_native_instance(self):
        src = PATCHER.read_text()
        self.assertIn('tihulu-standalone-dvbpipe-', src)
        self.assertIn('QUuid::createUuid()', src)
        self.assertIn('QCoreApplication::applicationPid()', src)
        self.assertIn('QLatin1String(".m2t")', src)
        self.assertIn('#include <QUuid>', src)

    def test_14_native_ai_launch_path_is_absolute_not_gui_path(self):
        patcher = PATCHER.read_text()
        radio = RADIO.read_text()
        for source in (patcher, radio):
            self.assertNotIn('startDetached(QLatin1String("tihulu-media-standalone-cli")',source)
            self.assertIn('QLatin1String("/.local/bin/tihulu-media-standalone-cli")',source)

    def test_15_packaged_welle_overrides_external_env_and_no_sudo(self):
        src = SHELL.read_text()
        aux = heredoc(src,"SAFE_WELLE")
        self.assertIn("export TIHULU_MEDIA_STANDALONE=1", aux)
        with tempfile.TemporaryDirectory(prefix="stand-welle-") as root:
            home = Path(root)
            wrapper = home / "aux/install_welle.sh"
            wrapper.parent.mkdir()
            wrapper.write_text(aux)
            original = home / ".local/opt/tihulu-media-standalone/current/share/kaffeine_next/install_welle.sh"
            original.parent.mkdir(parents=True)
            original.write_text('#!/bin/bash\nprintf "%s\\n" "$TIHULU_MEDIA_STANDALONE" > "$HOME/welle-mode"\n')
            result = subprocess.run(["/bin/bash",str(wrapper)],
                env={"HOME": str(home), "PATH": "/bin",
                     "TIHULU_MEDIA_STANDALONE":"0"},
                capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((home / "welle-mode").read_text(),"1\n")

    def test_18_installed_source_welle_cannot_sudo_without_env(self):
        source = (ROOT / "kaffeine_next/install_welle.sh").read_text()
        with tempfile.TemporaryDirectory(prefix="stand-welle-source-") as root:
            home = Path(root)
            installed = (home / ".local/opt/tihulu-media-standalone/releases"
                         / "r2-test/share/kaffeine_next/install_welle.sh")
            installed.parent.mkdir(parents=True)
            installed.write_text(source)
            fakebin = home / "fakebin"
            fakebin.mkdir()
            sudo = fakebin / "sudo"
            sudo.write_text('#!/bin/sh\nprintf "SUDO_ENTERED" > "$HOME/sudo-invoked"\nexit 98\n')
            sudo.chmod(0o700)
            git = fakebin / "git"
            git.write_text("#!/bin/sh\nexit 47\n")
            git.chmod(0o700)
            proc = subprocess.run(["/bin/bash", str(installed)],
                env={"HOME": str(home), "PATH": str(fakebin) + ":/usr/bin:/bin",
                     "TIHULU_MEDIA_STANDALONE": "0"},
                cwd=root, capture_output=True, text=True, timeout=10)
            self.assertEqual(proc.returncode, 47, proc.stderr)
            self.assertFalse((home / "sudo-invoked").exists())
            self.assertTrue((home / ".local/share/tihulu-media-standalone/welle").is_dir())
            self.assertFalse((home / ".local/share/tihulu-media-center/welle").exists())


    def test_16_ai_companion_executes_with_minimal_path_and_standalone_env(self):
        src = SHELL.read_text()
        cli = heredoc(src,"CLI")
        with tempfile.TemporaryDirectory(prefix="stand-minimal-") as root:
            home = Path(root)
            public = home / ".local/bin/tihulu-media-standalone-cli"
            public.parent.mkdir(parents=True)
            public.write_text(cli)
            public.chmod(0o700)
            pkg = home / ".local/opt/tihulu-media-standalone/current/share/tv_center"
            pkg.mkdir(parents=True)
            (pkg / "__init__.py").write_text("")
            (pkg / "__main__.py").write_text(
                'import os,sys\n'
                'print("COMPANION_OK",os.getenv("TIHULU_MEDIA_STANDALONE"),sys.argv[1:])\n')
            result = subprocess.run(["/bin/sh",str(public),"ai-market"],
                env={"HOME":str(home),"PATH":"/bin","PYTHONPATH":""},
                capture_output=True,text=True,timeout=6)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("COMPANION_OK 1 ['ai-market']",result.stdout)


if __name__ == "__main__":
    unittest.main()
