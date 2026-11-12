# TIHULU Cross-Repository Engineering Coordination (English only)

This is a **read-only planning and audit phase**, not a release, integration, repo migration or permission to change existing behavior. The owner has explicitly requested **no changes to any existing application's features, defaults, installers, configuration, saved data, user interface or device lifecycle** while this audit is in progress. All technical operations, docs, issue/PR bodies, commit summaries, code comments and coding-agent prompts are English. Every application must eventually expose user-interface strings in **English (default), Turkish and German**. Discuss with the owner in Turkish if requested; never make Turkish the repo engineering language.

## Five actual canonical application sources

| App | Current canonical source | Approved final source | Status |
|---|---|---|---|
| Media Center | Tihulu/TIHULU-TEXT-CENTER | Tihulu/tihulu-media-center | destination user-created EMPTY; pending cutover |
| Satellite Center | Tihulu/TIHULU-TEXT-CENTER | Tihulu/tihulu-satellite-center | destination user-created EMPTY; pending cutover |
| RF Geolocation Center | Tihulu/TIHULU-TEXT-CENTER | Tihulu/tihulu-rf-geolocation-center | destination user-created EMPTY; pending cutover |
| Text Center | Tihulu/TIHULU-TEXT-CENTER | same repository (GitHub ID 1447637221) | RETAINED and actively maintained |
| Flight Radar | Tihulu/tihulu-flight-radar | same separately canonical repository | RETAINED, no source fork |

A repo rename of the original Text Center is a separate, post-audit owner-authorized operation that must preserve original PR/Issue provenance, repo ID, working installers, GitHub Pages URLs, PWA scope, static paths, Flight Radar mirror and verified redirects. A GitHub repository rename does not inherently redirect GitHub Pages project URLs. Never perform one here.

## Source of truth and work rules

1. Read `apps/_coordination/MASTER_REQUIREMENTS.json`, `apps/_coordination/PROGRESS.json`, `apps/CANONICAL_REPOSITORY_TOPOLOGY.json`, `apps/registry.json`, `apps/HISTORY_ORIGIN_FALLBACK_POLICY.md`, `apps/_archives/HISTORY_COVERAGE_AUDIT.json`, each app's FEATURE/COMPONENT/MODEL/ORIGIN_FALLBACKS matrices and project `AGENTS.md`. Read canonical Flight Radar's AGENTS.md as well.
2. The initial requirements inventory is **NOT complete proof**; reconcile all original conversations, prior GitHub Issues/PRs and original source code before claiming full coverage.
3. **No modifications** to app runtime source, `main`, model weights, compiled/installed programs, UI assets, native icons, firmware, releases, packaging scripts, service configuration or user files during this phase.
4. All proposed work is in an app/scope-specific branch, based on coordinator-advertised frozen audit base `chore/master-requirements-zero-regression-coordination-2026-11-11` after it exists, then Draft PR. Never force-push a shared branch, merge, close someone else's Issue or rewrite old PR review approvals.
5. Do not create the first commit in the user's three EMPTY destination repositories without **a separate owner approval**. Audits target original source/standalone Flight Radar appropriate branch only.
6. No shared-file collisions. Each worker owns `apps/_coordination/workstreams/<NN>/**` (reports) and its assigned issue discussion; only coordinator edits master requirements, progress and canonical maps. Workers may propose app-level matrix changes in their PRs, but may not edit global files.
7. To request a change owned by a different worker, **comment on that worker's GitHub Issue** with Requirement ID, evidence URL, proposed tests and exact dependency. Do not edit their files. For cross-repo dependency, comment on the central coordination Issue and link a follow-up Issue in the affected repo if authorized. GitHub Issues/PR comments, not unseen ChatGPT histories, are the inter-agent message bus.
8. Each worker reports `requested / draft-coded / unit-verified / hardware-verified / released` separately and uses source SHAs, evidence URLs and explicit blockers. A source directory or clean CI run is not an installed hardware validation.
9. Each output must preserve historical PR URLs, original author/time and GitHub repository numeric IDs; items that cannot be exported become explicit `TRANSFER_GAPS.json` with a verified pointer or marked unavailable source. DO NOT push private chat text, secret tokens, unique serials, pairing tokens or personal locations into public repos.
10. Do not change Flight Radar's `legacy/v0.3.1` reference or merge open Draft PR #7 or #13; do not merge original Text Center PRs #65–#74 without explicit approval and conflict/regression checks. Protect Text Center's active `textcenter/` and `web/` when other apps eventually cut over.
11. The exact **five already-approved red/black/white TIHULU mascot logo PNG designs**, tracked by SHA256 in `apps/BRANDING_APPROVED_MANIFEST.json`, are the only approved artwork. No new searched stock/replacement logos. They are PNG, **not genuine editable SVG**, and no runtime icon changes are authorized yet.
12. Progress and ETA are evidence-based: record measured counts and explicit incomplete checks; remaining hours and minutes are `null` until worker estimates include audited task counts and written assumptions. Never fabricate a countdown or claim asynchronous task completion.

## Coordination message template (GitHub Issue comment)

```md
### Handoff — REQ-ID
**Owner workstream:** <01..06>
**Issue / PR:** <full GitHub URLs>
**Original source:** <repo ID + URL + commit SHA, if known>
**Implementation state:** requested | draft-coded | CI-verified | hardware-verified | released | unknown
**Changes proposed:** <documentation/audit only until owner approval>
**Feature invariants:** <what cannot change>
**Requested cross-team action:** <file/requirement/test and reason>
**Tests executed:** <exact commands/results or NOT RUN>
**Blocked by:** <specific dependency or missing evidence>
**Minutes/hours remaining:** unknown until scoped and measured
```

## Acceptance / stop conditions

- Every app has its actual repo ID and active source roots mapped.
- Every requirement is connected to a verified source (or marked source-unverified), code evidence, test and original issue/PR link.
- A passing CI check never overrides missing physical RF/TV/SDR/device validation.
- Missing historical comments or broken renamed links block a claim of complete migration, not necessarily the status of a documentation-only audit.
- No feature, subtitle timing, source selection, device hard-stop, data preservation, or native installer changes in this coordination phase.
- Before future code changes, obtain **specific user approval**, create independent reviewed feature PRs and design per-feature rollback and comparison tests.
