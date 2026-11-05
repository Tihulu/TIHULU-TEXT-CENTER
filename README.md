# TIHULU TEXT CENTER

A lightweight, offline-first, English-language information and text-network center for desktop browsers and Raspberry Pi. Designed as a **standalone application** with a future integration path into [Tihulu Survival Kit](https://github.com/Tihulu/tihulu-survival-kit).

## Scope

- Teletext-style numbered navigation and a modern responsive interface.
- Read-only, source-attributed **broadcast text imports**, with page/subpage support (no fabricated reception).
- On-demand RSS/Atom ingestion, searchable local article cache, and external text-community directories.
- Local, offline bulletin-board notes and bookmarks.
- FM RDS, DAB+ DLS/Journaline, DVB Teletext, HF weather text, APRS and similar protocols as **optional external-decoder adapters**, never as claims of built-in reception.
- No transmitter, SDR driver, DVB tuner control, background polling, AI runner or live emergency-warning receiver in this initial standalone build.

## Run

Requires Python **3.11+**, no third-party Python packages:

```bash
python3 -m textcenter --host 127.0.0.1 --port 8787
```

Open **http://127.0.0.1:8787/**. The app creates its SQLite database in `~/.local/share/tihulu-text-center/` unless `--db` is set.

To run tests:

```bash
python3 -m unittest discover -s tests -v
```

The web server binds to loopback by default. **Do not expose it directly to the internet or LAN**. For future access from phones at `tihulu.lan`, use an authenticated, TLS-enabled same-origin Survival Kit reverse proxy. A local bulletin board is **not** an RF packet-radio messaging service.

## Real data, not demo telemetry

The interface starts with a clearly labeled offline index and empty incoming feeds. It does not pretend that ARD Teletext, FM RDS, emergency signals, or any tuner is active. You can import genuine text from your own authorized decoders:

```bash
python3 -m textcenter import-text --db ./text-center.db --file ./decoded-pages.json
```

The input schema is in [docs/DATA_FORMAT.md](docs/DATA_FORMAT.md). Imported page timestamps and attribution must originate from the decoder or source; simulated contents must be labeled as demo.

## Privacy and resource policy

- No default background fetch, tuner activation, crawling, telemetry, or AI inference.
- Feed refresh occurs only on explicit user action and obeys bounded time, response size, item count and URL validation.
- The original source, medium, original language, observed timestamp and cache state are recorded.
- A local bulletin board is not an authenticated multi-user chat. It is for owner-authenticated use behind the future portal, or locally on loopback.
- Official alerts must come through separately verified emergency integrations; random received broadcast text is not a verified warning.

## Project map

- `textcenter/`: Python standard-library HTTP/SQLite/backend.
- `web/`: responsive offline-ready frontend; no external JS/CSS frameworks.
- `tests/`: synthetic security, parsing, storage and API tests.
- `docs/`: integration and provenance notes.

Development is additive and intentionally keeps the standalone project independent of existing Survival Kit stages.
