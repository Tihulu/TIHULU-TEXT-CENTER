# TIHULU TEXT CENTER — Integration handoff (2026-11-06)

This handoff is for the primary Text Center/Survival Kit agent working in
parallel on live translation, ASR/NPU/GPU, persistent radio and TV.

## Authoritative source and write isolation

- Feature branch: \`fix/live-fm-audio-dab-mot-one-line-install-2026-11-06\`.
- Base main SHA when authored: \`7cf810ed5730d7e774ec94b4f3dba00bb16c6baf\`.
- **Never force push, reset, or overwrite main or other agents' branches.**
  Do not change \`textcenter/compute.py\`, \`textcenter/speech.py\`,
  \`textcenter/transcripts.py\`, \`textcenter/postprocess.py\`, or
  \`textcenter/live_tv.py\` in this branch. The AI/translation agent owns them.
- Real hardware acceptance is still pending. CI synthetic fixtures and
  source lint do **not** establish live audio/MOT operation on Nooelec.

## User-visible regression and tested code change

The user enabled speech transcription and translation while running FM
98.6 MHz on Pop!_OS. Their local compute panel explicitly reported
the CPU Whisper model missing and GPU speech runtime unavailable. Before
this patch, \`LiveFM.start\` attempted to create \`SpeechPipeline\` after
starting receiver and encoder. A \`SpeechError\` from absent models
reached startup exception handling and closed **both** receiver and audio.
Live FM no longer depends on optional speech/translation readiness:
requested but unavailable ASR reports \`subtitle_unavailable_reason\`,
\`subtitles_active=false\`, and continues true audio + optional recording.
Do not fabricate captions, suppress errors, or auto-download speech models.

In \`web/app.js\`, the status shows listener connection and unavailable
subtitle reason, with **SHOW AUDIO PLAYER** action and browser playback
error diagnostics. Ensure media dock/stream MIME and CSRF protections stay.

## DAB+ slideshow

- \`DABReader.refresh\` reads **only** an already-running, localhost-only
  \`welle-cli\` decoder. No SDR process spawn or retune; DAB centre roster
  allows attributed images on actual Band III blocks, including 8B and 11D.
- Per-service \`mot_image_status\` distinguishes saved, not broadcast,
  decoder/read error, skipped and missing frequency; the reader also
  exposes counts. Originals stay PNG/JPEG, bounded 320 KiB per image,
  with actual decoder timestamp, source, frequency and station.
- \`web/app.js\` adds a separate **DAB MOT Slideshow** on Radio Data 400
  and Live Radio 410. **SYNC CURRENT DAB MOT** is an explicit POST to
  the existing reader; the slideshow only rotates saved local images
  after the user's click and does not automatically fetch the Internet.
  Media gallery refreshes in-place and per-station decoded MOT is shown
  when available.
- With a **single** NESDR device, FM playback and different-frequency
  DAB reception are mutually exclusive. Previous offline images can be
  viewed while listening to FM; new images require stopping FM and
  tuning a real DAB signal in independently launched welle-cli.
- Do not substitute Google/Internet album cover art for received MOT.

## Installation and update

\`install.sh\` is Bash/Python 3.11+ only. Creates local wrappers
\`~/.local/bin/tihulu-text-center\` and
\`~/.local/bin/tihulu-text-center-update\`.
No sudo, no RF/background activity, no forced merges, no systemd service,
no implicit decoder/model installation. A \`--update\` refuses a dirty
tree and uses only \`git fetch\` and \`git merge --ff-only\` on the
**currently checked-out branch**. The SQLite DB and recordings are not
touched. This is a one-command **application** installation; the
optional system dependencies (rtl-sdr, ffmpeg, redsea, welle.io, Whisper
models, Argos Translate pairs) still need explicit per-platform setup.

## Verification gates before integration

1. Run \`python3 -m unittest discover -s tests -v\`,
   \`python3 -m compileall -q textcenter tests\`,
   \`node --check web/app.js\` and \`bash -n install.sh\`.
2. Rebase/cherry-pick **only additive deltas** onto the latest main, not
   entire old \`web/app.js\`/\`http_app.py\` if another agent has edited
   them. Preserve all text/language/compute settings and DVB/TV features.
3. Physical Pop!_OS test: with no conflicting SDR owner, tune FM 98.6
   in Firefox, first with subtitles OFF, then ON but model missing.
   Confirm status stays running, browser audio reaches a connected
   listener, real audio is audible and optional MP3 recording persists.
   Verify error messaging if playback fails. Do not claim this pass
   solely from unit tests.
4. Stop FM; launch \`welle-cli -c 11D -PC 1 -w 7979\` explicitly.
   Confirm actual WDR ensemble, then request MOT sync, ensure no
   fabricated artwork. If no genuine MOT transmitted, show an honest
   \`not_broadcast\` state. If available, check JPEG/PNG is shown and
   archived across restart. Test a second DAB block only if the receiver
   actually locks.
5. Test single-device lock: attempting FM while welle-cli owns the
   RTL-SDR must fail closed. Never kill the independent receiver.
6. Verify the installer/updater on a clean isolated worktree and
   preserve the user's existing \`~/TIHULU-TEXT-CENTER\` checkout.
7. Keep PR draft until integration, CI and real RF checks pass.
