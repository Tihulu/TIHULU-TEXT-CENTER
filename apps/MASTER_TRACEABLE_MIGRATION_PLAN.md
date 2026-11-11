# TIHULU master plan — traceable history and approved logos

**Scope:** all five TIHULU applications. **Current phase: metadata, original-source links, approved-design asset staging.** Do not rename a repo, create a new canonical repo, merge Draft PRs or change installed app behavior during this phase.

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
