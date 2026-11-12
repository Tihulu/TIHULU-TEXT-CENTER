"""STAND-TEXT: isolated Linux single-app CLI/web and storage smoke tests.

Copy ONLY canonical textcenter/ and web/ source trees. This is not a package
installer or a Windows/macOS/Raspberry Pi hardware/native GUI acceptance test.
No actual SDR, tuner, GNSS, optional decoder, model, or foreign service runs.
"""
import http.client
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from textcenter.core import Store
from textcenter.dab_bridge import DABError
from textcenter.fm_audio import AudioError
from textcenter.fm_rds import CaptureError
from textcenter.fm_survey import SurveyError
from textcenter.http_app import LocalServer
from textcenter.live_fm import LiveError


ROOT = Path(__file__).resolve().parents[1]
ISOLATED_ENTRY = """
import builtins
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

root, port, db = sys.argv[1:]
sys.path.insert(0, root)
forbidden = (
    "tv_center", "kaffeine_next", "flight_radar", "tihulu_flight_radar",
    "satellite_center", "rf_geolocation", "geo_center",
    "tihulu_survival_kit", "tihulu_ai_tools", "apps",
)
original_import = builtins.__import__
def no_other_application(name, *args, **kwargs):
    if any(name == item or name.startswith(item + ".") for item in forbidden):
        raise AssertionError("Standalone Text imported foreign application: " + name)
    return original_import(name, *args, **kwargs)

sys.argv = ["textcenter", "serve", "--host", "127.0.0.1",
            "--port", port, "--db", db]
with patch("builtins.__import__", side_effect=no_other_application):
    runpy.run_module("textcenter", run_name="__main__")
"""


def get_json(port, route):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1.5)
    try:
        connection.request("GET", route)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


class StandaloneTextSmokeTests(unittest.TestCase):
    def test_single_app_cli_serve_loads_ui_from_isolated_source_tree(self):
        # Unlike import-only cleanroom tests, this launches the REAL CLI
        # serve entry point and requests real HTTP static assets/API.
        with tempfile.TemporaryDirectory(prefix="stand-text-cleanroom-") as td:
            base = Path(td)
            only_text = base / "only-text"
            only_text.mkdir()
            shutil.copytree(ROOT / "textcenter", only_text / "textcenter")
            shutil.copytree(ROOT / "web", only_text / "web")
            self.assertEqual(sorted(p.name for p in only_text.iterdir()),
                             ["textcenter", "web"])
            state_db = base / "owned-state" / "text-center.sqlite"
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            process = subprocess.Popen(
                [sys.executable, "-I", "-c", ISOLATED_ENTRY, str(only_text),
                 str(port), str(state_db)],
                cwd=base, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )
            try:
                ready = False
                for _ in range(80):
                    if process.poll() is not None:
                        break
                    try:
                        status, body = get_json(port, "/api/bootstrap")
                        if status == 200:
                            ready = True
                            break
                    except (OSError, http.client.HTTPException):
                        time.sleep(0.05)
                self.assertTrue(ready, "Isolated Python CLI service never started")
                bootstrap = json.loads(body)
                self.assertEqual(bootstrap["mode"], "local_offline_first")
                self.assertFalse(bootstrap["background_refresh"])
                self.assertEqual(bootstrap["radio_receiver"], "not_connected")
                self.assertEqual(bootstrap["dvb_receiver"], "not_connected")
                self.assertEqual(get_json(port, "/")[0], 200)
                self.assertIn(b"TIHULU TEXT CENTER", get_json(port, "/")[1])
                self.assertEqual(get_json(port, "/assets/app.js")[0], 200)
                self.assertEqual(get_json(port, "/assets/styles.css")[0], 200)
                self.assertEqual(get_json(port, "/favicon.svg")[0], 200)
                self.assertFalse(json.loads(get_json(port, "/api/dab/last")[1])["connected"])
                self.assertEqual(json.loads(get_json(port, "/api/live/tv/channels")[1])["channels"], [])
                self.assertTrue(state_db.is_file())
            finally:
                process.terminate()  # only the child created by this test
                try:
                    process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=3)
            self.assertEqual(process.poll() is not None, True)

    def test_two_isolated_instances_have_distinct_ports_and_sqlite_ownership(self):
        # Independent Text instances share no implicit database, token, or
        # HTTP listener, and closing one leaves the other responsive.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            foreign = base / "other-app" / "do-not-touch.txt"
            foreign.parent.mkdir()
            foreign.write_bytes(b"foreign user data remains intact")
            one = LocalServer(("127.0.0.1", 0), Store(base / "text-one" / "text.sqlite"))
            two = LocalServer(("127.0.0.1", 0), Store(base / "text-two" / "text.sqlite"))
            thread_one = threading.Thread(target=one.serve_forever, daemon=True)
            thread_two = threading.Thread(target=two.serve_forever, daemon=True)
            thread_one.start()
            thread_two.start()
            try:
                self.assertNotEqual(one.server_port, two.server_port)
                self.assertNotEqual(one.csrf_token, two.csrf_token)
                one.store.add_bulletin("Text One", "Local-only", "fixture")
                status_a, body_a = get_json(one.server_port, "/api/bootstrap")
                status_b, body_b = get_json(two.server_port, "/api/bootstrap")
                self.assertEqual((status_a, status_b), (200, 200))
                self.assertEqual(json.loads(body_a)["counts"]["bulletins"], 1)
                self.assertEqual(json.loads(body_b)["counts"]["bulletins"], 0)
                one.shutdown()
                one.server_close()
                thread_one.join(timeout=3)
                self.assertFalse(thread_one.is_alive())
                self.assertEqual(get_json(two.server_port, "/")[0], 200)
                self.assertEqual(foreign.read_bytes(), b"foreign user data remains intact")
            finally:
                if thread_one.is_alive():
                    one.shutdown()
                    one.server_close()
                    thread_one.join(timeout=3)
                two.shutdown()
                two.server_close()
                thread_two.join(timeout=3)
            self.assertFalse(thread_two.is_alive())
            self.assertEqual(foreign.read_bytes(), b"foreign user data remains intact")

    def test_absent_optional_rf_dab_tv_providers_fail_closed_without_spawn(self):
        # Unlike existing device-specific fixture tests, all optional
        # providers are absent in one isolated Text application session.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            server = LocalServer(("127.0.0.1", 0), Store(root / "text" / "db.sqlite"))
            missing = lambda: {"platform": "Linux", "rtl_usb_count": 0,
                               "decoders": {}, "dvb_frontends": []}
            for part in (server.rds, server.survey, server.audio, server.live_fm):
                part.inventory = missing
                part.lookup = lambda _: None
                part.conflicts = lambda: []
            server.live_tv.channels_file = root / "no-operator-tv-sources.json"
            server.dab.fetcher = lambda *_: (_ for _ in ()).throw(
                DABError("external welle-cli is not running"))
            try:
                with patch("subprocess.Popen",
                           side_effect=AssertionError("An optional decoder was launched")):
                    self.assertFalse(server.rds.availability()["ready"])
                    self.assertFalse(server.survey.availability("dab")["ready"])
                    self.assertFalse(server.audio.availability()["ready"])
                    self.assertFalse(server.live_fm.availability()["ready"])
                    self.assertFalse(server.live_tv.availability()["ready"])
                    with self.assertRaises(CaptureError):
                        server.rds.start(frequency_mhz=98.6, duration=15)
                    with self.assertRaises(SurveyError):
                        server.survey.start("dab")
                    with self.assertRaises(AudioError):
                        server.audio.start(98.6, 12)
                    with self.assertRaises(LiveError):
                        server.live_fm.start(98.6)
                    with self.assertRaises(DABError):
                        server.dab.refresh()
                self.assertEqual(server.store.counts()["events"], 0)
                self.assertFalse((root / "no-operator-tv-sources.json").exists())
                self.assertFalse((root / "text" / "recordings").exists())
            finally:
                server.server_close()


if __name__ == "__main__":
    unittest.main()
