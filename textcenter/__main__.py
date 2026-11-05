"""CLI: foreground local server, explicit feed registration, decoder JSON import."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import os

from .core import Store
from .http_app import run_server


def default_db() -> Path:
    return Path(os.environ.get("TIHULU_TEXT_DB", str(Path.home() / ".local/share/tihulu-text-center/text-center.db")))


def main():
    parser = argparse.ArgumentParser(prog="python -m textcenter")
    sub = parser.add_subparsers(dest="command")
    server = sub.add_parser("serve", help="Start loopback-only web application")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8787)
    server.add_argument("--db", type=Path, default=default_db())
    importer = sub.add_parser("import-text", help="Import attributed decoder-produced JSON")
    importer.add_argument("--db", type=Path, default=default_db())
    importer.add_argument("--file", type=Path, required=True)
    feed = sub.add_parser("add-feed", help="Register a trusted HTTPS RSS/Atom feed")
    feed.add_argument("--db", type=Path, default=default_db())
    feed.add_argument("--title", required=True)
    feed.add_argument("--url", required=True)
    args = parser.parse_args()
    if args.command is None:
        args.command = "serve"
        args.host, args.port, args.db = "127.0.0.1", 8787, default_db()
    if args.command == "serve":
        if args.host != "127.0.0.1":
            parser.error("Only --host 127.0.0.1 is permitted; use an authenticated TLS reverse proxy for LAN access")
        if not 1 <= args.port <= 65535:
            parser.error("Port must be 1–65535")
        run_server(Store(args.db), host=args.host, port=args.port)
    elif args.command == "import-text":
        content = args.file.read_bytes()
        if len(content) > 4_000_000:
            parser.error("Import file exceeds four-megabyte limit")
        data = json.loads(content)
        print(json.dumps(Store(args.db).import_data(data), indent=2))
    elif args.command == "add-feed":
        print("Registered feed:", Store(args.db).add_feed(args.title, args.url))


if __name__ == "__main__":
    main()
