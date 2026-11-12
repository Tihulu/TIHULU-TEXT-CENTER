"""P67-GAP-07 — deterministic owned-sidecar rollback regressions.

Standalone PR stacked on original Media #67; PR #90 stays test-only and
unmodified. The first test turns its known `expectedFailure` into a normal
passing regression. Every tool invocation is faked: no FFmpeg, RF, CPU/GPU
model, system service, device or user recording is opened.
"""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from tv_center import recording_export as export


SRT = "1\n00:00:00,100 --> 00:00:01,200\n[Music] Original speech\n\n"


class SafeSidecarRollbackTests(unittest.TestCase):
    def _inputs(self, root):
        root = Path(root)
        media = root / "original.wav"
        subtitle = root / "input.srt"
        media.write_bytes(b"immutable original media and recording")
        subtitle.write_text(SRT, encoding="utf-8")
        return media, subtitle

    def _run(self, root, media, subtitle, **kwargs):
        return export.run_export(
            sources={"original": str(subtitle)}, destination=str(root),
            name="export", formats=("txt", "srt"), media=str(media),
            mux=True, mode="complete", **kwargs)

    def test_known_gap_sidecar_is_rolled_back_when_later_mux_fails(self):
        """PR90 Stage5 expectedFailure, WITHOUT the expectedFailure decorator."""
        with tempfile.TemporaryDirectory(prefix="tihulu-media-partial-sidecar-") as work:
            root = Path(work)
            media, subtitle = self._inputs(root)
            with patch.object(export, "_run_ffmpeg",
                              side_effect=RuntimeError("synthetic FFmpeg failure")):
                with self.assertRaisesRegex(RuntimeError, "synthetic FFmpeg failure"):
                    export.run_export(
                        sources={"original": str(subtitle)}, destination=str(root),
                        name="export", formats=("srt",), media=str(media),
                        mux=True, mode="complete",
                    )
            self.assertEqual(media.read_bytes(),
                             b"immutable original media and recording")
            self.assertEqual(subtitle.read_text(encoding="utf-8"), SRT)
            self.assertFalse(
                (root / "export.original.srt").exists(),
                "Incomplete export sidecar must not remain after failing mux",
            )

    def test_mux_failure_removes_only_two_new_sidecars(self):
        with tempfile.TemporaryDirectory(prefix="tihulu-media-rollback-") as work:
            root = Path(work)
            media, subtitle = self._inputs(root)
            unrelated = root / "finished-old-recording.srt"
            unrelated.write_bytes(b"do not touch original user recordings")
            def fake_ffmpeg(argv):
                self.assertEqual(argv[-1], str(root / "export-subtitled.mkv"))
                raise RuntimeError("fake FFmpeg returned failure")
            with patch.object(export, "_run_ffmpeg", side_effect=fake_ffmpeg):
                with self.assertRaisesRegex(RuntimeError, "fake FFmpeg"):
                    self._run(root, media, subtitle)
            self.assertFalse((root / "export.original.txt").exists())
            self.assertFalse((root / "export.original.srt").exists())
            self.assertEqual(unrelated.read_bytes(),
                             b"do not touch original user recordings")
            self.assertEqual(media.read_bytes(),
                             b"immutable original media and recording")

    def test_competing_mkv_after_preflight_remains_when_mux_fails(self):
        with tempfile.TemporaryDirectory(prefix="tihulu-media-foreign-mkv-") as work:
            root = Path(work)
            media, subtitle = self._inputs(root)
            foreign = root / "export-subtitled.mkv"
            def fake_ffmpeg(argv):
                foreign.write_bytes(b"other creator's own finished MKV")
                raise RuntimeError("competing MKV exists")
            with patch.object(export, "_run_ffmpeg", side_effect=fake_ffmpeg):
                with self.assertRaisesRegex(RuntimeError, "competing MKV"):
                    self._run(root, media, subtitle)
            self.assertEqual(foreign.read_bytes(),
                             b"other creator's own finished MKV")
            self.assertFalse((root / "export.original.srt").exists())
            self.assertFalse((root / "export.original.txt").exists())
            self.assertEqual(media.read_bytes(),
                             b"immutable original media and recording")

    def test_foreign_replacement_of_sidecar_is_not_removed_after_mux_failure(self):
        with tempfile.TemporaryDirectory(prefix="tihulu-media-racing-sidecar-") as work:
            root = Path(work)
            media, subtitle = self._inputs(root)
            changed = root / "export.original.srt"
            foreign_inode = {}
            def fake_ffmpeg(_argv):
                self.assertTrue(changed.exists(), "our sidecar should precede mux")
                changed.unlink()  # simulate another process replacing path
                changed.write_bytes(b"foreign creator's replacement file")
                foreign_inode["value"] = changed.stat().st_ino
                raise RuntimeError("mock mux failed after external replacement")
            with patch.object(export, "_run_ffmpeg", side_effect=fake_ffmpeg):
                with self.assertRaisesRegex(RuntimeError, "external replacement"):
                    self._run(root, media, subtitle)
            self.assertFalse((root / "export.original.txt").exists())
            self.assertEqual(changed.read_bytes(),
                             b"foreign creator's replacement file")
            self.assertEqual(changed.stat().st_ino, foreign_inode["value"])
            self.assertEqual(media.read_bytes(),
                             b"immutable original media and recording")

    def test_foreign_symlink_swap_is_preserved_and_never_followed(self):
        with tempfile.TemporaryDirectory(prefix="tihulu-media-symlink-race-") as work:
            root = Path(work)
            media, subtitle = self._inputs(root)
            target = root / "outside-user-output"
            target.write_bytes(b"external kept bytes")
            sidecar = root / "export.original.srt"
            def fake_ffmpeg(_argv):
                sidecar.unlink()
                sidecar.symlink_to(target)
                raise RuntimeError("synthetic mux failed after symlink swap")
            with patch.object(export, "_run_ffmpeg", side_effect=fake_ffmpeg):
                with self.assertRaisesRegex(RuntimeError, "symlink swap"):
                    self._run(root, media, subtitle)
            self.assertTrue(sidecar.is_symlink())
            self.assertEqual(target.read_bytes(), b"external kept bytes")
            self.assertFalse((root / "export.original.txt").exists())

    def test_second_sidecar_exclusive_create_race_preserves_foreign_bytes(self):
        with tempfile.TemporaryDirectory(prefix="tihulu-media-exclusive-race-") as work:
            root = Path(work)
            foreign = root / "take.original.srt"
            first = root / "take.original.txt"
            writer = export._write_new
            def competing_writer(path, data, **kwargs):
                if Path(path) == foreign:
                    foreign.write_bytes(b"racing external sidecar")
                    # Real os.O_EXCL still protects it, not a fake error.
                return writer(path, data, **kwargs)
            with patch.object(export, "_write_new", side_effect=competing_writer):
                with self.assertRaises(FileExistsError):
                    export.export_tracks(
                        {"original": [export.Cue(0.1, 1.2, "[Music] Original speech")]},
                        root, "take", formats=("txt", "srt"))
            self.assertFalse(first.exists())
            self.assertEqual(foreign.read_bytes(), b"racing external sidecar")

    def test_existing_sidecar_preflight_never_calls_ffmpeg_or_changes_bytes(self):
        with tempfile.TemporaryDirectory(prefix="tihulu-media-existing-") as work:
            root = Path(work)
            media, subtitle = self._inputs(root)
            existing = root / "export.original.srt"
            existing.write_bytes(b"pre-existing export")
            with patch.object(export, "_run_ffmpeg",
                              side_effect=AssertionError("no ffmpeg allowed")):
                with self.assertRaises(FileExistsError):
                    self._run(root, media, subtitle)
            self.assertEqual(existing.read_bytes(), b"pre-existing export")
            self.assertFalse((root / "export.original.txt").exists())

    def test_success_preserves_outputs_and_source(self):
        with tempfile.TemporaryDirectory(prefix="tihulu-media-success-") as work:
            root = Path(work)
            media, subtitle = self._inputs(root)
            fake_mkv = root / "export-subtitled.mkv"
            def fake_ffmpeg(_argv):
                fake_mkv.write_bytes(b"simulated owned media export")
            with patch.object(export, "_run_ffmpeg", side_effect=fake_ffmpeg):
                paths = self._run(root, media, subtitle)
            self.assertEqual(set(paths), {
                root / "export.original.txt",
                root / "export.original.srt", fake_mkv})
            self.assertIn("[Music] Original speech",
                          (root / "export.original.srt").read_text())
            self.assertEqual(media.read_bytes(),
                             b"immutable original media and recording")

    def test_failed_burn_after_successful_mux_rolls_back_sidecars_but_keeps_mkv(self):
        with tempfile.TemporaryDirectory(prefix="tihulu-media-burn-failure-") as work:
            root = Path(work)
            media, subtitle = self._inputs(root)
            generated = root / "export-subtitled.mkv"
            def fake_mux(_media, _tracks, _output):
                generated.write_bytes(b"previous successful media stage")
                return generated
            with patch.object(export, "mux_tracks", side_effect=fake_mux), \
                 patch.object(export, "burn_video",
                              side_effect=RuntimeError("synthetic burn failure")):
                with self.assertRaisesRegex(RuntimeError, "burn failure"):
                    export.run_export(
                        sources={"original": str(subtitle)}, destination=str(root),
                        name="export", formats=("txt", "srt"), media=str(media),
                        mux=True, burn=True, burn_track="original",
                        mode="complete")
            self.assertEqual(generated.read_bytes(),
                             b"previous successful media stage")
            self.assertFalse((root / "export.original.txt").exists())
            self.assertFalse((root / "export.original.srt").exists())
            self.assertEqual(subtitle.read_text(encoding="utf-8"), SRT)

    def test_bad_burn_track_after_sidecars_also_rolls_back(self):
        with tempfile.TemporaryDirectory(prefix="tihulu-media-invalid-track-") as work:
            root = Path(work)
            media, subtitle = self._inputs(root)
            with patch.object(export, "_run_ffmpeg",
                              side_effect=AssertionError("ffmpeg should not start")):
                with self.assertRaisesRegex(ValueError, "Burn-in track"):
                    export.run_export(
                        sources={"original": str(subtitle)}, destination=str(root),
                        name="export", formats=("txt", "srt"), media=str(media),
                        burn=True, burn_track="translation-tr",
                        mode="complete")
            self.assertFalse((root / "export.original.txt").exists())
            self.assertFalse((root / "export.original.srt").exists())

    def test_rollback_failure_is_explicit_and_retains_foreign_output(self):
        with tempfile.TemporaryDirectory(prefix="tihulu-media-rollback-warning-") as work:
            root = Path(work)
            media, subtitle = self._inputs(root)
            foreign = root / "export-subtitled.mkv"
            def fake_ffmpeg(_argv):
                foreign.write_bytes(b"foreign MKV")
                raise RuntimeError("deliberate simulated FFmpeg error")
            def cannot_remove(owned):
                if owned.path.suffix == ".txt":
                    raise PermissionError("synthetic removal denied")
                return real_remove(owned)
            real_remove = export._remove_owned_sidecar
            with patch.object(export, "_run_ffmpeg", side_effect=fake_ffmpeg), \
                 patch.object(export, "_remove_owned_sidecar",
                              side_effect=cannot_remove):
                with self.assertRaisesRegex(RuntimeError,
                        "could not be removed"):
                    self._run(root, media, subtitle)
            self.assertEqual(foreign.read_bytes(), b"foreign MKV")
            self.assertTrue((root / "export.original.txt").exists(),
                            "Unremoved owned file must be reported, not concealed")

    def test_owned_sidecar_descriptors_close_on_success_and_failure(self):
        """Protect against retained descriptor/VRAM-like resource leaks."""
        with tempfile.TemporaryDirectory(prefix="tihulu-media-fd-lifetime-") as work:
            root = Path(work)
            media, subtitle = self._inputs(root)
            pins = []
            real_writer = export._write_new
            def capture_pin(path, data, **kwargs):
                owned = real_writer(path, data, **kwargs)
                if owned.pin_fd is not None:
                    pins.append(owned.pin_fd)
                return owned
            with patch.object(export, "_write_new", side_effect=capture_pin), \
                 patch.object(export, "_run_ffmpeg", side_effect=RuntimeError(
                     "forced late failure")):
                with self.assertRaisesRegex(RuntimeError, "forced late failure"):
                    self._run(root, media, subtitle)
            self.assertEqual(len(pins), 2)
            for fd in pins:
                with self.assertRaises(OSError):
                    os.fstat(fd)
            self.assertFalse((root / "export.original.srt").exists())
            self.assertFalse((root / "export.original.txt").exists())

        with tempfile.TemporaryDirectory(prefix="tihulu-media-fd-success-") as work:
            tracks = {"original": [export.Cue(0.1, 1.2, "[Music] Original speech")]}
            pins = []
            def capture_pin(path, data, **kwargs):
                owned = real_writer(path, data, **kwargs)
                if owned.pin_fd is not None:
                    pins.append(owned.pin_fd)
                return owned
            with patch.object(export, "_write_new", side_effect=capture_pin):
                created = export.export_tracks(
                    tracks, work, "kept", formats=("srt", "txt"))
            self.assertEqual(len(created), 2)
            self.assertEqual(len(pins), 2)
            for fd in pins:
                with self.assertRaises(OSError):
                    os.fstat(fd)
            self.assertTrue((Path(work) / "kept.original.srt").is_file())

    def test_media_only_failure_does_not_generate_persistent_sidecars(self):
        with tempfile.TemporaryDirectory(prefix="tihulu-media-no-formats-") as work:
            root = Path(work)
            media, subtitle = self._inputs(root)
            with patch.object(export, "_run_ffmpeg",
                              side_effect=RuntimeError("media-only fake FFmpeg failure")):
                with self.assertRaisesRegex(RuntimeError, "media-only"):
                    export.run_export(
                        sources={"original": str(subtitle)}, destination=str(root),
                        name="export", formats=(), media=str(media),
                        mux=True, mode="complete")
            self.assertFalse((root / "export.original.srt").exists())
            self.assertEqual(subtitle.read_text(encoding="utf-8"), SRT)
            self.assertFalse(any(root.glob(".tihulu-tracks-*")))
