# TIHULU — portable self-contained application roadmap

**Owner requirement:** all applications (Media Center, Satellite Center, RF Geolocation, Text Center, Flight Radar) must eventually live, build and evolve independently in their own GitHub repositories, with editable source, tests, installers, user-visible English/Turkish/German and all development knowledge accessible by coding LLMs. Engineering language, internal design, code comments and PR documentation: English.

## What is prepared today
- Frozen, **exact Git tree copies** under `apps/<app>/source/` for all four apps presently embedded in TEXT CENTER. Media Center explicitly includes its own `kaffeine_next/`, `tv_center/` and copied `textcenter/` because it reuses shared code. Text Center separately owns its `textcenter/` and `web/` snapshot. Satellite and RF Geolocation each have their own source tree snapshots.
- Flight Radar already has its own canonical repository `Tihulu/tihulu-flight-radar`, so it must remain independently editable there; the TEXT CENTER Pages mirror is an output, not a second source repo.
- Current runtime/launcher/import paths remain completely unchanged. `apps/*/source/` are **read-only preservation copies, not build inputs**. Under Git, exact tree SHA reuse proves content equality at the snapshot commit.

## What source copying does *not* do
- It does NOT include upstream KDE Kaffeine itself (pinned upstream release is fetched externally with GPL licensing), host libraries, model weights, native platform SDKs or verified installed dependencies.
- It does NOT automatically transfer full root-level tests, CI workflows, executable entrypoints, installation scripts, web assets outside declared copied roots, or independent launch success. Their proper dependency closure must be audited.
- It does NOT incorporate all later changes on unmerged Draft PRs (#65, #67, or unrelated satellite/RF branches). Each app requires PR conflict reconciliation and source hash audit before cutover.
- It does NOT make the snapshot a second active development copy. In this monorepo only the original source roots are edited; snapshots are refreshed by controlled, hash-verified copy of approved code.
- It does NOT archive GitHub native approvals/PR numbers as relocatable objects, nor automatically export private chats.

## Before creating or moving to an independent repository
1. Inventory active code roots and all runtime imports/required external packages; compute transitive dependency closure and verify licenses/attribution. Required shared TIHULU code gets a **local owned copy** in target repository or an explicitly versioned dependency with a checked offline fallback. Never pretend that copying only an interface gives self-contained offline functionality.
2. Include tests (including test fixtures), docs, release workflows, OS packaging, one-line installer, static website assets, localized resources and configuration migrator **inside that target repo**. Keep existing install paths operational until validated; no automatic overwrite of users' existing setups.
3. Reconcile every feature and unmerged PR using `FEATURE_MATRIX.json`, `COMPONENT_MATRIX.json`, `MODEL_MATRIX.json`, plus `HISTORY_LINKS.json` and the root historical PR ledger. Compare source SHA per application and per draft branch. No lossy squash that deletes needed provenance.
4. Prove standalone offline-first build in a fresh checkout *without depending on the old monorepo*. Hardware Start/Stop, exclusive SDR/DVB ownership, live subtitles/timing, recordings and translations must remain feature-parity tested. Actual device acceptance is distinct from CI.
5. Use `apps/REPOSITORY_RENAME_LINK_POLICY.md` for the old repo's potential rename. Repository IDs and historical aliases keep old origin references; current URLs are resolved and verified at cutover. A redirect is not an archival export.
6. All user-facing UIs require `en`, `tr` and `de` bundles and tests before declaring the *new independent release* complete. Internals remain English; no unreviewed locale changes in the current app.
7. Prepare **both** ends: old repo read-only pointer to new canonical source, and new repo root AGENTS.md/CLAUDE.md/DEEPSEEK_START.md/DEVELOPMENT_AGENT_GUIDE.md, model/component/feature matrices, original PR/issue/history link map, provenance and unapproved historical reviews. Write reciprocal old/new PR URL links when verified.
8. Obtain explicit owner approval to activate cutover, freeze old app source edits and change canonical registry. Continue **only** in its independent repo after cutover. Keep original branches, archives and recorded source copy available.

### Framework/design freedom
Rust, Python, Qt, GTK, Flutter, Tauri and other stacks are allowed. Any layout, theme and UI design is allowed. Every existing user-visible feature, default, accessibility action, saved setting, original media, source provenance and timing must survive. New features are additive and preferably opt-in. No extra LLM installation is required for source/agent matrices.

### Status
**Frozen source copies created; standalone dependency closure, localization, independent builds, complete historical comments and actual repo migration are not completed.** All this work is on a separate Draft branch. Main remains unchanged.

## Verified owner-created destinations (2026-11-11)

`Tihulu/tihulu-media-center`, `Tihulu/tihulu-satellite-center` and `Tihulu/tihulu-rf-geolocation-center` now exist but contain no application sources, startup instructions or releases (all observed GitHub `size=0`). They are **not yet active/canonical**. Use `apps/VERIFIED_DESTINATION_REPOSITORIES.json` and exact immutable GitHub repository IDs. For `apps/geolocation-center`, the prior speculative `Tihulu/tihulu-geolocation` name is superseded; do not create or target that alternate repository.

Logos must be the five **previously approved red/white/black TIHULU mascot designs** only, matched by `apps/BRANDING_APPROVED_MANIFEST.json` hash. Binary image assets remain in the verified conversation ZIP until a separate approved GitHub asset staging action; no existing app icon has been changed.

The three new repositories must be bootstrapped with a first commit only after the owner has authorized that next scope. Then application source import, independent build/CI, history preservation and native release validation occur on review branches. Text Center's separate future repo is not yet chosen; Flight Radar already has its own canonical repository. This branch performs no code import, repo rename or cutover.
