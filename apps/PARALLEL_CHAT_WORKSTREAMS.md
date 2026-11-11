# Six independent LLM workstreams

The user may run six separate ChatGPT conversations in parallel. This is a **manual coordination plan**, not an autonomous multi-agent scheduler. No other chat is launched by this document.

**Shared base branch:** `chore/portable-self-contained-apps-rename-links-i18n-2026-11-11`. Give every chat a different `audit/<scope>-2026-11-11` branch and a separate Draft PR against the shared base. Do not have two chats edit one manifest or one test file. If this plan is merged, the coordinator adjusts base references in explicit review only.

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

All six agents must start from the updated source-copy and provenance branch `chore/portable-self-contained-apps-rename-links-i18n-2026-11-11`, not from #69 alone. Verify latest commit SHA against the GitHub branch reference before branching. Worker 1 audits Media Center's own `kaffeine_next` + `tv_center` + `textcenter` copies; Worker 2 Satellite; Worker 3 Geolocation; Worker 4 Text and separately canonical Flight Radar; Worker 5 global independent-repo contracts and EN/TR/DE UI; Worker 6 global original/new PR links and old-repo rename. Edit only assigned **metadata**, not frozen `source/` copies or active app code. If multiple workers need a shared path, central coordination owns it. Draft PRs only. No repo cutover or rename authorized by these prompts.
