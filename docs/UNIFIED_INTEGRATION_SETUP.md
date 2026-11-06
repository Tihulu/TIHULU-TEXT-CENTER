# TIHULU Text Center unified integration — install, Pages and acceptance

Integration draft PR: https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/12

Branch: `integration/unified-text-center-pages-desktop-radar-2026-11-06`

This is **not** a release. It brings PR #8 and PR #10 onto the current AI, translation and live TV baseline. Do not merge into main before tests on the real hardware.

## GitHub Pages preview

The static responsive PWA is in `docs/`; the hardware backend is NOT hosted by GitHub Pages.

1. Open https://github.com/Tihulu/TIHULU-TEXT-CENTER/settings/pages.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Choose branch **integration/unified-text-center-pages-desktop-radar-2026-11-06** and folder **/docs**, then **Save**.
4. When GitHub Pages finishes deploying, preview https://tihulu.github.io/TIHULU-TEXT-CENTER/.
5. The Pages PWA has offline browser-local notes, informational navigation and links to local P410/P420/P450/P880 pages. A USB decoder is not connected to GitHub-hosted infrastructure. The same computer's local backend must be started separately to access its own hardware.

**Important:** a remote phone cannot resolve the PC's `127.0.0.1` (loopback refers to the PHONE). Full mobile control requires an authenticated same-origin TLS gateway and authorized receiver API on the PC/Pi, with permissions and browser local-network protection. No public raw SDR endpoint should be exposed. Until that gateway is implemented, the Pages PWA acts as a launcher/information hub, NOT a live SDR frontend.

## Safe Linux and Raspberry Pi OS install (review scripts first)

Review https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/integration/unified-text-center-pages-desktop-radar-2026-11-06/scripts/bootstrap-unix.sh

Then, if satisfied:

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/integration/unified-text-center-pages-desktop-radar-2026-11-06/scripts/bootstrap-unix.sh | bash -s -- integration/unified-text-center-pages-desktop-radar-2026-11-06
~/.local/bin/tihulu-text-center desktop
```

The script installs the app under `~/.local/opt/tihulu-text-center`, registers a Linux Applications shortcut and uses fast-forward-only updates. It never resets an existing Git repository or deletes `~/.local/share/tihulu-text-center` recordings/database, never downloads models and never starts background RF scans. Your older `~/TIHULU-TEXT-CENTER` checkout is not automatically overwritten. Native desktop UI uses optional PySide6 Qt WebEngine; otherwise a separate browser app window is used.

To use the existing clone instead of a second checkout, review your current Git status, create a new worktree from the integration branch, then run its `bash install.sh`:

```bash
cd ~/TIHULU-TEXT-CENTER
git fetch origin integration/unified-text-center-pages-desktop-radar-2026-11-06
git worktree add -b textcenter-integration-test ../TIHULU-TEXT-CENTER-INTEGRATION origin/integration/unified-text-center-pages-desktop-radar-2026-11-06
cd ../TIHULU-TEXT-CENTER-INTEGRATION
bash install.sh
~/.local/bin/tihulu-text-center desktop
```

Git update is intentionally not allowed across different branches or dirty working trees.

## Windows x64 (experimental)

Review https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/integration/unified-text-center-pages-desktop-radar-2026-11-06/scripts/install-windows.ps1

PowerShell (Python 3.11+ and Git for Windows required):

```powershell
$env:TIHULU_TEXT_BRANCH='integration/unified-text-center-pages-desktop-radar-2026-11-06'; irm 'https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/integration/unified-text-center-pages-desktop-radar-2026-11-06/scripts/install-windows.ps1' | iex
```

This registers **TIHULU Text Center** in Start Menu. It does not bundle Windows RTL-SDR drivers or a tested direct FM USB decoder. Windows remote/local authorized MPEG-TS and online radar are the intended initial supported paths.

## macOS Apple Silicon

The Unix bootstrap above creates a user-local macOS app bundle in `~/Applications/Tihulu Text Center.app`. Python 3.11+, Git, a compatible GUI (native PySide6 QtWebEngine or Chrome/Chromium/Edge/Firefox fallback) and any desired native radio decoder are separate dependencies. No Apple Silicon SDR, TV or audio decoder hardware verification has been claimed.

## Radio, TV, metadata, translation and Flight Radar

- FM, FM RDS/RadioText+, FM Auto Scan, separate FM Spectrum Analyzer, DAB+ service scanning, DLS and MOT run only with appropriate working decoders and an available receiver. Scans are opt-in and sequential.
- An FM radio and ADS-B Flight Radar cannot both tune the same NESDR SmART v5 to unrelated frequencies. Do not stop others' readsb/tar1090, welle-cli or protected recordings.
- Live TV currently relays an authorized local MPEG-TS stream. Hauppauge frontend detection is not itself live DVB-T2/Teletext tuning.
- Captions: original EN/DE/TR and translated tracks, separately archived, with Auto/CPU/GPU/NPU reporting actual model readiness. Extra Argos packs add **text translation** languages; they do not automatically add speech recognition language models.
- Recorded FM/TV media can be transcribed later. Audio/video and SRT/VTT are distinct artifacts. Genuine DAB MOT slideshow is only shown when the broadcaster and decoder supply original image bytes.
- Flight Radar P880 preserves the full tar1090 viewer as a separate option, and adds an on-demand local readsb/Internet adsb.lol/hybrid aircraft overlay. Internet provider terms and source attribution apply. Cached positions are historical, not live.
- All apps stay offline-first with background polling disabled by default. Closing the desktop should free only Text Center-owned tuner subprocesses and scans.

## Acceptance gates (must be checked manually)

Real Nooelec FM listen/stop/record; FM no-ASR fallback; RDS2 metadata; DAB ensemble and actual slideshow; Hauppauge detection, firmware, real DVB lock and TV stream; after-record speech-to-text and additional language pack download; Linux COSMIC application entry, Windows Start Menu and macOS application; Pages PWA offline cache; stale radar data provenance; browser close process teardown; single-device Flight Radar lock; no lost existing recordings or SQLite DB; mobile/TLS gateway security (still not implemented).

Current GitHub CI validates synthetic fixtures, Python syntax/tests and portability import smoke; **it cannot certify physical RF or the full platform acceptance list**.
