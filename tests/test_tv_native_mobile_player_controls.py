"""Paired remote commands operate on the running owner-local MPV only."""
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tv_center.core import TVCapture
from tv_center.web_control import WebCommandQueue
from tv_center.web_desktop import TVWebMixin


class NativePlayerSocketTests(unittest.TestCase):
    def test_real_mpvsocket_ack_controls_only_safe_properties(self):
        cap=TVCapture()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"mpv.sock"
            listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            listener.bind(str(path))
            listener.listen(4)
            received=[]
            def accept_loop():
                for _ in range(4):
                    conn,_=listener.accept()
                    with conn:
                        received.append(json.loads(conn.recv(4096)))
                        conn.sendall(b'{"error":"success"}\n')
            worker=threading.Thread(target=accept_loop,daemon=True)
            worker.start()
            cap._ipc_dir=SimpleNamespace(name=d)
            cap.player=mock.Mock()
            cap.player.poll.return_value=None
            self.assertTrue(cap.control_player("pause")["ok"])
            self.assertTrue(cap.control_player("resume")["ok"])
            self.assertTrue(cap.control_player("volume",27)["ok"])
            self.assertTrue(cap.control_player("mute",True)["ok"])
            worker.join(timeout=3)
            listener.close()
            self.assertEqual([message["command"] for message in received],[
              ["set_property","pause",True],
              ["set_property","pause",False],
              ["set_property","volume",27],
              ["set_property","mute",True]])
            with self.assertRaises(ValueError):
                cap.control_player("volume",101)
            with self.assertRaises(ValueError):
                cap.control_player("mute","true")
            with self.assertRaises(ValueError):
                cap.control_player("run_shell","anything")
            self.assertEqual(len(received),4)

    def test_no_host_player_fails_without_touching_tuner(self):
        cap=TVCapture()
        with self.assertRaises(RuntimeError):
            cap.control_player("pause")
        for name in ("measure_signal","video","player_target","sources",
                     "pause","previous","next","volume","tv_channel",
                     "set_desktop_caption_mode","desktop_subtitles_running"):
            self.assertIn(name,WebCommandQueue.ACTIONS)
        self.assertNotIn("arbitrary_shell",WebCommandQueue.ACTIONS)


class NativeCapabilityTests(unittest.TestCase):
    def test_native_mpvsnapshot_does_not_claim_pts_or_kaf_buffer(self):
        class Host(TVWebMixin): pass
        host=Host()
        host.capture=SimpleNamespace(
            _stream_verified=False,zap=None,
            mobile_stream_dir=lambda:None,
            caption_mode="teletext",source_lang="de",target_lang="tr",
            page=150)
        host.web_target="host"
        result=host.native_web_snapshot()
        self.assertFalse(result["mobile_video"])
        self.assertFalse(result["mobile_sources"][0]["available"])
        self.assertFalse(result["desktop_control_capabilities"]["buffer"])
        self.assertFalse(result["desktop_control_capabilities"]["offset"])
        self.assertTrue(result["desktop_control_capabilities"]["mode"])
        self.assertIsNone(result["caption_timing"]["host_effective_buffer_ms"])
        self.assertFalse(result["caption_timing"]["host_buffer_verified"])

if __name__=="__main__":
    unittest.main()
