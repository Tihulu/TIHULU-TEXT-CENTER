"""Portable localhost-only static launcher, not a native SDR/GNSS decoder.

This serves ONLY explicitly allowlisted app shell assets on 127.0.0.1.
No LAN endpoint, automatic downloads, filesystem directory browsing, telemetry,
RF capture, shared SDR lease or Windows driver installation.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import hmac
import secrets
import re
from urllib.parse import parse_qs
from .dvb_bridge import DVBScanBridge
from .radio_metadata import read_local_radio_metadata
import platform
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
ASSETS = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/sw.js": ("sw.js", "text/javascript"),
    "/web/app.mjs": ("web/app.mjs", "text/javascript"),
    "/web/maps.mjs": ("web/maps.mjs", "text/javascript"),
    "/web/receivers.mjs": ("web/receivers.mjs", "text/javascript"),
    "/web/auto_explorer.mjs": ("web/auto_explorer.mjs", "text/javascript"),
    "/web/usb_sdr.mjs": ("web/usb_sdr.mjs", "text/javascript"),
    "/web/rf_survey.mjs": ("web/rf_survey.mjs", "text/javascript"),
    "/web/catalog_discovery.mjs": ("web/catalog_discovery.mjs", "text/javascript"),
    "/web/simple_ui.mjs": ("web/simple_ui.mjs", "text/javascript"),
    "/web/hardware_manager.mjs": ("web/hardware_manager.mjs", "text/javascript"),
    "/web/dvb_bridge_client.mjs": ("web/dvb_bridge_client.mjs", "text/javascript"),
    "/web/style.css": ("web/style.css", "text/css"),
    "/web/icon.svg": ("web/icon.svg", "image/svg+xml"),
    "/core/gnss.mjs": ("core/gnss.mjs", "text/javascript"),
    "/core/positioning.mjs": ("core/positioning.mjs", "text/javascript"),
    "/core/evidence.mjs": ("core/evidence.mjs", "text/javascript"),
    "/core/location_layers.mjs": ("core/location_layers.mjs", "text/javascript"),
    "/core/source_provenance.mjs": ("core/source_provenance.mjs", "text/javascript"),
    "/core/rf_ranging.mjs": ("core/rf_ranging.mjs", "text/javascript"),
    "/core/source_catalog.mjs": ("core/source_catalog.mjs", "text/javascript"),
    "/core/dvb_scan.mjs": ("core/dvb_scan.mjs", "text/javascript"),
    "/core/scan_map.mjs": ("core/scan_map.mjs", "text/javascript"),
    "/scripts/dvb_scan_linux.sh": ("scripts/dvb_scan_linux.sh", "text/plain"),
    "/scripts/usb_prepare_linux.sh": ("scripts/usb_prepare_linux.sh", "text/plain"),
}
CSP = ("default-src 'self'; script-src 'self' https://esm.sh; style-src 'self'; "
       "connect-src 'self' https://esm.sh https://celestrak.org https://celestrak.com "
       "https://overpass-api.de https://opensky-network.org http://127.0.0.1:8794; "
       "img-src 'self' data: https://tile.openstreetmap.org; "
       "frame-src https://www.openstreetmap.org; "
       "worker-src 'self'; manifest-src 'self'; object-src 'none'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


DVB = DVBScanBridge()
PAGES_BRIDGE_ENABLED = False
PAGES_ORIGIN = "https://tihulu.github.io"


def safe_asset(url_path: str):
    """Resolve only fixed app-owned file paths. Never arbitrary repo paths."""
    if not isinstance(url_path, str) or len(url_path) > 2048:
        return None
    url = urlsplit(url_path)
    if url.query or url.fragment:
        return None
    key = unquote(url.path)
    if key not in ASSETS:
        return None
    relative, kind = ASSETS[key]
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
        return None
    return path, kind


class LocalAppHandler(BaseHTTPRequestHandler):
    server_version = "TihuluRFGeo/0.1"
    sys_version = ""

    def _respond(self, head_only: bool):
        # Host validation additionally protects against DNS-rebinding probes.
        host = self.headers.get("Host", "").split(":")[0].lower()
        if host not in ("127.0.0.1", "localhost"):
            self.send_error(403, "Only loopback Host headers supported")
            return
        asset = safe_asset(self.path)
        if asset is None:
            self.send_error(404, "Not an allowed geolocation resource")
            return
        path, kind = asset
        try:
            raw = path.read_bytes()
        except OSError:
            self.send_error(503, "App asset not readable")
            return
        self.send_response(200)
        self.send_header("Content-Type", kind + ("; charset=utf-8" if kind.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        if not head_only:
            self.wfile.write(raw)

    def _pair_page(self):
        """On-device approval; no session token in URLs or third-party pages."""
        host = self.headers.get("Host", "").split(":")[0].lower()
        if host not in ("127.0.0.1", "localhost"):
            self.send_error(403, "Loopback only")
            return
        params = parse_qs(urlsplit(self.path).query)
        nonce = params.get("nonce", [""])[0]
        destination = params.get("origin", [""])[0]
        if not re.fullmatch(r"[A-Za-z0-9_-]{24,100}", nonce):
            self.send_error(400, "Invalid pairing challenge")
            return
        port = self.server.server_address[1]
        if destination == "pages" and PAGES_BRIDGE_ENABLED:
            target = PAGES_ORIGIN
        elif destination == "local":
            # Local UI may have been opened at localhost instead of 127.0.0.1.
            opener_host = params.get("from", ["127.0.0.1"])[0]
            if opener_host not in ("localhost", "127.0.0.1"):
                self.send_error(403, "Unapproved local UI hostname")
                return
            target = "http://" + opener_host + ":" + str(port)
        else:
            self.send_error(403, "This origin is not enabled for local pairing")
            return
        # The explicit click is a local user's approval for this one browser
        # session; the only postMessage recipient is the allowlisted origin.
        script_nonce = secrets.token_urlsafe(20)
        payload = json.dumps({"type": "tihulu:dvb-bridge-paired",
                              "nonce": nonce, "token": DVB.token})
        # Escape every HTML-sensitive character before embedding JSON in script.
        payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        target_js = json.dumps(target)
        js = ("document.getElementById('approve').addEventListener('click',()=>{"
              "if(!window.opener){document.getElementById('status').textContent='Return to TIHULU and try again; opener missing.';return;}"
              "window.opener.postMessage(" + payload + "," + target_js + ");"
              "document.getElementById('status').textContent='Approved for the originating TIHULU tab only. You can close this window.';"
              "window.close();});")
        body = ("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TIHULU local TV pairing</title>
<style>body{font:16px system-ui,sans-serif;color:#e6f7f6;background:#0b1e30;margin:0;padding:36px}
main{max-width:560px;margin:auto;background:#173143;border:1px solid #46748a;border-radius:14px;padding:26px}
button{border:0;border-radius:9px;background:#52c5b6;color:#061f23;padding:13px 22px;font-weight:800;cursor:pointer}
p{line-height:1.6;color:#bed5df}small{color:#9ec9d9}</style></head>
<body><main><h1>Allow local TV tuner access?</h1>
<p>The official TIHULU Geolocation tab is requesting access to the DVB backend on this computer.
Approve only if you started this local service and wish to connect your own TV tuner.</p>
<p><strong>No scan starts now.</strong> TV scans still require a separate button click. Permission is not shared with other websites.</p>
<button id="approve">Approve this tab</button><p id="status">Otherwise just close this window.</p>
<small>Private localhost bridge · no token to copy or paste</small></main>
<script nonce="PAIR_SCRIPT_NONCE">PAIR_SCRIPT_BODY</script></body></html>""").replace("PAIR_SCRIPT_NONCE", script_nonce).replace("PAIR_SCRIPT_BODY", js)
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'nonce-" + script_nonce +
                         "'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def _bridge_origin(self):
        """Authorize only same-origin local UI or opt-in official Pages origin."""
        origin = self.headers.get("Origin")
        port = self.server.server_address[1]
        valid = {"http://127.0.0.1:" + str(port), "http://localhost:" + str(port)}
        if PAGES_BRIDGE_ENABLED:
            valid.add(PAGES_ORIGIN)
        if origin is None:
            return None  # token still required for non-browser clients
        if origin not in valid:
            raise PermissionError("Origin is not approved for local DVB scanner")
        return origin

    def _bridge_headers(self, origin):
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _json(self, status, payload, origin=None):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._bridge_headers(origin)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _authorize_bridge(self):
        host = self.headers.get("Host", "").split(":")[0].lower()
        if host not in ("127.0.0.1", "localhost"):
            raise PermissionError("Loopback Host required")
        origin = self._bridge_origin()
        token = self.headers.get("X-Tihulu-Bridge-Token", "")
        if not hmac.compare_digest(token, DVB.token):
            raise PermissionError("Invalid local DVB bridge session token")
        return origin

    def _api_get(self):
        try:
            origin = self._authorize_bridge()
        except PermissionError as error:
            self._json(403, {"error": str(error)})
            return
        route = urlsplit(self.path).path
        if route == "/api/dvb/capabilities":
            self._json(200, DVB.capabilities(), origin)
        elif route == "/api/dvb/status":
            self._json(200, DVB.status(), origin)
        elif route == "/api/radio/decoded":
            self._json(200, read_local_radio_metadata(), origin)
        else:
            self._json(404, {"error": "Unknown DVB API endpoint"}, origin)

    def _api_post(self):
        try:
            origin = self._authorize_bridge()
        except PermissionError as error:
            self._json(403, {"error": str(error)})
            return
        route = urlsplit(self.path).path
        if route not in ("/api/dvb/scan", "/api/dvb/stop"):
            self._json(404, {"error": "Unknown DVB API endpoint"}, origin)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 2048:
                raise ValueError("Body must be at most 2048 bytes")
            body = self.rfile.read(length) if length else b"{}"
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError("Expected object with adapter and listed profile")
            if route == "/api/dvb/scan":
                result = DVB.start(data.get("adapter"), data.get("profile"))
            else:
                result = DVB.stop()
            self._json(200, result, origin)
        except (ValueError, RuntimeError, TypeError) as error:
            self._json(400, {"error": str(error)}, origin)

    def do_OPTIONS(self):
        if urlsplit(self.path).path not in ("/api/radio/decoded", "/api/dvb/capabilities", "/api/dvb/status",
                                           "/api/dvb/scan", "/api/dvb/stop"):
            self.send_error(404)
            return
        try:
            origin = self._bridge_origin()
        except PermissionError:
            self.send_error(403, "CORS origin denied")
            return
        if origin is None:
            self.send_error(403, "CORS origin required")
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Tihulu-Bridge-Token")
        if self.headers.get("Access-Control-Request-Private-Network", "").lower() == "true":
            # Only allowed Pages/local origin may request local private-network access.
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self):
        if urlsplit(self.path).path == "/pair":
            self._pair_page()
        elif urlsplit(self.path).path.startswith(("/api/dvb/", "/api/radio/")):
            self._api_get()
        else:
            self._respond(False)

    def do_HEAD(self):
        self._respond(True)

    def do_POST(self):
        if urlsplit(self.path).path.startswith("/api/dvb/"):
            self._api_post()
        else:
            self.send_error(405, "Only specific authorized DVB scan endpoints permit POST")

    def log_message(self, format_string, *args):
        # Only route metadata, no coordinates/receiver data are received.
        super().log_message(format_string, *args)


def doctor():
    return {
        "name": "TIHULU RF Geolocation Center",
        "version": "0.1.0-dev",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "app_directory": str(ROOT),
        "static_assets": len(ASSETS),
        "binding": "loopback-only when running serve",
        "rf_receiver": "NOT IMPLEMENTED",
        "dvb_bridge": "REAL LINUX DVBv5 VIA OPT-IN LOOPBACK; LOCAL APPROVAL PAIRING (NO TOKEN PASTE)",
        "dvb_backend_status": DVB.capabilities(),
        "native_gnss_decoder": "NOT IMPLEMENTED",
        "gnss_positional_provider": "browser geolocation / imported or Web Serial NMEA only",
        "github_pages_deployed": "NOT VERIFIED",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local-only RF Geolocation browser app")
    sub = parser.add_subparsers(dest="command", required=True)
    srv = sub.add_parser("serve", help="serve locally, never expose a LAN RF API")
    srv.add_argument("--port", type=int, default=8794)
    srv.add_argument("--enable-pages-bridge", action="store_true", help="explicitly allow token-protected cross-origin access from official https://tihulu.github.io Pages only")
    sub.add_parser("doctor", help="print verified local application capabilities")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        print(json.dumps(doctor(), indent=2))
        return 0
    global PAGES_BRIDGE_ENABLED
    PAGES_BRIDGE_ENABLED = bool(args.enable_pages_bridge)
    if args.port < 1024 or args.port > 65535:
        parser.error("Port must be 1024–65535")
    with ThreadingHTTPServer(("127.0.0.1", args.port), LocalAppHandler) as server:
        print("TIHULU RF Geolocation Center: http://127.0.0.1:" + str(args.port) + "/")
        print("Loopback-only: no LAN binding or automatic RF scan. Native DVB scanner requires explicit consent.")
        print("DVB browser bridge: " + ("official Pages allowed with token" if PAGES_BRIDGE_ENABLED else "localhost-only (use --enable-pages-bridge for official Pages)"))
        print("No token copying needed: click Connect TV in TIHULU, then Approve in the local pairing window.")
        print("No TV scanning starts until you press Scan TV in the browser.")
        try:
            server.serve_forever(poll_interval=0.3)
        except KeyboardInterrupt:
            print("\nStopping this local app server.")
    return 0
