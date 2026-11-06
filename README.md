# TIHULU TEXT CENTER

A lightweight, offline-first, English-language information and text-network center for desktop browsers and Raspberry Pi. Designed as a **standalone application** with a future integration path into [Tihulu Survival Kit](https://github.com/Tihulu/tihulu-survival-kit).

## Scope

- Teletext-style numbered navigation and a modern responsive interface.
- Passive local RTL2832U USB / DVB frontend inventory and installed decoder tool checks (does not access or tune radios).
- Read-only, source-attributed **broadcast text imports**, with page/subpage support (no fabricated reception).
- On-demand RSS/Atom/JSON Feed 1.0/1.1 ingestion, searchable local article cache, and external text-community directories.
- Local, offline bulletin-board notes and bookmarks.
- FM RDS/RadioText+ is an opt-in real rtl_fm/redsea decoder session; a separate optional read-only welle-cli bridge can import DAB+ DLS and MOT images. Journaline, off-air DVB Teletext, HF weather text and APRS still require dedicated decoder integrations.
- No transmitter, DVB tuner control, automatic background polling, AI runner or live emergency-warning receiver. **FM RDS requires an explicit, bounded capture and installed rtl_fm/redsea**.

## One-command local install and safe updates (Python 3.11+)

A user-local installer is provided at the repository root. From an existing
checkout, run \`bash install.sh\` to create
\`~/.local/bin/tihulu-text-center\` and
\`~/.local/bin/tihulu-text-center-update\`. The installer requires Git,
Python 3.11+, and Bash; does **not** require sudo, create services, tune an
antenna, download AI models, or overwrite your SQLite media archive. It
only checks that optional RTL-SDR, welle-cli and ffmpeg utilities exist.
Those real receiver executables must be installed separately when used.

For a new **feature-branch test checkout**, run this single command (if
the repository is private, Git may require your existing GitHub credentials):

\`\`\`bash
bash -c 'set -e; p="$HOME/TIHULU-TEXT-CENTER-media-fix"; if [ -e "$p/.git" ]; then bash "$p/install.sh" --update; else git clone --branch fix/live-fm-audio-dab-mot-one-line-install-2026-11-06 https://github.com/Tihulu/TIHULU-TEXT-CENTER.git "$p"; bash "$p/install.sh"; fi'
\`\`\`

Launch the standalone loopback server without touching other checkouts:

\`\`\`bash
"$HOME/.local/bin/tihulu-text-center" serve --port 8791
\`\`\`

After review/merge, the same installer will track **the selected local
branch** on user-requested update only:

\`\`\`bash
"$HOME/.local/bin/tihulu-text-center-update"
\`\`\`

The updater insists on a clean checkout and a fast-forward. It **never**
resets, force-pushes, switches branches, merges another agent's work, or
removes local recordings. Restart the Python server and hard-refresh the
browser after an update; a running process is not hot-reloaded. Use the
latest integrated main checkout once the draft PR is reviewed and merged.

### Receiver/audio/subtitle and DAB MOT behavior

- Missing Whisper/speech/translation models no longer abort an otherwise
  available **continuous FM audio** stream. UI reports *audio only*
  without inventing original or translated captions. Installing a real
  local model is a separate opted-in process.
- The **DAB MOT Slideshow** on Radio Data (400) and Live Radio (410)
  rotates locally archived genuine JPEG/PNG slides on an explicit click.
  **SYNC CURRENT DAB MOT** reads an already-running welle-cli receiver
  on localhost:7979; it does not start or retune a tuner.
- One RTL-SDR cannot receive FM and a different DAB block simultaneously:
  stop FM, launch welle-cli and tune a genuine DAB ensemble before requesting
  fresh MOT slides. If a station sends no slideshow, show the unavailable
  state (not a stock image). Previously archived MOT may be viewed offline.
- DAB images are limited to bounded decoder-provided image bytes with
  actual source, timestamp and frequency. All standard Band III block
  centres may be attributed, but the frequency roster itself does not
  establish reception or a lock.

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

This imports **0 records**, as expected: an empty template is not a received radio capture. Real RF acquisition is handled separately by explicit receiver actions on page 400. Run `python3 -m textcenter doctor` to check your SQLite record counts and installation state.

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

## Auto Discover (v0.3)

Radio Data (400) now contains **Auto Discover** for passive local USB/DVB/decoder/source/archive inventory and **Scan FM Band** for explicit one-shot rtl_power spectral measurements. Spectrum peaks are not yet named stations. Manual RDS/RadioText+ confirmation requires redsea and a free RTL-SDR. Active readsb, dump1090, Gqrx or other known receiver programs block capture instead of being stopped. See [Auto Discovery](docs/AUTO_DISCOVERY.md) and [all Survival Kit integration requirements](docs/SURVIVAL_KIT_MASTER_PROMPT.md).

## Scan every supported source, without conflating RF and Internet

Each of the 31 protocol/service capabilities now has its own readiness/scan action in **Protocols (860)**. The **Radio Data (400)** scan picker includes FM, DAB Band III, APRS VHF, DRM HF, RTTY HF, NAVTEX and WeatherFAX energy-survey modes. Surveys cannot identify broadcasters or decode text without the appropriate protocol receiver; full DVB scanning is pending a protected DVB tuner lease and TS Teletext decoder. **Text Networks (800)** are Internet-only links, not antenna stations. Pre-cached feeds and received pages remain accessible offline. [Full scan matrix](docs/SCANNING_MODES.md).

## Radio audio, broadcast images and Hauppauge DVB preparation (v0.4)

- **Short FM listening preview:** Radio Data (400) includes opt-in 10–20-second local WAV previews using a REAL RTL-SDR and `rtl_fm`; no `redsea` required for audio. This is **not continuous live radio**. The preview remains in local server memory, is never automatically recorded, and is lost on restart. It cannot run alongside Flight Radar/other receiver sessions on the same SDR. Playback uses the local browser `<audio>` element. See [Radio and DVB setup](docs/RADIO_AND_DVB.md).
- **Broadcast picture archive:** stores actual bounded PNG/JPEG received images with source, timestamp and frequency. `redsea --streams` enables optional RDS2/RFT logo capture where supported by redsea 1.2+ and the broadcaster, at greater CPU cost. DAB+ DLS and MOT images can be retrieved from an already-running local welle-cli web receiver via an explicit read-only sync, or MOT images can be imported from a genuine external decoder using `python3 -m textcenter import-media --file path/to/decoder-media.json`. No DAB tuner process is bundled or automatically started. No Internet artwork is substituted for RF images.
- **Hauppauge WinTV-soloHD 01589:** the application passively reports actual Hauppauge USB product strings, Linux DVB frontend paths, relevant SI2168 firmware candidates and DVB utilities. The model's order/delivery does NOT prove it is physically connected or has locked a TV service. No automatic, unprotected DVB retune or Teletext decoder is claimed.

### Live DAB read-only bridge

In **Radio Data (400)**, use **READ RUNNING DAB RECEIVER** after independently starting a compatible welle-cli web receiver on local TCP port 7979 and confirming that it owns an available device. Text Center reads only `/mux.json`, `/channel` and bounded `/slide/<service_id>` via GET. It never retunes welle-cli. Decoded DLS text is archived with original broadcast/decoder timestamp where a known channel frequency exists; MOT images are stored as source-attributed JPEG/PNG. Missing/weak signals and absent welle-cli are shown as unavailable. See [Radio and DVB setup](docs/RADIO_AND_DVB.md). Journaline and a continuous embedded DAB player remain future integrations.
