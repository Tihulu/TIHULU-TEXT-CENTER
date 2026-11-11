# Six independent LLM workstreams

The user may run six separate ChatGPT conversations in parallel. This is a **manual coordination plan**, not an autonomous multi-agent scheduler. No other chat is launched by this document.

**Shared base branch:** `chore/llm-framework-portability-matrices-2026-11-11`. Give every chat a different `audit/<scope>-2026-11-11` branch and a separate Draft PR against the shared base. Do not have two chats edit one manifest or one test file. If this plan is merged, the coordinator adjusts base references in explicit review only.

| Chat | Owner file scope | Mission |
| --- | --- | --- |
| 1 | `apps/media-center/**` | Media Center feature and AI contract audit |
| 2 | `apps/satellite-center/**` | Satellite portability audit |
| 3 | `apps/geolocation-center/**` | Geolocation math and UI contract audit |
| 4 | `apps/text-center/** and apps/flight-radar/**` | Text Center + canonical Flight Radar boundaries |
| 5 | `apps/_schemas/**, apps/LLM_FRAMEWORK_PORTABILITY.md, apps/DESIGN_EXTENSIBILITY_POLICY.md, apps/PARITY_RELEASE_GATES.md` | Cross-framework porting and LLM model schema |
| 6 | `apps/_archives/**, apps/MIGRATION_PROTOCOL.md, tests/test_portability_contracts.py` | Historical requests, review evidence and no-regression gates |

Task prompts are under `apps/_prompts/`; paste `00-common.md` plus one mission prompt into a separate chat. Only the central coordinator reviews cross-application dependencies, source tree hash preservation, CI and final PR stacking. New framework ports are **later separate feature branches**, not part of these audits. No current repo migration is authorized.
