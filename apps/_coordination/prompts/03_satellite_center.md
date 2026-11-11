# 03 · Satellite Center — passes, capture and decoder parity

## Agent mission
Current canonical source lives within `Tihulu/TIHULU-TEXT-CENTER`; `Tihulu/tihulu-satellite-center` ID `1454319572` has been created but remains **EMPTY**. Audit `SAT-001..SAT-008` plus relevant old user requests and PRs, maps to `satellite_center/` and frozen `apps/satellite-center/source/`.
Focus on Earth+Sky map, real TLE pass predictions and time zones, window 280°/near zenith, ISS SSTV/Robot36, Meteor M2-3/M2-4 LRPT, NOAA APT, CubeSat profiles, large CU8/CS8 and WAV + IQ recording, scheduled pass splitting beyond browser capture limits, correct native RTL-SDR lease and Stop, decode output provenance, CADU=0/PLL unlock report without fake images, offline-first, optional CPU/GPU acceleration only when verified.
Deliver dependency closure including third-party licenses, source-specific test fixtures, no model hallucination, independent installer/CI proposal, all EN/TR/DE UI coverage gaps. No device tests claimed unless actual device access and logs are provided. Do not touch empty target repo.

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
2. A JSON source-to-requirement and test matrix in `apps/_coordination/workstreams/03/` (proposal, not main).
3. A Draft PR on your OWN branch only, referencing the designated GitHub Issue and the central coordinator Issue.
4. A GitHub Issue comment summarizing measured progress, blockers and remaining effort evidence.
