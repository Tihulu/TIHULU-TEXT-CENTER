# Satellite Center — standalone satellite SDR companion

**Independent of TIHULU Text Center and the Survival Kit.** The receiver backend
lives in the [Satellite Center draft feature branch](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/9).
The public web UI is published separately on the repository's `gh-pages` branch.

**Web:** https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/

**Local USB service/dashboard:** http://127.0.0.1:8791/

## What the satellite app does

- Predict potential ISS, Meteor-M, amateur CubeSat and Iridium NEXT passes
  using cached or operator-refreshed CelesTrak orbit data, with observer
  coordinates anywhere in Europe, Germany, Türkiye or elsewhere.
- Scan allowed RF bands manually using a local RTL-SDR; save bounded raw I/Q,
  ISS APRS text if `multimon-ng` is available, or FM/WAV for external SSTV
  decoder tools.
- Use installed SatDump to try converting real Meteor-M LRPT captures into
  images. Images only appear after an actual successful decoder run.
- Schedule opted-in passes while the local receiver companion remains running.
  An orbital pass is not proof of a transmission or received data.
- Track Iridium satellite positions and relative RF energy only. This does
  not decode private user traffic, authenticate Iridium transmissions or
  identify an individual satellite from an energy peak.
- Release Satellite Center's own SDR subprocesses when stopped or closed.
  It never kills `readsb`, Gqrx or other independent SDR applications.

## Install / update — ONE LINE

Run the installer as your **normal user**, after reviewing its source. The
installer clones/updates the feature branch under your home directory,
creates a Python virtual environment and installs the Skyfield orbital
library. It **does not** secretly install SDR drivers, start captures, or
enable a background network listener.

### Linux: Debian, Ubuntu, Pop!_OS; Raspberry Pi OS (ARM32/ARM64)

Requires `git`, Python 3.11+ and `python3-venv`.

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/feature/satellite-center-standalone-2026-11-06/satellite_center/install/install.sh | bash
```

Launch from Applications (**TIHULU Satellite Center**) or run:

```bash
~/.local/bin/tihulu-satellite
```

For radio hardware tools (Debian/Ubuntu/Pop!_OS/Raspberry Pi OS), install
separately:

```bash
sudo apt install rtl-sdr
```

This is a recommended explicit step, **not** a hidden dependency installed
automatically. If `readsb` is using the dongle, close/stop it manually
*only when you want to pause Flight Radar*. Satellite Center will not
preempt it. If Linux driver/udev permissions prevent opening the USB
receiver, review the OS and hardware driver setup.

### macOS: Apple Silicon (M1/M2/M3/M4) or Intel

With `git`, Python 3.11+ and `venv`, the same Bash one-liner works.
The installer creates `~/Applications/TIHULU Satellite Center.command`.
Install SDR command-line utilities separately if required, for example
`brew install librtlsdr`. A native `.app` bundle is **not** produced.

### Windows 10/11 x64 (PowerShell)

Requires Python 3.11+ available via `py` or `python`.

```powershell
irm https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/feature/satellite-center-standalone-2026-11-06/satellite_center/install/install.ps1 | iex
```

Open **TIHULU Satellite Center** via the Start menu. Windows RTL-SDR
binaries on PATH and a compatible WinUSB driver may be required for USB
access; the installer never changes drivers automatically. A standalone
signed `.exe` is not yet provided.

The current installer links to a **draft development branch**, not a stable
numbered release. If that branch is deleted, these direct URLs will need
to be replaced with a release/tag or the eventual `main` location.

## Connect USB SDR from GitHub Pages

1. Insert the **Nooelec NESDR SMArt v5** RTL-SDR into the computer's USB port.
   Connect a suitable RF antenna to the dongle's SMA antenna input.
2. Start the local companion, open `http://127.0.0.1:8791/`.
3. On the **local** page choose **Reveal GitHub Pages pairing token**.
   This is a secret **64-character hexadecimal token**, not the dongle's
   serial number, GitHub password or an antenna identifier.
4. Visit the hosted Satellite Center page on the **same computer**; paste
   the pairing token and choose **Connect to 127.0.0.1:8791**.
5. Choose **Test USB receiver (temporary access)**. This temporarily uses
   `rtl_test` to confirm receiver opening and releases it afterward;
   it does **not** prove that satellites or radio signals were detected.

For Meteor-M weather downlinks, consider a 137 MHz V-dipole or QFH antenna.
For ISS VHF signals, use an antenna suitable for about 145 MHz. Iridium
L-band around 1.6 GHz generally needs its own properly matched antenna,
often with a suitable filter/LNA. The bundled telescopic antenna is not
equally suitable for all these services.

### About Amazon ASIN B0152XLPFS

The linked **Hauppauge WinTV-soloHD 01589** is a DVB-T/T2/C television
receiver and belongs to the *TV/DVB* capability of Text Center. It is **not**
a replacement satellite SDR, not DVB-S/S2, and does not receive ISS/Meteor
or Iridium data just because it connects via USB.

## Safety and limits

- **GitHub Pages does not itself talk to USB.** Local helper is required.
- Receiver lock prevents cooperative Text Center conflicts, and known
  Linux third-party SDR process conflicts (including readsb) are rejected.
  It cannot guarantee all unrelated SDR applications will respect the lock.
- Closing the browser tab stops an owned *manual* scan; explicitly scheduled
  scans may continue while the local helper stays running. **Quit companion
  & release SDR** also stops Satellite Center's own RF child processes.
- Scheduled captures require a running local helper, no autostart daemon is
  installed by default. A phone's `localhost` is the phone, not the
  USB-connected PC. Safari and other browsers may limit cross-origin
  HTTPS-to-HTTP loopback access; the local dashboard remains available.
- No real Nooelec, Windows, macOS ARM or Raspberry Pi satellite reception
  has been certified by automated tests. Hardware behavior must be
  validated on the target device.

For implementation, current test status and open issues see
[PR #9](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/9)
and [Satellite Center WEB_AND_INSTALL.md on the feature branch](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/feature/satellite-center-standalone-2026-11-06/satellite_center/WEB_AND_INSTALL.md).
