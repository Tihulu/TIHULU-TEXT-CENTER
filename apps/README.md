# Portable TIHULU app workspaces

**Migration status:** NO applications have been moved. Each embedded app now has an **exact, read-only source snapshot** under `apps/<app>/source/` together with metadata; Flight Radar remains external-canonical. These are not active source/import/installer paths. Existing application behavior and main are untouched; standalone build and dependency closure are not yet verified. A future split needs explicit user authorization.

| App | Source paths today | Current canonical code |
| --- | --- | --- |
| TIHULU Media Center | `kaffeine_next/`, `tv_center/` | `Tihulu/TIHULU-TEXT-CENTER` |
| TIHULU Satellite Center | `satellite_center/` | `Tihulu/TIHULU-TEXT-CENTER` |
| TIHULU RF Geolocation Center | `rf_geolocation_center/` | `Tihulu/TIHULU-TEXT-CENTER` |
| TIHULU Text Center | `textcenter/`, `web/` | `Tihulu/TIHULU-TEXT-CENTER` |
| TIHULU Flight Radar | external repository | `Tihulu/tihulu-flight-radar` |

Read `registry.json` for machine-readable canonical status, then the application's `AGENTS.md`. Read `_archives/README.md` for the historic record and freshness limits.

**Rule:** Do not edit or execute copied sources under `apps/<app>/source/` as the active application; they are exact frozen preservation snapshots. Edit only the current canonical source roots until explicit cutover, and refresh snapshots via verified SHA equality. In the future, each new repo receives its own editable copy. Preserve code and every external/shared dependency, PRs/issues and source author/date, model/component/feature matrices, original PR URLs, multilingual UI requirements and exact commit/tree provenance.

## Coding-LLM onboarding: not the application model catalog

Read repo-root DEVELOPMENT_AGENT_GUIDE.md and apps/DEVELOPMENT_AGENT_MATRIX.json for Claude Code, DeepSeek, ChatGPT or other coding assistants. Root CLAUDE.md is a Claude Code-friendly entry point; DEEPSEEK_START.md is a manual/coding-client prompt (automatic loading is **not** assumed). These are **plain documentation**; no additional model, GPU/NPU or cloud provider is needed to read them. The per-app MODEL_MATRIX.json instead documents optional inference models **inside** the application.

## Cross-repo independence, rename, history and UI languages

Read `SELF_CONTAINED_APP_PORTABILITY.md`, `REPOSITORY_RENAME_LINK_POLICY.md`, `TRILINGUAL_UI_POLICY.md`, `REPOSITORY_IDENTITY.json`, each app's `PORTABLE_PACKAGE.json`, `SOURCE_SNAPSHOT.md`, `HISTORY_LINKS.json`, `LOCALIZATION_CONTRACT.json`, and `_archives/PORTABLE_HISTORY_LINK_MAP.json`. Engineering is English, UI target is English/Turkish/German. No repository rename, code move or UI translation has happened yet.
