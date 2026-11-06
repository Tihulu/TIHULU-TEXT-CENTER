"""Mock-only safety tests: no real radio process or USB device touched."""
import time
import unittest
from unittest.mock import patch

from textcenter.managed_dab import ManagedDABReceiver,ReceiverServiceError


class FakeProcess:
    def __init__(self):
        self.pid=239123
        self.returncode=None
    def poll(self):return self.returncode
    def wait(self,timeout=None):return self.returncode


class ReceiverManagerTests(unittest.TestCase):
    def setUp(self):
        self.proc=FakeProcess()
        self.calls=[]
        self.manager=ManagedDABReceiver(
            which=lambda _: "/usr/bin/welle-cli",
            conflicts=lambda: [],
            popen=self.fake_popen,
            heartbeat_timeout=18)
        self.busy=patch.object(self.manager,"_port_busy",return_value=False)
        self.busy.start()
        self.kill=patch("textcenter.managed_dab.os.killpg",side_effect=self.fake_kill)
        self.kill.start()

    def tearDown(self):
        self.manager.close()
        self.kill.stop()
        self.busy.stop()

    def fake_popen(self,args,**kw):
        self.calls.append(args)
        self.assertEqual(args[:2],["/usr/bin/welle-cli","-c"])
        self.assertTrue(kw["start_new_session"])
        return self.proc

    def fake_kill(self,pid,signal):
        self.assertEqual(pid,self.proc.pid)
        self.proc.returncode=0

    def test_owned_child_only_released_when_matching_tab_closes(self):
        start=self.manager.start("11D",owner="test-browser-session-123")
        self.assertTrue(start["active"])
        self.assertEqual(start["channel"],"11D")
        self.assertEqual(self.calls[0],[
            "/usr/bin/welle-cli","-c","11D","-PC","1","-w","7979"])
        wrong=self.manager.stop(owner="another-browser-tab",owner_only=True)
        self.assertFalse(wrong["stopped"])
        self.assertTrue(self.manager.status()["active"])
        same=self.manager.stop(owner="test-browser-session-123",owner_only=True)
        self.assertTrue(same["stopped"])
        self.assertFalse(same["active"])

    def test_refuses_busy_external_receiver_and_illegal_channels(self):
        self.manager.conflicts=lambda:[{"process":"readsb","pid":12}]
        with self.assertRaisesRegex(ReceiverServiceError,"readsb"):
            self.manager.start("11D",owner="test-browser-session-123")
        self.assertFalse(self.manager.status()["active"])
        self.manager.conflicts=lambda:[]
        with self.assertRaises(ReceiverServiceError):
            self.manager.start("11D; echo anything",owner="test-browser-session-123")
        with self.assertRaises(ReceiverServiceError):
            self.manager.start("11D",owner="invalid / !")
        with patch.object(self.manager,"_port_busy",return_value=True):
            with self.assertRaisesRegex(ReceiverServiceError,"7979"):
                self.manager.start("11D",owner="test-browser-session-123")

    def test_closing_server_cleans_child_but_not_external_processes(self):
        self.manager.start("5C",owner="test-browser-session-123")
        self.manager.close()
        self.assertFalse(self.manager.status()["active"])

    def test_heartbeat_renews_only_matching_browser_ownership(self):
        self.manager.start("8B",owner="test-browser-session-123")
        with self.manager._lock:
            self.manager._last_seen=time.monotonic()-5
            original=self.manager._last_seen
        self.manager.status(owner="another-browser-tab")
        self.assertEqual(self.manager._last_seen,original)
        self.manager.status(owner="test-browser-session-123")
        self.assertGreater(self.manager._last_seen,original)


if __name__=="__main__":unittest.main()
