# TIHULU TEXT CENTER — TV Teletext-first subtitles and unified reader

Date: 2026-11-06
Integration branch: feature/tv-teletext-subtitles-priority-fallback-2026-11-06
Base: PR #23, which is layered on PR #22 (Text & Alerts) and PR #15.

## User-facing workflow

The user may select **Live Captions**, **Translate available subtitles**, and
subtitle source **Auto / Teletext only / Speech only** before starting a TV
stream. Auto prioritizes genuine FFmpeg/libzvbi decoded DVB Teletext subtitle
cues, translating the decoded text with a *separately installed* offline Argos
language model where supported. If no timely Teletext subtitles arrive for
15 seconds, optional Whisper ASR processes the authorized TV audio as fallback.

A broadcast may contain other subtitle formats: this implementation is only
for *text-decodable Teletext subtitles*. Bitmap-based DVB subtitles do not
suddenly become text without a real OCR decoder, so they are **not** sent to
Argos or presented as translated text.

The persistent TV/radio player includes independent checkboxes for
**Captions**, **Original text**, **Translation**, a translation target, and TV
source preference. FM captions can start and stop on the *existing* PCM tee
without retuning. DAB optional speech can be stopped/restarted without killing
the externally owned welle-cli or re-opening an SDR. TV live subtitle preference,
display and translation can be changed without closing the video.

IMPORTANT: If a TV stream started without a PCM speech tap, turning on ASR
later is not yet possible without restarting the stream with subtitles enabled;
this limitation is reported truthfully, never simulated. Already decoded
Teletext is still accepted if the safe sidecar can be started.

## Safe Teletext decoder: multi-client relay is explicit

The TV tuner/firmware and the TV application's *own existing Teletext
functionality* are untouched. The new optional sidecar reads only an already
authorized **loopback MPEG transport stream**. Because a second client might
cause a TV relay to retune its tuner, it is disabled unless the owner adds this
to the trusted local \`TIHULU_TV_CHANNELS_FILE\` channel record:

\`\`\`json
{
  "id": "channel-id",
  "name": "My TV channel",
  "url": "http://127.0.0.1:9981/stream/channelid",
  "teletext_shared_safe": true,
  "teletext_subtitle_index": 0,
  "teletext_subtitle_page": "subtitle",
  "teletext_language": "de"
}
\`\`\`

**Do not set \`teletext_shared_safe=true\` until the local TV relay is
confirmed to support multiple simultaneous clients without retuning or
interrupting recordings.** It is false by default. The stream URL is validated
by existing TV config, not accepted from browser user input. The optional
ffmpeg/libzvbi sidecar is separately owned; it cannot kill the TV playback
or an external tuner service. Actual Teletext cues are bounded, timestamped,
source-attributed and archived with
\`compute_backend=broadcast_teletext\`. Broken ~1193-hour SRT end timestamps
and other unrealistic cues are discarded. Without decoded text, there is no
fabricated caption.

FFmpeg source documentation:
https://github.com/FFmpeg/FFmpeg/blob/master/doc/decoders.texi

## Full TV Teletext pages and cross-app reader

A separate collapsed **Teletext pages** panel inside TV Center now browses
already received and imported DVB Teletext numbered pages, searchable by
channel/station/source and page number. It reads the existing
\`/api/pages\` and \`/api/page\` archive, with page identity verification
and provenance. The same received pages remain accessible in **Text & Alerts**.
The TV application's native Teletext view is not modified, replaced or removed.
Pages only show up once an actual decoder imported them: the subtitle sidecar
itself decodes subtitles, not the entire 100–899 interactive Teletext service.

## Tests and physical blockers

- Unit tests for SRT subtitle validation, shared-relay opt-in, no unsafe URL,
  Teletext-first source priority, fallback on missing/stale Teletext, retention
  and no invented captions.
- Preserve FM, DAB, TV and Text & Alerts tests and all platform smoke checks.
- Actual Hauppauge tuner/DVB-T2 driver and live MPEG-TS relay must be checked
  independently. A successful simulated test does not verify Teletext reception.
- Need an actual broadcaster's Teletext subtitle stream and an FFmpeg build
  with libzvbi to verify end-to-end subtitles, timed alignment, language and
  translation. Missing models must not stop video or audio.
- FFmpeg sidecar two-client safety on the exact installed relay is a physical
  acceptance blocker.
- GitHub Pages cannot run these local subprocesses by a permission popup;
  the local companion remains required.

Never merge this draft into main before review. All work in other repositories
and previous concurrent AI/driver branches must remain unchanged.
