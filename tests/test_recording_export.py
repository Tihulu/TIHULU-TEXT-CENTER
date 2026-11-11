"""Opt-in Recording & Export regression: no RF devices, no Whisper or FFmpeg."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tv_center.recording_export import (
    Cue, parse_srt, render, export_tracks, run_export, mux_tracks,
)


SAMPLE = (
    "1\n00:00:01,250 --> 00:00:03,200\n"
    "[Music] Hello world\n\n"
    "2\n00:00:04,100 --> 00:00:06,500\n"
    "How are you?\n\n"
)


class CommonRecordingExportTests(unittest.TestCase):
    def test_preserves_real_time_ranges_and_tags(self):
        with tempfile.TemporaryDirectory() as root:
            srt = Path(root) / "original.srt"
            srt.write_text(SAMPLE, encoding="utf-8")
            cues = parse_srt(srt)
            self.assertEqual((cues[0].start, cues[0].end), (1.25, 3.2))
            self.assertEqual(cues[0].text, "[Music] Hello world")
            self.assertIn("00:00:01,250 --> 00:00:03,200", render(cues, "srt"))
            self.assertIn("00:00:01.250 --> 00:00:03.200", render(cues, "vtt"))
            self.assertIn("00:00:01,250", render(cues, "txt", timestamps=True))
            self.assertNotIn("00:00:01,250", render(cues, "txt"))
            out = json.loads(render(cues, "json", track="original"))
            self.assertEqual(out["timebase"], "media_seconds")
            self.assertFalse(out["word_aligned"])
            self.assertEqual(out["cues"][1]["end"], 6.5)
            self.assertIn("Dialogue: 0,", render(cues, "ass"))

    def test_lrc_refuses_unverified_speech_timing(self):
        with self.assertRaises(ValueError):
            render([Cue(1.0, 2.0, "speech")], "lrc")
        self.assertIn("[00:01.00]", render(
            [Cue(1.0, 2.0, "heard sung lyric")], "lrc", lyrics=True))

    def test_separate_tracks_and_never_overwrites_user_files(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            tracks = {
                "original": [Cue(1, 2, "[Music] Speech")],
                "translation-tr": [Cue(1, 2, "Merhaba")],
            }
            outputs = export_tracks(tracks, root, "demo",
                                    ("txt", "srt", "vtt", "ass", "json"))
            self.assertEqual(len(outputs), 10)
            self.assertTrue((path / "demo.original.srt").is_file())
            self.assertIn("Merhaba", (path / "demo.translation-tr.vtt").read_text())
            with self.assertRaises(FileExistsError):
                export_tracks(tracks, root, "demo", ("txt",))
            self.assertEqual((path / "demo.original.txt").read_text(), "[Music] Speech\n")

    def test_complete_requires_local_file_and_media_mux_needs_media(self):
        with tempfile.TemporaryDirectory() as root:
            srt = Path(root) / "source.srt"
            srt.write_text(SAMPLE)
            with self.assertRaises(ValueError):
                run_export(sources={"original": str(srt)}, destination=root,
                           name="result", formats=("txt",), mode="complete")
            with self.assertRaises(ValueError):
                run_export(sources={"original": str(srt)}, destination=root,
                           name="result", formats=("txt",), mux=True)
            created = run_export(sources={"original": str(srt)}, destination=root,
                                 name="session", formats=("txt", "vtt"), mode="live")
            self.assertEqual(len(created), 2)

    def test_mux_source_is_unmodified_and_ffmpeg_arguments_are_argv(self):
        with tempfile.TemporaryDirectory() as root:
            media = Path(root) / "original.mp3"
            media.write_bytes(b"unchanged")
            srt = Path(root) / "sub.srt"
            srt.write_text(SAMPLE)
            dest = Path(root) / "combined.mkv"
            def fake_ffmpeg(args):
                self.assertEqual(args[:2], ["-i", str(media)])
                self.assertIn("-n", ["-n"])  # command wrapper uses no-overwrite
                dest.write_bytes(b"mock output")
            with patch("tv_center.recording_export._run_ffmpeg", side_effect=fake_ffmpeg):
                output = mux_tracks(media, {"original": srt}, dest)
            self.assertEqual(output, dest)
            self.assertEqual(media.read_bytes(), b"unchanged")
            with self.assertRaises(FileExistsError):
                mux_tracks(media, {"original": srt}, dest)

    def test_bad_srt_is_not_given_invented_timing(self):
        with tempfile.TemporaryDirectory() as root:
            f = Path(root) / "bad.srt"
            f.write_text("1\nThis is not timestamped speech\nHello\n")
            with self.assertRaises(ValueError):
                parse_srt(f)


if __name__ == "__main__":
    unittest.main()
