# TIHULU Satellite Center — GitHub Pages and desktop install

This additive companion is not merged into Text Center or Survival Kit yet.
It uses port **8791** only on **127.0.0.1**, without starting a receiver or
fetching TLE data in the background. It cannot control USB directly from Pages.

## v0.15 — Satellite Images and source-attributed recordings (2026-11-06)

**Satellite Images** in the browser-only/Pages app offers two distinct,
non-interchangeable acquisition paths:

1. **Received with user's RTL-SDR:** actual ISS **Robot36 SSTV** events
   (frequency and image mode are event-dependent; consult the
   [ARISS schedule](https://www.ariss.org/upcoming-sstv-events.html)).
   Select a locally captured demodulated FM WAV, or experiment with
   recorded unsigned CU8 → narrowband FM → 1200 Hz sync detection →
   320×240 Robot36 conversion. A decoded image is only shown if there
   are repeated, aligned audio syncs. All such decodes are experimental
   candidates, never assured ISS origin. Raw frequency power/geometry
   does not count as a received image.
2. **Meteor-M2-3/M2-4 LRPT:** locally captured CU8 can be decoded with
   the optional native SatDump CLI. The installed companion supports
   72k/80k pipeline choices and displays only real SatDump PNG/JPEG
   outputs. No unsupported promise to decode Meteor LRPT in the
   browser-only page; the in-browser RF/FM/Robot36 path is SSTV only.
3. **Online original imagery:** NASA DSCOVR EPIC Earth photographs and
   historic ISS Earth photographs from the NASA Images archive are
   requested *on demand* via official NASA APIs. The online gallery
   labels actual source and acquisition timestamps and never presents
   external NASA downloads as if they were received via the local USB
   antenna. NASA API rate limits/CORS may require opening the official
   gallery. Official EUMETSAT and NOAA weather image viewers are also
   linked for international use.

**Filename convention:** `TIHULU_<SATELLITE-CANDIDATE>_<YYYYMMDDTHHMMSSZ>_<FREQUENCY>Hz[_<SAMPLE-RATE>SPS]_<IQ|SSTV|LRPT|...>.<ext>`.
UTC avoids Windows/macOS/Linux/Raspberry Pi timezone ambiguity. Unknown
attribution is explicitly `RF-UNATTRIBUTED`; observing a TLE pass is
not proof of the transmitted signal's identity. Existing legacy raw
recordings remain openable. The most recent browser I/Q recording
is available for local FFT analysis and optional experimental SSTV
decode, without uploading samples.

**Shared cross-platform UI:** The installed Python local companion
on Debian/Ubuntu/Pop!_OS, Raspberry Pi OS, Windows x64 and macOS Apple
Silicon now exposes **Open live map and Satellite Images**, loading the
exact same browser sources as GitHub Pages from its local
`/browser/index.html` route. The 1-second LIVE TLE view, Pause, Sky,
Earth map, and image gallery thus share one implementation.
The embedded web interface is only loaded when requested and releases
its own USB session on close. Two SDR frontends cannot own the same
physical dongle simultaneously. Page-only WebUSB requires a compatible
desktop Chromium-family browser; the desktop companion uses its native
RTL-SDR tools for its own capture workflows.

**Verification limits:** Core browser JS parses, UI controls are wired,
image-naming metadata round-trips, and synthetic 240-scan-line Robot36
audio yielded a 320×240 candidate. Cross-platform CI is defined for
Ubuntu x64/ARM, Windows, and macOS, but physical SSTV/LRPT, receiving
antennas, browser CORS and native hardware remain unverified until
tested on compatible real RF data. No fabricated space imagery.

## GitHub Pages publishing (separate branch, main stays unchanged)

A dedicated **`gh-pages`** branch now exists in the same repository, containing
only static public pages: `index.html`, `satellite_center/index.html`,
`satellite/index.html`, `404.html`, and `.nojekyll`. The source application
and draft PR remain unchanged until independently reviewed.

**Required one-time repository-owner action:** visit
`https://github.com/Tihulu/TIHULU-TEXT-CENTER/settings/pages`, then
**Build and deployment → Source: Deploy from a branch → Branch: gh-pages →
Folder: /(root) → Save**. The companion cannot enable repository Pages
settings through the current GitHub connection. Once GitHub finishes deploying,
the expected static entry points are:

- `https://tihulu.github.io/TIHULU-TEXT-CENTER/`
- `https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/`
- `https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite/`

These URLs should **not** be called live until GitHub Pages reports a successful
deployment. The account homepage `https://tihulu.github.io/` may still return
404: this is a **project** site under the repository path.

The `gh-pages` branch is a snapshot of the Satellite Center UI; further
changes to the draft feature branch are **not automatically deployed** until
the static HTML is copied to the Pages branch. Never put the Python backend,
recordings, credentials, or pairing tokens on Pages.

## Hosted UI using the existing repository

No second repository and no Pages workflow replacing the current site is
needed. In GitHub **Settings → Pages**, keep the current publishing source.

- Source = branch `main`, folder `/(root)`: hosted path
  `https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/`
- Source = branch `main`, folder `/docs`: hosted path
  `https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite/`

The HTML is mirrored at `satellite_center/index.html` and
`docs/satellite/index.html` for both source layouts. These are **intended
paths**, not verified live deployments: this feature is currently in a draft
PR, not on `main`. After review/merge, enable/check Pages if needed.

## Hardware pairing

Install the companion program on the **same computer** as your RTL-SDR. Start
its dashboard at `http://127.0.0.1:8791/`; select **Reveal GitHub Pages
pairing token** and copy the 64-hex-character secret to the official hosted
page. The token remains in JS memory, never URL/localStorage. The backend
also checks HTTP Host, exact allowed Origin, bearer authentication and CSRF.
Do not share the token. The server is loopback-only, not a public relay.

Chrome/Edge may ask for explicit *loopback-network* permission; Safari can
block cross-origin HTTPS-to-HTTP localhost entirely, so use the **local**
dashboard on Safari. Mobile phone browser localhost means the phone itself:
remote desktop access is **not** supported without an independently secured
TLS/authenticated local portal. No public USB/WebUSB promise.

## One-line install (draft branch)

For **Debian, Ubuntu, Pop!_OS, Raspberry Pi OS** (32/64-bit) and
**macOS Apple Silicon or Intel**, with `git`, `curl`, Python 3.11+,
Python `venv`:

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/feature/satellite-center-standalone-2026-11-06/satellite_center/install/install.sh | bash
```

For **Windows 10/11 x64 PowerShell**, with Python 3.11+:

```powershell
irm https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/feature/satellite-center-standalone-2026-11-06/satellite_center/install/install.ps1 | iex
```

Review these downloaded scripts before executing; piping remote text to a
shell gives code access to your account. Run as a normal user, not root or
Administrator. The installer downloads the explicitly selected Git branch,
creates a private Python environment, installs Skyfield and a local launcher.

After the PR is merged, use `TIHULU_CHANNEL=main` (Linux/macOS) or
`$env:TIHULU_CHANNEL='main'` (Windows) and switch URLs to `/main/`.

**Installed launchers:**

- Linux: `~/.local/bin/tihulu-satellite` and the Applications-menu shortcut.
- macOS: `~/Applications/TIHULU Satellite Center.command`.
- Windows: Start Menu → TIHULU Satellite Center.

The dashboard works for orbit planning without radio tools. **To capture
real RF** you must separately provide drivers, USB permissions, tools and
a suitable antenna:

- Debian/Pi: `sudo apt install rtl-sdr multimon-ng`; possible DVB kernel
  driver contention/udev changes require manual hardware configuration.
- macOS M-series: `brew install librtlsdr` (rtl_power/rtl_sdr/rtl_fm).
- Windows: install native RTL-SDR command-line tools and a compatible
  WinUSB driver separately; verify `rtl_test`. Driver changes are not
  performed by the installer.
- Meteor LRPT image decoding additionally needs the installed `satdump`
  CLI supported pipeline; SSTV image output requires a separate decoder.

Iridium support is only **orbital tracking and RF power surveying**, never
private messaging decoding or satellite authentication.

## Scheduler and safety

Pending passes survive process restarts in local disk storage. Execution,
however, **requires the companion process to remain open**. No Windows
Scheduled Task, macOS LaunchAgent, Linux systemd unit, autostart, or hidden
RF/network polling is enabled by these installers. The separate opt-in
always-running service workflow is left for later testing.

Only one RTL-SDR is reserved at a time; Linux uses the Text Center
cooperative lock. On Windows/macOS, the companion uses its own local lock,
and third-party SDR programs might not respect it. Do not run readsb,
welle.io or another exclusive SDR client simultaneously.

Tests cover local HTTP authorization, cross-origin rejection, token
persistence and existing synthetic satellite receivers. No physical hardware
acceptance has been performed on Windows, macOS, Raspberry Pi or Pop!_OS in
this build.


## Releasing the RTL-SDR on exit (v0.2.2)

- Closing the Satellite Center **browser tab** sends a best-effort authenticated
  departure request that immediately stops that tab's **manual** capture.
- If browser cleanup is dropped, a missing status heartbeat automatically stops
  its manual scan after approximately **14 seconds**. Scheduled captures that
  were explicitly authorized are exempt; they can execute with the tab closed,
  **only while the companion service remains running**.
- **Quit companion & release SDR** stops the companion and every subprocess
  it launched, including `rtl_power`, `rtl_sdr`, `rtl_fm` and decoder pipelines.
  SIGTERM, Ctrl+C, and normal server closure use the same owned-child cleanup.
- Previously queued jobs remain on disk but cannot execute while the companion
  is shut down; restarting the app may resume pending future jobs.
- The shared receiver file lock is released after the capture worker exits.
  Other applications such as `readsb`, `welle.io` and Flight Radar are **never
  killed or disabled**. If `readsb` owns the dongle, it remains busy until you
  stop `readsb` yourself. Abrupt OS process kill/power loss cannot guarantee
  cleanup on every platform; actual hardware verification is still pending.

Suggested Linux diagnostics after stopping the companion:

```bash
pgrep -a -f '(^|/)(rtl_power|rtl_sdr|rtl_fm)( |$)' || true
systemctl is-active readsb || true
```

The first command may also show SDR processes owned by other applications.
Do not terminate unrecognized processes automatically.


## v0.2.3: USB connection and TV tuner classification

The Pages and local dashboards now provide a first-run **Connect your USB SDR**
guide, including operating-system-specific installation commands,
cross-origin pairing steps, antenna coax wiring and an explicit **Test USB
receiver (temporary access)** action. USB diagnostics never start automatically.

### Physical Nooelec NESDR SMArt v5 setup

1. Insert the **Nooelec NESDR SMArt v5 RTL2832U** into a USB port (or a stable
   powered hub). Connect the antenna coax to the dongle's **SMA RF input**.
   A USB plug goes into the computer; an antenna connector does not.
2. Select an antenna suited to the band. ISS VHF is near 145 MHz; Meteor-M
   weather downlinks use ~137 MHz (V-dipole/QFH recommended); Iridium NEXT
   uses 1616–1626.5 MHz (L-band antenna and usually a suitable LNA/filter).
   A TV antenna is not automatically suitable for these bands.
3. Install and launch the **local** Satellite Center companion on the
   USB-connected computer. On Pop!_OS/Debian/Raspberry Pi OS, optionally
   install `rtl-sdr` utilities with `sudo apt install rtl-sdr`.
4. Open `http://127.0.0.1:8791/` ON THAT COMPUTER and click
   **Reveal GitHub Pages pairing token**. Copy the full local 64-hex-character
   secret. It is *not* an SDR serial number, a GitHub token, or a password
   supplied by an antenna.
5. Paste the token into the HTTPS GitHub Pages view; click **Connect**.
   Click **Test USB receiver**. It requests the selected `rtl_test -t`
   executable, and reports real hardware-open evidence only. Some R820T
   tuners correctly report that E4000-specific tests are not available;
   the app does not treat this as an RF reception failure.
6. If you see **CONFLICT: readsb** the same RTL-SDR is already being used by
   Flight Radar. Only if you intend to pause it, stop it manually with
   `sudo systemctl stop readsb`; Satellite Center will **not** terminate
   other applications. When the test completes, it releases its own SDR
   subprocess and receiver lock. Re-enable readsb only when you choose.

**Amazon ASIN B0152XLPFS** is **Hauppauge WinTV-soloHD model 01589**.
The manufacturer documents **DVB-T, DVB-T2 and DVB-C**, and a bundled portable
terrestrial TV antenna; it does **not** support DVB-S/S2 or general RTL-SDR
satellite capture. It belongs to the existing Text Center's
`textcenter/dvb_hardware.py` TV detection, NOT Satellite Center's Nooelec
SDR selection. Official Hauppauge specs:
`https://hauppauge.de/site/products/data_solohd.html`.
Product: `https://www.amazon.de/dp/B0152XLPFS`.

### Diagnostic safety

`POST /api/usb-test` is the same authenticated, owner-initiated, CSRF-checked
operation as captures. It requires `rtl_test`, checks for active job /
cooperating lock / known `readsb` conflicts, runs a bounded test for a
maximum of about seven seconds, and stops only its own child. Successful
device-open evidence is **not** proof of an RF signal, satellite, or data
decode. On Windows/macOS installed USB tools and drivers are still required;
passive Linux sysfs inventory is not available there. No drivers are
silently modified and no unrelated SDR processes are killed.
