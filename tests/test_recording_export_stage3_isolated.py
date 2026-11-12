"""Isolated Media PR #67 export contract tests; synthetic files and mocked tools.

No FFmpeg invocation, Whisper model, network, Qt, SDR or tuner is used.
These tests are not proof of real mux/burn or audio/subtitle synchronization.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tv_center import recording_export as export


VALID_SRT = (
    "1\n00:00:00,100 --> 00:00:01,200\n"
    "[Music] Original speech\n\n"
)


class RecordingExportStage3Tests(unittest.TestCase):
    def test_ffmpeg_argv_enforces_no_overwrite_without_spawning_process(self):
        captured = []
        def fake_run(argv, **kwargs):
            captured.append((list(argv), kwargs))
            return SimpleNamespace(returncode=0, stderr="", stdout="")
        with patch.object(export.subprocess, "run", side_effect=fake_run):
            export._run_ffmpeg(["-i", "fake-input.wav", "fake-output.mkv"])
        self.assertEqual(len(captured), 1)
        argv, kwargs = captured[0]
        self.assertEqual(argv[:5],
                         ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error"])
        self.assertEqual(argv[5:7], ["-n", "-i"])
        self.assertEqual(argv[-2:], ["fake-input.wav", "fake-output.mkv"])
        self.assertFalse(kwargs["check"])
        self.assertTrue(kwargs["capture_output"])

    def test_real_newlines_are_required_not_literal_backslash_n(self):
        with TemporaryDirectory(prefix="tihulu-media-srt-") as work:
            good = Path(work) / "good.srt"
            bad = Path(work) / "bad.srt"
            good.write_text(VALID_SRT, encoding="utf-8")
            bad.write_text(VALID_SRT.replace("\n", r"\n"), encoding="utf-8")
            valid = export.parse_srt(good)
            self.assertEqual((valid[0].start, valid[0].end), (0.1, 1.2))
            with self.assertRaises(ValueError):
                export.parse_srt(bad)

    def test_existing_track_files_remain_identical(self):
        with TemporaryDirectory(prefix="tihulu-media-exclusive-") as work:
            cues = {"original": [export.Cue(1.0, 2.0, "[Music] Keep me")]}
            original = Path(work) / "session.original.srt"
            original.write_bytes(b"pre-existing private content")
            with self.assertRaises(FileExistsError):
                export.export_tracks(cues, work, "session", formats=("txt", "srt"))
            self.assertEqual(original.read_bytes(), b"pre-existing private content")
            self.assertFalse((Path(work) / "session.original.txt").exists())

    def test_mock_mux_preserves_source_and_maps_language_separately(self):
        with TemporaryDirectory(prefix="tihulu-media-mux-") as work:
            source = Path(work) / "input.wav"
            srt = Path(work) / "translation.srt"
            destination = Path(work) / "joined.mkv"
            source.write_bytes(b"synthetic unchanged media")
            srt.write_text(VALID_SRT, encoding="utf-8")
            captured = []
            def fake_ffmpeg(args):
                captured.append(list(args))
            with patch.object(export, "_run_ffmpeg", side_effect=fake_ffmpeg):
                output = export.mux_tracks(source, {"translation-tr": srt}, destination)
            self.assertEqual(output, destination)
            self.assertEqual(source.read_bytes(), b"synthetic unchanged media")
            self.assertEqual(len(captured), 1)
            self.assertIn("-c:s", captured[0])
            self.assertIn("language=tr", captured[0])
            self.assertEqual(captured[0][-1], str(destination))
            self.assertFalse(destination.exists(), "Mock does not create a real MKV")

    def test_export_with_complete_mode_requires_real_media_argument(self):
        with TemporaryDirectory(prefix="tihulu-media-complete-") as work:
            subtitle = Path(work) / "caption.srt"
            subtitle.write_text(VALID_SRT, encoding="utf-8")
            with self.assertRaises(ValueError):
                export.run_export(sources={"original": str(subtitle)}, destination=work,
                                  name="trial", formats=("txt",), mode="complete")
            self.assertEqual(list(Path(work).glob("trial.*")), [])


if __name__ == "__main__":
    unittest.main()
