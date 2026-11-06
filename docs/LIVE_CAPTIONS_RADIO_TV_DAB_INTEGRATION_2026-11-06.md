# TIHULU TEXT CENTER — Live Radio & TV Captions and Translation (2026-11-06)

## UI goal
The shared Radio Center (FM/DAB+) and TV Center channel library now exposes
**Live transcription** and **Translate speech live**, with original spoken
language, translation destination, and optional CPU/GPU/NPU compute selection.
English is the initial selection for both languages; *Detect language* is
available when an installed Whisper CPU/GPU model is known to support it.
Options apply when **Play/Watch** starts a new session. They do not silently
retune the receiver or reinstall models.

A persistent playback dock presents actual transcribed original-language
captions and, if an installed offline Argos language pair succeeds,
translated captions. The dock provides separate original/translated SRT and
VTT export links. Captions come from real audio samples only and are saved
to the existing `TranscriptStore` with session identifiers.

## Audio source contracts

- **FM:** Existing `LiveFM` taps real `rtl_fm` PCM before browser MP3
  encoding and recording. The Channel Center now passes the selected caption
  and translation options to its existing start endpoint. FM reception continues
  without compatible ASR/translation models.
- **TV:** Existing authorized loopback MPEG-TS `LiveTV` uses a separate
  PCM tap from ffmpeg. The Channel Center now passes captions/translation
  options. An unavailable optional Whisper model now degrades to
  **video-only** without killing the requested TV stream.
  This does *not* discover a TV driver, convert a scan result into an MPEG-TS
  relay, or touch the existing television Teletext feature.
- **DAB+:** A new explicit, optional **DAB speech tap** reads only the
  currently verified welle-cli MP3 audio service on fixed loopback address,
  using the existing no-redirect service validation. A private, app-owned
  ffmpeg decode process produces 32-kHz 16-bit mono PCM for the shared
  `SpeechPipeline` and `TranscriptStore`. It does **not** run a second
  tuner, start/kill external welle-cli, read a user-supplied URL, claim USB
  or generate captions from DLS/RDS metadata. It closes its own stream,
  decoder, and speech worker on Stop, browser heartbeat expiry, receiver
  disconnect, tuner retune, and owned-only HARD STOP. Playback remains
  available when the optional speech tap or models are absent.

## Status and limitations

- Browser captions update from actual transcript archive at approximately
  1.8-second UI intervals. Speech uses 8-second windows, so captions are
  **near-live**, not guaranteed word-by-word low-latency synchronization.
- Real-world latency depends on the model, CPU/GPU/NPU runtime, decoder,
  weak RF reception and translation availability. No synthetic subtitles,
  model auto-download, or unverified language detection.
- A target language equal to the actual speech language is not translated;
  the original remains available. Unsupported/missing model pairs leave
  translated text absent without replacing genuine original captions.
- DAB may expose its MP3 service to multiple loopback clients; acceptance
  must verify welle-cli supports simultaneous browser listening and one
  read-only transcription tap for the tested version.
- This is **backend-enabled local Text Center**, not a guarantee that
  GitHub Pages alone can run ffmpeg, DAB decoders or Whisper models.
  WebUSB experimental receive-only features and their boundaries remain.
- The separate Hauppauge DVB driver/firmware work stays untouched.

## Tests and acceptance

Synthetic checks: optional DAB transcriber missing-model fallback, fixed
service/consent routing, private ffmpeg child cleanup, no modification of
external RF service, correct UI options and exports. Existing radio/TV/AI,
Windows/Linux ARM/macOS smoke must remain intact.

Physical acceptance pending: FM audio with 8s original/translated captions
when a compatible model is installed; DAB WDR 5/1LIVE MP3 tap with an
actually decoded audio service and no interrupt to welle-cli; configured
TV MPEG-TS stream that really has an audio track, video uninterrupted
with missing ASR model; correct source attribution; Stop/browser-close
cleanup and retained SRT/VTT exports.

This feature is layered atop PR #22 → #15 → #14 → #13 and must not
discard concurrent independent work or modify `main` without review.
