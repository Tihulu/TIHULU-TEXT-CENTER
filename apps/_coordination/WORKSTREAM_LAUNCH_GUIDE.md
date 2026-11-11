# Open six independent ChatGPT conversations (GitHub-mediated)

The six GitHub branches and six **Draft PRs #83–#88 are already created**, with one isolated `TASK.md` and source/test candidate table each. All are English and **none changes an application**. Branches were cut from the PR #82 coordination branch and have disjoint paths.

**Important:** Creating a GitHub Issue/branch/PR is NOT equivalent to creating a ChatGPT conversation or running an autonomous agent. The owner must open each new chat manually and send the corresponding prompt below. No background job or time-based promise is implied.

## One-copy starter instruction (choose the appropriate numbers below)

Use this short English instruction in a new chat, replacing the links using the corresponding row. The long task file contains every requirement ID and candidate source/test path.

```text
You are the dedicated TIHULU Workstream <N> audit agent. Connect to the authorized GitHub repository Tihulu/TIHULU-TEXT-CENTER.

Read this exact prepared Draft PR: <DRAFT PR URL>
Read the detailed English task: <TASK URL>
Read the assigned Issue: <ISSUE URL>
Read coordinator rules: https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75

Adopt ONLY the dedicated audit branch in the task. Do a SOURCE-BASED, READ-ONLY audit of all assigned requirements. Commit ONLY an English REPORT.md and EVIDENCE.json under YOUR owned apps/_coordination/workstreams/<NN>/ directory, then leave the PR in Draft and post a result comment to YOUR Issue. To communicate with another worker, comment on their Issue and link central #75; never edit their workstream or coordinator-owned global files.

Owner's absolute requirements: do not change or remove ANY working app feature, default, behavior, settings, installer, device ownership, existing UI/icon, recording or source code. Never modify main, merge existing Draft PRs, create first commits in empty repos, rename an original repo, release installs, or claim actual SDR/DVB/hardware tests without physical evidence. All code, PRs, GitHub instructions, documentation and internal language ENGLISH; all five apps' user interfaces support English(default), Turkish, German. ONLY the five already approved red/black/white TIHULU mascot logos are permitted; do not use internet images or create substitute logos. Report source paths, exact SHAs, verified tests vs synthetic/static checks, original PR/comment URLs, missing evidence, cross-team blockers, and an hours/minutes estimate only if grounded; otherwise explicitly say UNKNOWN.

Start auditing now. Do NOT wait for further confirmation for documentation-only changes. Do NOT implement runtime fixes; those need separate user approval.
```

## The six independently owned GitHub assignments

| Chat | Responsibility | Issue | Draft PR | TASK.md |
|---|---|---|---|---|
| 1 · Media Center | TV, DVB-T2, DAB+, FM, Whisper, subtitles, Teletext auto-fallback, TV↔radio receiver lifecycle, karaoke/Qwen alignment, lip-sync, local file and FFmpeg recording/export; preserve media #65→#66→#67 ancestry. | [#76](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/76) | [#83](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/83) | [Task 1](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/audit/ws01-media-zero-regression-2026-11-11/apps/_coordination/workstreams/01/TASK.md) |
| 2 · Flight Radar | Canonical independent Flight Radar GitHub repo, PR #7/#13, legacy 0.3.1, readsb, tar1090, I/R, source evidence, RF circles, developer matrices + Claude/DeepSeek and dual Pages rename safety. | [#77](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/77) | [#84](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/84) | [Task 2](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/audit/ws02-flight-standalone-2026-11-11/apps/_coordination/workstreams/02/TASK.md) |
| 3 · Satellite Center | Pass planning, IQ continuity, long capture, ISS SSTV, Meteor LRPT, NOAA, Robot36, native/browser feature differences and authentic decoder/hardware evidence. | [#78](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/78) | [#85](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/85) | [Task 3](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/audit/ws03-satellite-parity-2026-11-11/apps/_coordination/workstreams/03/TASK.md) |
| 4 · RF Geolocation Center | PSF/Gaussian, provenance, source rings LIVE/BEST, true calibrated multi-source RF timing, native GNSS-SDR limitations, positioning accuracy, independence. | [#79](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/79) | [#86](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/86) | [Task 4](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/audit/ws04-rf-geolocation-2026-11-11/apps/_coordination/workstreams/04/TASK.md) |
| 5 · Text Center | Keep active Text Center source and web in original repo, preserve FM/DAB/TV functionality and historical archive, verify optional later rename/PWA/Pages/raw installer links and both Flight Radar mirrors. | [#80](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/80) | [#87](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/87) | [Task 5](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/audit/ws05-text-retained-2026-11-11/apps/_coordination/workstreams/05/TASK.md) |
| 6 · Cross-app QA, history and branding | Original PR/Issue/review/comment provenance, missing user-history gaps without private leakage, all five approved red TIHULU badges, EN engineering vs EN/TR/DE UI, regression gates and audit progress. | [#81](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/81) | [#88](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/88) | [Task 6](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/audit/ws06-provenance-qa-2026-11-11/apps/_coordination/workstreams/06/TASK.md) |

## Cross-workstream handoffs

- Worker 01 and 05: do not simultaneously rewrite Text Center active `textcenter/` or `web/`; this audit must not edit either at all. Media migration uses #65→#66→#67 exact source ancestry and a separately approved future integration gate.
- Worker 02 and 04: RF positioning cross-app API requests are GitHub Issue comments, not direct cross-file edits. Flight Radar's code stays in its own canonical repo; the Text Center branch for Worker 02 is **audit notes only**.
- Worker 02 and 05: Flight Radar dual Pages and same-repo Text Center rename risk needs verified original/current links, but **no repo rename or live Pages change is authorized**.
- Worker 03 and 04: coordinate receiver ownership evidence, and never claim browser-only capabilities equal native hardware.
- Worker 06 resolves shared provenance/branding/locale questions; no live icon changes, no private chat dump, no fabricated GitHub approvals.

## Progress and time

Ready GitHub assignments: **6/6 branches, 6/6 Draft PRs, 6/6 Issues**. Independent worker ChatGPT conversations launched automatically: **0/6**. Worker audits finished: **0/6**. Initial requirement records: **97**; candidate source links: 198; candidate test links: 127; test candidates missing for 11 requirements. Current GitHub PR #82 CI success does NOT certify native hardware.

Hours/minutes remaining: **UNKNOWN** until every worker produces a source-based task count and test-time assumptions.

[Machine-readable workstream index](WORKSTREAM_HANDOFF_INDEX.json) · [Full protocol](COORDINATION_PROTOCOL.md) · [Master Plan](MASTER_PLAN.md).
