# Portable TIHULU app workspaces

**Migration status:** NO applications have been moved. These are *metadata-only* app ownership folders. Existing source paths and launchers are untouched. A future split needs explicit user authorization.

| App | Source paths today | Current canonical code |
| --- | --- | --- |
| TIHULU Media Center | `kaffeine_next/`, `tv_center/` | `Tihulu/TIHULU-TEXT-CENTER` |
| TIHULU Satellite Center | `satellite_center/` | `Tihulu/TIHULU-TEXT-CENTER` |
| TIHULU RF Geolocation Center | `rf_geolocation_center/` | `Tihulu/TIHULU-TEXT-CENTER` |
| TIHULU Text Center | `textcenter/`, `web/` | `Tihulu/TIHULU-TEXT-CENTER` |
| TIHULU Flight Radar | external repository | `Tihulu/tihulu-flight-radar` |

Read `registry.json` for machine-readable canonical status, then the application's `AGENTS.md`. Read `_archives/README.md` for the historic record and freshness limits.

**Rule:** Do not edit code through `apps/`; these directories are only a portable development-memory package and future repo handoff. Avoid duplicating application sources. Before a migration, preserve prior PRs, issues, independent original author/timestamps, model selection evidence, test matrix and exact commit/tree provenance.
