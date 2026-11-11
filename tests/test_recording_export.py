"""Opt-in Recording & Export regression: no RF devices, no Whisper or FFmpeg."""
import json
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tv_center.recording_export import (
    Cue, parse_srt, render, export_tracks, run_export, mux_tracks,
    split_caption_translations,
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
            self.assertEqual(out["timebase"], "srt_cue_seconds")
            self.assertIn("sync unverified", out["clock_source"])
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

    def test_original_and_translation_tracks_do_not_swallow_sound_labels(self):
        cues = [Cue(1, 3, "[Music] spoken words\n[TR] Merhaba\n[DE] Hallo"),
                Cue(4, 7, "[Speaker 1] Welcome\n[TR] Hoş geldiniz")]
        tracks = split_caption_translations(cues)
        self.assertEqual(set(tracks), {"original", "translation-tr", "translation-de"})
        self.assertIn("[Music]", tracks["original"][0].text)
        self.assertIn("[Speaker 1]", tracks["original"][1].text)
        self.assertEqual(tracks["translation-tr"][0].text, "Merhaba")
        self.assertEqual(tracks["translation-tr"][1].start, 4)
        self.assertEqual(tracks["translation-de"][0].text, "Hallo")

    def test_media_only_mux_can_use_separate_timed_language_tracks(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / "record.srt"
            file.write_text("1\n00:00:01,000 --> 00:00:03,000\n"
                            "Good morning\n[TR] Günaydın\n\n")
            media = Path(root) / "record.mkv"
            media.write_bytes(b"immutable input")
            captured = {}
            def mock_mux(src, tracks, destination):
                captured["tracks"] = {
                    label: parse_srt(path) for label, path in tracks.items()
                }
                Path(destination).write_bytes(b"mock joined file")
                return Path(destination)
            with patch("tv_center.recording_export.mux_tracks", side_effect=mock_mux):
                created = run_export(
                    sources={"combined": str(file)}, destination=root,
                    name="result", formats=(), media=media,
                    mode="live", mux=True, split_translations=True)
            self.assertEqual(len(created), 1)
            self.assertEqual(set(captured["tracks"]), {"original", "translation-tr"})
            self.assertEqual(captured["tracks"]["translation-tr"][0].text, "Günaydın")
            self.assertEqual(media.read_bytes(), b"immutable input")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "FFmpeg tools are unavailable")
    def test_real_ffmpeg_mkv_keeps_original_audio_and_timed_srt(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            media = folder / "untouched.wav"
            ffmpeg = subprocess.run([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i",
                "anullsrc=channel_layout=mono:sample_rate=16000",
                "-t", "1.5", "-c:a", "pcm_s16le", str(media),
            ], capture_output=True, text=True, check=False)
            if ffmpeg.returncode:
                self.skipTest("FFmpeg test audio generator unavailable")
            before = media.read_bytes()
            srt = folder / "words.srt"
            srt.write_text("1\\n00:00:00,100 --> 00:00:01,200\\n"
                           "Test speech only\\n\\n", encoding="utf-8")
            destination = folder / "recording-subtitled.mkv"
            mux_tracks(media, {"original": srt}, destination)
            self.assertTrue(destination.is_file())
            self.assertEqual(before, media.read_bytes())
            streams = subprocess.run([
                "ffprobe", "-v", "error", "-show_entries",
                "stream=codec_type", "-of", "json", str(destination),
            ], capture_output=True, text=True, check=True)
            types = {row["codec_type"] for row in
                     json.loads(streams.stdout)["streams"]}
            self.assertEqual(types, {"audio", "subtitle"})

    def test_bad_srt_is_not_given_invented_timing(self):
        with tempfile.TemporaryDirectory() as root:
            f = Path(root) / "bad.srt"
            f.write_text("1\nThis is not timestamped speech\nHello\n")
            with self.assertRaises(ValueError):
                parse_srt(f)


if __name__ == "__main__":
    unittest.main()
