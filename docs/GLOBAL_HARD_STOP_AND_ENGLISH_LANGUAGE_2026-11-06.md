# TIHULU TEXT CENTER — English defaults, language detection, global HARD STOP

## Scope and status

- All new FM/TV, saved recording and offline translator source/target/later-translation
  selectors default to **English (en)**. Existing transcript language and archives
  are not changed; this is a UI default, not an automatic translation.
- Speech input offers **Detect language (Whisper CPU/GPU)** when at least one
  compatible, already-installed local CPU/GPU ASR runtime is ready.
  The explicit NPU path remains unsupported for automatic detection.
- Whisper.cpp CPU `-l auto` detection is parsed from actual decoder diagnostics.
  faster-whisper GPU uses the model's detected language and confidence;
  confidence below 0.60 or unknown/out-of-scope languages are marked `und`.
  No successful detection is fabricated. For auto-detected audio, each saved
  caption contains its verified EN/DE/TR language or `und`; automatic translation
  is skipped when the original language cannot be verified.
- Offline text translation shows **Detect language** only when the optional
  local `langdetect` package is actually installed. The setting is initially
  disabled otherwise. Detection is local, needs at least 20 characters,
  requires >=0.80 confidence, and supports English/German/Turkish.
  It does not silently install packages or download any models.

## HARD STOP — scope and safeguards

A permanently visible **HARD STOP** button is in the full Text Center topbar,
all page sections. On explicit confirmation it calls the same-origin CSRF-gated
`POST /api/receiver/hard-stop` with `confirm: true`. The local backend requests
stop/wait on the server's **own** FM, DAB, radio, TV, audio, RDS, survey,
FM/DAB discovery and saved-recording transcription workers. Responses mark each
worker `confirmed_stopped`, `unconfirmed` or `stop_failed`. The UI does
not announce release unless all statuses confirm inactive. Recordings/archive
contents are not deleted. Auto-stop-on-exit and background-off remain defaults.

The GitHub Pages global header HARD STOP releases only **that tab's WebUSB**
session. Satellite browser page adds an explicit HARD STOP for its own receiver.
Neither Pages nor the local Text Center can stop other apps' independent
readsb, welle-cli, tar1090 or another browser tab/origin. The future
cross-application device lease broker is still a separate project requirement:
this button is **not** a privileged OS-wide hardware kill switch.

## Validation

Run `python -m unittest discover -s tests -v` and `node --check web/app.js`,
`node --check docs/webusb-radio.js`, `node --check docs/satellite/browser.js`.
Mock tests demonstrate source attribution, opt-in permissions and stop response
contracts but cannot replace physical Nooelec, Hauppauge or DAB acceptance.
No changes to unrelated private Tihulu repositories or `main`.
