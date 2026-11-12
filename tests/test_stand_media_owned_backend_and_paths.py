"""STAND-MEDIA independent storage and backend contracts, no RF or models.

These tests use isolated temporary homes and deterministic fake model data.
Original STAND #105 assertions remain unchanged in their separate copied file.
"""
from __future__ import annotations
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock
import json
import os
import tempfile
import unittest

from tv_center.ai_settings import AISettings
from tv_center.media_paths_cli import main as paths_cli
from tv_center.media_backend.languages import LANGUAGES, validate_language
from tv_center.media_backend.compute import choose_backend
from tv_center.media_backend.database import MediaTranscriptStore
from tv_center.media_backend.transcripts import TranscriptStore
from tv_center.paths import media_paths, discover_legacy


class MediaOwnedPathsAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tihulu-media-stand-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.home_patch = mock.patch("pathlib.Path.home", return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)
        self.xdg_patch = mock.patch.dict(os.environ, {
            "XDG_CONFIG_HOME": str(self.home / "config"),
            "XDG_DATA_HOME": str(self.home / "data"),
            "XDG_CACHE_HOME": str(self.home / "cache"),
            "XDG_STATE_HOME": str(self.home / "state"),
            "XDG_RUNTIME_DIR": str(self.home / "runtime"),
        })
        self.xdg_patch.start()
        self.addCleanup(self.xdg_patch.stop)

    def test_fresh_import_and_paths_create_nothing(self):
        root = media_paths()
        self.assertEqual(root.config, self.home / "config/tihulu-media-center")
        self.assertEqual(root.models, self.home / "data/tihulu-media-center/models")
        self.assertEqual(root.cache, self.home / "cache/tihulu-media-center")
        self.assertEqual(root.runtime, self.home / "runtime/tihulu-media-center")
        self.assertFalse((self.home / "data").exists())
        self.assertFalse((self.home / "config").exists())

    def test_old_weights_and_settings_are_discovered_but_never_opened_or_migrated(self):
        old = self.home / ".config/tihulu-tv-center/ai-settings.json"
        old.parent.mkdir(parents=True)
        secret = "legacy-should-not-be-read"
        old.write_text(secret, encoding="utf-8")
        foreign = self.home / ".local/share/tihulu-tv-center/models"
        foreign.parent.mkdir(parents=True)
        foreign.symlink_to(self.home / "do-not-follow")
        expected = old.read_bytes()
        found = discover_legacy()
        self.assertEqual(old.read_bytes(), expected)
        self.assertEqual(len(found), 2)
        self.assertEqual([x["type"] for x in found], ["file", "symlink"])
        self.assertIn("skip", found[1]["action"])
        self.assertNotIn(secret, json.dumps(found))
        self.assertFalse(media_paths().ai_settings.exists())

    def test_symlinked_legacy_parent_is_never_traversed(self):
        foreign = self.home / "foreign-configuration"
        foreign.mkdir()
        (foreign / "ai-settings.json").write_text(
            "confidential; must not be read", encoding="utf-8")
        (self.home / ".config").mkdir()
        (self.home / ".config/tihulu-tv-center").symlink_to(
            foreign, target_is_directory=True)
        results = discover_legacy()
        blocked = [x for x in results if x["path"].endswith("ai-settings.json")]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["type"], "symlink-parent")
        self.assertIn("skip", blocked[0]["action"])
        self.assertNotIn("confidential", json.dumps(results))
        self.assertFalse(media_paths().ai_settings.exists())

    def test_explicit_configurable_model_cache_recording_roots_preserve_legacy(self):
        old = self.home / ".config/tihulu-tv-center/ai-settings.json"
        old.parent.mkdir(parents=True)
        old.write_text('{"sentinel":"immutable"}', encoding="utf-8")
        config = AISettings()
        self.assertFalse(config.path.exists())
        config.update({
            "model_dir": str(self.home / "external-ssd/whisper"),
            "recording_dir": str(self.home / "recordings"),
            "cache_dir": str(self.home / "subtitle-cache"),
        })
        self.assertTrue(config.path.exists())
        self.assertIn("external-ssd/whisper",
                      json.dumps(AISettings().values))
        self.assertEqual(old.read_text(), '{"sentinel":"immutable"}')
        self.assertFalse((self.home / "external-ssd").exists())
        self.assertEqual(media_paths().recordings_root(config.values["recording_dir"]),
                         self.home / "recordings")

    def test_cli_preview_reads_only_metadata_and_never_logs_secrets(self):
        old = self.home / ".config/tihulu-tv-center/remote-gpu-token"
        old.parent.mkdir(parents=True)
        old.write_text("MY-PRIVATE-TOKEN", encoding="utf-8")
        target = self.home / "models"
        out = StringIO()
        with redirect_stdout(out):
            result = paths_cli(["--discover-legacy", "--set-model-dir", str(target)])
        self.assertEqual(result, 0)
        state = json.loads(out.getvalue())
        self.assertTrue(state["wrote_settings"])
        self.assertFalse(state["legacy_auto_migrated"])
        self.assertEqual(state["models"], str(target))
        self.assertNotIn("MY-PRIVATE-TOKEN", out.getvalue())
        self.assertEqual(old.read_text(), "MY-PRIVATE-TOKEN")
        self.assertFalse(target.exists())

    def test_reject_symlink_and_relative_storage_destinations(self):
        real = self.home / "real"
        real.mkdir()
        link = self.home / "custom"
        link.symlink_to(real, target_is_directory=True)
        for candidate in (str(link), "relative/cache", "/"):
            with self.subTest(candidate=candidate), redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit) as error:
                    paths_cli(["--set-cache-dir", candidate])
                self.assertNotEqual(error.exception.code, 0)
        self.assertFalse(media_paths().ai_settings.exists())


class MediaBackendAcceptance(unittest.TestCase):
    def test_language_and_backend_selection_stays_truthful_without_models(self):
        self.assertIn("tr", LANGUAGES)
        self.assertGreaterEqual(len(LANGUAGES), 100)
        self.assertEqual(validate_language("de"), "de")
        self.assertRaises(ValueError, validate_language, "xx-NOT-IN-WHISPER")
        profile = {
            "devices": [{"id": "cpu", "detected": True, "name": "CPU"},
                        {"id": "gpu", "detected": True, "name": "CUDA"},
                        {"id": "npu", "detected": False, "name": "NPU"}],
            "speech": {"ready_cpu": False, "ready_gpu": False, "ready_npu": False},
        }
        choice = choose_backend(profile)
        self.assertEqual(choice["selected"], "cpu")
        self.assertFalse(choice["ready"])
        self.assertIn("No compatible", choice["reason"])

    def test_media_only_transcript_store_and_srt_do_not_touch_text_database(self):
        with tempfile.TemporaryDirectory() as root:
            db = Path(root) / "media-only.sqlite3"
            self.assertFalse(db.exists())
            captions = TranscriptStore(MediaTranscriptStore(db))
            session = "0" * 32
            key = captions.add(
                session=session, medium="dvb_tv", source_id="DVB-586",
                language="de", text="Guten Tag", backend="cpu",
                start=1.5, end=3.25)
            self.assertEqual(len(key), 32)
            self.assertEqual(captions.list(session)[0]["original_text"], "Guten Tag")
            subtitle = captions.export(session, fmt="srt")
            self.assertIn("00:00:01,500 --> 00:00:03,250", subtitle)
            self.assertIn("Guten Tag", subtitle)
            self.assertEqual(captions.export(session, fmt="vtt").splitlines()[0], "WEBVTT")
            import sqlite3
            with sqlite3.connect(db) as connection:
                tables = {r[0] for r in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("captions", tables)
            self.assertNotIn("feeds", tables)
            self.assertNotIn("pages", tables)


if __name__ == "__main__":
    unittest.main()
