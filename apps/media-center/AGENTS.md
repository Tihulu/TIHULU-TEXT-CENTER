# TIHULU Media Center — development ownership instructions

Current status: **EMBEDDED IN TIHULU-TEXT-CENTER; NOT MOVED**.

Canonical repo: `Tihulu/TIHULU-TEXT-CENTER`
Actual source roots: `kaffeine_next/`, `tv_center/`
Source branches to inspect: `feat/unified-lyrics-caption-refresh-2026-11-10`, `feat/media-unified-recording-export-2026-11-11`
Proposed future destination: `Tihulu/tihulu-media-center` (not created by this scaffold).
Special note: Native TV, DAB/radio, audio/video, caption/export. tv_center is shared; do not assume sole ownership of all code.

## Before coding
1. Read `apps/registry.json` and this file. If registry marks `external_canonical`, follow the recorded destination; STOP changing this monorepo copy.
2. Read `apps/_archives/pr-index.json` and relevant `pr-body-*.json` parts and source PR URLs. Old requests, discussion comments, reviews and decisions are authoritative only when fully archived or linked and verified. Do not infer that absent comments were preserved.
3. Read `apps/media-center/MODEL_MATRIX.md`: preserve verified backend/translation/hardware support and legacy choices rather than inventing a model preference.
4. Keep app-specific CI, installers and settings stable; any change to shared Python modules or SDR/device resource owners needs explicitly coordinated regression tests.
5. Never auto-merge previous Draft PRs, rewrite their base branches, or move the canonical repository without authorization.
6. Future migration: follow `apps/MIGRATION_PROTOCOL.md`; the target repository's AGENTS.md becomes authoritative after explicit owner-approved cutover only.

## Continuing past work
The original PR descriptions have been snapshotted into portable archives. Review comments, approvals, issue timelines and conversational instructions are not automatically copied merely by this template. Verify archive completeness before moving. Commit history is preserved in original Git, not embedded in the JSON archive.

## Read-only source copies, old PR links, repo rename and languages

Read `apps/media-center/SOURCE_SNAPSHOT.md`, `PORTABLE_PACKAGE.json`, `HISTORY_LINKS.json` and `LOCALIZATION_CONTRACT.json`. For embedded apps, `apps/media-center/source/` is a SHA-identical frozen source archive, NOT the active build, package, import or development path. Do not edit it separately. Flight Radar is already canonical in its separately owned repository; TEXT CENTER only mirrors it.
Original PR URLs and historical review author/timestamps remain in the source history and link ledger, not regenerated as native GitHub approvals. A later rename of TEXT CENTER must preserve repository numeric ID, original source URLs and tested aliases. All eventual standalone repos must offer en/tr/de **user interfaces**, with English-only engineering, schema keys and internal operations. Do not pretend translation coverage, standalone builds or full dependency closure have already been verified.
