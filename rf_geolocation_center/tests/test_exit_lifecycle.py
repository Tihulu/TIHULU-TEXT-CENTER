"""EXIT-01 RF Geolocation: strictly synthetic owned DVB subprocess and HTTP shutdown.

No real DVB frontend, SDR, readsb/tar1090, port binding, sudo or model workload.
"""
import unittest
from unittest.mock import patch

from rf_geolocation_center.dvb_bridge import DVBScanBridge, DEFAULT_PROFILE
from rf_geolocation_center.native import run_owned_server


class FakeProcess:
    def __init__(self, terminate_exits=True):
        self.terminate_exits = terminate_exits
        self.exited = False
        self.terminated = 0
        self.killed = 0

    def poll(self):
        return 0 if self.exited else None

    def terminate(self):
        self.terminated += 1
        if self.terminate_exits:
            self.exited = True

    def kill(self):
        self.killed += 1
        self.exited = True


class FakeWorker:
    def __init__(self, process):
        self.process = process
        self.joined = 0

    def is_alive(self):
        return not self.process.exited

    def join(self, timeout):
        self.joined += 1


class ExitLifecycleTests(unittest.TestCase):
    def test_owner_grant_blocks_other_clients_and_closes_only_own_child(self):
        scanner = DVBScanBridge()
        scanner._owner = "a" * 48
        scanner._data["state"] = "RUNNING"
        owned, foreign = FakeProcess(), FakeProcess()
        scanner._process = owned
        scanner._worker = FakeWorker(owned)
        with self.assertRaisesRegex(PermissionError, "another client"):
            scanner.stop(owner="b" * 48)
        self.assertEqual(owned.terminated, 0)
        self.assertEqual(foreign.terminated, 0)
        self.assertEqual(scanner.stop(owner="a" * 48)["state"], "STOPPING")
        self.assertEqual(owned.terminated, 1)
        output = scanner.shutdown(timeout=0.1)
        self.assertEqual(output["state"], "STOPPED")
        self.assertFalse(output["owned_worker_alive"])
        self.assertFalse(output["owned_process_alive"])
        self.assertEqual(foreign.terminated, 0)
        self.assertEqual(foreign.killed, 0)
        self.assertEqual(scanner.token, "")
        self.assertEqual(scanner.shutdown()["state"], "STOPPED")

    def test_bounded_escalation_targets_only_tracked_owned_child(self):
        scanner = DVBScanBridge()
        scanner._data["state"] = "RUNNING"
        owned, foreign = FakeProcess(terminate_exits=False), FakeProcess()
        scanner._process = owned
        scanner._worker = FakeWorker(owned)
        output = scanner.shutdown(timeout=0)
        self.assertEqual(output["state"], "STOPPED")
        self.assertEqual(owned.terminated, 1)
        self.assertEqual(owned.killed, 1)
        self.assertEqual(foreign.terminated, 0)
        self.assertEqual(foreign.killed, 0)

    def test_shutdown_denies_future_start_and_never_launches_late_child(self):
        scanner = DVBScanBridge()
        self.assertEqual(scanner.shutdown()["state"], "STOPPED")
        with patch("rf_geolocation_center.dvb_bridge.adapters",
                   return_value=[{"adapter": 0}]), \
             patch("rf_geolocation_center.dvb_bridge.shutil.which",
                   return_value="/mock/dvbv5-scan"), \
             patch("rf_geolocation_center.dvb_bridge.subprocess.Popen") as popen:
            with self.assertRaisesRegex(RuntimeError, "shutting down"):
                scanner.start(0, DEFAULT_PROFILE, owner="f" * 48)
            scanner._run(0, DEFAULT_PROFILE, [], scanner._cancel)
            popen.assert_not_called()

    def test_native_server_quit_closes_only_own_server_and_bridge(self):
        class FakeServer:
            closed = 0

            def serve_forever(self, poll_interval):
                self.poll_interval = poll_interval
                raise KeyboardInterrupt()

            def server_close(self):
                self.closed += 1

        class FakeBridge:
            calls = 0

            def shutdown(self, timeout):
                self.calls += 1
                self.timeout = timeout
                return {"state": "STOPPED", "owned_worker_alive": False,
                        "owned_process_alive": False}

        server, bridge = FakeServer(), FakeBridge()
        self.assertEqual(run_owned_server(server, bridge)["state"], "STOPPED")
        self.assertEqual(server.closed, 1)
        self.assertEqual(bridge.calls, 1)
        self.assertEqual(bridge.timeout, 3.0)

    def test_incomplete_shutdown_reports_partial_without_killing_other_processes(self):
        class ForeverWorker:
            def is_alive(self):
                return True
            def join(self, timeout):
                pass

        scanner = DVBScanBridge()
        scanner._worker = ForeverWorker()
        scanner._data["state"] = "RUNNING"
        output = scanner.shutdown(timeout=0)
        self.assertEqual(output["state"], "STOP_FAILED_PARTIAL")
        self.assertTrue(output["owned_worker_alive"])


if __name__ == "__main__":
    unittest.main()
