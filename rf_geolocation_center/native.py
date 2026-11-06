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
    "/scripts/dvb_scan_linux.sh": ("scripts/dvb_scan_linux.sh", "text/plain"),
    "/scripts/usb_prepare_linux.sh": ("scripts/usb_prepare_linux.sh", "text/plain"),
}
CSP = ("default-src 'self'; script-src 'self' https://esm.sh; style-src 'self'; "
       "connect-src 'self' https://esm.sh https://celestrak.org https://celestrak.com "
       "https://overpass-api.de https://opensky-network.org; "
       "img-src 'self' data: https://tile.openstreetmap.org; "
       "frame-src https://www.openstreetmap.org; "
       "worker-src 'self'; manifest-src 'self'; object-src 'none'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


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

    def do_GET(self):
        self._respond(False)

    def do_HEAD(self):
        self._respond(True)

    def do_POST(self):
        self.send_error(405, "Read-only offline app; POST unavailable")

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
        "native_gnss_decoder": "NOT IMPLEMENTED",
        "gnss_positional_provider": "browser geolocation / imported or Web Serial NMEA only",
        "github_pages_deployed": "NOT VERIFIED",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local-only RF Geolocation browser app")
    sub = parser.add_subparsers(dest="command", required=True)
    srv = sub.add_parser("serve", help="serve locally, never expose a LAN RF API")
    srv.add_argument("--port", type=int, default=8794)
    sub.add_parser("doctor", help="print verified local application capabilities")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        print(json.dumps(doctor(), indent=2))
        return 0
    if args.port < 1024 or args.port > 65535:
        parser.error("Port must be 1024–65535")
    with ThreadingHTTPServer(("127.0.0.1", args.port), LocalAppHandler) as server:
        print("TIHULU RF Geolocation Center: http://127.0.0.1:" + str(args.port) + "/")
        print("Loopback-only browser app; no SDR capture, no background GNSS.")
        try:
            server.serve_forever(poll_interval=0.3)
        except KeyboardInterrupt:
            print("\nStopping this local app server.")
    return 0
