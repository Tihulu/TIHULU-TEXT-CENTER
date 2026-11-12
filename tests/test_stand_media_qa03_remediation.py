"""QA-03 remediation: no hardware, models, downloads or real installations.

All Git trees, foreign files, staged .deb bytes and rollback transactions use
temporary directories. Original #105 strict tests are preserved separately.
"""
import ast
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from kaffeine_next import media_install_guard as guard
from tv_center.media_backend.database import clean_text, MediaTranscriptStore
from tv_center.media_backend.transcripts import TranscriptStore
from tv_center.media_backend import speech
from tv_center.media_paths_cli import main as media_paths_main
from tv_center.model_market import ModelLibrary, ModelError, argos_remove
from tv_center.paths import media_paths

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "kaffeine_next/captions_overlay.py"


def git(*args, cwd):
    proc = subprocess.run(["git", *args], cwd=cwd, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=10, check=True)
    return proc.stdout.strip()


class NativeModelMarketButton(unittest.TestCase):
    def test_button_launches_real_new_companion_without_text_center(self):
        source = SOURCE.read_text(encoding="utf-8")
        matches = [n for n in ast.walk(ast.parse(source))
                   if isinstance(n, ast.FunctionDef) and n.name == "launch_market"]
        self.assertEqual(len(matches), 1)
        local = {}
        exec(compile(ast.Module(body=[matches[0]], type_ignores=[]),
                     str(SOURCE), "exec"), local)
        with patch("subprocess.Popen") as popen:
            local["launch_market"]()
        popen.assert_called_once_with(
            ["tihulu-media-cli", "ai-market"], close_fds=True)
        self.assertNotIn('["tihulu-tv-center","ai-market"]', source)

    def test_clean_debian_package_ships_exact_executable_for_button(self):
        if not shutil.which("dpkg-deb"):
            self.skipTest("Debian artifact test requires dpkg-deb")
        with tempfile.TemporaryDirectory(prefix="media-pkg-qa03-") as d:
            out, unpack = Path(d)/"packages", Path(d)/"installed"
            subprocess.run(["bash", str(ROOT/"tv_center/packaging/build-deb.sh"),
                            str(out)], capture_output=True, text=True,
                           check=True, timeout=25)
            packages = list(out.glob("tihulu-media-center-ai_*.deb"))
            self.assertEqual(len(packages), 1)
            subprocess.run(["dpkg-deb", "-x", str(packages[0]), str(unpack)],
                           capture_output=True, check=True, timeout=25)
            binary = unpack/"usr/bin/tihulu-media-cli"
            self.assertTrue(binary.is_file())
            self.assertTrue(os.access(binary, os.X_OK))
            self.assertEqual(shutil.which("tihulu-media-cli",
                                           path=str(binary.parent)), str(binary))
            self.assertFalse((unpack/"usr/bin/tihulu-tv-center").exists())
            self.assertFalse((unpack/"usr/share/tihulu-media-center/textcenter").exists())
            self.assertIn('exec "$PYTHON" -m tv_center "$@"',
                          binary.read_text(encoding="utf-8"))


class FakeInstallerTransaction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="media-qa03-home-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root/"home"
        self.home.mkdir()
        self.source = self.root/"repo"
        (self.source/"tv_center").mkdir(parents=True)
        (self.source/"kaffeine_next").mkdir(parents=True)
        (self.source/"tv_center/__main__.py").write_text("pass\n")
        (self.source/"kaffeine_next/patch_upstream.py").write_text("pass\n")
        shutil.copyfile(ROOT/"kaffeine_next/media_install_guard.py",
                        self.source/"kaffeine_next/media_install_guard.py")
        shutil.copyfile(ROOT/"kaffeine_next/install.sh",
                        self.source/"kaffeine_next/install.sh")
        git("init", "-q", cwd=self.source)
        git("config", "user.name", "CI Synthetic", cwd=self.source)
        git("config", "user.email", "nobody@example.invalid", cwd=self.source)
        git("add", ".", cwd=self.source)
        git("commit", "-qm", "synthetic owned source", cwd=self.source)
        self.sha = git("rev-parse", "HEAD", cwd=self.source)
        self.patch_pkg = patch.object(guard, "package_version", return_value="")
        self.patch_pkg.start()
        self.addCleanup(self.patch_pkg.stop)

    def make_owned_launcher(self):
        p = guard.paths(self.home)
        p["launch"].parent.mkdir(parents=True)
        p["base"].mkdir(parents=True)
        p["launch"].write_bytes(b"MEDIA-LAUNCHER-OWNED\n")
        p["launch_mark"].write_text(guard.sha(p["launch"]) + "\n")
        return p

    def new_release(self):
        path = self.home/".local/opt/tihulu-media-center/releases"/self.sha[:12]
        path.mkdir(parents=True)
        (path/".tihulu-media-owned-release").write_text(self.sha + "\n")
        (path/"bin").mkdir()
        (path/"bin/tihulu-media-center").write_bytes(b"fake-owned-native-binary")
        return path

    def test_dry_run_complete_and_read_only(self):
        before = set(self.home.rglob("*"))
        status = guard.preflight(self.home, self.source, self.sha)
        self.assertTrue(status["dry_run"])
        self.assertIn("APT build dependencies", " ".join(status["steps"]))
        self.assertEqual(before, set(self.home.rglob("*")))

    def test_shell_dry_run_skips_sudo_and_has_no_home_writes(self):
        if os.geteuid() == 0:
            self.skipTest("Desktop installer refuses root by design")
        fake_bin = self.root/"fakes"
        fake_bin.mkdir()
        sentinel = self.root/"sudo-called"
        (fake_bin/"sudo").write_text("#!/bin/sh\ntouch " + str(sentinel) + "\nexit 5\n")
        (fake_bin/"sudo").chmod(0o700)
        env = {**os.environ, "HOME": str(self.home),
               "TIHULU_MEDIA_SOURCE_DIR": str(self.source),
               "TIHULU_MEDIA_SOURCE_SHA": self.sha,
               "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]}
        result = subprocess.run(["bash", str(self.source/"kaffeine_next/install.sh"),
                                 "--dry-run", "--with-dab"], cwd=self.source,
                                env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["optional"]["dab"])
        self.assertFalse(sentinel.exists())
        self.assertEqual(list(self.home.rglob("*")), [])

    def test_refuse_foreign_regular_alias_with_valid_other_owned_launcher(self):
        p = self.make_owned_launcher()
        p["alias"].write_bytes(b"FOREIGN REGULAR LAUNCHER KEEP EVERY BYTE")
        original = p["alias"].read_bytes()
        before = hashlib.sha256(original).hexdigest()
        with self.assertRaisesRegex(guard.GuardError, "Foreign regular file"):
            guard.preflight(self.home, self.source, self.sha)
        self.assertEqual(p["alias"].read_bytes(), original)
        self.assertEqual(guard.sha(p["alias"]), before)

    def test_refuse_foreign_symlink_and_missing_per_alias_marker(self):
        p = self.make_owned_launcher()
        p["alias"].symlink_to("foreign-application")
        with self.assertRaises(guard.GuardError):
            guard.preflight(self.home, self.source, self.sha)
        self.assertEqual(os.readlink(p["alias"]), "foreign-application")
        p["alias"].unlink()
        p["alias"].symlink_to("tihulu-kaffeine")
        with self.assertRaisesRegex(guard.GuardError, "Unowned"):
            guard.preflight(self.home, self.source, self.sha)

    def test_reject_symlink_parent_before_any_asset_mutation(self):
        foreign = self.root/"foreign-bin"
        foreign.mkdir()
        (self.home/".local").mkdir()
        (self.home/".local/bin").symlink_to(foreign)
        (foreign/"tihulu-media-center").write_bytes(b"FOREIGN")
        with self.assertRaisesRegex(guard.GuardError, "parent"):
            guard.preflight(self.home, self.source, self.sha)
        self.assertEqual((foreign/"tihulu-media-center").read_bytes(), b"FOREIGN")

    def test_git_head_match_does_not_authorize_dirty_source(self):
        dirty = self.source/"untracked.cpp"
        dirty.write_text("unreviewed source")
        with self.assertRaisesRegex(guard.GuardError, "Dirty"):
            guard.preflight(self.home, self.source, self.sha)
        dirty.unlink()
        tracked = self.source/"tv_center/__main__.py"
        tracked.write_text("uncommitted change")
        with self.assertRaisesRegex(guard.GuardError, "Dirty"):
            guard.preflight(self.home, self.source, self.sha)

    def test_first_owned_activation_and_rollback_without_other_app_cleanup(self):
        release = self.new_release()
        foreign = self.home/"my-recordings/old.mkv"
        foreign.parent.mkdir()
        foreign.write_bytes(b"USER RECORDING IMMUTABLE")
        snap = guard.snapshot(self.home, self.source, self.sha)
        self.assertEqual(snap["phase"], "snapshot")
        launched = self.root/"new-launcher"
        launched.write_bytes(b"#!/bin/sh\nexit 0\n")
        desktop = self.root/"new.desktop"
        desktop.write_bytes(b"[Desktop Entry]\nExec=tihulu-media-center\n")
        companion = self.root/"fake-deb"
        companion.write_bytes(b"TEST PACKAGE NO INSTALL")
        state = guard.activate(self.home, self.sha, launched, desktop,
                               release, companion)
        self.assertEqual(state["phase"], "active")
        self.assertEqual(guard.paths(self.home)["alias"].readlink(), Path("tihulu-kaffeine"))
        self.assertEqual(guard.rollback_plan(self.home, self.sha)["package_action"],
                         "remove")
        guard.rollback_files(self.home, self.sha)
        self.assertEqual(foreign.read_bytes(), b"USER RECORDING IMMUTABLE")
        self.assertFalse(guard.paths(self.home)["launch"].exists())
        self.assertFalse(guard.paths(self.home)["alias"].is_symlink())
        self.assertFalse(guard.paths(self.home)["current"].is_symlink())

    def test_restore_previous_verified_media_release_exactly(self):
        p = self.make_owned_launcher()
        p["desktop"].parent.mkdir(parents=True)
        p["desktop"].write_bytes(b"OWNED DESKTOP BEFORE")
        p["desktop_mark"].write_text(guard.sha(p["desktop"]) + "\n")
        p["alias"].symlink_to("tihulu-kaffeine")
        p["alias_mark"].write_text("tihulu-kaffeine\n")
        old_sha = "a" * 40
        old = self.home/".local/opt/tihulu-media-center/releases"/old_sha[:12]
        old.mkdir(parents=True)
        (old/".tihulu-media-owned-release").write_text(old_sha)
        (old/"companion.deb").write_bytes(b"OLD PACKAGE")
        (old/".tihulu-media-companion.sha256").write_text(
            guard.sha(old/"companion.deb"))
        p["current"].symlink_to(old)
        original = (p["launch"].read_bytes(), p["desktop"].read_bytes())
        self.patch_pkg.stop()
        self.patch_pkg = patch.object(guard, "package_version", return_value="0.1.0-old")
        self.patch_pkg.start()
        new = self.new_release()
        guard.snapshot(self.home, self.source, self.sha)
        launcher, desktop, deb = (self.root/x for x in ("launcher", "desktop", "package"))
        launcher.write_bytes(b"NEW OWNED LAUNCH")
        desktop.write_bytes(b"NEW OWNED DESKTOP")
        deb.write_bytes(b"NEW PACKAGE")
        guard.activate(self.home, self.sha, launcher, desktop, new, deb)
        plan = guard.rollback_plan(self.home, self.sha)
        self.assertEqual(plan["package_action"], "restore")
        self.assertEqual(plan["previous_deb"], str(old/"companion.deb"))
        guard.rollback_files(self.home, self.sha)
        self.assertEqual(p["launch"].read_bytes(), original[0])
        self.assertEqual(p["desktop"].read_bytes(), original[1])
        self.assertEqual(os.readlink(p["current"]), str(old))
        self.assertEqual((old/"companion.deb").read_bytes(), b"OLD PACKAGE")

    def test_changed_after_activation_is_preserved_on_rollback(self):
        release = self.new_release()
        guard.snapshot(self.home, self.source, self.sha)
        launcher, desktop, deb = (self.root/x for x in ("launch", "desktop", "deb"))
        for x in (launcher, desktop, deb):
            x.write_bytes(b"APP OWNED STAGED FILE")
        guard.activate(self.home, self.sha, launcher, desktop, release, deb)
        path = guard.paths(self.home)["launch"]
        path.write_bytes(b"FOREIGN REPLACEMENT")
        with self.assertRaisesRegex(guard.GuardError, "User-modified"):
            guard.rollback_files(self.home, self.sha)
        self.assertEqual(path.read_bytes(), b"FOREIGN REPLACEMENT")


class MultilingualTranscriptGolden(unittest.TestCase):
    def test_whitespace_matches_original_transcript_core_contract(self):
        vectors = [
            ("tr", "  İyi\t\tgünler \r\n  nasılsınız\u00a0? ",
             "İyi günler nasılsınız ?"),
            ("de", "\nGuten  \t Tag\r\n   Grüße  \n", "Guten Tag Grüße"),
            ("en", "Hello \t world\n from \r\n Media", "Hello world from Media"),
            ("tr", r"arka\splan  metin", r"arka\splan metin"),
        ]
        for language, text, expected in vectors:
            with self.subTest(language=language, raw=text):
                self.assertEqual(clean_text(text, 3000), expected)
        self.assertEqual(clean_text(None), "")
        self.assertEqual(clean_text(123), "")
        self.assertEqual(clean_text("  X   Y ", 2), "X ")

    def test_multilingual_database_export_and_delayed_translation_golden(self):
        vectors = [("tr", "İyi \t akşamlar\n  Dünya", "İyi akşamlar Dünya"),
                   ("de", "Hallo \n  schöne  Welt", "Hallo schöne Welt"),
                   ("en", "Good \t morning\r\n friend", "Good morning friend")]
        for code, raw, expected in vectors:
            with self.subTest(source=code), tempfile.TemporaryDirectory() as tmp:
                store = TranscriptStore(MediaTranscriptStore(Path(tmp)/"cues.sqlite3"))
                session = "0" * 32
                key = store.add(session=session, medium="dvb_tv", source_id="TV-01",
                                language=code, text=raw, backend="cpu",
                                start=1.25, end=2.75)
                self.assertEqual(store.list(session)[0]["original_text"], expected)
                self.assertIn("00:00:01,250 --> 00:00:02,750",
                              store.export(session, fmt="srt"))
                self.assertIn(expected, store.export(session, fmt="vtt"))
                def mock_translator(value, original, target):
                    self.assertEqual(value, expected)
                    self.assertEqual(original, code)
                    self.assertEqual(target, "fr")
                    return "  Bonjour  \t le \n monde "
                updated = store.translate_later(key, "fr", translator=mock_translator)
                self.assertEqual(updated["translated_text"], "Bonjour le monde")
                self.assertIn("Bonjour le monde", store.export(session, translated=True))


class BorrowedModelAndGpuSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="media-model-owned-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.homemock = patch("pathlib.Path.home", return_value=self.home)
        self.homemock.start()
        self.addCleanup(self.homemock.stop)
        self.dataenv = patch.dict(os.environ, {"XDG_DATA_HOME": str(self.home/"data")})
        self.dataenv.start()
        self.addCleanup(self.dataenv.stop)

    def test_external_ssd_model_is_readable_but_not_deletable(self):
        external = self.home/"external-ssd/models"
        external.mkdir(parents=True)
        data = external/"ggml-tiny.bin"
        data.write_bytes(b"BORROWED")
        lib = ModelLibrary(external)
        with self.assertRaises(ModelError):
            lib.remove("tiny")
        self.assertEqual(data.read_bytes(), b"BORROWED")

    def test_unmarked_media_model_not_deletable_but_owned_verified_copy_can_be(self):
        root = media_paths().models
        lib = ModelLibrary(root)
        original = root/"ggml-tiny.bin"
        original.write_bytes(b"BORROWED")
        with self.assertRaisesRegex(ModelError, "unmarked"):
            lib.remove("tiny")
        self.assertEqual(original.read_bytes(), b"BORROWED")
        original.unlink()
        candidate = self.home/"verified.bin"
        candidate.write_bytes(b"VERIFIED")
        lib.catalog["tiny"] = {**lib.catalog["tiny"],
                               "sha256": hashlib.sha256(b"VERIFIED").hexdigest(),
                               "max_bytes": 1000}
        lib.add_local("tiny", candidate)
        self.assertTrue(lib._receipt("tiny").is_file())
        lib.remove("tiny")
        self.assertEqual(candidate.read_bytes(), b"VERIFIED")
        self.assertFalse(original.exists())

    def test_argos_uninstall_never_uses_home_as_proof_of_ownership(self):
        shared = self.home/"shared-argos/de_en"
        shared.mkdir(parents=True)
        entry = SimpleNamespace(from_code="de", to_code="en", package_path=str(shared))
        fake_pkg = ModuleType("argostranslate.package")
        fake_pkg.get_installed_packages = lambda: [entry]
        fake_pkg.uninstall = Mock()
        fake_mod = ModuleType("argostranslate")
        fake_mod.package = fake_pkg
        with patch.dict(sys.modules, {
            "argostranslate": fake_mod, "argostranslate.package": fake_pkg,
        }):
            with self.assertRaisesRegex(ModelError, "Borrowed"):
                argos_remove("de", "en")
        fake_pkg.uninstall.assert_not_called()
        self.assertTrue(shared.exists())

    def test_symlink_parent_rejected_on_storage_change(self):
        root = self.home/"external"
        root.mkdir()
        (self.home/"link").symlink_to(root, target_is_directory=True)
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit):
                media_paths_main(["--set-recording-dir",
                                  str(self.home/"link/nested/recordings")])
        self.assertIn("symlink", stderr.getvalue().lower())

    def test_cuda_cache_cannot_clear_while_owned_inference_lock_held(self):
        fake = ModuleType("faster_whisper")
        fake.WhisperModel = lambda *args, **kwargs: object()
        with patch.dict(sys.modules, {"faster_whisper": fake}):
            speech._cached_cuda_whisper("fake-model-path")
        self.assertEqual(speech._cached_cuda_whisper.cache_info().currsize, 1)
        with speech._faster_whisper_lock:
            with self.assertRaisesRegex(speech.SpeechError, "active"):
                speech.release_owned_speech_caches()
            self.assertEqual(speech._cached_cuda_whisper.cache_info().currsize, 1)
        self.assertTrue(speech.release_owned_speech_caches())
        self.assertEqual(speech._cached_cuda_whisper.cache_info().currsize, 0)


if __name__ == "__main__":
    unittest.main()
