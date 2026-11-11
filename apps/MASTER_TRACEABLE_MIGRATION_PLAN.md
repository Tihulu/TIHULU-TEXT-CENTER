# TIHULU master plan — traceable history and approved logos

**Scope:** all five TIHULU applications. **Current phase: metadata, original-source links, approved-design asset staging.** Three owner-created destination repository shells now exist (all verified empty). Do not populate or cut over to them, rename any repo, merge Draft PRs or change installed app behavior during this documentation phase.

## Objectives
- Each app gets a complete independent source/dependency/build/test/localization/brand package, with no external monorepo runtime dependency. Flight Radar is already separately canonical and is handled there.
- Every copied item retains its original source pointer. Every missing, blocked, partial or GitHub-native nonportable record has a gap entry and an old-repo link. Names/URLs after old repo rename are resolved using GitHub repo ID plus tested aliases.
- Original PR/issue/comment/review evidence, original IDs, authors, dates, review decisions and source SHA provenance are not discarded, even when native GitHub objects cannot be duplicated in new repos.
- Claude Code, DeepSeek, ChatGPT and other coding LLMs read the same documented code→feature→component→tests and history-gap maps; no extra coding LLM is required to read static JSON/Markdown.
- Approved app logos have per-app masters and future vector/source variants. English engineering/internals, English/Turkish/German UI.

## Gates and deliverables
**G0 — Evidence freeze:** source branch/shas and approved logo master PNG SHA256, old repo identity and PR/issue original URLs preserved. Status: first snapshot and branding approval prepared.
**G1 — Completeness audit:** enumerate PR bodies/comments, inline review threads, reviews/approvals, issue events, source commits, workflows, decision records, approved external chats. Record every missing category with source link and reason. Status: descriptions linked, comments/reviews/chats not fully exported.
**G2 — Self-contained source dependency closure:** find own copies of required TIHULU modules, upstream KDE Kaffeine and other third-party library/ABI/licensing constraints, tests, workflow, installers and offline packages. Status: frozen copies available, independent full builds not verified.
**G3 — Logo/locale assets:** import approved binary masters per repo; generate true vector source if desired; design parity and icon size/platform/PWA tests; EN/TR/DE UI. Status: approved PNG pack delivered in conversation, not installed in GitHub app code; translation implementation pending.
**G4 — Parallel six-audit workers:** assigned disjoint scope; each checks feature/source gaps, old/new anchors, tests, locale and logo integration dependencies. Status: prompts only, no parallel chats started.
**G5 — Regression parity:** source-specific native builds, settings/file migration, broadcasts/subtitles/media/SDR ownership, packaging all target OS platforms, hardware signal tests. Status: not complete.
**G6 — Explicit owner-approved cutover:** create/populate final repos with files, history gaps and links, new root AGENTS/CLAUDE/DeepSeek instructions, logo resources and verified bidirectional PR/issue map. Current monorepo keeps old links, read-only historical code and freeze marker. Status: not started.
**G7 — Future parent-repo rename:** only after all raw installer, Pages/PWA, workflow, mirror, callback, licensing and history redirect tests; update aliases, not original URLs. Status: not requested or performed.

## No-feature-loss guarantee
Existing behavior, fonts/UI settings, existing features, user recordings, subtitle/translation timings, RF/SDR/DVB device lease/stop and all installers remain unchanged. Approved branding is a later asset-only release with its own test gate. New repo may be redesigned/reimplemented (Rust etc) only on isolated branches with complete feature-by-feature compatibility evidence.

## How to read progress
Documentation source/link maps and approved design are complete **for their current limited scope**. Full history export, self-contained builds, localization, icon integration, hardware tests and repo relocation remain separate incomplete milestones. Do not invent hours/minutes until measurable audit results provide a credible estimate. No background work is implied by this plan.


## Verified destination repos — 2026-11-11 addendum
Three user-created, public GitHub repository shells were verified, all empty (`size=0`):
| App | Verified destination | GitHub repository ID | Code imported? | Canonical now? |
| --- | --- | ---: | --- | --- |
| Media Center | `Tihulu/tihulu-media-center` | 1454318539 | No | No |
| Satellite Center | `Tihulu/tihulu-satellite-center` | 1454319572 | No | No |
| RF Geolocation Center | `Tihulu/tihulu-rf-geolocation-center` | 1454320329 | No | No |
Text Center has **no separately selected destination**. Flight Radar is already canonical at `Tihulu/tihulu-flight-radar` (ID 1447534043). The old source repo `Tihulu/TIHULU-TEXT-CENTER` remains canonical for the three embedded apps (original repository ID 1447637221). The verified destination registry is `apps/VERIFIED_DESTINATION_REPOSITORIES.json`.

### Updated migration sequence (do not auto-execute)
1. **Freeze and reconcile source:** per-app exact tree snapshots, latest stacked PR heads and branch differences, unmerged root-level tests, upstream third-party dependencies and licenses. No unreviewed change to current source.
2. **Complete source-linked history inventory:** original PR/Issue bodies, comments, reviews, inline threads, decisions, snapshots and gaps. Never add private chats or secrets into public repos without review. Every partial/untransferable item must link to original repo ID and historical URL, plus a checked rename alias and independent archived evidence where authorized.
3. **Bootstrap empty repos only after separate owner approval:** each has an English README, root AGENTS/CLAUDE/DeepSeek instructions, `ORIGIN.md`, link map, copyright/license inventory and safe non-runtime metadata. An empty repo may have a default branch *label* but no usable commit/branch until initial commit; do not assume an open PR is already possible.
4. **Import per-app standalone code on isolated branches:** own copies of required shared TIHULU code, necessary external dependencies via permitted pinned packages, test fixtures, CI workflows, supported platform installers. Preserve source provenance and all unresolved old/new PR mappings. No silent squashing of historical decisions.
5. **Stage the exact approved red-black-white TIHULU mascot logos:** five specific SHA-256-identified PNG designs from the approved chat pack (pack SHA256 `49eeccd46ab8b6e630b5567b4e08c0580f22430696de8e215b80d21a52043f84`). No alternative generated/search logos. Stage per-app assets before separately testing actual icon replacements. Genuine SVG is still a separate art task; PNG is not native vector.
6. **EN/TR/DE and behavior-parity tests:** English code/architecture/CI/agent instructions; English/Turkish/German user-facing UI. Test native hardware SDR/DVB radio-TV switching, satellite, radar, positioning, subtitle clocks, media preservation, profile/translation settings, standalone clean installs and rollback across supported platforms. Flag current shipped vs requested vs Draft-only features.
7. **Explicit cutover:** only owner-approved, fully verified standalone repo becomes canonical. Archive old app source as read-only pointer with bidirectional old/new PR/issue references. Do not update installer links or old repo redirects before verification.
8. **Future monorepo rename (separate later approval):** original GitHub numeric ID and URLs preserved, alias resolution and live redirect tests for PR, Pages, raw files, installers and workflows; no destructive rename during migration.

**Hard rule:** existing application source, UI behavior, settings, shipped logos, release installers and `main` remain unchanged by this plan. Three repositories' existence is not migration completion.
