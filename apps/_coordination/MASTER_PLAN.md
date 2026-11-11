# TIHULU Master Engineering Plan — Zero Regression, English Internals, EN/TR/DE UI

**Approved work scope as of 2026-11-11:** user authorized careful planning and audits. No application program behavior change is authorized. This document augments, and does not replace, `apps/MASTER_TRACEABLE_MIGRATION_PLAN.md`, PR #65–#74 and existing feature/component/model matrices.

## Non-negotiable preservation contract

- NEVER remove, reduce or silently change any shipped or previously requested feature, default, option, UI control, caption/timing path, device lifecycle, recording, user setting, one-line installer, pages URL or rollback. If an improvement would alter behavior, isolate it as **proposed, opt-in and not shipped** pending separate approval.
- Protect original Text Center as a functioning app and historical source host; its `textcenter/` and `web/` must remain actively usable after Media/Satellite/Geolocation migrations.
- Protect Flight Radar's separately canonical repo, true tar1090, source I/R labels, readsb native desktop, internet-only mode, legacy 0.3.1, two synchronized Pages locations, existing PR #7/#13 and independent devices.
- Protect media Draft PR #65 for karaoke/TV/radio subtitle behavior, #67 for full-file and live caption export, plus other unmerged feature branches. Never silently cherry-pick one over another, overwrite, or mark finished solely because code exists.
- Preserve original PR/Issue reviews and comments as source-linked historic evidence; original GitHub repo numeric ID 1447637221 is stable even if its display name changes. Use a tested current alias; do not expect Pages redirect on rename.
- Use ONLY the original five user-approved red-black-white TIHULU mascot logos; existing SVG in Flight Radar is not one of the approved icons. PNG-to-SVG wrapper is not a genuine editable vector.
- ALL repo engineering prose, source, tests, GitHub Issues, PR descriptions, code comments, developer prompts and commit messages ENGLISH; every app user-facing UI supports `en` (default), `tr`, `de`; unknown coverage is NOT marked complete. Conversation with owner may be Turkish.

## App workstreams and scope

### W1 Media Center — 41 initial requirements
Native Kaffeine Next DVB/TV, FM/DAB welle.io DLS/RDS, proper device handoff and hard stop, TV/radio buffering parity, captions and Teletext/Whisper source matching, audio/sound labels not blocking speech, Qwen karaoke forced-aligner separate lipsync, instrumental hold, lyrics confidence/refresh/window, translation model readiness, GPU/CPU/NPU/optional remote pairing, local file pre-transcription, timed captions/recording export, playback display and full-screen behavior. Preserve main and reconcile #65 and #67 plus prior drafts without rewriting source in this phase.

### W2 Flight Radar — 17 initial requirements
Already independently canonical; its own Git PRs and legacy rollback remain. Need verified feature/component/model/development-agent matrices, Claude/DeepSeek handoff, old Text Center history fallback links and app-logo staging; compare PR #7/#13 and main. Two distinct webpages, RF versus I-source provenance, true tar1090, provider/license rules, RF circles/PSF, incremental History and native RTL-SDR resource ownership. No second editable mirror.

### W3 Satellite Center — 8 initial requirements
Offline-first pass planner, valid TLE/local time, Sky/Earth maps and antenna-facing 280° profiles, ISS SSTV, NOAA APT, Meteor LRPT IQ capture and CADU decode, scheduled multi-part recordings, native SDR driver ownership, truthful capture/decoder errors and hardware signal validation. Destination currently empty; no cutover.

### W4 RF Geolocation Center — 8 initial requirements
PSF/Gaussian and honest uncertainty, independent RF/non-RF evidence, correct 3+ aircraft constraints, source-specific LIVE/BEST/location/aircraft rings, source arrays and layered maps, native device lease, incremental history, offline map. Destination currently empty; coordinate shared API contracts with W2 without cross-editing.

### W5 Text Center — 8 initial requirements
Text Center stays in original repo as an active app + historic source archive; FM RDS/RadioText, DAB DLS/Journaline/MOT, DVB-T2/Teletext, optional AIS/ACARS/NOAA/RTL-433, shared device ownership, on-demand default, native desktop without mandatory WebUSB. Audit rename impacts across original and mirrored Flight Radar Pages and old one-line installers; no rename now.

### W6 Central provenance / brand / QA — 15 initial common requirements
User-request completeness, existing draft ancestry mapping, PR/Issue comments/reviews/timelines/history archives, immutable source ID and rename-safe references, logo asset hashes and genuine SVG validation, EN/TR/DE user UI contract, English internal engineering, model/feature/component/developer-agent matrix parity and cost/time tracking. Other optional Survival Kit areas kept in related-project ledger, not silently fused into five apps.

## Controlled milestones and authorization gates

| Phase | Task | User approval gate | Completion proof |
|---|---|---|---|
| P0 | Freeze refs and document current source, #65–#74 + Flight #7/#13 | current audit approval | 5 GitHub repo IDs, branch/commit pointers, 0 runtime diffs |
| P1 | Reconcile entire user history and the 97 initial acceptance IDs | audit | requirement sources verified, gaps explicit |
| P2 | Six nonoverlapping GitHub Issue workstreams + Draft report PRs | audit | per-worker inventory and source-backed evidence |
| P3 | Reconcile stacked app Draft PRs, test boundaries and shared dependency closure | code changes require new approval | conflict map and no-regression test plan |
| P4 | Bootstrap existing 3 empty repos and stage exact app sources, licensed dependencies | **separate explicit approval** | standalone builds and source hashes |
| P5 | Port in approved PNG branding and EN/TR/DE UI without losing old behavior | **separate explicit approval** | icon/locale platform tests, rollback |
| P6 | Apply functionality fixes + run native RF/DVB and platform regression | **separate explicit approval** | feature-by-feature baseline comparison |
| P7 | Three-app canonical cutover; retain Text Center, Flight Radar | **separate explicit approval** | verified installers, history maps, no shared runtime dependency |
| P8 | Optional rename of original Text Center repository | **separate explicit approval** | old/new PR, Pages/PWA, URLs and installers validated |

## Current evidence and time estimate

The 97 requirement records are an initial consolidated classification, **not a certification that every old request was recovered**, coded or released. Do not use a percent-complete figure based on the count alone. `apps/_coordination/PROGRESS.json` is the single source for counts and verified tests. Remaining hours/minutes are currently `null` because testing and dependency graphs are not sufficiently audited. Each worker must inventory tasks and measured effort before a defensible ETA is possible; do not invent elapsed time or promise background completion.
