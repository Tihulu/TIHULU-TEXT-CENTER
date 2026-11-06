"""No-radio native cross-platform launcher tests.

All network tests bind only to 127.0.0.1; never LAN, USB or GNSS receivers.
"""
from __future__ import annotations
import contextlib
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import unittest

from rf_geolocation_center.native import ASSETS, LocalAppHandler, safe_asset, doctor


class AppServerTests(unittest.TestCase):
    def test_static_allowlist_and_no_repo_leak(self):
        self.assertIsNotNone(safe_asset("/index.html"))
        self.assertIsNotNone(safe_asset("/web/app.mjs"))
        self.assertIsNotNone(safe_asset("/core/gnss.mjs"))
        self.assertIsNone(safe_asset("/../../AGENTS.md"))
        self.assertIsNone(safe_asset("/%2e%2e/%2e%2e/AGENTS.md"))
        self.assertIsNone(safe_asset("/web/../AGENTS.md"))
        self.assertIsNone(safe_asset("/rf_geolocation_center/tests/core.test.mjs"))
        self.assertIsNone(safe_asset("/index.html?owner=secret"))
        self.assertIsNone(safe_asset("/anything/"))
        self.assertGreaterEqual(len(ASSETS), 10)

    def test_capabilities_never_pretend_rf_backend(self):
        d = doctor()
        self.assertEqual(d["rf_receiver"], "NOT IMPLEMENTED")
        self.assertEqual(d["native_gnss_decoder"], "NOT IMPLEMENTED")
        self.assertEqual(d["binding"], "loopback-only when running serve")
        self.assertEqual(d["github_pages_deployed"], "NOT VERIFIED")

    def test_actual_loopback_server_host_and_method_guards(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), LocalAppHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port = server.server_address[1]
        base = "http://127.0.0.1:" + str(port)
        with contextlib.closing(urlopen(base + "/index.html", timeout=3)) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("text/html", response.headers["Content-Type"])
            self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
            self.assertIn(b"RF Geolocation Center", response.read())
        request = Request(base + "/web/app.mjs", method="HEAD")
        with contextlib.closing(urlopen(request, timeout=3)) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"")
        for endpoint in ("/../../AGENTS.md", "/tests/core.test.mjs", "/api/receiver/start"):
            with self.subTest(endpoint=endpoint), self.assertRaises(HTTPError) as cm:
                urlopen(base + endpoint, timeout=3)
            self.assertEqual(cm.exception.code, 404)
        request = Request(base + "/", method="POST", data=b"tx=1")
        with self.assertRaises(HTTPError) as cm:
            urlopen(request, timeout=3)
        self.assertEqual(cm.exception.code, 405)
        evil = Request(base + "/", headers={"Host": "malicious.example"})
        with self.assertRaises(HTTPError) as cm:
            urlopen(evil, timeout=3)
        self.assertEqual(cm.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
