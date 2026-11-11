# TIHULU Media Center — Recording & Export v2 (Draft)

**Status:** feature development on top of the isolated, unchanged multi-app
preservation baseline. No main merge, installer switch or RF device test.

## Intended matrix

| Source | Live playback/capture | Complete before playback |
| --- | --- | --- |
| Local audio file | Existing media player with optional concurrent whole-file AI | Existing opt-in full prepass + subtitles before start |
| Local video file | Existing media player with optional concurrent whole-file AI | Existing opt-in full prepass + subtitles before start |
| Live DAB/Internet radio | Existing source recording + optional Whisper speech SRT | Not available; cannot precompute an unknown future broadcast |
| Live DVB/Internet TV | Existing native TV/source recording + live AI SRT | Not available; cannot precompute an unknown future broadcast |

**Crucial limitation:** local-file concurrent transcription currently creates
the full sidecar asynchronously; it does **not yet stream each recognized chunk
to the player subtitle overlay during playback**. Do not claim this is a
finished continuous live-file caption implementation. It is a separate,
non-regressing follow-up.

## New shared export path

`tihulu-tv-center recording-export --srt FILE --destination DIRECTORY
--name SESSION --formats txt,srt,vtt,ass,json --split-translations`

Options:
- `--track original=/path/original.srt --track translation-tr=/path/tr.srt`:
  preserve independently recorded TV tracks.
- `--split-translations`: on a combined local-file/live-radio SRT,
  split explicit language-prefixed [TR]/[DE]/[EN] lines into separate tracks.
  Sound/speaker labels stay in original text.
- `--media /path/completed-recording.mkv --mux`: create separate
  selectable subtitle streams in a new MKV while copying source audio/video.
  Also works with completed audio-only files using Matroska.
- `--media /path/video.mp4 --burn-video`: re-encode video as a new MP4 with
  captions burned in; never offered for audio-only.
- `--timestamps`: text-file time spans; SRT/VTT/ASS/JSON always retain
  real cue boundaries.
- `--verified-lyrics --formats lrc`: LRC is only permitted for explicitly
  identified time-coded lyric sources; raw speech is not lyrics.
- `--mode live|complete`: complete mode requires a finished local media file.
  Live TV/Radio must use live mode and finalize after Stop.

The Python engine itself never acquires SDR/DVB, calls cloud models, restarts
Whisper or alters playback buffers. It creates files exclusively and refuses
preexisting destinations. FFmpeg uses argv without shell expansion, `-n`
no-overwrite and non-destructive remuxing.

## User interfaces on this draft branch

- Local Audio/Video: existing Complete-first gate remains; new
  **Save timed transcript / subtitle formats** dialog after a real SRT exists.
- Live TV captions: independent, existing Start/Stop SRT; optional
  TXT/VTT/ASS/JSON conversions when user stops the SRT session.
- Live radio: independent **Save live AI subtitles** starts/stops SRT of
  actual shown Whisper speech, separate from audio recording, lyrics and DLS.
  Its timestamps are **estimated displayed-cue timing**, not DAC or true
  word-level audio presentation timestamps. It must not be automatically
  asserted to be synchronized with a separately started MP3 recording.
- Native unified Recordings library: import completed TV/radio recordings;
  use their existing SRT sidecar or select one manually to export TXT,
  SRT, VTT, ASS, JSON, selectable MKV and optional burned-video MP4.

## Mandatory follow-up acceptance

1. Native Qt5 Kaffeine patch must **compile**, and source-only regression
   tests must pass without weakening old tests.
2. Real Pop!_OS DVB-T2 / DAB / file audio / file video playback and recording
   must be tested with the user's actual devices. Verify receiver handoffs,
   durable recording files, spoken subtitles, latency and no background SDR.
3. Verify internet radio / internet TV URLs and offline file outputs, output
   translations and final original / translated track language metadata.
4. Check subtitle timebase against an actual recorded media clock; never fake
   verified lip-sync from display/ASR wall-clock estimates.
5. Implement progressive file Live caption UI with revision-safe streaming
   while preserving existing Complete-first behavior; no new default AI
   process on file open without user consent.
6. Add explicit per-track selection for burned subtitles when multiple target
   languages are present, and test FFmpeg filter quoting on Windows/macOS
   paths.
7. Satellite, RF Geolocation and canonical Flight Radar apps must remain
   unchanged and independently runnable.

This branch remains Draft until all applicable checks pass.
