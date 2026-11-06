# TIHULU TEXT CENTER — GitHub Pages, Desktop and Flight Radar Integration

## Branch, safety and ownership

This document describes the new consolidated draft candidate on branch `integration/consolidated-pages-webusb-2026-11-06`. It is NOT merged to main. Existing AI/ASR/translator owner files are preserved. PR #8 verified FM and DAB channel discovery, PR #10 missing-ASR audio fallback, genuine MOT slideshow and safe local installation are composed additively. The final RF and platform acceptance gates remain open.

## GitHub Pages (static website / browser entry point)

**Enable deployment manually in GitHub** because GitHub Pages is disabled by default in the supplied screenshot:

1. Open `Tihulu/TIHULU-TEXT-CENTER` → Settings → Pages.
2. Under **Build and deployment** choose **Deploy from a branch**.
3. Set **Branch** to `integration/consolidated-pages-webusb-2026-11-06`, **Folder** to `/docs`, click **Save**.
4. After GitHub reports a completed Pages build, the expected project URL is `https://tihulu.github.io/TIHULU-TEXT-CENTER/` (do not assume it is live until GitHub has deployed).

`docs/index.html`, `pages.js`, `pages.css`, `manifest.webmanifest`, `pages-icon.svg` and `sw.js` provide a responsive independent Pages frontend, offline-first browser notes and same-origin static-asset caching. It is **not** the Python backend hosted on GitHub. Pages cannot start OS executables such as `rtl_fm`/`redsea`/readsb/ffmpeg, and cannot automatically connect to a remote Raspberry Pi behind a firewall. However, the new Direct USB (415) view can ask for WebUSB permission on supported desktop Chromium browsers and use a pinned WebUSB RTL-SDR driver to attempt experimental in-browser FM mono or raw IQ reception without a Python backend. It does NOT implement RDS, DAB+ service/MOT decoding, ADS-B decoding, DVB-T2, GPU ASR or arbitrary OS service management. The optional full-featured Pages-to-desktop links open the **local, separately running** full application at `http://127.0.0.1:8787/#page=410|420|450|880` (works only when running on the same computer).

On a smartphone, `127.0.0.1` refers to the phone, not the nearby Pi/PC. True phone-controlled radio and TV requires a **TLS authenticated same-origin reverse proxy / pairing service** through the Survival Kit gateway (`tihulu.lan`), a hardware lease broker and strict Origin/CORS/CSRF rules. Do not expose the existing unauthenticated Python server with `--host 0.0.0.0`, and do not advertise WebUSB support as universal or sufficient.

## One-line installation — development branch

Review scripts in GitHub before running them. The bootstrap is user-local, rejects divergent Git checkouts and never overwrites SQLite, recordings, custom files or AI models.

Debian / Ubuntu / Pop!_OS / Raspberry Pi OS (64-bit Python 3.11+) / macOS Apple Silicon with a supported browser:

```bash
curl -fsSL 'https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/integration/consolidated-pages-webusb-2026-11-06/scripts/bootstrap-unix.sh' | bash -s -- 'integration/consolidated-pages-webusb-2026-11-06'
```

Installed source defaults to `~/.local/opt/tihulu-text-center`, launcher `~/.local/bin/tihulu-text-center`, Linux XDG/COSMIC Applications menu shortcut, and user-local macOS `.app`. Start with:

```bash
tihulu-text-center desktop
# Or if the bin directory isn't in PATH:
~/.local/bin/tihulu-text-center desktop
```

**Windows x64 PowerShell:** review `scripts/install-windows.ps1`. Git and Python 3.11+ required; run after reviewing source:

```powershell
$env:TIHULU_TEXT_BRANCH='integration/consolidated-pages-webusb-2026-11-06'; irm 'https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/integration/consolidated-pages-webusb-2026-11-06/scripts/install-windows.ps1' | iex
```

This installs a user-local Start Menu shortcut to a standalone browser-app window. It is NOT a signed Windows EXE/MSI nor an Apple-notarized DMG. The UI and loopback server can run on Windows, but native RTL-SDR capture is still **Linux-only** in the current implementation. Windows and macOS live TV require an external authorized local TS stream, not guaranteed direct USB support. Raspberry Pi OS also needs the correct 64-bit Python/runtime and receiver drivers; cross-platform smoke tests do not prove hardware.

For development, a separate clone preserves an existing checkout:

```bash
git clone --branch integration/consolidated-pages-webusb-2026-11-06 https://github.com/Tihulu/TIHULU-TEXT-CENTER.git ~/TIHULU-TEXT-CENTER-integration
cd ~/TIHULU-TEXT-CENTER-integration
python3 -m unittest discover -s tests -v
node --check web/app.js
node --check docs/pages.js
node --check docs/sw.js
bash -n install.sh scripts/bootstrap-unix.sh
python3 -m textcenter desktop
```

## Full tar1090 and source filters

Page 880 in the local app offers either an existing full tar1090 viewer (`127.0.0.1:8080/tar1090/`, `127.0.0.1/tar1090/`) or Tihulu Flight Radar's local built-in map (`127.0.0.1:8505/`). Embedding in an iframe is attempted only by user action; viewers may enforce `X-Frame-Options` / `frame-ancestors` denying embedding, so opening the full original map in a new tab remains available. Do not delete or replace the standalone Flight Radar app, its receiver controls, raw aircraft data, tracks, receiver diagnostics or exports.

The overlay supports **Antenna, Internet, Hybrid** manual refresh and separately toggled local-only, Internet-only, both and historical-cache filters. Antenna data come from existing local Tihulu Flight Radar/readsb endpoints only (no new SDR process), Internet reports from the public adsb.lol point API. URL and radius are bounded; user-provided coordinates are explicit, and provider calls are limited to one per 30 seconds. The provider attribution is **adsb.lol / ODbL 1.0**. Old positions are visibly historical, never navigation data. Real aircraft observations are required; no positions are inferred or synthesized.

Source overlay currently complements the full map and does not modify the tar1090 provider itself. A future actual **inside-tar1090 overlay** requires cooperating with the separate Flight Radar code/repository and its service API, which is not silently modified here. It cannot use the same Nooelec for simultaneous FM/DAB and 1090 MHz ADS-B.

## Unified playback, metadata, MOT and languages

The local UI retains persistent FM and TV playback dock, Play/Stop, volume/mute, optional recording indicator and previously verified RDS artist/title when decoded by redsea. **Historical station metadata are clearly timestamped, not claimed to be live synchronized RDS**, because a second FM decoder cannot independently own the single Nooelec concurrently with FM audio. PR #10 provides a manual DAB MOT gallery and honest `not_broadcast` vs `decoder_error`/save states. A live MOT image requires a real broadcast and an already running supported DAB decoder.

Existing AI covers EN/DE/TR source and destination captions with auto/manual CPU/GPU/NPU backend selection and offline model readiness checks. Extra Argos language-pack index and installation are explicit user actions on Translator Page 450. Extra packs currently enable **offline text translation only**, not automatic new live speech-language support. The user must also install a compatible ASR model and adjust the speech pipeline. No download/install performed in background and no invented subtitles.

## Regression gates and open blockers

- Python 3.11/3.12/3.13: offline unit tests, SQLite persistence and HTTP tests.
- JS: `node --check` for local `web/app.js` and Pages `docs/pages.js`, `docs/sw.js`.
- Shell installer: `bash -n` plus safe fast-forward/dirty-checkout regression tests; Windows PowerShell AST/manual smoke remains an independent validation gate.
- Portable import smoke: Windows x64, macOS ARM runner, Linux ARM runner. This does not certify native SDR capture or Pi board drivers.
- Physical FM: missing Whisper model must NOT stop live audio; verify Play, Stop, volume, optional MP3 recording, RDS and station scan using actual on-air signals.
- Physical DAB: welle-cli ensemble and FIC service enumeration, DLS, real MOT Slideshow, image persistence across restart and no-image states on actual RF.
- Hauppauge WinTV-SoloHD 01589: USB identity, driver/firmware, DVB-T2 channel lock, transport stream, full Teletext pages and TV recording acceptance pending hardware setup.
- Authoritative RTL-SDR lease broker, mobile TLS paired gateway, macOS/Windows native driver/backend parity and separate Internet/antenna source semantics must be validated before production release.
- No direct push/merge to `main` until all applicable hardware acceptance gates are met.


## Direct browser WebUSB security and acceptance gate

The Direct USB page has user-gesture-only pairing; it does not choose a device
or begin capture on page load. Browser-owned receiver sessions are explicitly
stopped and released on Stop, tab hide or tab exit; OS/browser crash cleanup
cannot be promised. A competing external readsb or welle-cli process is never
stopped by Pages. The Nooelec is single-tuner, so a WebUSB session cannot run
concurrently with 1090 MHz ADS-B, FM, and DAB.

Direct browser audio uses a small, experimental mono FM discriminator and
browser AudioWorklet; actual over-the-air quality is unverified. Optional
MediaRecorder output downloads on a normal Stop. Raw IQ capture saves bounded
64 MiB .cu8 files and is *not* a decoded station or aircraft feed.
Pinned @jtarrio/webrtlsdr browser JS is fetched from esm.sh on first use:
it is not an OS installation, but requires Internet to load unless the browser
already has a usable cache. Browser-side WebUSB permissions do not bypass
OS driver/udev/kernel requirements. Firefox/Safari remain unsupported.

For Pages publication, in repository **Settings → Pages** select **Deploy from a
branch**, branch `integration/consolidated-pages-webusb-2026-11-06`,
folder `/docs`, and Save. This is a one-time GitHub account setting and is
not available as a write action through this connector. The expected URL is
`https://tihulu.github.io/TIHULU-TEXT-CENTER/`; do not claim a successful
deployment until the actual site opens and the Pages build succeeds.
