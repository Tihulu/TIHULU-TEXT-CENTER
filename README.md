# TIHULU TEXT CENTER

A lightweight, offline-first, English-language information and text-network center for desktop browsers and Raspberry Pi. Designed as a **standalone application** with a future integration path into [Tihulu Survival Kit](https://github.com/Tihulu/tihulu-survival-kit).

## Scope

- Teletext-style numbered navigation and a modern responsive interface.
- Passive local RTL2832U USB / DVB frontend inventory and installed decoder tool checks (does not access or tune radios).
- Read-only, source-attributed **broadcast text imports**, with page/subpage support (no fabricated reception).
- On-demand RSS/Atom ingestion, searchable local article cache, and external text-community directories.
- Local, offline bulletin-board notes and bookmarks.
- FM RDS, DAB+ DLS/Journaline, DVB Teletext, HF weather text, APRS and similar protocols as **optional external-decoder adapters**, never as claims of built-in reception.
- No transmitter, DVB tuner control, automatic background polling, AI runner or live emergency-warning receiver. **FM RDS requires an explicit, bounded capture and installed rtl_fm/redsea**.

## Run

Requires Python **3.11+**, no third-party Python packages:

```bash
python3 -m textcenter receivers  # hardware/tool inventory, never tunes the SDR
python3 -m textcenter serve --host 127.0.0.1 --port 8787
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
python3 -m textcenter import-text --file ./decoded-pages.json
```

The `decoded-pages.json` filename is **not bundled receiver data**. It must be produced from a real decoder output; see [docs/DATA_FORMAT.md](docs/DATA_FORMAT.md). Imported timestamps and attribution must originate from the decoder/source. **Never treat sample text as received signals.**

To create a correctly formatted but **completely empty** import file:

```bash
python3 -m textcenter make-template
python3 -m textcenter import-text --file decoded-pages.json
```

This imports **0 records**, as expected: no physical receiver is integrated yet. Run `python3 -m textcenter doctor` to check your SQLite record counts and installation state.

### Troubleshooting (Pop!_OS / Linux)

Keep `python3 -m textcenter serve` running in a terminal while the browser is open. If you press **Ctrl+C**, browser API calls fail because the local server has stopped. Start it again and reload the tab. A lost API connection must not be interpreted as a missing Teletext page.

Run commands from the repository directory (or install the package in a suitable environment):

```bash
cd ~/TIHULU-TEXT-CENTER
python3 -m textcenter doctor
python3 -m textcenter serve
```

If `python3 -m textcenter` is launched from a different directory without installing the package, Python will not find it. The default database remains in `~/.local/share/tihulu-text-center/` across restarts.

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

## Receiver detection

The Radio Data (400) page now shows passive USB candidates and available decoder tools. See [Receiver status and connection notes](docs/RECEIVER_STATUS.md). A detected device does **not** mean its RF signal was decoded or its USB interface is free.

### If the CLI detects your SDR but the sidebar still says it is missing

The old static sidebar placeholder was removed. After updating, **stop the old Python server** with Ctrl+C, run `git pull --ff-only`, restart `python3 -m textcenter serve`, and hard-refresh the browser. From the same local browser, `http://127.0.0.1:8787/api/receivers` should show `rtl_usb_count` and the decoder-tool inventory. Click **Check USB status** in the sidebar or **Refresh Device Status** on page 400. A receiver may be USB-detected while its **text decoder remains inactive**; that is expected until an authorized real decoder pipeline is integrated.

## Live FM RDS: explicit 10–90 second capture (Linux)

Text Center v0.2 includes an optional local **FM RDS receiver session**. This only runs when manually started from Radio Data (400). It uses an actual USB RTL2832U receiver and two external executables: `rtl_fm` and `redsea`. Real JSON output is archived in SQLite, grouped by measured capture frequency, with UTC receive time and source labels. No actual RF session is claimed to have run in GitHub CI.

See [Live FM RadioText setup](docs/FM_RDS_LIVE.md). This feature will claim the USB receiver, so **close Gqrx/welle.io/readsb and any other receiver job first**. A cooperative lock only prevents other instances using this same locking convention; it cannot protect a tuner from third-party applications.
