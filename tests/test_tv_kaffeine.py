"""Offline regression tests for the Kaffeine DVB stream tap."""
import os
import queue
import socket
import tempfile
import time
from pathlib import Path
from unittest import TestCase, mock

from kaffeine_next.captions_overlay import CaptionTap, validate_socket
from kaffeine_next.patch_upstream import REVISION, PATHS

class KaffeineCaptionTapTests(TestCase):
    def test_upstream_release_is_immutable(self):
        self.assertEqual(REVISION, "e7ea15b86dafed3b20b151cbcb080578ab8e2d5c")
        self.assertEqual(len(PATHS), 3)

    def test_socket_accepts_only_private_kaffeine_endpoint(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": root}):
                valid = str(Path(root)/"tihulu-dvb-12345.sock")
                self.assertEqual(validate_socket(valid), Path(valid))
                with self.assertRaises(ValueError):
                    validate_socket(str(Path(root)/"other.sock"))
                with self.assertRaises(ValueError):
                    validate_socket("/tmp/tihulu-dvb-12345.sock")

    def test_datagrams_do_not_claim_dvb_device(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": root}):
                path = str(Path(root)/"tihulu-dvb-1001.sock")
                events = queue.Queue()
                tap = CaptionTap(path, lambda: {"mode":"off"}, events)
                tap.start()
                try:
                    packet = b"\x47" + b"\x00" * 187
                    sender = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                    try:
                        sender.sendto(packet * 12, path)
                    finally:
                        sender.close()
                    for _ in range(30):
                        if tap.packet_count:
                            break
                        time.sleep(0.02)
                    self.assertEqual(tap.packet_count, 12)
                    self.assertEqual(tap.bad_packets, 0)
                finally:
                    tap.close()
                self.assertFalse(Path(path).exists())
