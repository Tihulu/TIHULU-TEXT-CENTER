# TIHULU TV — Kaffeine-native rebuild (experimental)

A **real C++ source-code extension of KDE Kaffeine**, not another
unrelated Python DVB player. Uses pinned Kaffeine **v2.0.19** at immutable
upstream commit **e7ea15b86dafed3b20b151cbcb080578ab8e2d5c**.
Source transformations are in patch_upstream.py and keep Kaffeine's GPL
licensing and contributor notices.

## One-line installation

Debian/Ubuntu/Pop!_OS and 64-bit Raspberry Pi OS:

~~~bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/architecture/kaffeine-core-tv-2026-11-07/kaffeine_next/install.sh | bash
~~~

Read the script first if preferred. It installs the KDE/Qt5 DVB build
dependencies, clones verified upstream code, patches, compiles and installs
the new application under HOME/.local/opt/tihulu-kaffeine. The normal
installer also attempts to install user-owned Whisper Tiny (~78MB),
whisper.cpp CPU and German/English/Turkish Argos translation packages.
A failed model installation does NOT uninstall or disable TV. All downloads
are initiated by the user's explicit installation action.

Start:

~~~bash
~/.local/bin/tihulu-kaffeine
~~~

A separate **TIHULU TV (Kaffeine)** desktop entry is installed. The original
system Kaffeine executable and personal channel database are preserved.
Both Kaffeine builds may share settings, so back up settings before
experimenting; close the original Kaffeine before starting the fork.

## Kaffeine-style player and native antenna scan

**There is now only one default television interface:** Kaffeine's original
channel sidebar, live player, normal playback controls, EPG, channel editor,
Teletext and recording UI. Opening either `tihulu-tv-center` or
`tihulu-kaffeine` launches **Kaffeine's Television tab**. The separate
Python player and w_scan_cpp scanner have been withdrawn from the default
route; the old preview is available explicitly through
`tihulu-tv-center legacy-player` for debugging only.

To use the **actual native Kaffeine antenna scanner** on a device already
known to receive the three DVB-T2 multiplexes:

1. Quit any other Kaffeine or DVR program which owns the same DVB frontend.
2. Open **Television → Configure Television → Device 1 → DVB-T2**.
   Ensure **DVB-C Source = No Source** for an aerial antenna, and select
   **Source = TIHULU tested: 538 / 586 / 626 MHz** for DVB-T2.
   This targeted source uses the frequencies previously detected on the
   owner's antenna, not fabricated channel entries. It is optional and
   not a claim about other cities in Germany.
3. Choose **Television → Full Antenna Scan...**. If video is playing,
   confirm that Kaffeine may stop live playback temporarily: this releases
   the frontend for a full frequency sweep rather than restricting the
   normal **Channels** editor to the currently playing transponder.
   Select **Terrestrial (T2)** as Source, then Start Scan. Kaffeine itself
   tunes and obtains real channel service tables. When services appear,
   choose TV/free-to-air filters, **Add Filtered** or **Add Selected**, then OK.
4. Alternatively use Kaffeine's own **Autoscan** DVB-T2 source for a
   broader real frequency sweep. It can take longer and may fail to
   resolve services if RF signal or PLP selection is unstable.

The targeted scan source is implemented *inside Kaffeine's own
DvbManager::getTransponders* so it continues working even if the optional
scanfile.dvb is missing or stale. This does not use w_scan_cpp, dvbv5-scan,
Python USB access or WebUSB, and does not touch saved channel databases.

For separate receiver health diagnostics (which must **not** take the tuner
away from Kaffeine), run `tihulu-tv-center kaffeine-doctor`. Lock and
C/N/UCB cannot be honestly measured while Kaffeine owns the tuner; use
Kaffeine's own scanning UI metrics instead.

## Feature architecture

- **Real TV:** upstream Kaffeine owns USB DVB device, discovery/scanning,
  EPG, favorites, DVR/timeshift, built-in Teletext and existing libVLC player.
  The user's Kaffeine scan results, not new synthetic channel catalogs, are
  the starting point.
- **Whisper & Translator Market:** native Kaffeine TIHULU AI menu opens
  the existing installed market with Tiny/Small, DE/EN/TR Argos packs,
  external SSD storage, user-managed updates/deletions and backend
  CPU/GPU/NPU compatibility checks. No AI inference runs by default.
- **Caption and Teletext:** a separate always-on-top caption controller
  offers real Teletext page 100-899, broadcaster subtitle, Whisper ASR and
  fallback. Source and translated captions are displayed together, with
  actual processing latency. A user-selected 10-second segment plus
  inference latency means this is NOT word-for-word instantaneous.
- **Same tuner, selected channel:** Kaffeine's DvbLiveView copies its
  already-filtered MPEG-TS packets into a bounded nonblocking private
  UNIX datagram socket only when a caption consumer is listening.
  No second frontend open, scan or PID filter; slow AI consumers drop their
  own copies and cannot block ordinary TV playback.
- **iPhone/Android from the same Wi-Fi (experimental):** caption controller
  can explicitly enable local Wi-Fi access with a six-digit PIN; separate
  H.264/AAC HLS switch transcodes the current Kaffeine program using
  FFmpeg. The program ID is extracted from the real MPEG-TS PAT. Changing
  the service stops the old HLS stream; restart manually. iPhone Safari
  supports native HLS; Android may need the bundled web client's hls.js
  library which is currently loaded from the Internet.
- **GitHub Pages:** informational/static web companion. Pages/WebUSB
  cannot access Kaffeine's tuner remotely or replace Linux DVB drivers.
  Telephones use the locally paired host web app.

## Pop!_OS / COSMIC / Conda Qt5 linker troubleshooting

When the old installer ends with a long list of
libQt5WaylandClient.so.5 missing QVulkanInstance or Qt_5_PRIVATE_API
symbols, the **link stage failed**. The missing executable/launcher is
a consequence of that earlier failure, not a missing PATH entry.
It often indicates that the linker picked Qt components from incompatible
builds (e.g., Conda base Qt5 plus Ubuntu Qt5) or the distro has
inconsistent Qt5Gui/Qt5WaylandClient packages. It is not proof that
Kaffeine's DVB device or Vulkan GPU acceleration is broken.

The updated one-line installer now configures and compiles using a
**clean system toolchain environment**, ignoring Conda linker/CMake/Qt
plugin path variables. It uses CMake --fresh in a new build directory,
so previously contaminated CMakeCache.txt cannot be reused. The
finished XWayland launcher similarly ignores Conda's Qt plugin and
library paths. Existing Kaffeine, SDR apps and the old build directory
remain untouched.

Retry the same installer from any shell, including (base); no manual
Conda deletion required. Build logs are saved under
HOME/.local/share/tihulu-kaffeine/logs/configure.log and build.log.

If undefined Qt_5_PRIVATE_API symbols remain after a clean build, inspect
the distribution packages before modifying system libraries:

~~~bash
dpkg-query -W libqt5core5a libqt5gui5 libqt5waylandclient5 qtbase5-dev
apt-cache policy libqt5gui5 libqt5waylandclient5
ldd -r /lib/x86_64-linux-gnu/libQt5WaylandClient.so.5 | grep -E 'not found|undefined'
~~~

**Do not** work around missing Qt symbols by ignoring linker errors,
forcing ABI-incompatible libraries or replacing system libQt5Gui.
The source-build CI proves it works with Ubuntu 24.04 distro Qt;
a particular desktop still needs runtime and DVB hardware testing.

## Live video freezes or stalls — Pop!_OS / COSMIC / NVIDIA

The tuner and Kaffeine must not be replaced with another scanner. There
are **two independent causes** of a frozen live picture:

- **RF loss:** the previous Hauppauge WinTV-soloHD tests showed real
  uncorrected blocks (UCB) and MPEG-TS continuity errors. Software
  cannot reconstruct missing DVB packets. Reposition the indoor aerial
  and compare a free-to-air channel at 538/586 MHz; keep other DVB apps
  closed during TV playback.
- **HEVC/AAC-LATM/libVLC decoder:** NVIDIA + Wayland/COSMIC previously
  produced VA-API/VDPAU initialization failures. libVLC may also emit
  AAC-LATM unsupported subframe warnings. A good signal is not proof that
  the decoder is healthy.

The Kaffeine-native app now has three per-session playback profiles,
without changing system Kaffeine, AI settings, channel lists or the tuner:

- Normal launcher: `~/.local/bin/tihulu-kaffeine`. On NVIDIA **and**
  Wayland it selects a software decoder profile by default. On Pi 5 and
  other systems it leaves Kaffeine's original libVLC selection alone.
- `~/.local/bin/tihulu-kaffeine --software-video`: explicitly disables
  libVLC accelerated decoding and applies 1500ms file FIFO caching.
  Requires more CPU; compare a known free-to-air HEVC channel.
- `~/.local/bin/tihulu-kaffeine --auto-video`: return to Kaffeine's
  original hardware-decoding preferences for performance comparison.
- `~/.local/bin/tihulu-kaffeine --diagnose-no-audio`: same software video
  path, temporarily disable audio, to isolate the previous AAC-LATM
  issue. This is *diagnostic only*, not a replacement for audio support.

Kaffeine **Settings → Configure Kaffeine → libVLC arguments** continues
to take precedence if you explicitly set hardware decoding or caching
flags there. The profiles apply at process startup, so quit Kaffeine
fully before switching. Logging can be captured with:

~~~bash
~/.local/bin/tihulu-kaffeine --software-video 2>&1 | tee ~/tihulu-tv-playback.log
~~~

Do **not** assume the new profile fixes antenna signal loss. Look for
VLC decoder failures and compare with DVB signal lock/UCB changes. When
TV plays normally but the caption panel stutters, close the AI consumer
temporarily to distinguish Whisper CPU saturation from playback.

## Known limitations and cautions

Kaffeine itself uses **libVLC**. Existing VA-API/VDPAU, AAC-LATM, HEVC
and signal/UCB problems will not disappear simply because the DVB
foundation is Kaffeine. The prior tests found severe RF continuity and
uncorrected-block problems; these must be tested again on hardware.
Do not run two DVB applications against the same frontend.

Remote TCP port 8769 is **OFF by default**. Pairing uses unencrypted
HTTP and must be enabled only on trusted Wi-Fi; never port-forward.
For external access use owner-authenticated HTTPS/Tailscale Serve.

**This version supports Linux DVB hosts**, including a Raspberry Pi 5
only if its hardware and codecs work with the distro. Windows/macOS
native DVB/BDA backends are not implemented. iPhone/Android/browser
access to the Linux receiver is cross-platform. Actual WinTV-soloHD
and Raspberry Pi 5 acceptance tests remain pending.

The caption controller is a separate always-on-top window; an embedded
Kaffeine video OSD is a later UI improvement. Verify current KiKA/ARTE
Teletext, German speech, translated Turkish subtitles, switching
channels, and iPhone HLS before calling this a stable release.
