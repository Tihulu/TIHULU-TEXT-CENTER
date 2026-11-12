# 02 · Flight Radar — canonical independence, source history and agent docs

## Agent mission
Canonical repo is **already** `Tihulu/tihulu-flight-radar`, numeric ID `1447534043`. It has working `AGENTS.md`, `pyproject.toml`, installers, tests, dual Pages workflows and 0.3.1 legacy rollback. It lacks independent standard `FEATURE_MATRIX/COMPONENT_MATRIX/MODEL_MATRIX/DEVELOPMENT_AGENT_MATRIX` and root Claude/DeepSeek documents. Evaluate requirement IDs `FLIGHT-001..FLIGHT-017` and both **OPEN Draft PRs #7 and #13** without merging, and own 11 historical PRs + 2 independent Issues.
Audit:
- Native readsb/RTL-SDR vs optional browser WebUSB and exact start/stop/never-kill-external-service behavior.
- Real ICAO/I-R dedup, internet source licenses/rate limits, original full tar1090, plane details/routes, RF circles LIVE/BEST, PSF/Gaussian, history and false physical TOA precision prevention.
- Existing 0.3.1 pinned restore and current main CI; source and hardware tests distinguished.
- Flight's own Pages and the Text Center's generated /flight_radar mirror use source-revision SHA. Check future Text Center same-repo rename impact on Pages URL, PWA, permissions, caches, raw installers and workflows; old main repo numeric ID `1447637221` persists but old Pages URLs may break.
- Crosslink historical Flight-related original Text Center PR/Issue and comment source pointers and honest missing-history ledger, without duplicating editable source.
- Propose new English `CLAUDE.md`, `DEEPSEEK_START.md`, `DEVELOPMENT_AGENT_GUIDE.md` and 4 matrix shapes aligned with other apps. Static reading requires no new model installation.
Deliver report under coordinator-owned branch and optionally an **unmerged docs-only Draft PR** in canonical Flight Radar repo; no active web/icon/installer code changes.

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
2. A JSON source-to-requirement and test matrix in `apps/_coordination/workstreams/02/` (proposal, not main).
3. A Draft PR on your OWN branch only, referencing the designated GitHub Issue and the central coordinator Issue.
4. A GitHub Issue comment summarizing measured progress, blockers and remaining effort evidence.
