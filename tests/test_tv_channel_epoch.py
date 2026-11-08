"""Kaffeine-owner TV tune epoch: preserve channels while captions UI stays open."""
import os
from pathlib import Path
import queue
import socket
import tempfile
import time
import unittest
from unittest.mock import patch, Mock

from kaffeine_next.captions_overlay import CaptionTap
from kaffeine_next.mpegts import current_program_id, current_program_identity
from kaffeine_next.tv_tune_state import read_native_tune
from kaffeine_next.mobile import KaffeineMobile


def pat(service, multiplex):
    """One complete 188-byte PAT with a chosen SID and transport-stream ID."""
    section = bytes([0x00, 0xB0, 0x0D, multiplex >> 8, multiplex & 255,
                     0xC1, 0x00, 0x00, service >> 8, service & 255,
                     0xE0, 0x10, 0x00, 0x00, 0x00, 0x00])
    packet = b"\\x47\\x40\\x00\\x10\\x00" + section
    return packet.ljust(188, b"\\xff")


def wait_for(predicate, seconds=2.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.04)
    return bool(predicate())


class TvTuneEpochTests(unittest.TestCase):
    def test_same_service_id_other_multiplex_is_distinct(self):
        original = pat(42, 201)
        switched = pat(42, 202)
        self.assertEqual(current_program_identity(original), (42,201))
        self.assertEqual(current_program_identity(switched), (42,202))
        self.assertEqual(current_program_id(switched),42)
        self.assertIsNone(current_program_identity(b"bad TS"))

    def test_marker_is_bounded_private_and_ignores_invalid_content(self):
        with tempfile.TemporaryDirectory() as root:
            sock = Path(root)/"tihulu-dvb-417.sock"
            state = Path(root)/"tihulu-tv-tune-417.txt"
            self.assertIsNone(read_native_tune(sock))
            state.write_text("51 42 201\\n")
            self.assertEqual(read_native_tune(sock), (51,42,201))
            state.write_text("52 0 0\\n")
            self.assertEqual(read_native_tune(sock), (52,0,0))
            for invalid in ("invalid", "53 99999 10\\n", "54 0 201\\n",
                            "55 40 20\\n"+("x"*100)):
                state.write_text(invalid)
                self.assertIsNone(read_native_tune(sock))
            state.unlink()
            target = Path(root)/"user-owned.txt"
            target.write_text("56 40 20\\n")
            state.symlink_to(target)
            self.assertIsNone(read_native_tune(sock))
            self.assertIsNone(read_native_tune(Path(root)/"random.sock"))

    def test_reader_rejects_old_pat_before_new_channel_audio(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"tihulu-dvb-765.sock"
            state = Path(root)/"tihulu-tv-tune-765.txt"
            state.write_text("1 42 201\\n")
            observed = []
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR":root}):
                tap = CaptionTap(str(path),lambda:{"mode":"off","revision":0},
                                 queue.Queue(),owner_tune_changed=observed.append)
                sender = socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
                try:
                    tap.start()
                    self.assertTrue(wait_for(lambda:tap.native_tune_state==(1,42,201)))
                    sender.sendto(pat(42,200),str(path))
                    time.sleep(.18)
                    self.assertIsNone(tap.program_id)
                    sender.sendto(pat(42,201),str(path))
                    self.assertTrue(wait_for(lambda:tap.program_id==42))
                    start_epoch=tap.program_epoch
                    # Same service number on different transport stream:
                    # stale packets must not be accepted as new captions.
                    state.write_text("2 42 202\\n")
                    self.assertTrue(wait_for(lambda:tap.native_tune_state==(2,42,202)))
                    self.assertGreater(tap.program_epoch,start_epoch)
                    self.assertIsNone(tap.program_id)
                    sender.sendto(pat(42,201),str(path))
                    time.sleep(.18)
                    self.assertIsNone(tap.program_id)
                    sender.sendto(pat(42,202),str(path))
                    self.assertTrue(wait_for(lambda:tap.program_id==42))
                    self.assertEqual(observed,[(1,42,201),(2,42,202)])
                    state.write_text("3 0 0\\n")
                    self.assertTrue(wait_for(lambda:tap.native_tune_state==(3,0,0)))
                    self.assertIsNone(tap.program_id)
                finally:
                    sender.close()
                    tap.close()

    def test_mobile_old_channel_hls_is_stopped(self):
        mobile = KaffeineMobile(lambda:{"mode":"auto","page":150},lambda _:None)
        mobile.receive(pat(42,201))
        mobile.set_caption({"original":"Old program","source":"local_asr"})
        old_hls=Mock()
        mobile.hls=old_hls
        mobile.owner_tune_changed((2,43,202))
        old_hls.stop.assert_called_once()
        self.assertIsNone(mobile.hls)
        self.assertIsNone(mobile.service_id)
        self.assertEqual(mobile.caption["original"],"")
        self.assertEqual(mobile.caption["source"],"channel_changed")

    def test_caption_settings_are_nonmodal_and_never_reuse_old_pid(self):
        from kaffeine_next import captions_overlay, patch_upstream
        from inspect import getsource
        native=getsource(patch_upstream.transform)
        ui=getsource(captions_overlay.main)
        self.assertIn("tihuluNotifyNativeCaptionTune",native)
        self.assertIn("channel->transportStreamId",native)
        self.assertIn("QSaveFile",native)
        self.assertIn("window.setWindowModality(Qt.NonModal)",ui)
        self.assertIn("back_to_tv.clicked.connect(window.showMinimized)",ui)
        self.assertIn("def reset_channel_captions",ui)
        self.assertIn("teletext_pid=None, audio_pid=None, audio_language=None",ui)
        self.assertIn("if tap.program_epoch != last_ui_program_epoch:",ui)
        self.assertIn('data.get("program_epoch") != tap.program_epoch',ui)
        self.assertIn("Automatic broadcaster subtitles (new TV service)",ui)


if __name__ == "__main__":
    unittest.main()
