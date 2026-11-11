# Future GitHub repository rename and immutable history policy

**No repository has been renamed by this plan.** The name `Tihulu/TIHULU-TEXT-CENTER` is a historical alias and current observed owner/name, not a permanent identity that must appear in compiled binaries or new installers.

## Stable reference chain
1. `apps/REPOSITORY_IDENTITY.json` stores original GitHub repository numeric `id` **1447637221** and `node_id` **R_kgDOVkkw5Q** plus observed aliases. When a rename is approved, read current GitHub repo metadata, update `current_repository_full_name`, append aliases, never delete original.
2. Use repository-relative paths for new coding-agent instructions, matrices, test paths and sources; use versioned module/import names for **application identity**, not a dependency on GitHub display name. Do not change runtime import or install URLs as part of this metadata PR.
3. Store immutable historical PR and issue source IDs/numbers/URLs and source head/base commit SHAs under `apps/_archives/PORTABLE_HISTORY_LINK_MAP.json`. Preserve the original HTML URLs *literally*. After renaming, also record a resolved current canonical URL and check each redirect; do not assume every Pages/Pages assets/raw GitHub/installer link transparently follows the redirect.
4. Once app repos exist, add `migration/origin.json`, `migration/PR_MAP.json` and the full portable ledger in new repos. Link old PR #n / review thread / source issue to newly created issue/PR #m, with **two-way pointers** if permissions permit. Never represent copied comments or approvals as native originals.
5. Audit GitHub Pages base URLs, PWA scopes, service workers, CORS/callbacks, OAuth/docs badges, install scripts, user desktop launchers, dependency URLs, code-signing/packaging metadata, CI workflow paths, raw.githubusercontent.com and hardcoded repo identifiers before actual rename.
6. If an app's new canonical repository is already active, a rename of the **old** monorepo must not change its future PR target or make the old mirror writable. Source repo rename is independent of app repo cutover.
7. Execute renames only after explicit approval and final link/installer/access/CI tests. Never rename mid-port, rewrite original historic citations, force-push, or delete source branches to make links appear tidy.

## Link lifecycle
`original_only_not_migrated` -> `exported_historical_evidence` -> `target_pr_created_pending_crosslink` -> `bidirectional_link_verified`; independent `broken_redirect_requires_alias_fix` and `cannot_recreate_native_review` states. A link map should record both the old and current resolved URL, test time and HTTP status from a real check. Unknown remains `not_checked`.

## Reference safety
The original repository numeric ID is a continuity anchor within GitHub. A repository move/rename may still require privilege changes and link repair; the numeric ID is not a magic replacement for web URLs, independent archives or correct Git remote settings.

## Existing destination identity anchors

Confirmed future independent repos: Media Center ID `1454318539`, Satellite Center ID `1454319572`, RF Geolocation Center ID `1454320329`. These IDs must accompany original GitHub URLs, destination aliases and eventual canonical PR links. Repos are currently empty; their **existence does not change the source repo** or permit renaming the original. Do not rely on GitHub redirects alone; keep exported evidence and test paths after any future rename.

## Text Center retained on same GitHub numeric repository ID

Any approved future rename of repository ID `1447637221` changes only its name/URLs, not the Text Center app's repository identity. Keep the active `textcenter/` and `web/` code, its Pages and installers, historical PRs and central origin-gap ledgers in that **same** repo. Verify installation links, raw assets, PWA scope and old URL redirects before renaming. The three new app repos use their own linked original PR/Issue evidence; they must not depend on a fixed old repo display name.
