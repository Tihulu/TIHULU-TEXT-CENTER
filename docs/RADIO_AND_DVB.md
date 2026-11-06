# Radio playback, broadcast metadata, station images and Hauppauge DVB setup

TIHULU TEXT CENTER v0.4 — English UI, offline-first, default background RF/network activity OFF.

## A. Known Pop!_OS hardware state (from user's November 6, 2026 check)

- Nooelec NESDR SMArt v5 on Linux USB 0bda:2838: detected. Passive ID does not guarantee an exclusive tuner lease or real signal.
- rtl_fm, rtl_power and redsea: installed; actual live RDS/RT+ success still requires a real antenna capture and appropriate broadcasts.
- rtl_433: installed. Other SDR services and readsb must be protected.
- welle-cli: not found in last check (the separate welle.io GUI may work independently).
- dvbv5-scan/zap, direwolf, multimon-ng, fldigi and dream: not found in last check.
- A Linux adapter0/frontend0 path was present in the last report. That path is NOT automatically identified as the not-yet-delivered Hauppauge receiver.

## B. Local FM radio listening and metadata

Update and launch:

```bash
cd ~/TIHULU-TEXT-CENTER
git pull --ff-only
python3 -m unittest discover -s tests -q
python3 -m textcenter receivers
python3 -m textcenter serve
```

Open http://127.0.0.1:8787/ and choose **Radio Data (400)**.

- **FM Audio: Record & Listen** generates a 10–20-second mono WAV preview from real rtl_fm decoded audio; the browser's audio controls can then play it. It uses only the local USB dongle and no Internet or redsea. This is NOT continuous radio streaming. Audio remains in memory until another preview or server shutdown.
- **FM RDS / RadioText+** supports explicit sessions up to 90 seconds, source station labels, text, PI, rich RT+ artist/song tags, programme type (PTY), traffic programme/announcement (TP/TA) and broadcaster-supplied music flags. RDS text is unauthenticated broadcast data, not an official emergency alert.
- **RDS2 station logos** may be captured only after checking the explicit image checkbox. Requires a redsea release with `--streams` support (v1.2+; check `redsea --help`). This can increase decoder CPU by 3–4x. Most broadcasts will have no RDS2 logos; the UI must display that truthfully. The logo bytes are stored only after bounded PNG/JPEG validation.
- Audio preview, RDS decoding and spectrum scanning claim the same single RTL-SDR. They must run sequentially, not concurrently, unless a future shared-radio demultiplexer is tested. Never automatically stop Flight Radar/readsb, rtl_433, Gqrx, welle.io, recordings or the user's Radio Center. Existing process checks and flock are a conservative fail-closed fallback; a real authoritative shared lease broker is required in Survival Kit.

## C. DAB+ DLS, service metadata, MOT slideshow and available player

`welle-cli` can expose an already-running DAB receiver's service list and decoded metadata over its built-in local web server. This Text Center bridge ONLY performs bounded HTTP GETs to 127.0.0.1:7979 on `/channel`, `/mux.json` and `/slide/<validated service id>` when the user clicks **Read Running DAB Receiver**.

It never launches welle-cli, makes POST requests to `/channel`, acquires or retunes a USB device, or interrupts an existing SDR service. Network access is limited to the local loopback endpoint; no configurable arbitrary URLs or SSRF-style proxy is provided. DAB labels and DLS are saved to SQLite only when a verified receiver channel-to-frequency mapping and original decoder timestamp are available. The initial channel map explicitly supports 5C (178.352 MHz) and 11D (222.064 MHz); other channels are shown without inventing frequency attribution. The DAB service may expose MP3 playback through its own welle-cli web interface, but this is not yet embedded in Text Center as a continuous authenticated mobile/desktop player.

Once `welle-cli` has been separately installed (not bundled by Text Center) and the USB device is **free**, a user-authorized example is:

```bash
command -v welle-cli
# Only if the device is free; using this command WILL open/retune your SDR:
welle-cli -c 11D -C 1 -w 7979
```

The local receiver's page is then http://127.0.0.1:7979/ on that same machine. A first-party Kit portal on phones must use a properly authenticated TLS proxy, NOT a hard-coded 127.0.0.1 URL. The welle-cli service requires a broadcaster actually using DLS/MOT and a sufficiently strong signal. The owner must check hardware availability and explicitly launch it; never use this example while Flight Radar is acquiring the same dongle.

**Journaline is not provided by this DAB bridge.** Interactive Journaline menus, TPEG and some other data applications need their own decoder/service/licensing assessment. The MOT slideshow is a broadcast image, not a download of Internet album art. A real station may broadcast no picture at all.

Upstream receiver: https://github.com/AlbrechtL/welle.io

## D. Decoder-imported offline images

Stored images are limited to actual PNG/JPEG source bytes (max 320 KiB each), 120 most recently captured distinct images, and original medium/station/frequency/capture time/provenance. Remote HTML/SVG and network URLs cannot be imported into the media cache.

External, already-decoded MOT images can also be imported without running a tuner:

```bash
python3 -m textcenter import-media --file /path/to/real-decoder-media.json
```

Input must be a versioned JSON object with an `images` list; each entry includes a real `medium` (`dab_mot` or `fm_rds2_logo`), `station`, `source_id`, `frequency_hz`, timezone-aware `received_at`, `provenance`, and `image_base64` containing actual decoder-produced bytes. Placeholder images are NOT radio reception evidence. Developer tests use synthetic media only and do not assert hardware results.

## E. Hauppauge WinTV-soloHD model 01589 — tomorrow's hardware

Manufacturer documentation confirms model 01589 supports DVB-T, DVB-T2 and DVB-C, through a separate USB television tuner; the standard package lists a portable terrestrial TV antenna. This device is not an FM/DAB RTL-SDR replacement. Some European models/driver revisions require SI2168 firmware. Do not claim DVB lock or Teletext reception until the actual USB device is connected and its hardware path verified.

Recommended first diagnostics after plugging it in (without disrupting existing devices):

```bash
cd ~/TIHULU-TEXT-CENTER
git pull --ff-only
python3 -m textcenter dvb-diagnose
lsusb
ls -l /dev/dvb/adapter* 2>/dev/null
command -v dvbv5-scan || true
apt-cache policy dvb-tools
find /lib/firmware /usr/lib/firmware -name 'dvb-demod-si2168-*.fw' 2>/dev/null
sudo dmesg | grep -Ei 'dvb|si2168|firmware|hauppauge' | tail -n 40
```

If `dvbv5-scan` is missing, inspect the system's `dvb-tools` package candidate; install through the distro package manager only if needed and explicitly approved. If firmware is missing, inspect the exact **kernel driver request** in `dmesg` first. Do not blindly add Hauppauge kernel PPAs to a custom Pop!_OS kernel (e.g. 7.2.x); upstream packaging support may target older Ubuntu kernel versions, and changing kernels/driver trees risks other working SDR/TV modules. Follow current official Hauppauge support for the identified hardware revision.

The app's passive DVB diagnostics display vendor/product strings (Hauppauge USB vendor 2040 where available), kernel frontend paths, SI2168 firmware filename candidates and relevant tools. A generic DVB adapter0 path is **not** proof that the attached tuner is model 01589. No DVB service scan or Teletext PID demultiplexer is yet built: the user should not expect TV channels or P100/P200 pages before a true transport stream is obtained. All tuner access must eventually use the Survival Kit TV/Radio shared hardware lease broker and regional channel presets.

Manufacturer product: https://www.hauppauge.co.uk/site/products/data_solohd.html
Linux support and firmware: https://www.hauppauge.com/pages/support/support_linux.html

## F. Verification and user acceptance

- GitHub Actions uses fake PCM, fixture JSON, artificial spectrum data and test PNG bytes; it validates software behavior only.
- Verify station listening, RDS/RT+, RDS2 images, DAB DLS/MOT, DVB service detection, Teletext subpages and resource arbitration separately using real user-supplied hardware captures.
- Every piece of content must show whether it came from LIVE RF via a named decoder, an imported capture, Internet, or offline cache. A saved image is not a verified official emergency notification.
- Full continuous FM audio, genuine DVB Teletext decoding, native DAB channel scanning, Journaline text hierarchy and optional Internet artwork remain distinct future stages; never mark them done simply because an image or spectrum scanner exists.


## User-initiated automatic FM & DAB station discovery (new)

**Radio Data (400)** now separates two **real decoder-backed auto-discovery**
workflows from the existing manual **RF spectrum survey**.

### FM Auto Scan
- One user-authorized rtl_power sweep covers the **entire 87.5–108 MHz**
  band. The scanner uses a more sensitive, explicitly unverified peak list
  than the visible spectrum analyzer (4 dB / 1.8×MAD heuristic, bounded
  local maxima); it selects neighboring 100-kHz FM tuning grid points.
- Each selected frequency is then tuned **sequentially** using the existing
  rtl_fm + redsea receive-only RDS decoder for a bounded **10-second**
  verification. Only real, non-fallback PS/station labels are added to the
  confirmed results. Captured RadioText remains stored with source
  provenance through the existing SQLite event archive.
- **Quick** checks up to 16 tuning points; **Extended** up to 48. Full band
  means the initial energy survey covers 87.5–108 MHz, **not** that every
  possible FM carrier is individually demodulated. Non-RDS stations,
  crowded channels and weak/multipath RF may be missed. Neither option
  can guarantee all local broadcasters. User may stop anytime.
- The existing separate manual **Spectrum Analyzer** still exposes
  unidentified peaks, and an independent manual RDS capture still works.

### DAB+ Auto Scan
- Requires the user to **start welle-cli separately** on a free RTL-SDR,
  e.g. \`welle-cli -c 11D -PC 1 -w 7979\`.
- From Text Center, explicit consent allows the new dedicated DAB auto
  scanner to issue bounded POSTs to **only**
  \`http://127.0.0.1:7979/channel\`, using allow-listed Band III channels.
  Mode **Full** scans all standard **5A–13F** blocks (38 channels);
  **Detected blocks** scans only nominal raster matches from the most
  recently completed DAB energy survey. One channel is tuned at a time.
  Default dwell: 8 seconds per block; available settings 5–18 seconds.
- Actual decoded FIC ensemble and service metadata returned by
  \`/mux.json\` populate the station list. Service names, advertised
  audio/data roles and available DLS text/timestamps come from the
  decoder — never from an Internet channel catalogue. Only real DLS
  timestamps enter the persistent archive. No decoded services means the
  block is not claimed as received.
- **This retunes an existing welle-cli instance and interrupts its current
  audio stream**. Require explicit ownership and consent. Text Center
  **never kills or launches** that process. On successful scan/cancel it
  attempts to restore the starting block **only if no other client changed
  the tuned channel**; otherwise it stops and leaves the external
  receiver alone. Scan aborts if the browser stops polling.
- After scanning, click **TUNE THIS BLOCK FOR LISTENING** on a genuinely
  decoded block. This expressly retunes welle-cli, then
  **OPEN WELLE-CLI PLAYER** opens its existing service list and Play
  buttons; do not pretend a second built-in MP3 player was created. The
  current DAB read-only bridge remains available to fetch genuine DLS
  and optional MOT slides from the currently tuned block. MOT artwork
  is **not guaranteed**, and the rapid scanning loop itself does not
  wait 80 seconds on every service or falsely save images.
- Internet access, third-party SDR preemption, packet-radio TX, automatic
  power-up scanning and global OS-level exclusive device leasing are
  **not** implemented by this change. Only explicit opt-in workflows run;
  scan status is held in RAM during the server session. Hardware
  acceptance on the user's physical device is still required.

### Quick local validation (after PR review)
1. Stop existing Text Center server; update the selected worktree; restart
   \`python3 -m textcenter serve\` and hard-refresh the page.
2. **FM:** stop welle-cli and all other SDR owners; select Quick FM Auto Scan,
   acknowledge the device-ownership checkbox, and let the browser remain
   on Radio Data (400). Review actual RDS-confirmed stations.
3. **DAB:** after FM scan has stopped, start welle-cli in a separate terminal
   and verify its local web interface. With explicit consent, select
   DAB Full or Detected scan and monitor progress; inspect the FIC station
   list; verify original channel restoration and the stop button.
4. Open the welle web player for listening. For DLS/MOT while tuned,
   use the separate **READ RUNNING DAB RECEIVER** panel.
5. **Never** simultaneously operate manual spectrum scan, FM audio, FM
   RDS capture, Flight Radar/readsb or other radio recording on the same
   RTL-SDR. CI uses synthetic decoder fixtures only.
