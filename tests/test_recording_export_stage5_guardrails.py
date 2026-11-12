"""Media #67 export safety characterization — synthetic fixtures only.

All files live in TemporaryDirectory. No actual ffmpeg, ffprobe, audio device,
radio, GPU, video window or user recording is opened. The known expected
failure is an explicit uncorrected incomplete-sidecar cleanup requirement.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tv_center import recording_export as export


SRT = "1\n00:00:00,100 --> 00:00:01,200\n[Music] Original speech\n\n"


class MediaExportStage5Guards(unittest.TestCase):
    def test_racing_second_output_preserves_foreign_file_and_rolls_back_ours(self):
        with TemporaryDirectory(prefix="tihulu-media-race-") as work:
            root = Path(work)
            created_by_someone_else = root / "take.original.srt"
            first_output = root / "take.original.txt"
            original_writer = export._write_new

            def competing_writer(path, data):
                if Path(path) == created_by_someone_else:
                    # Simulate a new file appearing after export's preflight.
                    created_by_someone_else.write_bytes(b"foreign untouched export")
                    raise FileExistsError("race at exclusive-create boundary")
                return original_writer(path, data)

            with patch.object(export, "_write_new", side_effect=competing_writer):
                with self.assertRaisesRegex(FileExistsError, "race"):
                    export.export_tracks(
                        {"original": [export.Cue(0.1, 1.2, "[Music] Original speech")]},
                        root, "take", formats=("txt", "srt"),
                    )
            self.assertFalse(first_output.exists(), "Our partial TXT must roll back")
            self.assertEqual(created_by_someone_else.read_bytes(),
                             b"foreign untouched export")

    def test_ffmpeg_error_after_competing_mkv_creation_does_not_remove_other_file(self):
        with TemporaryDirectory(prefix="tihulu-media-mux-race-") as work:
            root = Path(work)
            media = root / "original.wav"
            subtitle = root / "caption.srt"
            output = root / "safe.mkv"
            media.write_bytes(b"original audio bytes untouched")
            subtitle.write_text(SRT, encoding="utf-8")

            def fake_mux_failure(argv):
                self.assertEqual(argv[-1], str(output))
                output.write_bytes(b"another process's output")
                raise RuntimeError("synthetic ffmpeg cannot take output")

            with patch.object(export, "_run_ffmpeg", side_effect=fake_mux_failure):
                with self.assertRaisesRegex(RuntimeError, "synthetic ffmpeg"):
                    export.mux_tracks(media, {"original": subtitle}, output)
            self.assertEqual(media.read_bytes(), b"original audio bytes untouched")
            self.assertEqual(output.read_bytes(), b"another process's output")
            self.assertEqual(subtitle.read_text(encoding="utf-8"), SRT)

    def test_burn_rejects_audio_only_source_without_spawning_ffmpeg(self):
        with TemporaryDirectory(prefix="tihulu-media-audio-burn-") as work:
            root = Path(work)
            media = root / "audio.wav"
            subtitle = root / "caption.srt"
            output = root / "subtitled.mp4"
            media.write_bytes(b"original audio only")
            subtitle.write_text(SRT, encoding="utf-8")
            with patch.object(export, "_has_video", return_value=False), \
                 patch.object(export, "_run_ffmpeg",
                              side_effect=AssertionError("FFmpeg must not run")):
                with self.assertRaisesRegex(ValueError, "local video"):
                    export.burn_video(media, subtitle, output)
            self.assertFalse(output.exists())
            self.assertEqual(media.read_bytes(), b"original audio only")

    @unittest.expectedFailure
    def test_known_gap_sidecar_is_rolled_back_when_later_mux_fails(self):
        """P67-GAP-07: source currently leaves newly created sidecars on mux error.

        Expected-failure is NOT release acceptance. A separate source fix and
        real FFmpeg acceptance are required; no source is changed by this test.
        """
        with TemporaryDirectory(prefix="tihulu-media-partial-sidecar-") as work:
            root = Path(work)
            media = root / "original.wav"
            subtitle = root / "input.srt"
            media.write_bytes(b"original immutable media")
            subtitle.write_text(SRT, encoding="utf-8")
            with patch.object(export, "_run_ffmpeg",
                              side_effect=RuntimeError("synthetic FFmpeg failure")):
                with self.assertRaisesRegex(RuntimeError, "synthetic FFmpeg failure"):
                    export.run_export(
                        sources={"original": str(subtitle)}, destination=str(root),
                        name="export", formats=("srt",), media=str(media),
                        mux=True, mode="complete",
                    )
            self.assertEqual(media.read_bytes(), b"original immutable media")
            self.assertFalse(
                (root / "export.original.srt").exists(),
                "Incomplete export sidecar must not remain after failing mux",
            )


if __name__ == "__main__":
    unittest.main()
