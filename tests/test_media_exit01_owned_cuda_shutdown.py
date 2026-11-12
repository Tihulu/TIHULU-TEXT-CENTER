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


class ShutdownEdgeCaseTests(unittest.TestCase):
    """Additional mock-only full-Quit races and partial-release accounting."""

    def test_failed_force_reap_retains_held_child_for_retry_and_closes_admission(self):
        class DelayedReap(FakeOwnedProcess):
            fail_reap = True

            def wait(self, timeout=None):
                if self.fail_reap:
                    self.events.append(("wait", timeout))
                    raise subprocess.TimeoutExpired("fake-owned-cuda", timeout)
                return super().wait(timeout)

        worker = cuda._PersistentCUDAWorker()
        child = DelayedReap(stubborn=True)
        worker.process = child
        with self.assertRaisesRegex(RuntimeError, "did not exit after kill"):
            worker.close()
        self.assertIs(worker.process, child)
        self.assertTrue(worker._closing.is_set())
        self.assertTrue(child.stdin.closed)
        self.assertTrue(child.stdout.closed)
        self.assertEqual(child.events,
                         ["terminate", ("wait", 3), "kill", ("wait", 2)])
        with mock.patch.object(cuda.subprocess, "Popen") as spawn:
            with self.assertRaisesRegex(RuntimeError, "shutting down"):
                worker.transcribe_details(b"\\x00\\x00", "en", "/fake")
            spawn.assert_not_called()
        child.fail_reap = False
        worker.close()
        self.assertIsNone(worker.process)
        self.assertTrue(child.reaped)
        self.assertEqual(child.events[-1], ("wait", 0.25))

    def test_two_simultaneous_quits_reap_same_held_child_once(self):
        entered = threading.Event()
        release = threading.Event()
        class SlowReap(FakeOwnedProcess):
            def wait(self, timeout=None):
                entered.set()
                if not release.wait(2):
                    raise AssertionError("mock synchronization timeout")
                return super().wait(timeout)
        worker = cuda._PersistentCUDAWorker()
        child = SlowReap()
        worker.process = child
        errors = []
        def quit_once():
            try:
                worker.close()
            except Exception as exc:
                errors.append(exc)
        first = threading.Thread(target=quit_once, daemon=True)
        second = threading.Thread(target=quit_once, daemon=True)
        first.start()
        self.assertTrue(entered.wait(2))
        second.start()
        release.set()
        first.join(timeout=2)
        second.join(timeout=2)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(child.events, ["terminate", ("wait", 3)])
        self.assertTrue(child.reaped)

    def test_quit_during_delayed_popen_reaps_late_owned_child_without_inference(self):
        worker = cuda._PersistentCUDAWorker()
        child = FakeOwnedProcess()
        spawn_entered = threading.Event()
        allow_spawn = threading.Event()
        outcomes = []
        errors = []
        def fake_spawn(*args, **kwargs):
            spawn_entered.set()
            if not allow_spawn.wait(2):
                raise AssertionError("fake Popen was not released")
            return child
        with mock.patch.object(cuda, "FasterWhisperCUDA") as market, \\
                mock.patch.object(cuda.subprocess, "Popen", side_effect=fake_spawn) as spawn:
            market.return_value.installed.return_value = True
            market.return_value.model_dir = Path("/fake-owned")
            market.return_value.python = Path("/mock-python")
            market.return_value.worker_env.return_value = {}
            def infer():
                try:
                    worker.transcribe_details(
                        b"\\x00\\x00", "en", "/fake-owned")
                    outcomes.append("unexpected result")
                except RuntimeError as exc:
                    outcomes.append(str(exc))
            def exit_now():
                try:
                    worker.close()
                except Exception as exc:
                    errors.append(exc)
            t = threading.Thread(target=infer, daemon=True)
            t.start()
            self.assertTrue(spawn_entered.wait(2))
            quitter = threading.Thread(target=exit_now, daemon=True)
            quitter.start()
            self.assertTrue(worker._closing.wait(2))
            allow_spawn.set()
            t.join(timeout=2)
            quitter.join(timeout=2)
            self.assertFalse(t.is_alive())
            self.assertFalse(quitter.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(outcomes, [
                "CUDA Faster-Whisper worker is shutting down"])
            self.assertEqual(spawn.call_count, 1)
            self.assertEqual(child.events, ["terminate", ("wait", 3)])
            self.assertTrue(child.reaped)
            self.assertEqual(child.stdin.writes, [])

    def test_owned_qprocess_benchmark_graceful_and_kill_fallback(self):
        class FakeBenchmark:
            NotRunning = 0
            Running = 1
            def __init__(self, stubborn=False):
                self.running = True
                self.stubborn = stubborn
                self.events = []
            def state(self):
                return self.Running if self.running else self.NotRunning
            def terminate(self):
                self.events.append("terminate")
                if not self.stubborn:
                    self.running = False
            def kill(self):
                self.events.append("kill")
                self.running = False
            def waitForFinished(self, ms):
                self.events.append(("wait", ms))
                return not self.running
        ready = FakeBenchmark(stubborn=False)
        overlay.stop_owned_benchmark_process(ready)
        self.assertEqual(ready.events, ["terminate", ("wait", 3000)])
        stubborn = FakeBenchmark(stubborn=True)
        overlay.stop_owned_benchmark_process(stubborn)
        self.assertEqual(stubborn.events, [
            "terminate", ("wait", 3000), "kill", ("wait", 2000)])
        overlay.stop_owned_benchmark_process(stubborn)
        self.assertEqual(len(stubborn.events), 4)

    def test_unreaped_owned_benchmark_is_reported_without_skipping_other_cleanup(self):
        class UnkillableBenchmark:
            NotRunning = 0
            def state(self):
                return 1
            def terminate(self):
                self.events.append("terminate")
            def kill(self):
                self.events.append("kill")
            def waitForFinished(self, ms):
                self.events.append(("wait", ms))
                return False
        benchmark = UnkillableBenchmark()
        benchmark.events = []
        events = []
        tap = mock.Mock()
        tap.request_stop.side_effect = lambda: events.append("stop")
        tap.close.side_effect = lambda: events.append("join")
        recorder = mock.Mock(active=True)
        recorder.stop.side_effect = lambda: events.append("flush")
        other = [mock.Mock() for _ in range(3)]
        for label, resource in zip(("mobile", "ipc", "control"), other):
            resource.close.side_effect = lambda label=label: events.append(label)
        issues = overlay.shutdown_owned_caption_resources(
            tap, recorder, *other, benchmark_process=benchmark,
            cuda_shutdown=lambda: events.append("cuda"))
        self.assertEqual(benchmark.events, [
            "terminate", ("wait", 3000), "kill", ("wait", 2000)])
        self.assertEqual(events, [
            "stop", "flush", "cuda", "join", "mobile", "ipc", "control"])
        self.assertEqual(len(issues), 1)
        self.assertIn("stop owned AI benchmark", issues[0])
        self.assertIn("still running", issues[0])

    def test_tap_close_clears_private_caption_buffers_and_preserves_foreign_file(self):
        from collections import deque
        from kaffeine_next.continuous_captions import BufferedCaptionQueue
        with tempfile.TemporaryDirectory(prefix="tihulu-owned-socket-") as root:
            foreign = Path(root) / "tihulu-dvb-1.sock"
            foreign.write_bytes(b"foreign session must survive")
            tap = object.__new__(overlay.CaptionTap)
            tap.path = foreign
            tap.stop = threading.Event()
            tap.work_queue = BufferedCaptionQueue()
            tap.work_queue.items.append(object())
            tap.work_queue.bytes = 4096
            tap.sock = None
            tap.thread = None
            tap.worker = None
            tap._owned_socket_identity = (999, 888)  # Not this inode.
            tap.previous_original = "private speech"
            tap.previous_revision = 42
            tap.sentence_session = ("old channel",)
            tap.sentence_captured_start = 123.0
            tap.sentence_joiner = mock.Mock()
            tap._performance_lock = threading.Lock()
            tap._performance_samples = deque([{"private": b"audio"}])
            tap.close()
            self.assertTrue(tap.work_queue.closed)
            self.assertEqual(tap.work_queue.bytes, 0)
            self.assertEqual(len(tap.work_queue.items), 0)
            self.assertEqual(tap.previous_original, "")
            self.assertEqual(tap._performance_samples, deque())
            tap.sentence_joiner.reset.assert_called_once()
            self.assertEqual(foreign.read_bytes(),
                             b"foreign session must survive")

    def test_only_identity_matching_owned_socket_may_be_unlinked(self):
        import os
        import stat
        from types import SimpleNamespace
        tap = object.__new__(overlay.CaptionTap)
        tap.stop = threading.Event()
        tap.work_queue = mock.Mock()
        tap.sock = None
        tap.thread = None
        tap.worker = None
        tap._owned_socket_identity = (123, 456)
        tap.path = Path("/fake-private/caption.sock")
        with mock.patch.object(Path, "lstat", return_value=SimpleNamespace(
                st_dev=123, st_ino=456, st_uid=os.getuid(),
                st_mode=stat.S_IFSOCK)), \\
                mock.patch.object(Path, "unlink") as unlink:
            tap.close()
        unlink.assert_called_once_with()
        self.assertIsNone(tap._owned_socket_identity)

    def test_stalled_decoder_thread_is_reported_as_partial_not_silent_success(self):
        tap = object.__new__(overlay.CaptionTap)
        tap.stop = threading.Event()
        tap.work_queue = mock.Mock()
        tap.sock = None
        tap._owned_socket_identity = None
        tap.path = Path("/fake-private/never-unlink.sock")
        tap.thread = None
        worker = mock.Mock()
        worker.is_alive.return_value = True
        tap.worker = worker
        with self.assertRaisesRegex(RuntimeError,
                                    "Caption shutdown incomplete"):
            tap.close()
        worker.join.assert_called_once_with(timeout=2)
        self.assertTrue(tap.stop.is_set())

    def test_pending_caption_clip_does_not_start_asr_after_stop(self):
        tap = object.__new__(overlay.CaptionTap)
        tap.stop = threading.Event()
        tap.work_queue = mock.Mock()
        def get_and_quit(**_kwargs):
            tap.stop.set()
            return mock.Mock()
        tap.work_queue.get.side_effect = get_and_quit
        tap._decode = mock.Mock(side_effect=AssertionError(
            "ASR launched after Quit"))
        tap._worker()
        tap._decode.assert_not_called()

    def test_benchmark_and_qt_cleanup_are_wired_without_running_qt(self):
        source = inspect.getsource(overlay.main)
        self.assertIn("benchmark_process=benchmark_process", source)
        self.assertIn("benchmark_cancelled = True", source)
        self.assertIn("deferred_captions.clear()", source)
        self.assertIn("events.get_nowait()", source)
        self.assertIn("if window.terminating:", source)


if __name__ == "__main__":
    unittest.main()
