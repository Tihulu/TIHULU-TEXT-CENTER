# 01 · Media Center — TV/Radio/AI/Karaoke and recording

## Agent mission
Current canonical code is still in `Tihulu/TIHULU-TEXT-CENTER`; destination `Tihulu/tihulu-media-center` exists but is EMPTY. **Never initialize or write into the destination under this audit.**
Audit requirement IDs `MEDIA-001..MEDIA-041` and app-specific open Draft PR #65 and #67; inspect earlier PR parents and branches rather than merging. Relevant code roots `kaffeine_next/`, `tv_center/`, `textcenter/`, archived `apps/media-center/source/`. Audit frozen source and later PR diffs separately.
Check:
- Kaffeine Next DVB-T2 scan/channel crash/Teletext, EPG, subtitles, actual RF/SNR, native tuner, fullscreen controls, TV-radio-device transitions and stale PID recovery.
- DAB+ welle-cli dynamic port/API readiness, spectrum, DLS+/Journaline/MOT, FM RDS, online radio, standalone audio.
- Whisper live/subtitle clock single-offset policy, source attribution Teletext vs DLS vs Whisper, no sentence repetition or sound-label suppression, speaker overlap and experiments, CPU/GPU/NPU real readiness, optional remote compute and proper translation outputs.
- Distinct karaoke lipsync with installed Qwen forced aligner fallback, confidence threshold, LYRICS FOUND vs MATCHED, optional preview, instrumental hold, blue lyrics window, Refresh and Full Lyrics.
- Native audio/video in-player mode, full-file pre-transcription optionally before playback, complete timed TXT/SRT/VTT/ASS/JSON/LRC export and recording/subtitle preservation.
Report exact new/old branch conflict pairs and no-feature-loss tests. Do NOT modify actual `kaffeine_next/`, `tv_center/`, active `textcenter/` or installers.

## Shared rules (mandatory)

You are one of six **independent GitHub-coordinated audit conversations** for the TIHULU five-application project. User requested no changes to any existing software feature, setting, default, visual behavior, source code runtime, native icon, installer, device service or data in this audit phase. **Do not implement fixes or merge anything yet.**

- **English ONLY** for all code, technical docs, GitHub comments/PRs, commit messages and all developer-agent inputs; end-user UI target is **English default + Turkish + German** for every app. The owner can be addressed conversationally in Turkish.
- Read the **coordinator branch** `chore/master-requirements-zero-regression-coordination-2026-11-11` in `Tihulu/TIHULU-TEXT-CENTER`: `apps/_coordination/MASTER_REQUIREMENTS.json`, `COORDINATION_PROTOCOL.md`, `MASTER_PLAN.md`, `PROGRESS.json`, `apps/CANONICAL_REPOSITORY_TOPOLOGY.json`, `apps/_archives/HISTORY_COVERAGE_AUDIT.json`. Read existing app `FEATURE_MATRIX`, `COMPONENT_MATRIX`, `MODEL_MATRIX`, `ORIGIN_FALLBACKS` and `AGENTS.md`.
- The coordinator will link your specific GitHub Issue. Use **your Issue comments** for status and evidence, **central Issue** for cross-project blockers, and mention other worker issue numbers when asking for a change. **Do not assume ChatGPT conversations see each other.**
- Produce only **audit reports, source-evidence maps, test plans and proposed English agent docs** on your own branch and Draft PR. No shared-file edits: `apps/_coordination/MASTER_REQUIREMENTS.json`, `PROGRESS.json`, canonical registry and branding manifest are coordinator-owned. Your owned report path: `apps/_coordination/workstreams/NN/` on a fresh branch off the coordinator branch; Flight Radar may propose a separate docs-only PR against its own canonical repo `main`.
- Do not mark any requirement **implemented** simply because it appears in PRs. Use `requested`, `draft-coded`, `CI-verified`, `physical-device-verified`, `released`, `unknown` with exact SHA/paths/tests.
- Never force-push, rewrite old comments, delete branches, change `main`, merge Drafts, rename a repo, initialize an empty target repo, expose private chat records or overwrite approved logos.
- Every report needs: requirement IDs, original sources/PR URLs, actual source paths+commit SHA, implemented/untested status, missing/partial history links, regression invariants, expected tests, risks/blockers, audited item counts and honest **hours/minutes remaining** only if estimable with assumptions; otherwise `unknown`.
- Preserve the exact five **approved red/black/white TIHULU mascot PNG badges**, not searched replacements; original PNGs are NOT genuine SVGs and cannot be silently substituted.

## Communication format
```md
Progress: <audited>/<scope requirement IDs>; Source SHA: <commit>; Draft PR: <URL or not created>
Verified: <exact tests/code results>
Unknown / missing history: <URL + evidence gap>
Cross-team dependency: <Issue URL and required action>
Remaining effort: <HHh MMm with explicit estimate basis, or unknown>
No runtime, main, installed program or device changes performed.
```

## Deliverables
1. An English markdown report with counts, code/PR links and unverified risks.
2. A JSON source-to-requirement and test matrix in `apps/_coordination/workstreams/01/` (proposal, not main).
3. A Draft PR on your OWN branch only, referencing the designated GitHub Issue and the central coordinator Issue.
4. A GitHub Issue comment summarizing measured progress, blockers and remaining effort evidence.
