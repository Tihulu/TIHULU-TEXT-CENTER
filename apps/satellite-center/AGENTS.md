# TIHULU Satellite Center — development ownership instructions

Current status: **EMBEDDED IN TIHULU-TEXT-CENTER; NOT MOVED**.

Canonical repo: `Tihulu/TIHULU-TEXT-CENTER`
Actual source roots: `satellite_center/`
Source branches to inspect: `fix/satellite-native-scheduler-modes-2026-11-08`, `feature/satellite-segmented-captures-2026-11-07`
Proposed future destination: `Tihulu/tihulu-satellite-center` (not created by this scaffold).
Special note: Copied exact application tree; source branches have unmerged overlap outside satellite_center/.

## Before coding
1. Read `apps/registry.json` and this file. If registry marks `external_canonical`, follow the recorded destination; STOP changing this monorepo copy.
2. Read `apps/_archives/pr-index.json` and relevant `pr-body-*.json` parts and source PR URLs. Old requests, discussion comments, reviews and decisions are authoritative only when fully archived or linked and verified. Do not infer that absent comments were preserved.
3. Read `apps/satellite-center/MODEL_MATRIX.md`: preserve verified backend/translation/hardware support and legacy choices rather than inventing a model preference.
4. Keep app-specific CI, installers and settings stable; any change to shared Python modules or SDR/device resource owners needs explicitly coordinated regression tests.
5. Never auto-merge previous Draft PRs, rewrite their base branches, or move the canonical repository without authorization.
6. Future migration: follow `apps/MIGRATION_PROTOCOL.md`; the target repository's AGENTS.md becomes authoritative after explicit owner-approved cutover only.

## Continuing past work
The original PR descriptions have been snapshotted into portable archives. Review comments, approvals, issue timelines and conversational instructions are not automatically copied merely by this template. Verify archive completeness before moving. Commit history is preserved in original Git, not embedded in the JSON archive.
