"""Local HTTP application. No WAN listener, no CORS and no decoder/transmitter."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .core import Store, safe_https_url

WEB_DIR = Path(__file__).resolve().parents[1] / "web"

DIRECTORY = [
    {"name": "ARD Text", "category": "Teletext on the web", "url": "https://www.ard-text.de/", "note": "Publisher website, internet only; not antenna reception."},
    {"name": "TRT TELEGÜN", "category": "Teletext information", "url": "https://www.trt.net.tr/corporate/teletext", "note": "Publisher information; no Turkish broadcast reception claimed."},
    {"name": "Teletext Art", "category": "Teletext-style community", "url": "https://teletextart.co.uk/teletext-links", "note": "External web directory; community sites have their own permissions."},
    {"name": "LK0NOD", "category": "Packet/BBS community", "url": "https://www.lk0nod.de/lk0nod-hilfe-online.html", "note": "Public information; no radio TX or BBS gateway built in."},
    {"name": "Gemini protocol", "category": "Text-first internet", "url": "https://geminiprotocol.net/", "note": "Information about Gemini; a dedicated Gemini client is not bundled."},
    {"name": "Gopher", "category": "Text-first internet", "url": "https://gopher.floodgap.com/", "note": "Browser-accessible introductory directory; native Gopher client not bundled."},
]

INDEX_PAGES = {
    100: ("INDEX", "Browse local content, source-attributed RF imports, offline notes and opt-in internet feeds."),
    200: ("HEADLINES", "Cached RSS/Atom articles. Refresh only when requested."),
    300: ("WEATHER", "Weather text must be received from a genuine source; no synthetic forecast is displayed."),
    400: ("RADIO DATA", "FM RDS, DAB DLS, Journaline, NAVTEX and others require separately installed, tested decoders."),
    500: ("EMERGENCY", "Imported RF text is not an authenticated official alert. Use verified emergency sources."),
    600: ("LOCAL BOARD", "Offline bulletin board on loopback. No multi-user login and no radio transmission."),
    700: ("LIBRARY", "Stored articles, bookmarks and previously imported pages remain on this device."),
    800: ("NETWORKS", "Web directories for Teletext, blogs, BBS, Gemini and Gopher."),
    850: ("ABOUT", "Standalone service with on-demand workers and no default polling or RF receiver."),
}

class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, store: Store):
        self.store = store
        self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server: LocalServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        # Local diagnostic only; do not log bulletin contents or feed payloads.
        super().log_message(format, *args)

    def _send(self, status: int, body: bytes, content_type: str, *, cache: str = "no-store"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.close_connection = True
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self'; style-src 'self'; "
                         "img-src 'self' data:; connect-src 'self'; form-action 'self'; "
                         "base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload):
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        parsed = urlsplit(self.path)
        route = parsed.path
        q = parse_qs(parsed.query, keep_blank_values=True)
        try:
            if route in ("/", "/index.html", "/assets/app.js", "/assets/styles.css"):
                mapping = {"/": "index.html", "/index.html": "index.html",
                           "/assets/app.js": "app.js", "/assets/styles.css": "styles.css"}
                data = (WEB_DIR / mapping[route]).read_bytes()
                kind = "text/html" if route in ("/", "/index.html") else ("text/javascript" if route.endswith(".js") else "text/css")
                return self._send(200, data, kind + "; charset=utf-8", cache="no-cache")
            if route == "/api/bootstrap":
                return self._json(200, {
                    "version": __version__, "mode": "local_offline_first",
                    "csrf": self.server.csrf_token,
                    "counts": self.server.store.counts(),
                    "background_refresh": False, "radio_receiver": "not_connected",
                    "dvb_receiver": "not_connected",
                    "warning": "No built-in RF decoder or authenticated emergency feed."
                })
            if route == "/api/index":
                return self._json(200, [{"page": k, "title": v[0], "description": v[1]} for k,v in INDEX_PAGES.items()])
            if route == "/api/page":
                try:
                    page = int(q.get("number", ["100"])[0])
                    subpage = int(q.get("subpage", ["0"])[0])
                except ValueError:
                    raise ValueError("Page/subpage must be numbers")
                if not (100 <= page <= 899 and 0 <= subpage <= 99):
                    raise ValueError("Page outside supported 100–899 range")
                source = q.get("source_id", [""])[0][:90]
                if source:
                    data = self.server.store.page(source, page, subpage)
                    if not data:
                        return self._json(404, {"error": "No imported page with this source/number/subpage"})
                    return self._json(200, {"kind": "broadcast", **data, "source_status": "decoder_imported_not_authority_verified"})
                if page not in INDEX_PAGES:
                    return self._json(404, {"error": "Page not present in local index; select an imported source if available"})
                return self._json(200, {"kind": "local_index", "page": page, "subpage": 0,
                                        "title": INDEX_PAGES[page][0], "body": INDEX_PAGES[page][1]})
            if route == "/api/pages":
                return self._json(200, self.server.store.pages(q.get("source_id", [""])[0][:90] or None))
            if route == "/api/events":
                return self._json(200, self.server.store.events())
            if route == "/api/articles":
                return self._json(200, self.server.store.articles(q.get("q", [""])[0]))
            if route == "/api/feeds":
                return self._json(200, self.server.store.feeds())
            if route == "/api/bulletins":
                return self._json(200, self.server.store.bulletins())
            if route == "/api/bookmarks":
                return self._json(200, self.server.store.bookmarks())
            if route == "/api/directory":
                return self._json(200, DIRECTORY)
            return self._json(404, {"error": "Not found"})
        except (ValueError, TypeError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception:
            self._json(500, {"error": "Internal error. See local server logs."})

    def do_POST(self):
        route = urlsplit(self.path).path
        allowed = {"/api/feeds/add", "/api/feeds/refresh", "/api/bulletins", "/api/bookmarks"}
        if route not in allowed:
            return self._json(404, {"error": "Not found"})
        if self.headers.get("X-Tihulu-CSRF") != self.server.csrf_token:
            return self._json(403, {"error": "Missing or invalid local write token"})
        # Reject browser cross-site POSTs; same-origin JS provides an Origin header.
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host", ""):
            return self._json(403, {"error": "Origin mismatch"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._json(400, {"error": "Invalid length"})
        if not 0 < length <= 16_384 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self._json(413, {"error": "Require bounded application/json body"})
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Expected JSON object")
            if route == "/api/feeds/add":
                fid = self.server.store.add_feed(payload.get("title"), payload.get("url"))
                return self._json(201, {"id": fid})
            if route == "/api/feeds/refresh":
                fid = payload.get("id")
                if not isinstance(fid, str) or len(fid) > 100:
                    raise ValueError("Invalid feed ID")
                count = self.server.store.refresh_feed(fid)
                return self._json(200, {"imported": count})
            if route == "/api/bulletins":
                bid = self.server.store.add_bulletin(payload.get("title"),payload.get("body"),payload.get("author"))
                return self._json(201, {"id": bid})
            if route == "/api/bookmarks":
                self.server.store.add_bookmark(payload.get("label"),payload.get("target_type"),payload.get("target"))
                return self._json(201, {"saved": True})
        except KeyError as exc:
            self._json(404, {"error": str(exc)})
        except (ValueError, TypeError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception:
            self._json(502, {"error": "Feed request or local operation failed; no live data assumed."})


def run_server(store: Store, *, host: str = "127.0.0.1", port: int = 8787):
    if host != "127.0.0.1":
        raise ValueError("This standalone service is loopback-only")
    server = LocalServer((host, port), store)
    print(f"TIHULU TEXT CENTER v{__version__}: http://{host}:{server.server_port}/")
    print("Local mode. Background polling OFF. No connected tuner.")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
