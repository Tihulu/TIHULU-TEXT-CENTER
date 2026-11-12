"""EXIT-01 adversarial ownership/lifecycle tests (synthetic only).

No actual model, tuner, external daemon, GPU, TV or RF service is started.
"""
import http.client
import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from textcenter.core import Store
from textcenter.http_app import LocalServer
from textcenter.fm_audio import FMPreview
from textcenter.fm_rds import FMRSDSupervisor
from textcenter.fm_survey import FMSurveySupervisor
from textcenter.live_fm import LiveFM, LiveError
from textcenter.live_tv import LiveTV, LiveTVError
from textcenter.postprocess import RecordingTranscriber, PostProcessError
from textcenter.speech import SpeechPipeline, WINDOW_BYTES


PROFILE = {
    "devices": [{"id": "cpu", "name": "synthetic CPU", "detected": True}],
    "speech": {"ready_cpu": True, "model_path": "/fixture/not-a-real-model",
               "executable": "/fixture/not-a-real-whisper"},
}


class Captions:
    def __init__(self):
        self.rows = []

    def add(self, **kwargs):
        self.rows.append(kwargs)


class OwnedChild:
    """Fake held Popen, never an actual OS PID."""
    def __init__(self, *, unresponsive=False, stdout=None):
        self.unresponsive = unresponsive
        self._alive = True
        self.terminations = 0
        self.kills = 0
        self.stdin = None
        self.stdout = stdout
        self.wait_started = threading.Event()

    def poll(self):
        return None if self._alive else -15

    def terminate(self):
        self.terminations += 1
        if not self.unresponsive:
            self._alive = False

    def kill(self):
        self.kills += 1
        if not self.unresponsive:
            self._alive = False

    def wait(self, timeout=None):
        self.wait_started.set()
        if self._alive:
            raise subprocess.TimeoutExpired("synthetic-owned-child", timeout)
        return -15


class InstrumentedBuffer(bytearray):
    def __init__(self):
        super().__init__()
        self.peak = 0

    def extend(self, value):
        super().extend(value)
        self.peak = max(self.peak, len(self))


class SpeechRaceTests(unittest.TestCase):
    def make_speech(self, *, target=None, transcriber=None, translator=None):
        store = Captions()
        worker = SpeechPipeline(
            store=store, session="0" * 32, source_id="fm:synthetic",
            source_language="de", target_language=target,
            backend="cpu", profile=PROFILE,
            transcriber=transcriber, translator=translator,
        )
        return worker, store

    def test_feed_large_block_never_duplicates_unbounded_audio_in_RAM(self):
        worker, _ = self.make_speech(transcriber=lambda *_: "")
        buffer = InstrumentedBuffer()
        worker.buffer = buffer
        try:
            self.assertTrue(worker.feed(b"\x00" * (WINDOW_BYTES * 7 + 31)))
            self.assertLessEqual(buffer.peak, WINDOW_BYTES)
            self.assertEqual(len(worker.buffer), 31)
        finally:
            stopped = worker.stop(wait=True)
        self.assertEqual(stopped["lifecycle"], "STOPPED", stopped)
        self.assertEqual(stopped["queued_windows"], 0)
        self.assertEqual(stopped["buffered_bytes"], 0)
        self.assertFalse(worker.feed(b"\x01" * WINDOW_BYTES))

    def test_cancellation_mid_translation_never_writes_late_caption(self):
        entered = threading.Event()
        unblock = threading.Event()

        def translator(*_args):
            entered.set()
            unblock.wait(timeout=4)
            return "late translated caption"

        worker, captions = self.make_speech(
            target="en", transcriber=lambda *_: "speech", translator=translator)
        try:
            worker.feed(b"\x00" * WINDOW_BYTES)
            self.assertTrue(entered.wait(timeout=2))
            report = worker.stop(wait=True, timeout=.02)
            self.assertEqual(report["lifecycle"], "STOP_FAILED_PARTIAL")
            self.assertFalse(worker.feed(b"\x00" * WINDOW_BYTES))
            self.assertEqual(captions.rows, [])
        finally:
            unblock.set()
        report = worker.stop(wait=True, timeout=2)
        self.assertEqual(report["lifecycle"], "STOPPED", report)
        self.assertEqual(captions.rows, [])

    def test_builtin_cpu_whisper_terminates_only_held_child(self):
        captions = Captions()
        owned = OwnedChild()
        foreign = OwnedChild()
        worker = SpeechPipeline(
            store=captions, session="f" * 32, source_id="synthetic",
            source_language="de", target_language=None, profile=PROFILE,
            backend="cpu")
        with patch("textcenter.speech.subprocess.Popen", return_value=owned), \
             patch("os.killpg", side_effect=AssertionError("foreign PID kill")):
            try:
                worker.feed(b"\x00" * WINDOW_BYTES)
                self.assertTrue(owned.wait_started.wait(timeout=3))
                result = worker.stop(wait=True, timeout=2)
                self.assertEqual(result["lifecycle"], "STOPPED", result)
                self.assertGreaterEqual(owned.terminations, 1)
            finally:
                worker.stop(wait=True)
        self.assertEqual(foreign.terminations, 0)
        self.assertEqual(foreign.kills, 0)
        self.assertEqual(captions.rows, [])

    def test_unreapable_owned_whisper_remains_visible_even_if_worker_exits(self):
        captions = Captions()
        owned = OwnedChild(unresponsive=True)
        worker = SpeechPipeline(
            store=captions, session="f" * 32, source_id="synthetic",
            source_language="de", target_language=None, profile=PROFILE,
            backend="cpu")
        with patch("textcenter.speech.subprocess.Popen", return_value=owned), \
             patch("os.killpg", side_effect=AssertionError("foreign PID kill")):
            worker.feed(b"\x00" * WINDOW_BYTES)
            self.assertTrue(owned.wait_started.wait(timeout=2))
            worker.thread.join(timeout=2)
            report = worker.stop(wait=True, timeout=.02)
        self.assertEqual(report["lifecycle"], "STOP_FAILED_PARTIAL", report)
        self.assertTrue(report["child_alive"])
        self.assertFalse(report["worker_alive"])
        self.assertGreaterEqual(owned.kills, 1)
        self.assertFalse(worker.feed(b"\x00" * WINDOW_BYTES))
        self.assertEqual(captions.rows, [])
        # A fake unresponsive child is retained for diagnostics, not forgotten.
        self.assertIs(worker._active_child, owned)


class ForeignServiceAndModuleTests(unittest.TestCase):
    def test_unresponsive_live_fm_and_tv_children_remain_owned_and_report_partial(self):
        with tempfile.TemporaryDirectory() as td:
            foreign = OwnedChild()
            fm_child, tv_child = OwnedChild(unresponsive=True), OwnedChild(unresponsive=True)
            fm = LiveFM(archive_dir=Path(td))
            tv = LiveTV(archive_dir=Path(td))
            fm.receiver = fm_child
            tv.process = tv_child
            fm.state["active"] = True
            tv.state["active"] = True
            with patch("os.killpg", side_effect=AssertionError("must not kill external process")):
                fm_report = fm.stop(wait=True)
                tv_report = tv.stop(wait=True)
            self.assertEqual(fm_report["status"], "stop_failed_partial", fm_report)
            self.assertEqual(tv_report["status"], "stop_failed_partial", tv_report)
            self.assertIs(fm.receiver, fm_child)
            self.assertIs(tv.process, tv_child)
            self.assertEqual(foreign.terminations, 0)
            self.assertEqual(foreign.kills, 0)
            with self.assertRaisesRegex(LiveError, "still stopping"):
                fm.start(98.6)
            with self.assertRaisesRegex(LiveTVError, "still stopping"):
                tv.start("fake", upstream_authorized=True)
            # Late reap makes another idempotent stop release the held handle.
            fm_child._alive = False
            tv_child._alive = False
            self.assertEqual(fm.stop(wait=True)["status"], "stopped")
            self.assertEqual(tv.stop(wait=True)["status"], "stopped")
            self.assertIsNone(fm.receiver)
            self.assertIsNone(tv.process)

    def test_offline_transcriber_retains_unreapable_owned_children_and_blocks_restart(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            saved = base / "existing-FM-user.mp3"
            saved.write_bytes(b"original recording")
            fake_radio = type("Saved", (), {"recording": lambda self, name: saved})()
            t = RecordingTranscriber(
                transcripts=Captions(), radio=fake_radio, tv=fake_radio,
                lookup=lambda _: "/missing/never-run-ffmpeg", detect=lambda: PROFILE,
            )
            owned, foreign = OwnedChild(unresponsive=True), OwnedChild()
            t._asr_process = owned
            t._state["active"] = False
            with patch("os.killpg", side_effect=AssertionError("global service kill")):
                report = t.stop(wait=True)
            self.assertEqual(report["status"], "stop_failed_partial")
            self.assertIs(t._asr_process, owned)
            self.assertEqual(foreign.kills, 0)
            with self.assertRaises(PostProcessError):
                t.start(medium="fm", filename=saved.name, language="de")
            self.assertEqual(saved.read_bytes(), b"original recording")
            t.quit()
            self.assertTrue(t._closed)

    def test_stop_one_module_keeps_other_module_usable(self):
        with tempfile.TemporaryDirectory() as td:
            server = LocalServer(("127.0.0.1", 0), Store(Path(td) / "test.sqlite"))
            try:
                stopped = server.live_fm.stop(wait=True)
                self.assertFalse(stopped["active"])
                self.assertFalse(server.live_fm.closed)
                self.assertFalse(server.live_tv.closed)
                self.assertFalse(server.survey._closed)
                self.assertEqual(server.lifecycle, "RUNNING")
            finally:
                server.server_close()


class HTTPQuitRaceTests(unittest.TestCase):
    @staticmethod
    def send(server, route, payload):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=4)
        try:
            body = json.dumps(payload).encode()
            conn.request("POST", route, body=body, headers={
                "Content-Type": "application/json",
                "X-Tihulu-CSRF": server.csrf_token,
            })
            res = conn.getresponse()
            return res.status, json.loads(res.read())
        finally:
            conn.close()

    def test_full_quit_does_not_deadlock_behind_blocked_local_translation(self):
        with tempfile.TemporaryDirectory() as td:
            server = LocalServer(("127.0.0.1", 0), Store(Path(td) / "test.sqlite"))
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            entered, release = threading.Event(), threading.Event()
            translated = []

            def fake_translation(*args, **kwargs):
                entered.set()
                release.wait(timeout=5)
                return "fixture result"

            with patch("textcenter.http_app.translate_offline", side_effect=fake_translation), \
                 patch("os.killpg", side_effect=AssertionError("external process touched")):
                thread = threading.Thread(target=lambda: translated.append(self.send(
                    server, "/api/translation/text",
                    {"text": "fixture", "source": "de", "target": "en"})))
                try:
                    thread.start()
                    self.assertTrue(entered.wait(timeout=2))
                    status, response = self.send(server, "/api/quit", {})
                    self.assertEqual(status, 202)
                    self.assertEqual(response["lifecycle"], "STOPPING")
                    report = server.close_owned()
                    self.assertEqual(report["lifecycle"], "STOP_FAILED_PARTIAL", report)
                    self.assertTrue(any("in-process request" in e for e in report["errors"]))
                finally:
                    release.set()
                    thread.join(timeout=3)
                    server.shutdown()
                    server.server_close()
                    server_thread.join(timeout=3)
                self.assertFalse(thread.is_alive())
                self.assertFalse(server_thread.is_alive())


class DecoderLeaseTimeoutTests(unittest.TestCase):
    def test_rds_survey_and_preview_refuse_false_success_for_unreaped_children(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            store = Store(base / "records.sqlite")
            rds = FMRSDSupervisor(store, inventory=lambda: {},
                                  conflicts=lambda: [], lookup=lambda _: None)
            survey = FMSurveySupervisor(inventory=lambda: {}, conflicts=lambda: [],
                                        lookup=lambda _: None)
            preview = FMPreview(inventory=lambda: {}, conflicts=lambda: [],
                                lookup=lambda _: None)
            owned_rds = OwnedChild(unresponsive=True)
            owned_scan = OwnedChild(unresponsive=True)
            owned_preview = OwnedChild(unresponsive=True)
            foreign = OwnedChild()
            rds._rtlfm = owned_rds
            survey._process = owned_scan
            preview._process = owned_preview
            with patch("os.killpg", side_effect=AssertionError("global service kill")):
                for module, handle_name, owned in (
                    (rds, "_rtlfm", owned_rds),
                    (survey, "_process", owned_scan),
                    (preview, "_process", owned_preview),
                ):
                    report = module.quit()
                    self.assertEqual(report["status"], "stop_failed_partial", report)
                    self.assertIs(getattr(module, handle_name), owned)
                    self.assertGreaterEqual(owned.terminations, 1)
                    self.assertGreaterEqual(owned.kills, 1)
                    owned._alive = False
                    self.assertEqual(module.stop(wait=True)["status"], "stopped")
                    self.assertIsNone(getattr(module, handle_name))
            self.assertEqual(foreign.terminations, 0)
            self.assertEqual(foreign.kills, 0)

    def test_http_quit_reports_unreaped_owned_radio_subprocess(self):
        with tempfile.TemporaryDirectory() as td:
            server = LocalServer(("127.0.0.1", 0), Store(Path(td) / "test.sqlite"))
            owned = OwnedChild(unresponsive=True)
            external = OwnedChild()
            server.rds._rtlfm = owned
            try:
                with patch("os.killpg", side_effect=AssertionError("must never touch service")):
                    report = server.close_owned()
                self.assertEqual(report["lifecycle"], "STOP_FAILED_PARTIAL", report)
                self.assertTrue(any("fm_rds" in e for e in report["errors"]))
                self.assertIs(server.rds._rtlfm, owned)
                self.assertEqual(external.terminations, 0)
                self.assertEqual(external.kills, 0)
                self.assertEqual(server.close_owned(), report)
            finally:
                server.server_close()


if __name__ == "__main__":
    unittest.main()
