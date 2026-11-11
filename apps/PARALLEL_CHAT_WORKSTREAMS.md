# Six independent LLM workstreams

The user may run six separate ChatGPT conversations in parallel. This is a **manual coordination plan**, not an autonomous multi-agent scheduler. No other chat is launched by this document.

**Shared base branch:** `chore/register-user-created-app-repos-and-approved-red-logos-2026-11-11`. Give every chat a different `audit/<scope>-2026-11-11` branch and a separate Draft PR against the shared base. Do not have two chats edit one manifest or one test file. If this plan is merged, the coordinator adjusts base references in explicit review only.

| Chat | Owner file scope | Mission |
| --- | --- | --- |
| 1 | `apps/media-center/**` | Media Center feature and AI contract audit |
| 2 | `apps/satellite-center/**` | Satellite portability audit |
| 3 | `apps/geolocation-center/**` | Geolocation math and UI contract audit |
| 4 | `apps/text-center/** and apps/flight-radar/**` | Text Center + canonical Flight Radar boundaries |
| 5 | `apps/_schemas/**, apps/LLM_FRAMEWORK_PORTABILITY.md, apps/DESIGN_EXTENSIBILITY_POLICY.md, apps/PARITY_RELEASE_GATES.md` | Cross-framework porting and LLM model schema |
| 6 | `apps/_archives/**, apps/MIGRATION_PROTOCOL.md, tests/test_portability_contracts.py` | Historical requests, review evidence and no-regression gates |

Task prompts are under `apps/_prompts/`; paste `00-common.md` plus one mission prompt into a separate chat. Only the central coordinator reviews cross-application dependencies, source tree hash preservation, CI and final PR stacking. New framework ports are **later separate feature branches**, not part of these audits. No current repo migration is authorized.

## Updated entrypoint for each coding agent

Read root DEVELOPMENT_AGENT_GUIDE.md, apps/DEVELOPMENT_AGENT_MATRIX.json, and this workstream's app FEATURE_MATRIX.json, COMPONENT_MATRIX.json and MODEL_MATRIX.json. Coding LLM onboarding is **documentation only**. Runtime AI engines in MODEL_MATRIX are a separate inventory. Claude Code can start via CLAUDE.md. DeepSeek may start with DEEPSEEK_START.md pasted into a supported editor/chat; never assume automatic discovery. Each of the six independent chats uses its own file ownership and Draft PR. No new model installation or repository move is part of this work.

## Extended scope for every audit worker

All six assignments now inspect read-only per-app source snapshots, local dependency closure, the future monorepo rename alias/identity ledger and each app's old-to-new history links. Every future independent repo must include the same feature/component/LLM model/coding-agent matrices, own source and dependencies, plus EN/TR/DE **UI** localization contracts; engineering remains English. The snapshot paths under `apps/<app>/source/` are evidence only. Workers must **not edit copies or actual app source** in these documentation audits. If an app code root or external dependency is missing, report it rather than changing live code. Coordination owns shared global documents and PR link maps; never have two chats edit them concurrently.

## Critical six-chat handoff — current pinned source bundle

All six agents must start from the updated source-copy and provenance branch `chore/register-user-created-app-repos-and-approved-red-logos-2026-11-11`, not from #69 alone. Verify latest commit SHA against the GitHub branch reference before branching. Worker 1 audits Media Center's own `kaffeine_next` + `tv_center` + `textcenter` copies; Worker 2 Satellite; Worker 3 Geolocation; Worker 4 Text and separately canonical Flight Radar; Worker 5 global independent-repo contracts and EN/TR/DE UI; Worker 6 global original/new PR links and old-repo rename. Edit only assigned **metadata**, not frozen `source/` copies or active app code. If multiple workers need a shared path, central coordination owns it. Draft PRs only. No repo cutover or rename authorized by these prompts.

## Division of history and brand review

All six chats start from the updated `chore/register-user-created-app-repos-and-approved-red-logos-2026-11-11` branch. Each application chat audits its own `ORIGIN_FALLBACKS.json`, existing source/feature mappings, and approved logo installation risks. Worker 5 analyzes genuine SVG generation and platform icon integration plus EN/TR/DE tests; Worker 6 handles source PR/comment coverage, repo rename aliases and original/new bidirectional link audit. Global ledgers and brand manifest are coordinator-owned; none of the workers alter frozen app source copies, current icons or installers. Every worker opens its own Draft PR, not a merge.

## Complete provenance for copied and incomplete information

At task start read `apps/HISTORY_ORIGIN_FALLBACK_POLICY.md`, `apps/_archives/HISTORY_COVERAGE_AUDIT.json`, `apps/<app>/ORIGIN_FALLBACKS.json`, and `apps/<app>/APPROVED_BRANDING.json`. PR/Issue descriptions have origin links but comments, review submissions, review threads, CI events, missing branches and external ChatGPT requests are NOT yet completely exported. If an item cannot be transferred, preserve its old URL and GitHub repository ID 1447637221, plus an explicit remaining gap and reason. A future repo rename must update resolved aliases without erasing original URLs. Approved logos are separate PNG assets staged in the conversation package, not yet committed or installed in running apps. All engineering content remains English and every eventual app UI supports en/tr/de. Do not change any app code or installer during the documentation audit.

## Three verified empty repositories — no direct edits by audit workers

All six audit chats should use `chore/register-user-created-app-repos-and-approved-red-logos-2026-11-11` as the shared base for documentation-only analysis. The three confirmed destination repo IDs, statuses, and exact names are recorded in `apps/VERIFIED_DESTINATION_REPOSITORIES.json`. These repos are **empty** and must not be independently initialized, populated or repointed by parallel workers during the current audit. Worker 1 maps Media Center to `tihulu-media-center`, Worker 2 Satellite to `tihulu-satellite-center`, Worker 3 Geolocation to `tihulu-rf-geolocation-center`; Worker 4 retains Text Center destination as undecided and Flight Radar as already independent; Worker 5 tracks only the exact five approved red TIHULU badge PNGs and vector/UI validation; Worker 6 audits historical review/PR/issue links and repository ID aliases. All workers use English PRs/technical documentation and preserve current source/behavior. Central coordinator alone edits shared registry, logo manifest and destination map.
