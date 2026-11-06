# TIHULU Satellite Center — GitHub Pages and desktop install

This additive companion is not merged into Text Center or Survival Kit yet.
It uses port **8791** only on **127.0.0.1**, without starting a receiver or
fetching TLE data in the background. It cannot control USB directly from Pages.

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
