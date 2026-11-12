"""RQ-098 / EXIT-01 synthetic shutdown regression. No radio/TV/AI services used."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from textcenter.core import Store
from textcenter.http_app import LocalServer
from textcenter.live_fm import LiveFM, LiveError
from textcenter.live_tv import LiveTV, LiveTVError
from textcenter.speech import SpeechPipeline, WINDOW_BYTES


PROFILE = {
    "devices": [{"id": "cpu", "name": "Fixture CPU", "detected": True}],
    "speech": {"ready_cpu": True, "model_path": "/not-a-real-model",
               "executable": "/not-a-real-whisper"},
}


class Capture:
    def __init__(self):
        self.rows = []

    def add(self, **data):
        self.rows.append(data)


def speech(store=None, transcriber=None):
    return SpeechPipeline(
        store=store or Capture(), session="a" * 32, source_id="fm:fixture",
        source_language="de", target_language=None, backend="cpu",
        profile=PROFILE, transcriber=transcriber or (lambda *_: "Synthetic"),
    )


class SpeechShutdownTests(unittest.TestCase):
    def test_repeated_stop_clears_partial_pcm_and_refuses_late_feed(self):
        capture = Capture()
        worker = speech(capture)
        self.assertTrue(worker.feed(b"\x00" * 1000))
        first = worker.stop(wait=True)
        second = worker.stop(wait=True)
        self.assertEqual(first["lifecycle"], "STOPPED", first)
        self.assertEqual(second["lifecycle"], "STOPPED", second)
        self.assertFalse(first["worker_alive"])
        self.assertEqual(worker.status()["buffered_bytes"], 0)
        self.assertEqual(worker.status()["queued_windows"], 0)
        self.assertFalse(worker.feed(b"\x00" * WINDOW_BYTES))
        self.assertEqual(capture.rows, [])

    def test_blocked_inference_reports_partial_then_joins_without_late_caption(self):
        entered = threading.Event()
        allow_finish = threading.Event()
        archive = Capture()

        def blocked(*_args):
            entered.set()
            allow_finish.wait(timeout=3)
            return "A transcript completed after Stop"

        worker = speech(archive, blocked)
        try:
            self.assertTrue(worker.feed(b"\x01" * WINDOW_BYTES))
            self.assertTrue(entered.wait(timeout=1), "Worker never reached synthetic ASR")
            self.assertTrue(worker.feed(b"\x02" * (WINDOW_BYTES * 2 + 59)))
            result = worker.stop(wait=True, timeout=.01)
            self.assertEqual(result["lifecycle"], "STOP_FAILED_PARTIAL", result)
            self.assertTrue(result["worker_alive"])
            self.assertEqual(result["queued_windows"], 0)
            self.assertEqual(result["buffered_bytes"], 0)
            self.assertFalse(worker.feed(b"\x03" * WINDOW_BYTES))
        finally:
            allow_finish.set()
        joined = worker.stop(wait=True, timeout=2)
        self.assertEqual(joined["lifecycle"], "STOPPED", joined)
        self.assertFalse(joined["worker_alive"])
        self.assertEqual(archive.rows, [], "Cancelled inference must not persist late output")

    def test_duplicate_icao_or_hardware_not_needed_for_speech_cleanup(self):
        # A background worker with no recording data must exit without spawning tools.
        w = speech()
        with patch("subprocess.run", side_effect=AssertionError("external process touched")):
            self.assertEqual(w.stop(wait=True)["lifecycle"], "STOPPED")


class ModuleShutdownTests(unittest.TestCase):
    def test_radio_and_tv_quit_close_owned_recording_handles_preserve_files(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            fm_path, tv_path = base / "saved-FM-test.mp3", base / "saved-TV-test.mp4"
            fm_path.write_bytes(b"keep FM media")
            tv_path.write_bytes(b"keep TV media")
            radio = LiveFM(archive_dir=base, inventory=lambda: None)
            tv = LiveTV(archive_dir=base)
            radio.record_file = fm_path.open("ab")
            tv.record_file = tv_path.open("ab")
            radio.state["active"] = True
            tv.state["active"] = True
            with patch("subprocess.run", side_effect=AssertionError("system service touched")):
                self.assertFalse(radio.quit()["active"])
                self.assertFalse(tv.quit()["active"])
                self.assertFalse(radio.quit()["active"])
                self.assertFalse(tv.quit()["active"])
            self.assertTrue(radio.closed)
            self.assertTrue(tv.closed)
            self.assertTrue(radio.record_file is None)
            self.assertTrue(tv.record_file is None)
            self.assertEqual(fm_path.read_bytes(), b"keep FM media")
            self.assertEqual(tv_path.read_bytes(), b"keep TV media")
            with self.assertRaisesRegex(LiveError, "quit"):
                radio.start(98.6)
            with self.assertRaisesRegex(LiveTVError, "quit"):
                tv.start("fixture", upstream_authorized=True)

    def test_preview_and_rds_and_survey_do_not_start_after_server_shutdown(self):
        with tempfile.TemporaryDirectory() as td:
            server = LocalServer(("127.0.0.1", 0), Store(Path(td) / "db.sqlite"))
            try:
                with patch("subprocess.run", side_effect=AssertionError("external readsb touched")):
                    state = server.close_owned()
                    again = server.close_owned()
                self.assertEqual(state["lifecycle"], "STOPPED", state)
                self.assertEqual(state, again)
                self.assertTrue(server.rds._closed)
                self.assertTrue(server.survey._closed)
                self.assertTrue(server.audio._closed)
                self.assertEqual(server.audio._wav, None)
                self.assertEqual(server.lifecycle_status()["errors"], [])
            finally:
                server.server_close()


class HTTPShutdownTests(unittest.TestCase):
    def start_server(self, base):
        server = LocalServer(("127.0.0.1", 0), Store(base / "db.sqlite"))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    @staticmethod
    def request(server, route, payload=None):
        c = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        try:
            headers = {}
            body = None
            if payload is not None:
                body = json.dumps(payload).encode()
                headers = {"Content-Type": "application/json",
                           "X-Tihulu-CSRF": server.csrf_token}
            c.request("POST" if payload is not None else "GET", route,
                      body=body, headers=headers)
            reply = c.getresponse()
            return reply.status, json.loads(reply.read())
        finally:
            c.close()

    def test_stop_gate_rejects_start_after_quit_even_with_valid_csrf(self):
        with tempfile.TemporaryDirectory() as td:
            server, thread = self.start_server(Path(td))
            try:
                self.assertEqual(self.request(server, "/api/lifecycle")[1]["lifecycle"], "RUNNING")
                # Directly transition to STOPPING without closing HTTP; all new
                # synthetic POST tasks must be denied regardless of route.
                with server._lifecycle_lock:
                    server.lifecycle = "STOPPING"
                code, result = self.request(server, "/api/scans/start", {"band": "fm"})
                self.assertEqual(code, 503)
                self.assertIn("stopping", result["error"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_in_flight_start_and_quit_are_serialized(self):
        with tempfile.TemporaryDirectory() as td:
            server, thread = self.start_server(Path(td))
            entered, release = threading.Event(), threading.Event()
            result = {}

            def synthetic_start(_band):
                entered.set()
                release.wait(timeout=2)
                return {"status": "fixture", "active": False}

            server.survey.start = synthetic_start

            def submit():
                result["first"] = self.request(server, "/api/scans/start", {"band": "fm"})

            first = threading.Thread(target=submit)
            closing = threading.Thread(target=server.close_owned)
            try:
                first.start()
                self.assertTrue(entered.wait(timeout=1))
                closing.start()
                # The existing request owns the admission lock; Quit waits.
                self.assertTrue(closing.is_alive())
                release.set()
                first.join(timeout=3)
                closing.join(timeout=6)
                self.assertEqual(result["first"][0], 202)
                self.assertEqual(server.lifecycle, "STOPPED")
                self.assertEqual(self.request(server, "/api/scans/start", {"band": "fm"})[0], 503)
            finally:
                release.set()
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_authenticated_http_quit_ends_listener_and_owned_sessions(self):
        with tempfile.TemporaryDirectory() as td:
            server, thread = self.start_server(Path(td))
            try:
                status, body = self.request(server, "/api/quit", {})
                self.assertEqual(status, 202)
                self.assertEqual(body["lifecycle"], "STOPPING")
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive(), "Quit did not shut down the serve_forever loop")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
            self.assertEqual(server.lifecycle_status()["lifecycle"], "STOPPED")


if __name__ == "__main__":
    unittest.main()
