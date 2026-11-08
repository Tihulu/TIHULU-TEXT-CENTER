# TIHULU Media Center — paired phone & tablet

Two opt-in browser entry points exist today because they own **different**
trust boundaries and live-media sources. Do not treat them as interchangeable
or claim that the entire native desktop has been mirrored.

## 1 · Live native DVB-TV and Whisper captions (six-digit PIN)

Desktop: **TIHULU AI → Live Teletext / Whisper subtitles →
Diagnostics & network → Allow phone/tablet on trusted Wi-Fi**.
The host UI shows a 6-digit PIN and the local URL (port 8769 by default).
The local receiver/tuner stays on the PC; no second SDR connection is opened.

After pairing, the phone can:
- Select the current host DVB channel or captions-only mode.
- Request host H.264/AAC HLS encoding, start/stop **phone-side** playback.
- Select the intended phone / host / both view preference. Choosing phone
  does not magically stop/mute the host's tuner; use host volume/mute as needed.
- Send host playback, pause, next/previous, volume and TV channel commands
  through the **existing** native D-Bus interface (when supported).
- Start/stop desktop captions; change source mode, subtitle offset, or
  requested native TV buffer. These are queued to the Qt GUI thread and
  confirmed by later native status, not applied inside an HTTP worker.
- View original + translated subtitle cues and their timestamps, not just
  the most recent phrase. Hold the phone full-screen video container with
  captions or, in supported iPhone Safari video fullscreen, use the
  dynamically updated native WebVTT text track.

**Latency**: HLS consumes TS *before* the desktop's separately requested
libVLC 0–20 s playback buffer. Desktop effective delay and caption offset
are exposed to the phone and the user can choose:
- **Phone HLS estimate** (recommended while watching phone video):
  desktop effective buffer is subtracted from the original caption deadline,
  then an estimated remote HLS lag + optional fine adjustment is used.
- **Desktop timing** (captions-only or monitoring the computer's TV screen):
  use host's actual confirmed caption due time.
- **Manual**: source capture timing plus the phone-only correction.

These estimates **are not millisecond-accurate PTS alignment**. A proper
A/V presentation-clock correlation requires additional media pipeline work.
The host requested delay is never labeled *verified* unless its native
queue-primed acknowledgement is present.

**Native DVB scanning and channel management** are now available from
the **TIHULU TV Center native Qt application** when its own six-digit
PIN service is enabled. That Qt process drains the authenticated command
queue and invokes the real AutoScanner with the current selected adapter.
Remote scan prompts for confirmation, is cancelled from the same monitor
as local scans, and publishes only actual scan progress and saved services.
A terrestrial or cable profile hides satellite/DiSEqC controls; satellite
mode exposes the chosen orbital position and LNB input.

The **Kaffeine subtitle sidecar** also has a six-digit PIN but is not the
scanner owner. It cannot legitimately start Kaffeine's full scan through the
same interface: the phone now shows a truthful native DVB bridge unavailable
message instead of a non-functional scan form. Do not start another tuner
or claim that Kaffeine's channel import can be controlled without a real
native command bridge.

The full model market and installation of new large models remain
desktop-approved. Native MPV does not implement Kaffeine's 0–20 second
TS delay: phone controls for that exact desktop buffer and subtitle
offset are disabled when paired with MPV rather than silently ignored.

## 2 · Shared files, verified DAB+ and slideshow (eight-digit PIN)

Desktop: **TIHULU AI → Start paired remote media hub...**. Approve a
specific local media folder. The service listens on **127.0.0.1:8788**
and shows a separate 8-digit PIN. Use **private Tailscale Serve HTTPS**
from an authenticated personal device; **never Funnel or port-forward
this service to the public Internet**.

After pairing:
- Choose approved **media files**, **approved pictures**, or actually
  verified welle.io DAB services.
- Choose **Phone**, **Host only**, or **Phone + Host** for a selected stream.
  Host-only leaves an existing shared HLS stream intact. The single
  shared HLS encoder changes source for all watching devices when a new
  phone stream is selected. Multi-stream multi-tuner playback is NOT
  implemented.
- Use native MPRIS player controls (when available). Selecting a native
  TV channel controls the host only and does not imply DVB rebroadcast.
- View real DAB slideshow images, verified lyrics, transcription, and
  translation from the authorized receiver-side worker.
- Fullscreen translated captions in browsers supporting element fullscreen
  and via dynamic WebVTT in supported iOS native video fullscreen.
- Switch between host requested DAB audio delay, phone HLS lag estimate,
  and manual correction. DAB audio-output PTS is **not verified**.

### Privacy and security

Both services default to OFF. PIN/cookie authentication is required for
media and controls, with bounded attempts and explicit logout/revocation.
The DVB phone service is for explicitly trusted Wi-Fi. The Remote Hub
binds to loopback and needs private authenticated HTTPS proxying to reach
the phone. Browser pages never run shell commands, open arbitrary local
files, or get the host's microphone/USB device. Controls are allowlisted.
Dynamic subtitles are selectable text tracks, **not video pixels
permanently burned in by FFmpeg**.

DRM/DVD capture, arbitrary desktop screen mirroring and generic native
application UI mirroring are not supported. We do not invent video,
pictures, audio, subtitles, real-time device state or synchronization.
