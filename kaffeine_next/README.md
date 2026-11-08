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

## Live Whisper quality: GPU, missing speech and longer A/V buffer

The original first implementation threw away **an entire 4-second MPEG-TS
chunk whenever the previous Whisper calculation was still running**.
That creates speech gaps *before* translation. A TV playback delay cannot
restore those lost words.

The new Kaffeine-caption worker accepts **6-second continuous windows** with
approximately **1-second overlap** to preserve syllables/phrases crossing
segment boundaries. Every captured segment enters a chronological **bounded
FIFO** rather than being discarded when inference is busy. The default
desktop queue is 96 MiB (48 MiB on a Pi-family device), up to 24 clips.
This is finite storage, not a claim of guaranteed lossless recording
if CPU processing remains slower than capture indefinitely. The UI reports
queue depth and any overflow explicitly. Repeated words caused by overlap
are trimmed **before** sending the text to Argos/NLLB translation, so they
don't contaminate the translation.

The TV **audio+video delay is now manually adjustable from 0 to 20 seconds**.
The opt-in automatic recommender caps itself at 12 seconds on a desktop,
6 seconds on a Raspberry Pi 5, and may choose less when the actual MPEG-TS
bitrate would exceed the reserved memory. Audio and video are delayed
*together*; this is not the same as a caption-offset/lip-sync meter.
The underlying C++ buffer is still capped at 64 MiB and reverts safely
if an extremely high-bitrate service exceeds the cap.

To determine whether Whisper is actually accelerated, the caption status
explicitly reports **Whisper: GPU / CPU / NPU** and selected model when
the ASR engine is used. Hardware detection in the Model Market alone is
not proof of a working CUDA model. In particular, the Pop!_OS Kaffeine
`--software-video` switch affects **libVLC HEVC video rendering**, NOT
the separate CUDA Whisper speech engine. Both may be enabled together.

For NVIDIA RTX 5080, use Model Market to install the compatible
**CUDA whisper.cpp engine** (requires CUDA toolkit 12.8 or newer) and
a verified multilingual **Large-v3 Turbo / Large-v3 Turbo Q5** model.
Choose GPU or Auto and enable ASR. Large-v3 Turbo generally offers a
better accuracy/speed tradeoff than the default Tiny model, but actual
throughput depends on the installation. A Pi 5 without a supported speech
NPU needs a smaller model to keep up with live speech.

DVB radio audio selection also prefers an ordinary soundtrack tagged for
the requested source language rather than an unrelated language or an
accessibility audio-description track. It falls back to the existing
program audio if no matching track exists.

### Exactly what is delayed (and what is not)

The native Kaffeine DVB callback **duplicates each selected-service TS packet
before the playback buffer**. One copy is immediately sent over the
private UNIX datagram socket to the Python caption worker. Whisper
processes live audio in overlapping six-second windows and Argos/NLLB
then translates the actual recognized words; neither waits for
Kaffeine's delayed video output. The OTHER copy enters Kaffeine's
delayed MPEG-TS FIFO, so audio and video play together after the delay.
It is not an isolated audio track delay.

For example, when a caption becomes ready approximately 7 seconds
after speech enters the RF receiver, 10 seconds of native delayed
playback can give 3 seconds of alignment headroom. If the CPU cannot
process six seconds of speech inside the available playback window,
the worker's queue will grow regardless of how long the display waits.
The queue is bounded; missing RF packets or nonblocking-sidecar drops
cannot be recovered by buffering the video.

**Requested vs actually applied:** the native playback FIFO keeps a
64 MiB maximum and computes a safer bitrate-limited delay with ~48 MiB
of target capacity and 16 MiB of headroom. The caption panel reads
Kaffeine's per-second effective MPEG-TS delay status from the user's
private runtime directory. It shows both requested and applied seconds,
plus the sampled incoming TS bitrate. When a high-bitrate channel,
timeshift or a recovery cooldown reduces the effective delay, the
panel warns rather than falsely presenting the requested time as
what the viewer is actually watching. The number describes the native
FIFO, not VLC's extra decoder/video-output latency. Auto-sync still
requires live processing measurements; it does not guarantee exact
per-word lip sync.

### Broadcaster Teletext language and subtitle-channel picker

The caption settings now discover actual **DVB Teletext subtitle descriptors**
from the currently copied service's PAT/PMT tables. Choose the
real language, PID and page in **Broadcast subtitle channel**, then
press **Apply**. This follows Kaffeine's own subtitle menu behavior
without inventing nonexistent language channels. It also prevents
the old failure where both German and French captions were mixed from
the same Teletext stream. The chosen page is fed directly to FFmpeg
and the signalled source language is used for translation; manual
page entry and pure Whisper transcription remain separate modes.

Initially enabled offline source/target codes are German, English,
Turkish and French. Other languages require language-catalog/runtime
support and an installed translator model; discovery of a Teletext
language alone does not imply it can be translated. For captions
with original only, no translation model is required. Libre DVB
Teletext formatting escape `\\h` is normalized to whitespace
before display or translation.

### Choose a *real* TV audio channel for Whisper

In **TIHULU AI → Live Teletext / Whisper subtitles**, the new **Whisper
source audio channel** picker lists verified audio elementary-stream PIDs
signalled by the currently tuned DVB service's PMT. The first choice leaves
the normal language-aware, non-audio-description preference in place.
Selecting a specific PID means Whisper reads **only** that program audio;
it does not change Kaffeine's own TV soundtrack, retune the receiver,
or open a second tuner. If the selected track disappears, the sidecar
reports an error rather than transcribing a different language silently.

The **Broadcast subtitle channel** picker is independent: select an
actual Teletext language/page/PID for broadcast captions, or use
**Whisper live transcription** for a chosen soundtrack. In **Teletext →
Whisper fallback** mode the subtitle/translation source language follows
the broadcaster Teletext page when text is present; when Whisper is needed,
it follows the selected audio language. Other languages require matching
Whisper and translator support and real installed Argos/NLLB models.
Unknown PMT language codes are not guessed as German.

Native C++ playback buffering and subtitle cue scheduling now take the
**effective** playback delay reported by Kaffeine when its 64-MiB
memory cap reduces the user's requested delay. If no fresh matching
status exists, the UI labels the lateness estimate as unconfirmed instead
of claiming exact synchronization.

## Synchronized live subtitles, embedded on-video OSD and Apply / Reset

In Kaffeine choose **TIHULU AI → Live Teletext / Whisper subtitles**.
The companion remains on top for caption diagnostics, but the subtitles
are now **also drawn natively inside Kaffeine's actual video widget**
without replacing libVLC or Kaffeine's existing EPG/Teletext OSD.

- Source modes: broadcaster-marked Teletext subtitles first with Whisper
  fallback, Teletext-only, Whisper-only, and explicit manual Teletext page.
- Language: German, English, Turkish, optional disabled translation.
  Both spoken words and translation can be shown together on the video.
- Video overlay: toggle on/off, original/translated line switches, position
  top/bottom, font size and black background opacity.
- **Apply** commits all pending control changes atomically and drops
  stale cues from a previous source/language. **Reset** restores controls,
  then **Apply** makes them active.
- **Caption offset:** -10 to +10 seconds. Positive makes text appear
  later; negative requests earlier text, but recognition cannot predict
  speech before a segment has finished decoding.
- **TV playback buffer:** 0–20 seconds. The native Kaffeine MPEG-TS FIFO
  keeps **audio and video together** and optionally delays both behind
  the immediate RF/Whisper capture. This enables more realistic alignment
  without shifting audio relative to the picture. The delay queue is
  bounded to 64 MiB. Kaffeine timeshift is already a separate playback
  mode and is not double-buffered.

Whisper operates on approximately **6-second overlapping audio segments** (plus
inference/translation time); it is not truly simultaneous word-by-word
ASR. A 3–6 second broadcast delay may help where machine processing
is fast enough. Use the live **ASR+translate latency** and
**Caption lateness** readouts to choose a buffer. Default playback
buffer and caption offset are both **0** to preserve live TV and
minimize Pi 5 RAM use.

Subtitles are transferred only via a private 0600 file under the
current user's XDG_RUNTIME_DIR. Untrusted remote clients cannot
write captions. They expire automatically, and all temporary OSD and
buffer settings are removed when the caption controller closes.

### Real translation model detection

The offline Argos translator can live in TIHULU's isolated AI runtime
virtual environment even when the KDE/Qt5 caption process uses system
Python. Caption processing now explicitly invokes that private runtime
with bounded JSON input. It does not fetch translation models at
inference time. Missing German/English/Turkish packages are reported
with an actionable Model Market prompt rather than a generic label.

### Pop!_OS error-log corrections

Previous logs had:
- **QObject::connect: No such slot DvbTab::showFullScanDialog():** Full
  Antenna Scan now connects through Qt's compile-time-checked function
  pointer, not an unchecked string-based slot name. The actual C++
  source is compiled in CI.
- **software-no-audio + Using NVIDIA VDPAU:** the software profile now
  removes conflicting saved libVLC `--avcodec-hw` flags and forces
  `--avcodec-hw=none` both at instance and media level. The fallback
  VLC initialization also preserves software decoding and the
  no-audio diagnostic.
- **kf.i18n: Using an empty domain:** Kaffeine's static EPG genre
  translations are now initialized on first use, after the KDE
  translation domain is configured, not during global initialization.
- **QCommandLineParser: already having an option named h/help-all/v:**
  Qt help and version options are registered once by KAboutData.
- **KServiceTypeTrader: ThumbCreator not found:** missing optional
  KDE thumbnail service; not a DVB/decoder error and no privileged
  system packages are changed to mask it.
- **libEGL / VA-API / VDPAU:** the software decoder profile avoids
  hardware video decode, but this does not fix every graphics output
  driver or RF continuity error. Test on the actual Pop!_OS host.

To verify after updating and fully quitting older Kaffeine windows:

~~~bash
~/.local/bin/tihulu-kaffeine --software-video 2>&1 | tee ~/tihulu-tv-video-test.log
grep -E 'TIHULU playback|Using NVIDIA VDPAU|picture allocation failed|avcodec_send_packet' ~/tihulu-tv-video-test.log
~~~

The log should report an enforced software profile; **any remaining**
NVIDIA VDPAU decoder line or frozen picture needs more diagnosis rather
than a false success claim.

### Automatic synchronization (opt-in)

The companion now includes **Automatic sync · detect caption lag & adjust safe
TV buffer** (OFF by default). Select it and press **Apply**. It collects at
least **three real live Whisper/Argos results** and compares the audio
capture start against the timestamp at which the translated caption became
available. The display shows:

- **Estimated caption availability lag**, measured from actual processing.
- **Safe TV playback buffer range** and a recommended delay in seconds.
- Sample count and whether the safe hardware/memory limit was reached.

With automatic sync OFF, the recommendation is informational; **manual
caption offset and playback delay are not changed**. With it ON, the first
valid recommendation is applied to Kaffeine's existing audio+video MPEG-TS
buffer; later changes have a 30-second cooldown, 0.75-second hysteresis and
at most 0.5-second adjustment to avoid rapid playback stalls.

Automatic TV delay is limited to **15 seconds** on normal Linux systems,
**6 seconds** on Raspberry Pi 5 and a stricter value if the current
transport-stream bitrate would consume more than roughly **48 MiB**.
Manual playback delay supports 0–20 seconds; the 64 MiB native queue still limits what the hardware can safely buffer. When the
observed lag is above the safe maximum, the UI warns that speech/text
can remain late rather than pushing the buffer past its memory budget.

**Accuracy limitation:** this is an *availability-lag estimator*, not
speaker diarization, word-level Whisper timestamps or an independent
audio/video lip-sync meter. It cannot reconstruct the exact position of
each word inside a six-second audio chunk (with a short overlap). Manual **Caption offset**
remains available for visual fine-tuning; automatic mode does not
fabricate a precise text offset. Broadcaster Teletext is not used to
train Whisper latency and changing the DVB service clears measurements.

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

## Diagnosing missing words vs GPU inference

This version has independent end-to-end timing and transport telemetry.

- **Stage timings:** Teletext extraction, Whisper ASR, translation and
  total duration are reported separately. A 6-second Whisper chunk
  can take *longer than 6 seconds* when the CPU is too slow.
- **Backlog:** remaining queued capture clips and MiB are shown. Workers
  process clips in chronological order with a one-second overlapping
  tail; a full queue reports missed seconds rather than silently claiming
  there is no loss.
- **TS continuity gaps:** the sidecar now measures MPEG-TS discontinuities
  and requests a larger private UNIX socket receive buffer. Gaps can
  originate from antenna reception **or from Kaffeine's nonblocking
  sidecar packet sends**. This metric alone cannot blame the antenna.
- **Faster-Whisper on CUDA:** when the optional CUDA Faster-Whisper
  model/runtime is actually present, its large model is cached in GPU
  memory for subsequent short clips instead of loading weights anew
  for every clip. The whisper.cpp CLI path still starts an executable
  for every chunk and can have substantial loading overhead.

Use the read-only health command **without acquiring the DVB frontend**:

~~~bash
tihulu-tv-center ai-check
~~~

This prints the RTX/GPU/NPU discovery, selected backend, installed model,
CUDA-runtime readiness and translator backend separately. A detected
RTX 5080 is *not* proof that Whisper inference runs on the GPU.

For the settings UI, use `tihulu-tv-center ai-market`. Install a
multilingual GGML model and a compatible CUDA whisper.cpp runtime, choose
**Auto** or **GPU** in the market, save the settings, and reopen Kaffeine's
captions controller. If the output reports CPU, adjust the backend or
model rather than increasing TV playback delay indefinitely.

**Sync:** Automatic sync is optional (default OFF). Three real ASR
samples are required before it recommends delaying both video and audio.
The safe recommendation respects the current MPEG-TS bitrate and the
native 64 MiB bounded FIFO. Speech cannot be aligned earlier than
Whisper/translation finishes, and longer buffering is not a cure for
missing or corrupt incoming TS packets.

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

Kaffeine now includes the **experimental native on-video subtitle
OSD**. Closing the separate settings panel does not stop the caption
worker; use **Stop subtitles & Exit** to end it. This is source-build
tested, but not yet accepted on the user's live WinTV-soloHD hardware.
Verify current KiKA/ARTE Teletext, German speech, Turkish/English
translation, switching channels, and iPhone HLS before a stable release.
