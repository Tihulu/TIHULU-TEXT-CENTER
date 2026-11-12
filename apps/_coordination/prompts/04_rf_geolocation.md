# 04 · RF Geolocation — independent positioning mathematics

## Agent mission
Canonical source `rf_geolocation_center/` lives within `Tihulu/TIHULU-TEXT-CENTER`, with source snapshot `apps/geolocation-center/source/`. Destination `Tihulu/tihulu-rf-geolocation-center` ID `1454320329` exists but is EMPTY. Audit `GEO-001..GEO-008`.
Inspect GPS/NMEA, valid RF/aircraft evidence, single-SDR limitations, TDOA timestamps, horizon constraints, PSF/Gaussian inference, uncertainty not false location accuracy; independent Aircraft/Location/LIVE Fit/BEST Fit circles, RF On/Off default Location circle and no aircraft markers concealed; offline maps, multiple layers/models, history bounded indexing and cross-app interfaces. Check 3+ aircraft RF region computation without user lat/lon. Document source-specific test vectors and what remains scientifically unverified.
Coordinate with Flight Radar worker only via Issues, never edit Flight Radar own source or import it wholesale. English code/docs, EN/TR/DE UI target, no source/receiver behavior changes.

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
2. A JSON source-to-requirement and test matrix in `apps/_coordination/workstreams/04/` (proposal, not main).
3. A Draft PR on your OWN branch only, referencing the designated GitHub Issue and the central coordinator Issue.
4. A GitHub Issue comment summarizing measured progress, blockers and remaining effort evidence.
