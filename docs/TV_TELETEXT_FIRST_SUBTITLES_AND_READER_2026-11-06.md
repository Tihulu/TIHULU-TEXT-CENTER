# TIHULU TEXT CENTER — Teletext-first TV subtitles and channel Teletext reader

Continuation from PR #23 and PR #22. Draft feature. Main, tuner drivers, firmware, the separate TV application's existing Teletext feature, and unrelated repositories are unchanged.

## Priority and controls

1. Auto: actual timed DVB Teletext text subtitles take priority; if no cues after an 8-second grace period or the last cue is 10+ seconds old, use real TV audio Whisper recognition if a compatible local model exists.
2. Broadcast only: genuine libzvbi decoder cues; never infer subtitles from archived Teletext pages.
3. Speech only: existing TV PCM and Whisper pipeline.
4. Off: no requested subtitle processing.
5. The video dock permits Off, Original, Translated and Both visibility, and offers controls to pause/resume processing and translation without TV retuning. If no PCM stream was armed when playback began, enabling ASR later requires a new authorized TV session, not a hidden tuner restart.

## Real source and fail-closed behavior

- Teletext original captions use source IDs of configured_tv:<channel>:teletext:<stream> and compute_backend broadcast_teletext_libzvbi in the same TranscriptStore as original/translated SRT and VTT.
- The optional TVTeletextTap uses installed FFmpeg with libzvbi and ffprobe to select only actual dvb_teletext subtitle streams. DVB bitmap subtitle streams do not provide real text for translation without OCR.
- Decoder reads ONLY an explicitly authorized fixed localhost MPEG-TS relay; a secondary read-only connection is OFF until the user explicitly confirms that the relay is multi-client-safe. The TV video process and tuner remain independent. No driver, firmware, recording, unrelated process or external readsb/welle-cli is terminated.
- Only subtitle-marked pages are selected, rather than assuming page 888. Invalid timestamps (including 1193-hour anomalies), graphics, empty cues and unknown source languages cannot produce a fabricated translated subtitle.
- Source selection and current live status tell users if the active subtitle is actual DVB Teletext or Whisper audio transcription; no silent Internet caption substitution.
- The auxiliary subtitle reader estimates cue time from the real decoded arrival; perfect lip sync will need the eventual unified transport-stream PTS adapter after the user's separate tuner work.

## Teletext pages and websites

- TV Center offers a reader of actually imported DVB Teletext archive pages, searchable by station, page and title. Each opens the original numbered page reader; existing TV Teletext is untouched.
- Text & Alerts P500 continues to hold the same real page archive and other broadcast text protocols.
- Broadcaster Teletext websites from the existing source directory are clearly labeled Internet-only, never antenna data.
- A TV scan or configured video relay alone does not imply any page or subtitle was actually decoded.

## Acceptance and known blockers

- Python / JS CI and synthetic SRT/probe/priority tests are not real Hauppauge DVB-T2 acceptance.
- Validate actual libzvbi availability, real subtitle packet/PID, correct program, multi-client permissions, language tags, translation pair, and fallback during silent/waiting broadcast scenes.
- Actual DVB bitmap subtitles need separately verified OCR. Optional Whisper uses approximately eight-second audio chunks, so captions may lag.
- GitHub Pages cannot run local FFmpeg or DVB driver services without a trusted backend. No main merge until source validity and physical tuner acceptance.

References: https://www.ffmpeg.org/ffmpeg-codecs.html and https://ffmpeg.org/ffprobe.html