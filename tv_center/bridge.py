"""Token-free local web TV companion, bound only to 127.0.0.1.

The desktop app starts this same-origin browser UI automatically. A GitHub Pages
landing page can check a public, non-sensitive /api/health endpoint and link
to the local companion without copying a token.

SECURITY: privileged API requests and static assets are available ONLY on the
loopback host with a valid Host header. Cross-origin Github Pages requests are
only allowed to /api/health; cross-origin operations are *never* authorized.
No LAN listener, no wildcard CORS, no authorization header or shared secret.
Other devices use the separate, explicitly enabled PIN-paired MobileLAN server.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import json
import re
import threading

PAGES_ORIGIN = "https://tihulu.github.io"
WEB_ASSETS = frozenset({
    "index.html", "app.js", "web-controls.js", "scan-ui-state.js",
    "style.css", "webusb-ui.js", "webusb-em28xx.js", "ts-analyzer.js",
    "browser-ai-ui.js", "browser-ai-worker.js",
    "em28xx-driver-plan.js", "webusb-driver-ui.js", "wasm-ts-preview.js",
})
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


class TVBridge:
    def __init__(self, snapshot, change_page, host="127.0.0.1",
                 port=8768, commands=None, stream_dir=None):
        if host != "127.0.0.1":
            raise ValueError("Token-free companion must bind to 127.0.0.1 only")
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("Invalid local companion port")
        self.snapshot = snapshot
        self.change_page = change_page
        self.commands = commands
        self.stream_dir = stream_dir
        self.host, self.port = host, port
        self.httpd = None
        self.thread = None

    def start(self):
        if self.httpd:
            raise RuntimeError("Local TV companion already started")
        bridge = self
        root = Path(__file__).resolve().parent / "web"

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def allowed_host(self):
                host = self.headers.get("Host", "")
                port = bridge.httpd.server_port
                return host in (f"127.0.0.1:{port}", f"localhost:{port}")

            def local_request(self):
                if not self.allowed_host():
                    return False
                origin = self.headers.get("Origin")
                accepted = (f"http://127.0.0.1:{bridge.httpd.server_port}",
                            f"http://localhost:{bridge.httpd.server_port}")
                if origin is not None and origin not in accepted:
                    return False
                # Reject foreign-site simple requests even when Origin is omitted.
                site = self.headers.get("Sec-Fetch-Site", "")
                return site in ("", "none", "same-origin")

            def headers_safe(self, health=False):
                if health and self.headers.get("Origin") == PAGES_ORIGIN:
                    self.send_header("Access-Control-Allow-Origin", PAGES_ORIGIN)
                    self.send_header("Access-Control-Allow-Private-Network", "true")
                    self.send_header("Vary", "Origin")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Cross-Origin-Resource-Policy", "same-origin")
                self.send_header("Content-Security-Policy",
                    "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; "
                    "script-src 'self' https://cdn.jsdelivr.net; "
                    "connect-src 'self' https://cdn.jsdelivr.net https://*.jsdelivr.net "
                    "https://huggingface.co https://*.huggingface.co https://*.hf.co; "
                    "img-src 'self' data:; media-src 'self' blob:; "
                    "style-src 'self' 'unsafe-inline'; worker-src 'self' blob:")

            def reply(self, status, obj, health=False):
                raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.headers_safe(health=health)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_OPTIONS(self):
                # Pages can test reachability, but cannot issue privileged API
                # preflight requests or use wildcard/origin-based permissions.
                if not self.allowed_host():
                    return self.reply(403, {"error": "Invalid Host"})
                if self.path != "/api/health":
                    return self.reply(403, {"error": "Cross-origin controls forbidden"})
                if self.headers.get("Origin") != PAGES_ORIGIN:
                    return self.reply(403, {"error": "Origin not allowed"})
                self.send_response(204)
                self.headers_safe(health=True)
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def send_asset(self, name):
                if name not in WEB_ASSETS:
                    return self.reply(404, {"error": "Unknown asset"})
                file = root / name
                if not file.is_file():
                    return self.reply(404, {"error": "Web asset not installed"})
                if file.stat().st_size > 2_000_000:
                    return self.reply(413, {"error": "Asset too large"})
                raw = file.read_bytes()
                self.send_response(200)
                self.headers_safe()
                self.send_header("Content-Type", MIME[file.suffix])
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def serve_hls(self, name):
                if not bridge.stream_dir:
                    return self.reply(404, {"error": "HLS disabled"})
                if name != "index.m3u8" and not re.fullmatch(r"segment_\d{6}\.ts", name):
                    return self.reply(404, {"error": "Invalid HLS path"})
                folder = bridge.stream_dir()
                if not folder:
                    return self.reply(404, {"error": "HLS encoder not enabled"})
                file = Path(folder) / name
                if not file.is_file() or file.stat().st_size > 20_000_000:
                    return self.reply(404, {"error": "HLS segment unavailable"})
                raw = file.read_bytes()
                self.send_response(200)
                self.headers_safe()
                self.send_header("Content-Type",
                    "application/vnd.apple.mpegurl" if name.endswith(".m3u8")
                    else "video/mp2t")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                if not self.allowed_host():
                    return self.reply(403, {"error": "Invalid Host"})
                path = urlsplit(self.path).path
                if path == "/api/health":
                    # Public/non-sensitive reachability check for Pages button.
                    if not self.local_request() and self.headers.get("Origin") != PAGES_ORIGIN:
                        return self.reply(403, {"error": "Origin not allowed"})
                    return self.reply(200, {
                        "app": "tihulu-tv-center",
                        "mode": "tokenless_loopback",
                        "ready": True,
                        "url": f"http://127.0.0.1:{bridge.httpd.server_port}/"
                    }, health=True)
                if not self.local_request():
                    return self.reply(403, {"error": "Privileged API requires local origin"})
                if path in ("/api/status", "/api/channels", "/api/scan", "/api/models"):
                    if path == "/api/status":
                        return self.reply(200, bridge.snapshot())
                    if not bridge.commands:
                        return self.reply(503, {"error": "Local TV commands not available"})
                    action = {"/api/channels": "channels", "/api/scan": "scan_status",
                              "/api/models": "models"}[path]
                    try:
                        return self.reply(200, bridge.commands(action, {}))
                    except (RuntimeError, ValueError, TimeoutError) as exc:
                        return self.reply(503, {"error": str(exc)[:250]})
                if path.startswith("/hls/"):
                    return self.serve_hls(path[5:])
                if path == "/":
                    return self.send_asset("index.html")
                return self.send_asset(path.removeprefix("/"))

            def do_POST(self):
                if not self.local_request():
                    return self.reply(403, {"error": "Privileged API requires local origin"})
                path = urlsplit(self.path).path
                if path not in ("/api/command", "/api/teletext"):
                    return self.reply(404, {"error": "Unknown route"})
                if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                    return self.reply(415, {"error": "JSON required"})
                size = self.headers.get("Content-Length", "")
                if not size.isdigit() or not 0 < int(size) <= 2048:
                    return self.reply(413, {"error": "Invalid request size"})
                try:
                    data = json.loads(self.rfile.read(int(size)))
                    if not isinstance(data, dict):
                        raise ValueError("Expected JSON object")
                    if path == "/api/teletext":
                        page = data.get("page")
                        if type(page) is not int or not 100 <= page <= 899:
                            raise ValueError("Teletext page must be 100–899")
                        bridge.change_page(page)
                        return self.reply(200, {"page": page, "status": "requested"})
                    action, params = data.get("action"), data.get("params", {})
                    if not isinstance(action, str) or not isinstance(params, dict):
                        raise ValueError("Expected action and params")
                    if not bridge.commands:
                        return self.reply(503, {"error": "Local TV commands unavailable"})
                    result = bridge.commands(action, params)
                    return self.reply(200, {"ok": True, "result": result})
                except (ValueError, TypeError, KeyError) as exc:
                    return self.reply(400, {"error": str(exc)[:250]})
                except (RuntimeError, TimeoutError) as exc:
                    return self.reply(503, {"error": str(exc)[:250]})

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       name="tihulu-tv-tokenless-loopback", daemon=True)
        self.thread.start()
        return {"url": f"http://127.0.0.1:{self.httpd.server_port}/",
                "mode": "tokenless_loopback"}

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
