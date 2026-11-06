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

It never launches welle-cli, makes POST requests to `/channel`, acquires or retunes a USB device, or interrupts an existing SDR service. Network access is limited to the local loopback endpoint; no configurable arbitrary URLs or SSRF-style proxy is provided. DAB labels and DLS are saved to SQLite only when a verified receiver channel-to-frequency mapping and original decoder timestamp are available. The channel map now includes all standard European Band III DAB channel centre frequencies (including 5C, 8B, 9D and 11D) as attribution **lookups**, not reception evidence. Only actual welle-cli service data with decoder timestamps is archived. The DAB service may expose MP3 playback through its own welle-cli web interface, but this is not yet embedded in Text Center as a continuous authenticated mobile/desktop player.

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


### Diagnosing missing / unsaved DAB MOT images

After independently starting a real welle-cli decoder on a free RTL-SDR and
selecting a broadcast that is actually receivable, choose **Radio Data (400)**
→ **READ RUNNING DAB RECEIVER** with **Save decoded MOT slideshow images** checked.
The result is per-service, not a blanket promise that all stations send images:

- \`saved\`: decoder supplied valid PNG/JPEG data, stored in SQLite, with immediate image preview and refreshed offline gallery.
- \`not_broadcast\`: no MOT timestamp has been reported for this decoded service; no image is manufactured.
- \`empty\`: decoder advertised MOT but returned fewer than 40 bytes.
- \`failed\`: slide fetch failed, or bytes failed the bounded PNG/JPEG validation (320 KiB ceiling). The UI displays aggregate and per-service failures rather than silently swallowing them.
- \`not_requested\`: user left the image-saving option unchecked.
- \`frequency_unknown\`: unknown DAB block; image cannot be archived without attributable receive frequency.

If welle-cli is not installed/running at 127.0.0.1:7979, no DAB service
or image can be received by this adapter. The existing \`rtl_power\` spectrum
peaks cannot be converted into broadcaster MOT artwork. No Internet artwork
is substituted. This adapter never starts, stops or retunes the radio.
