# Portable no-regression gate

**Goal:** allow any UI/architecture/framework change with the same observable features and safe defaults. This is a *test plan*, not a claim that every feature can currently be exercised.

Required signoff stages:

| Gate | What to prove |
| --- | --- |
| G0 | Original source tree hashes and independent branch/pr histories remain available |
| G1 | All feature IDs in `FEATURE_MATRIX.json` have old implementation, port implementation, and documented unimplemented exceptions |
| G2 | CLI/API/data format compatibility and stable persisted preferences checked by fixtures |
| G3 | Original and translated caption timebase, Teletext/DLS provenance, subtitles and recordings parity |
| G4 | Hardware leases: no second SDR tuner, proper Start/Stop/Release and transition between TV/Radio/Satellite/Radar |
| G5 | LLM/runtime: no invented model installation/readiness, missing translator falls back, speaker/music labels never erase dialogue |
| G6 | UI redesign: accessibility, responsive viewport, keyboard/touch, fullscreen, all controls discoverable |
| G7 | Release packaging, install/upgrade/rollback, all supported OS/architectures; original data preserved |
| G8 | On-device acceptance results logged separately from GitHub CI; user approves changing canonical/release status |

CI source-level success **cannot substitute** for G4 or G8. Port failures must not make monorepo implementation change. Keep handoff and previous repo editable authority unchanged until explicit cutover.
