"""Synthetic cleanup tests: no SDR or Internet needed."""
import json
from http.client import HTTPConnection
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from satellite_center.__main__ import Station, Server


class CleanupTests(unittest.TestCase):
    def test_leave_stops_only_owned_manual_child(self):
        with tempfile.TemporaryDirectory() as td:
            app = Station(Path(td))
            proc = app._launch_receiver(
                [sys.executable, "-c", "import time;time.sleep(35)"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            try:
                app.manual_owner = "manual-owner-0123456"
                app.session["active"] = True
                app.heartbeat("manual-owner-0123456")
                app.leave("other-client-123456")
                self.assertIsNone(proc.poll())
                self.assertTrue(app.leave("manual-owner-0123456")["manual_capture_stop_requested"])
                self.assertIsNotNone(proc.poll())
                self.assertEqual(app.request_stop()["owned_processes_stop_requested"], 0)
            finally:
                app.close()

    def test_close_terminates_all_owned_pipeline_children(self):
        with tempfile.TemporaryDirectory() as td:
            app = Station(Path(td))
            a = app._launch_receiver([sys.executable, "-c", "import time;time.sleep(35)"])
            b = app._launch_receiver([sys.executable, "-c", "import time;time.sleep(35)"])
            app.close()
            self.assertIsNotNone(a.poll())
            self.assertIsNotNone(b.poll())
            app.close()
            with self.assertRaisesRegex(RuntimeError, "stopping"):
                app._launch_receiver([sys.executable, "-c", "print(1)"])

    def test_stale_browser_watchdog_releases_capture(self):
        with tempfile.TemporaryDirectory() as td:
            app = Station(Path(td))
            proc = app._launch_receiver([sys.executable, "-c", "import time;time.sleep(35)"])
            try:
                app.manual_owner = "manual-owner-1234567"
                app.session["active"] = True
                app.last_manual_heartbeat = time.monotonic() - 30
                thread = threading.Thread(target=app._manual_watchdog,
                                          args=("manual-owner-1234567",), daemon=True)
                thread.start()
                thread.join(3)
                self.assertFalse(thread.is_alive())
                self.assertIsNotNone(proc.poll())
            finally:
                app.close()

    def test_tab_leave_preserves_scheduled_capture(self):
        with tempfile.TemporaryDirectory() as td:
            app = Station(Path(td))
            proc = app._launch_receiver([sys.executable, "-c", "import time;time.sleep(35)"])
            try:
                app.manual_owner = None
                app.session.update(active=True, scheduled=True)
                self.assertFalse(app.leave("manual-owner-1234567")["manual_capture_stop_requested"])
                self.assertIsNone(proc.poll())
            finally:
                app.close()
            self.assertIsNotNone(proc.poll())

    def test_quit_api_shuts_down_local_service(self):
        with tempfile.TemporaryDirectory() as td:
            app = Station(Path(td))
            server = Server(("127.0.0.1", 0), app)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            try:
                conn.request("GET", "/api/status")
                csrf = json.loads(conn.getresponse().read())["csrf"]
                conn.request("POST", "/api/quit",
                             body=json.dumps({"csrf": csrf}),
                             headers={"Content-Type": "application/json"})
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["closing"])
                thread.join(5)
                self.assertFalse(thread.is_alive())
                self.assertTrue(app.closed.is_set())
            finally:
                conn.close()
                server.shutdown()
                server.server_close()
                thread.join(2)


if __name__ == "__main__":
    unittest.main()
