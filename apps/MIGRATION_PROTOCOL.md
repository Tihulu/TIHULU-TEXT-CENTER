# TIHULU source-repo handoff protocol

## Stages
1. **Inventory + frozen reference**: record source branch SHA/tree SHA, app code roots, shared dependencies, required models and test requirements. Export all relevant PR and issue bodies, comments/reviews/inline review threads, timeline and review decision states with original IDs, authors and times. If permissions or APIs are missing, report gaps without inventing records. Do not push access tokens.
2. **Read-only dry run**: create a fresh destination repo and branches, using `git filter-repo` (or `git subtree split` for single-root apps) and validate full commit ancestor graph, file hashes and path rewrites. Multi-root app e.g. Media Center needs a controlled filter-repo rewrite and explicit shared-component contracts.
3. **New development PRs**: recreate unresolved PR branches and work-in-progress in target repo with fresh PR numbers; copy summaries and link old PRs. Existing GitHub review approvals are NOT transferred as approvals; save their original state/author/time as historical evidence. Do not claim comments were authored at the new timestamp by original authors.
4. **Model/LLM matrix**: move source-backed model profile mapping and supported/incompatible device/language choices with provenance. Unknown mapping stays `unknown`, never reconstructed from guess.
5. **Verification**: test source tree/file equality under any normalized paths, all builds/CI, media recording, subtitle timing, native DVB, DAB, Sat/RF isolation, cross-platform packaging and existing config migration. `main` remains unchanged until reviewed.
6. **Cutover**: only on explicit owner authorization, update `apps/registry.json` to `external_canonical` with validated URL, commit, date, issue/PR correspondence, and code freeze for the app's old monorepo path. Add README and AGENTS.md **both** places. Old repo's historical branch stays available; no destructive deletion.
7. **Follow-on changes**: agents MUST inspect registry at task start; create future commits and PRs exclusively in new canonical repo. Do not mirror editable code back unless a separately reviewed read-only build/mirror contract exists. Shared code updates use semantic versioned dependencies, subtree/submodules with pinned SHA, or explicit coordinated PRs, never two diverging authoritative copies.
8. **Rollback**: if relocation validation fails before cutover, original repo retains authority; after cutover, pause writes and re-validate, do NOT force-merge or overwrite histories.

## New repository mandatory files
- Root README.md: prominent moved-from/moved-to origin and canonical statement
- Root AGENTS.md: "You are now in the canonical home", source archive pointer and editing/testing instructions
- `migration/origin.json`: source path, original ref & SHA, transfer ref & SHA, git hash map, review map, provenance time
- `migration/PR_MAP.json`: old PR URL/number -> newly created PR URL/number; review copies marked historical
- `history/requests.jsonl` and `history/decisions.md`: feature requests and why decisions were taken, link original issue/PR/chat exports
- `models/MATRIX.md` and `models/MATRIX.json`: verified source-backed models/translation/lip-sync/runtime hardware mapping
- tests and CI plus independent install entrypoints

## Accurate history limitations
Git history can be filtered/copied but rewritten root path can change commit hashes; keep a provenance map. GitHub PR/issue IDs, review approvals, original timestamps and immutable review state cannot be transplanted as native new-repo objects. Preserve accurate originals in exported JSON, include original URLs, use clear migration-bot attribution if re-posted. The ChatGPT conversation history is NOT fully available in this GitHub repository: store explicit user-approved conversation exports/documents with sources; don't claim unseen chats were archived. Never include passwords, tokens, precise personal data, or private model weights.

## Framework-independent migration with verifiable feature parity

Before copying a code tree into a new repo or translating it to Rust, Qt, GTK,
Flutter, Tauri or another framework, preserve the complete metadata bundle:
`apps/<app>/FEATURE_MATRIX.json`, `MODEL_MATRIX.json`, `PORTING_GUIDE.md`,
app `AGENTS.md`, historic PR/issue archive pointers, and the original source SHA.
The new repo should use `features/FEATURE_MATRIX.json`, `models/MODEL_MATRIX.json`,
`history/`, `migration/`, and framework-independent contract/golden fixtures.
No UI design, model backend or language/framework is permanently mandated.

A framework rewrite is NOT the same as a source repo move. A rewrite remains an
isolated preview until parity checks for every known feature ID, persisted setting,
caption clock, original/translation track, error/fallback, SDR ownership and
on-demand background policy are accepted. Unknown hardware results must remain
unknown. New features must be additive and opt-in; a UI redesign must keep controls
accessible. Run `apps/PARITY_RELEASE_GATES.md` and review
`apps/DESIGN_EXTENSIBILITY_POLICY.md` before cutover.

The six-chat plan is in `apps/PARALLEL_CHAT_WORKSTREAMS.md`, with distinct file
ownership, source evidence and Draft PR handoffs. Conversations are separate; do
not assume GitHub branches or chat history sync automatically. **No app is moved
merely by publishing these manifests.**

## Mandatory additions for all application migrations

Do not treat a source tree snapshot as a completed standalone app. Include dependency closure and external upstream license/commit details, root CI/tests and release/installer adapters, translated user interface resources for en/tr/de, and original app media/settings. Every new repository carries its own editable copy of required shared TIHULU code or a verified version-pinned independently available dependency (offline requirement must be tested). Source repo's old name is an alias, never the sole identity: pin original numeric repo ID and node ID, old source PR URL and original commit SHA; add verified current-alias/new-destination/reciprocal PR URLs in link maps. See `apps/SELF_CONTAINED_APP_PORTABILITY.md`, `apps/REPOSITORY_RENAME_LINK_POLICY.md`, `apps/TRILINGUAL_UI_POLICY.md` and `apps/_archives/PORTABLE_HISTORY_LINK_MAP.json`. Migration only after owner approval and parity gates; no forced feature changes.

## Complete provenance for copied and incomplete information

At task start read `apps/HISTORY_ORIGIN_FALLBACK_POLICY.md`, `apps/_archives/HISTORY_COVERAGE_AUDIT.json`, `apps/<app>/ORIGIN_FALLBACKS.json`, and `apps/<app>/APPROVED_BRANDING.json`. PR/Issue descriptions have origin links but comments, review submissions, review threads, CI events, missing branches and external ChatGPT requests are NOT yet completely exported. If an item cannot be transferred, preserve its old URL and GitHub repository ID 1447637221, plus an explicit remaining gap and reason. A future repo rename must update resolved aliases without erasing original URLs. Approved logos are separate PNG assets staged in the conversation package, not yet committed or installed in running apps. All engineering content remains English and every eventual app UI supports en/tr/de. Do not change any app code or installer during the documentation audit.

## Empty destination repositories already created by owner

The source migration checklist begins with real existing shells `Tihulu/tihulu-media-center` (GitHub ID 1454318539), `Tihulu/tihulu-satellite-center` (1454319572) and `Tihulu/tihulu-rf-geolocation-center` (1454320329). They were verified **empty** on 2026-11-11; no initial branch commit or source content has been verified. Before opening a new repo PR, first obtain explicit owner approval and create a safe initial commit (English readme/agent/origin pointer only) in that target. Use only the exact verified repository, not a proposed alias.

Do not confuse repository creation with a code cutover. Keep `apps/registry.json` canonical source on the old repo until full source/history/feature, independence, icon and locale checks pass. Original PRs, comment links and source GitHub numeric ID must remain immutable historical citations. Old source repository renaming is a separate post-cutover process.
