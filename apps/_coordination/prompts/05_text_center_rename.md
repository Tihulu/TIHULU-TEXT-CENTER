# 05 · Retained Text Center — RF data, existing source and rename contract

## Agent mission
Text Center STAYS in **`Tihulu/TIHULU-TEXT-CENTER`** repo ID `1447637221` permanently under the currently approved topology. No second Text Center repo, no code freeze, no rename in audit. Active code roots `textcenter/` and `web/`, not the frozen apps/text-center/source snapshots. Requirement IDs `TEXT-001..TEXT-008`.
Audit FM RDS/RadioText+, DAB DLS/DLS+/Journaline/MOT/full scan, DVB-T2/Teletext/TV, AIS/ACARS/NOAA/RTL-433 optional source honesty; native hardware, on-demand default/no background, responsive English/Turkish/German user interface and one-line installer, shared modules kept active after three app migrations.
Audit all historic PR/Issue original URLs and old repo ID when eventual rename changes repository display name. In particular Flight Radar dual Pages mirror and original textcenter PWA/service workers, raw.github/installer links and GitHub workflows MUST have tested alias/redirect strategy. Detect hardcoded `TIHULU-TEXT-CENTER` occurrences and categorize runtime/path/public links without changing them.
Report legacy path parity + safe future rename/rollback acceptance checklist. Do not rename, move or remove Text Center itself.

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
2. A JSON source-to-requirement and test matrix in `apps/_coordination/workstreams/05/` (proposal, not main).
3. A Draft PR on your OWN branch only, referencing the designated GitHub Issue and the central coordinator Issue.
4. A GitHub Issue comment summarizing measured progress, blockers and remaining effort evidence.
