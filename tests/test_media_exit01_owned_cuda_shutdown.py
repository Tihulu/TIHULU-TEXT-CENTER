"""RQ-098 / EXIT-01: fully synthetic Media-owned worker shutdown contracts.

No real GPU, CUDA, FFmpeg, Qt event loop, model download, SDR or host services.
The only processes in these tests are fake Popen objects.
"""
import inspect
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock

from tv_center import cuda_faster_whisper as cuda
from kaffeine_next import captions_overlay as overlay


class FakeStream:
    def __init__(self, result=b""):
        self.result = result
        self.closed = False
        self.writes = []

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def flush(self):
        return None

    def readline(self, limit=-1):
        return self.result[:limit]

    def close(self):
        self.closed = True


class FakeOwnedProcess:
    """Fake subprocess with controllable graceful or forced completion."""

    def __init__(self, *, stubborn=False, exited=False):
        self.stdin = FakeStream()
        self.stdout = FakeStream(
            json.dumps({"text": "late transcript", "words": []}).encode() + b"\n")
        self.stubborn = stubborn
        self.running = not exited
        self.events = []
        self.stopped = threading.Event()
        self.reaped = False

    def poll(self):
        return None if self.running else 0

    def terminate(self):
        self.events.append("terminate")
        if not self.stubborn:
            self.running = False
            self.stopped.set()

    def kill(self):
        self.events.append("kill")
        self.running = False
        self.stopped.set()

    def wait(self, timeout=None):
        self.events.append(("wait", timeout))
        if self.running:
            raise subprocess.TimeoutExpired("fake-owned-cuda-child", timeout)
        self.reaped = True
        return 0


class OwnedCUDAShutdownTests(unittest.TestCase):
    def test_quit_reaps_only_owned_child_and_preserves_weights_on_disk(self):
        with tempfile.TemporaryDirectory(prefix="tihulu-exit01-") as root:
            model = Path(root) / "stored-model.bin"
            model.write_bytes(b"owner kept these immutable weights")
            owned = FakeOwnedProcess()
            foreign = FakeOwnedProcess()
            worker = cuda._PersistentCUDAWorker()
            worker.process = owned
            worker.path = str(model)
            worker.close()
            worker.close()  # atexit or repeated Qt Quit is harmless
            self.assertEqual(owned.events, ["terminate", ("wait", 3)])
            self.assertTrue(owned.reaped)
            self.assertTrue(owned.stdin.closed)
            self.assertTrue(owned.stdout.closed)
            self.assertIsNone(worker.process)
            self.assertIsNone(worker.path)
            self.assertEqual(foreign.events, [])
            self.assertFalse(foreign.reaped)
            self.assertEqual(model.read_bytes(), b"owner kept these immutable weights")

    def test_timeout_escalates_to_kill_and_reaps(self):
        worker = cuda._PersistentCUDAWorker()
        owned = FakeOwnedProcess(stubborn=True)
        worker.process = owned
        worker.close()
        self.assertEqual(owned.events,
                         ["terminate", ("wait", 3), "kill", ("wait", 2)])
        self.assertTrue(owned.reaped)
        self.assertIsNone(worker.process)

    def test_already_exited_child_is_reaped_without_signals(self):
        worker = cuda._PersistentCUDAWorker()
        child = FakeOwnedProcess(exited=True)
        worker.process = child
        worker.close()
        self.assertEqual(child.events, [("wait", 0.25)])
        self.assertTrue(child.reaped)

    def test_quit_rejects_new_inference_without_starting_model(self):
        worker = cuda._PersistentCUDAWorker()
        worker.close()
        with mock.patch.object(cuda, "FasterWhisperCUDA") as market, \
                mock.patch.object(cuda.subprocess, "Popen") as spawn:
            with self.assertRaisesRegex(RuntimeError, "shutting down"):
                worker.transcribe_details(b"\x00\x00", "en", "/fake-model")
            market.assert_not_called()
            spawn.assert_not_called()

    def test_concurrent_quit_interrupts_inflight_inference_without_io_lock_wait(self):
        worker = cuda._PersistentCUDAWorker()
        owned = FakeOwnedProcess()
        ready_for_cancel = threading.Event()
        outcomes = []
        def waiting_select(readers, _write, _errors, _timeout):
            ready_for_cancel.set()
            self.assertTrue(owned.stopped.wait(2), "Quit must stop the owned child")
            return readers, [], []
        with mock.patch.object(cuda, "FasterWhisperCUDA") as market, \
                mock.patch.object(cuda.subprocess, "Popen", return_value=owned) as spawn, \
                mock.patch.object(cuda.select, "select", side_effect=waiting_select):
            market.return_value.installed.return_value = True
            market.return_value.model_dir = Path("/fake-verified-model")
            market.return_value.python = Path("/fake-python")
            market.return_value.worker_env.return_value = {}
            def infer():
                try:
                    worker.transcribe_details(
                        b"\x00\x00\x00\x00", "en", "/fake-verified-model")
                    outcomes.append("unexpected inference after Quit")
                except RuntimeError as exc:
                    outcomes.append(str(exc))
            thread = threading.Thread(target=infer, daemon=True)
            thread.start()
            self.assertTrue(ready_for_cancel.wait(2), "Fake inference did not start")
            started = time.monotonic()
            worker.close()
            self.assertLess(time.monotonic()-started, 1.5)
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(spawn.call_count, 1)
            self.assertTrue(owned.reaped)
            self.assertEqual(outcomes, ["CUDA Faster-Whisper worker is shutting down"])
            with self.assertRaisesRegex(RuntimeError, "shutting down"):
                worker.transcribe_details(
                    b"\x00\x00", "en", "/fake-verified-model")
            self.assertEqual(spawn.call_count, 1)

    def test_process_exit_and_shutdown_are_global_only_within_this_python_process(self):
        worker = cuda._PersistentCUDAWorker()
        child = FakeOwnedProcess()
        worker.process = child
        with mock.patch.object(cuda, "_worker", worker):
            cuda.shutdown_cuda_worker()
            cuda.shutdown_cuda_worker()
        self.assertEqual(child.events, ["terminate", ("wait", 3)])
        self.assertTrue(child.reaped)


class CaptionExitContracts(unittest.TestCase):
    def test_shutdown_stops_new_capture_then_flushes_and_unloads_before_join(self):
        events = []
        class Object:
            pass
        tap = Object()
        tap.request_stop = lambda: events.append("stop intake")
        tap.close = lambda: events.append("join thread")
        recorder = Object()
        recorder.active = True
        recorder.stop = lambda: events.append("flush SRT")
        mobile = Object()
        mobile.close = lambda: events.append("mobile")
        ipc = Object()
        ipc.close = lambda: events.append("ipc")
        control = Object()
        control.close = lambda: events.append("control")
        errors = overlay.shutdown_owned_caption_resources(
            tap, recorder, mobile, ipc, control,
            cuda_shutdown=lambda: events.append("terminate owned CUDA"))
        self.assertEqual(errors, [])
        self.assertEqual(events, [
            "stop intake", "flush SRT", "terminate owned CUDA",
            "join thread", "mobile", "ipc", "control"])

    def test_cleanup_failure_cannot_skip_owned_cuda_or_other_closes(self):
        events = []
        class Resource:
            def __init__(self, label, failure=False):
                self.label = label
                self.failure = failure
            def close(self):
                events.append(self.label)
                if self.failure:
                    raise OSError("synthetic failure")
        tap = Resource("tap")
        tap.request_stop = lambda: events.append("stop")
        recorder = Resource("SRT", failure=True)
        recorder.active = True
        recorder.stop = recorder.close
        errors = overlay.shutdown_owned_caption_resources(
            tap, recorder, Resource("mobile"), Resource("ipc"),
            Resource("control"), cuda_shutdown=lambda: events.append("cuda"))
        self.assertEqual(events,
                         ["stop", "SRT", "cuda", "tap", "mobile", "ipc", "control"])
        self.assertEqual(len(errors), 1)
        self.assertIn("flush original SRT", errors[0])

    def test_caption_tap_refuses_decode_after_stop_without_loading_models(self):
        tap = object.__new__(overlay.CaptionTap)
        tap.stop = threading.Event()
        tap.stop.set()
        with mock.patch("tv_center.ai_settings.AISettings") as ai:
            result = tap._decode(b"transport", {}, 0.0, 1.0)
        self.assertIsNone(result)
        ai.assert_not_called()

    def test_caption_tap_request_stop_is_idempotent_no_foreign_process_access(self):
        tap = object.__new__(overlay.CaptionTap)
        tap.stop = threading.Event()
        tap.work_queue = mock.Mock()
        tap.sock = mock.Mock()
        tap.request_stop()
        tap.request_stop()
        self.assertTrue(tap.stop.is_set())
        self.assertEqual(tap.work_queue.close.call_count, 2)
        self.assertEqual(tap.sock.close.call_count, 2)

    def test_both_explicit_exit_and_tray_quit_reach_before_qt_teardown(self):
        source = inspect.getsource(overlay.main)
        self.assertIn("app.aboutToQuit.connect(cleanup)", source)
        self.assertIn("quit_action.triggered.connect(app.quit)", source)
        self.assertIn("exit_subtitles.clicked.connect(stop_caption_service)", source)
        self.assertIn("shutdown_owned_caption_resources(", source)
        self.assertIn("timer.stop()", source)


if __name__ == "__main__":
    unittest.main()
