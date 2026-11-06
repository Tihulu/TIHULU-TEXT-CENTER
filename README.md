# TIHULU TEXT CENTER

A lightweight, offline-first, English-language information and text-network center for desktop browsers and Raspberry Pi. Designed as a **standalone application** with a future integration path into [Tihulu Survival Kit](https://github.com/Tihulu/tihulu-survival-kit).

## Satellite Center — standalone companion 🛰️

**[Open Satellite Center on GitHub Pages](https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/)** ·
[One-line installation / USB pairing guide](docs/SATELLITE_CENTER_COMPANION.md) ·
[Satellite Center source and review (PR #9)](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/9)

The separate `satellite_center/` application provides ISS, Meteor-M,
amateur CubeSat and Iridium NEXT orbital tracking, pass prediction, bounded
receive-only RTL-SDR scans and opt-in scheduled recordings. With compatible
local tools, it can collect ISS APRS text and attempt real Meteor-M LRPT
image decoding through SatDump. It releases its own SDR processes on stop;
it never preempts Flight Radar/readsb. **Iridium is orbital/spectrum
survey only**, not a private communications decoder.

**Browser-only WebUSB is now the preferred mode:** on supported desktop Chromium
browsers, open the hosted Satellite Center, grant permission to the Nooelec
RTL2832U, and capture raw IQ directly without installing the Python companion.
Firefox/Safari cannot use WebUSB; Windows/Linux may still need OS driver or
permission configuration. In-browser APRS/Meteor image decoding and closed-tab
scheduling are not implemented. The local companion remains **optional** for
external decoders and longer-lived jobs. The standalone companion is still
in an independent **draft PR**, not merged into the main backend.

**Optional companion install — Linux / Pop!_OS / Debian / Ubuntu / Raspberry Pi OS / macOS** (Git,
Python 3.11+ and venv required):

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/feature/satellite-center-standalone-2026-11-06/satellite_center/install/install.sh | bash
```

**Windows 10/11 x64** (PowerShell; Python 3.11+ required):

```powershell
irm https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/feature/satellite-center-standalone-2026-11-06/satellite_center/install/install.ps1 | iex
```

Read the remote scripts before running them. SDR receiver utilities,
device drivers and a suitable antenna may still need separate installation;
see the [setup guide](docs/SATELLITE_CENTER_COMPANION.md).

## Scope

- Teletext-style numbered navigation and a modern responsive interface.
- Passive local RTL2832U USB / DVB frontend inventory and installed decoder tool checks (does not access or tune radios).
- Read-only, source-attributed **broadcast text imports**, with page/subpage support (no fabricated reception).
- On-demand RSS/Atom/JSON Feed 1.0/1.1 ingestion, searchable local article cache, and external text-community directories.
- Local, offline bulletin-board notes and bookmarks.
- FM RDS/RadioText+ is an opt-in real rtl_fm/redsea decoder session; a separate optional read-only welle-cli bridge can import DAB+ DLS and MOT images. Journaline, off-air DVB Teletext, HF weather text and APRS still require dedicated decoder integrations.
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


## Unified browser/desktop consolidation candidate — Nov 2026

The draft [consolidation branch](https://github.com/Tihulu/TIHULU-TEXT-CENTER/tree/integration/consolidated-pages-webusb-2026-11-06)
preserves the current main WebUSB-first Satellite Center description and the
AI / ASR / translation files while combining [PR #8](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/8),
[PR #10](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/10),
[PR #11](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/11)
and [PR #12](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/12).
It adds a GitHub Pages portal with **Direct USB** (experimental in-browser
mono FM audio, optional local recording and bounded raw IQ) and an isolated
Satellite WebUSB page. DAB/MOT/RDS, TV, flight radar RF decoding, OS-managed
receiver lifecycle and local AI models still require compatible external
decoders/backends; direct WebUSB cannot override driver or OS permission
requirements. **No hardware certification or merge to main is implied.**
Read [Pages & desktop setup](docs/PAGES_AND_DESKTOP.md).


## Radio / TV Center consolidated channel UX (draft PR #15)

[PR #15 — Verified channel search, FM/DAB full scans, selectable DAB audio, DVB-T/T2 regional service discovery and editable station lists](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/15) builds on PR #14 and PR #13 without replacing their RF lifecycle, WebUSB Pages, translation or recording features.

The **Radio Center (P410)** shows separately verified FM RDS and DAB FIC stations with Play, search, favorites, local aliases, hidden-channel toggles and sort order. Full FM does a real 87.5–108 MHz survey and up to 128 RDS verification attempts. Full DAB scans the 5A–13F multiplex blocks through an approved local welle-cli session. A decoder-confirmed audio SID can be streamed through the in-app player from the fixed welle-cli localhost MP3 endpoint. Non-audio DAB data services are not falsely playable.

The **TV Center (P420)** offers actual DVB-T/T2 regional-plan discovery when Linux has dvbv5-scan, an installed frequency table and an accessible separate DVB tuner; the scanned services are saved, searchable and editable. The physical scan **does not itself create an MPEG-TS playback relay**. Only separately authorized, configured local stream entries are playable. **Advanced RF (P400)** contains equipment/spectrum/debug tools without duplicate main players.

### Safe preview install / update (Linux, Raspberry Pi OS, macOS)

Review the source of [bootstrap-unix.sh](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/feature/unified-channel-center-full-scan-ui-2026-11-06/scripts/bootstrap-unix.sh) before executing. Then:

\`\`\`bash
curl -fsSL 'https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/feature/unified-channel-center-full-scan-ui-2026-11-06/scripts/bootstrap-unix.sh' | bash -s -- feature/unified-channel-center-full-scan-ui-2026-11-06 --switch
\`\`\`

The explicit \`--switch\` option permits switching an existing, **clean** installed checkout from another development branch. It does **not** reset, force-push or delete another branch, the database or recordings. The updater refuses dirty checkouts, detached HEADs, unknown repository origin and divergent branch histories. These drafts remain unmerged and physical SDR acceptance is still pending.

See [UI / station-source audit](docs/END_TO_END_CHANNEL_UI_AUDIT_2026-11-06.md). GitHub Pages browser-only experimental FM/IQ remains separate from the local-backend DAB/TV full scan and native decoder.
