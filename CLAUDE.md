# Claude Code — TIHULU project instructions

Read AGENTS.md, DEVELOPMENT_AGENT_GUIDE.md and apps/DEVELOPMENT_AGENT_MATRIX.json before editing. Read apps/registry.json to identify the canonical repo, then the selected application's AGENTS.md, FEATURE_MATRIX.json, COMPONENT_MATRIX.json and MODEL_MATRIX.json.

These are documentation files for coding agents. No extra LLM, inference weights or GPU is required to read them. MODEL_MATRIX describes optional application-internal AI engines; DEVELOPMENT_AGENT_MATRIX describes how Claude Code and other coding assistants develop the program.

Preserve every original feature, setting, default, device lease, subtitle timing and saved recording. Only change application source in a separately approved feature task and preview branch. Porting to Rust or another framework and redesigning the interface are welcome after feature-by-feature parity checks. Never silently merge Draft PRs, repoint installers, move repositories or claim real hardware verification without tests.

Keep this root file concise; AGENTS.md and the app contracts remain the detailed source of truth.

Every app is intended to become a self-contained independent repo, with stable GitHub repo-ID/alias links and original PR provenance; read `apps/SELF_CONTAINED_APP_PORTABILITY.md` and each app's `PORTABLE_PACKAGE.json`, `HISTORY_LINKS.json`, `LOCALIZATION_CONTRACT.json`. Current `apps/<app>/source/` folders are frozen copies, not active code. English developer workflow, EN/TR/DE user interface target; do not alter current app features or pretend localization is complete.

## Complete provenance for copied and incomplete information

At task start read `apps/HISTORY_ORIGIN_FALLBACK_POLICY.md`, `apps/_archives/HISTORY_COVERAGE_AUDIT.json`, `apps/<app>/ORIGIN_FALLBACKS.json`, and `apps/<app>/APPROVED_BRANDING.json`. PR/Issue descriptions have origin links but comments, review submissions, review threads, CI events, missing branches and external ChatGPT requests are NOT yet completely exported. If an item cannot be transferred, preserve its old URL and GitHub repository ID 1447637221, plus an explicit remaining gap and reason. A future repo rename must update resolved aliases without erasing original URLs. Approved logos are separate PNG assets staged in the conversation package, not yet committed or installed in running apps. All engineering content remains English and every eventual app UI supports en/tr/de. Do not change any app code or installer during the documentation audit.

## Destination repository verification and approved logo identity (2026-11-11)

Three app destination shells are now confirmed: `Tihulu/tihulu-media-center`, `Tihulu/tihulu-satellite-center`, `Tihulu/tihulu-rf-geolocation-center`. All were empty on verification. Read `apps/VERIFIED_DESTINATION_REPOSITORIES.json` for immutable GitHub IDs and status before planning any migration. Their creation does NOT make them canonical. Text Center has no chosen separate destination and Flight Radar is already independent.

Brand identity is strictly the **same previously generated and user-approved red/black/white TIHULU mascot badges** documented with SHA256 in `apps/BRANDING_APPROVED_MANIFEST.json`. Do not use newly searched or substitute logos; never claim PNGs are genuine SVG vectors. Approved binaries are not committed to these app repos and none of the existing runtime icons are changed. Continue to preserve original PR/issue origins, partial transfer gaps, model/component/feature matrices and English development with EN/TR/DE UI.

## Final canonical repository exception (owner decision: 2026-11-11)

**Text Center remains in `Tihulu/TIHULU-TEXT-CENTER` (GitHub repository ID `1447637221`) and no separate Text Center repository is to be created.** This is the active Text Center codebase: keep `textcenter/` and `web/`, all its original features, source-level AI settings, tests, workflows, website and installers functional. Do NOT freeze the entire source repository when Media Center, Satellite Center and RF Geolocation Center later move. Only those three use their existing empty target GitHub repos; Flight Radar already lives separately. The original Text Center repository also hosts historic PR/Issue records, review gaps and source provenance for those migrated apps. Coding agents must read `apps/CANONICAL_REPOSITORY_TOPOLOGY.json` and the per-app `AGENTS.md` before deciding a change target. A future optional repo rename is a rename of the same repo ID with tested redirects, NOT a migration. Use exactly the five approved red/black/white TIHULU mascot logos, English engineering and EN/TR/DE UI policy. Static matrix-reading requires no additional local LLM. No code or installer changes are permitted in this planning PR.
