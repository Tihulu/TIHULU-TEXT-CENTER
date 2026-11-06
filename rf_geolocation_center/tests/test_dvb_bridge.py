"""DVB bridge tests use synthetic channel files and a loopback HTTP server only."""
import contextlib
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from rf_geolocation_center.dvb_bridge import (
    DVBScanBridge, _build_uhf_table, parse_channels, profiles, DEFAULT_PROFILE)
from rf_geolocation_center.native import DVB, LocalAppHandler


class DVBBridgeTests(unittest.TestCase):
    def test_uhf_european_profile_contains_only_unverified_tuning_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "test.conf"
            _build_uhf_table(output)
            text = output.read_text()
            self.assertEqual(text.count("DELIVERY_SYSTEM = DVBT2"), 28)
            self.assertIn("FREQUENCY = 474000000", text)
            self.assertIn("FREQUENCY = 690000000", text)
        self.assertEqual(profiles()[0]["id"], DEFAULT_PROFILE)

    def test_real_dvbv5_file_parser_not_a_location_fix(self):
        fake_native_export = "\n".join([
            "[WDR Fernsehen HD]",
            "DELIVERY_SYSTEM = DVBT2", "FREQUENCY = 514000000",
            "SERVICE_ID = 1234", "NETWORK_ID = 77", "TRANSPORT_ID = 88",
            "[Regional Radio]", "FREQUENCY = 514000000", "SERVICE_ID = 1235",
            "[No frequency]", "SERVICE_ID = 1236",
        ])
        channels = parse_channels(fake_native_export)
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels[0]["frequencyMHz"], 514)
        self.assertEqual(channels[0]["serviceId"], 1234)
        self.assertEqual(channels[0]["networkId"], 77)
        self.assertEqual(channels[0]["hardwareReceived"], True)
        self.assertEqual(channels[0]["transmitterIdentified"], False)
        self.assertEqual(channels[0]["positionFix"], False)
        self.assertEqual(parse_channels("[Not scanned]\nSERVICE_ID = 5"), [])

    def test_reject_unknown_adapter_before_spawning_any_process(self):
        bridge = DVBScanBridge()
        with patch("rf_geolocation_center.dvb_bridge.adapters", return_value=[]):
            with self.assertRaisesRegex(ValueError, "frontend not found"):
                bridge.start(0, DEFAULT_PROFILE)
            with self.assertRaisesRegex(ValueError, "valid enumerated"):
                bridge.start("../root", DEFAULT_PROFILE)
        self.assertEqual(bridge.status()["state"], "IDLE")

    def test_pairing_requires_explicit_local_approval_and_pages_opt_in(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), LocalAppHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        from urllib.parse import urlencode
        root = "http://127.0.0.1:" + str(server.server_address[1])
        nonce = "a" * 48
        def request(origin, challenge=nonce):
            query = urlencode({"origin": origin, "nonce": challenge})
            return urlopen(root + "/pair?" + query, timeout=3)
        with self.assertRaises(HTTPError) as err:
            request("pages")
        self.assertEqual(err.exception.code, 403)
        with self.assertRaises(HTTPError) as err:
            request("pages", "invalid")
        self.assertEqual(err.exception.code, 400)
        with self.assertRaises(HTTPError) as err:
            request("untrusted")
        self.assertEqual(err.exception.code, 403)
        with patch("rf_geolocation_center.native.PAGES_BRIDGE_ENABLED", True):
            with contextlib.closing(request("pages")) as response:
                body = response.read().decode()
                self.assertIn("Approve this tab", body)
                self.assertIn("window.opener.postMessage", body)
                self.assertIn("https://tihulu.github.io", body)
                self.assertIn(nonce, body)
                self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
                self.assertEqual(response.headers["Cache-Control"], "no-store")
            with contextlib.closing(request("local")) as response:
                body = response.read().decode()
                self.assertIn(root, body)
            with contextlib.closing(urlopen(root + "/pair?origin=local&from=localhost&nonce=" + nonce,
                                            timeout=3)) as response:
                self.assertIn("http://localhost:", response.read().decode())
            with self.assertRaises(HTTPError) as err:
                request("evil.example")
            self.assertEqual(err.exception.code, 403)

    def test_api_token_origin_and_cors_guards(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), LocalAppHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        root = "http://127.0.0.1:" + str(server.server_address[1])
        good_origin = "http://127.0.0.1:" + str(server.server_address[1])
        def get(headers):
            request = Request(root + "/api/dvb/capabilities", headers=headers)
            return urlopen(request, timeout=3)
        with self.assertRaises(HTTPError) as err:
            get({"Origin": good_origin})
        self.assertEqual(err.exception.code, 403)
        with self.assertRaises(HTTPError) as err:
            get({"Origin": "https://untrusted.example",
                 "X-Tihulu-Bridge-Token": DVB.token})
        self.assertEqual(err.exception.code, 403)
        with contextlib.closing(get({"Origin": good_origin,
                                     "X-Tihulu-Bridge-Token": DVB.token})) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), good_origin)
            self.assertIn(b"adapters", response.read())
        opt = Request(root + "/api/dvb/capabilities", method="OPTIONS",
                      headers={"Origin": "https://tihulu.github.io",
                               "Access-Control-Request-Headers": "x-tihulu-bridge-token"})
        with self.assertRaises(HTTPError) as err:
            urlopen(opt, timeout=3)
        self.assertEqual(err.exception.code, 403)
        with patch("rf_geolocation_center.native.PAGES_BRIDGE_ENABLED", True):
            with contextlib.closing(urlopen(opt, timeout=3)) as response:
                self.assertEqual(response.status, 204)
                self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://tihulu.github.io")
            private_opt = Request(root + "/api/dvb/capabilities", method="OPTIONS",
                    headers={"Origin": "https://tihulu.github.io",
                             "Access-Control-Request-Private-Network": "true"})
            with contextlib.closing(urlopen(private_opt, timeout=3)) as response:
                self.assertEqual(response.headers.get("Access-Control-Allow-Private-Network"), "true")
            request = Request(root + "/api/dvb/scan", method="POST",
                              headers={"Origin": "https://tihulu.github.io",
                                       "X-Tihulu-Bridge-Token": DVB.token,
                                       "Content-Type": "application/json"},
                              data=b'{"adapter":99,"profile":"eu-uhf-t2"}')
            with self.assertRaises(HTTPError) as err:
                urlopen(request, timeout=3)
            self.assertEqual(err.exception.code, 400)
        self.assertEqual(DVB.status()["state"], "IDLE")


if __name__ == "__main__":
    unittest.main()
