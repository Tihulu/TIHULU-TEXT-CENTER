# TIHULU TEXT CENTER — Engineering Instructions

**Language:** All user-facing UI copy, technical documentation, commit summaries and project collaboration should default to **English**.

**Architecture:** This repository is a standalone offline-first web application. Keep it independently runnable with Python 3.11+ and lightweight browser clients. An eventual Tihulu Survival Kit integration is optional and may only occur behind the Kit's authenticated local portal. Do not modify the Survival Kit or Flight Radar repositories from this one.

## Critical guarantees

1. Never invent received radio/TV data, current news, official warnings, frequency locks, decoder readiness, GNSS positions, or receiver metrics. Always distinguish published sources, cached internet, real decoder imports and authenticated official alerts.
2. Keep one-way TV Teletext and radio data separate from two-way BBS/packet/LoRa networks. No automatic RF transmission. Transmit integration requires different authorized hardware, relevant local rules, explicit user intent, and a separate security review.
3. Respect existing SDR/DVB tuner leases and protected recordings in an integration. Never silently retune a shared receiver, or delete original recordings while cleaning the text cache.
4. No background network/RF polling by default; no telemetry, invisible cloud LLM, or auto downloading large article/video archives. Use small, bounded owner-triggered operations.
5. Preserve source/provenance/observed timestamp/original text and show a clear unavailable/no data state rather than mocks claiming to be real signals.
6. Default HTTP server must remain loopback-only. A network-facing version needs validated TLS, session identity, per-owner isolation, CSRF, rate limits and tested gateway rules before deployment.
7. Preserve mobile/tablet/desktop keyboard and touch accessibility. Never insert untrusted feed/bulletin/import text via innerHTML; use textContent. Keep browser resource dependencies offline-capable.
8. Don't build an unrestricted HTTP proxy or fetcher for arbitrary untrusted network destinations. Existing feed support is explicit HTTPS, bounded and subject to network security restrictions.
9. Explain what is tested with mocks/unit tests vs verified on actual Raspberry Pi, TV tuner, Nooelec SDR, HF equipment or LoRa devices. No hardware acceptance has been completed here.

## Testing

Run: \`python3 -m unittest discover -s tests -v\`, \`python3 -m compileall -q textcenter tests\`, and \`node --check web/app.js\`.

No backend external Python dependencies are required for the initial version. Keep API and record formats documented in \`docs/DATA_FORMAT.md\` and integration boundaries in \`docs/SURVIVAL_KIT_INTEGRATION.md\`.

## Flight Radar — mandatory mirrored Pages contract

Flight Radar is **owned by** `Tihulu/tihulu-flight-radar`, not by TEXT CENTER. This repository contains a **built, read-only mirror** of its browser app at `gh-pages/flight_radar/`. Do not maintain a separate Flight Radar implementation here.

Every Flight Radar browser update must appear at **both**:
- https://tihulu.github.io/tihulu-flight-radar/ (standalone original repo)
- https://tihulu.github.io/TIHULU-TEXT-CENTER/flight_radar/ (TEXT CENTER mirror)

Read `docs/FLIGHT_RADAR_DUAL_PAGES.md` and the canonical Flight Radar repository's `AGENTS.md` before working on Flight Radar or its application links. The managed sync workflow `.github/workflows/sync-flight-radar-pages.yml` follows canonical branch `feature/github-pages-local-bridge-2026-11-06` until PR #6 merges. It polls every 15 minutes and supports manual dispatch; no second source of browser JavaScript is permitted. The website's `source-revision.json` must match the standalone publication's `source_sha`.

Future coding agents: never consider a Flight Radar change delivered if only the TEXT CENTER site or only the standalone site is updated. Preserve other TEXT CENTER Pages, especially Satellite, RF Geolocation and Radio Center, and do not merge unrelated project code. Note if the standalone repo has not yet enabled GitHub Pages under Settings → Pages → Source: GitHub Actions; a passing build does not guarantee a live site.


## Portable multi-app development handoff (future repositories)

Before changing Media Center, Satellite Center, RF Geolocation, Text Center, or the Flight Radar mirror, read `apps/registry.json` and the relevant `apps/<app-id>/AGENTS.md`. The `apps/` directories contain metadata **plus byte-for-byte, read-only frozen source snapshots** under `apps/<app>/source/` for the four embedded apps. These snapshots are NOT active import/build/installer paths; do NOT edit or run them as the current app, and do not change existing code/import/install paths. Flight Radar remains canonical in its own external repo.

If the app status is `embedded`, canonical code remains in the explicitly listed source roots of this repository. If and ONLY if the app was explicitly migrated and the registry records `external_canonical` with an actual target URL and verified cutover, never develop that app here; open the target repo and follow its root AGENTS.md, archive map and decision history. Flight Radar is already externally canonical; TEXT CENTER is only its built mirror.

Before any migration, archive and audit original issue/PR descriptions, comments, code review decisions, authors/timestamps, SHA ancestry, source-backed model matrices and owner requirements. A recreated PR does not inherit GitHub approvals or original numbers. See `apps/MIGRATION_PROTOCOL.md`. Do not manufacture historical comments, model capability or source verification. No application move or cross-repo retargeting is authorized by these files alone.

## All-app source independence, rename stability and localization

Every embedded application has its own pinned read-only source tree copies; Media Center includes `kaffeine_next/`, `tv_center/` and its own copied `textcenter/` dependency. The original source paths and all existing application features are unchanged. Read `apps/SELF_CONTAINED_APP_PORTABILITY.md`, `apps/REPOSITORY_RENAME_LINK_POLICY.md`, `apps/_archives/PORTABLE_HISTORY_LINK_MAP.json`, `apps/DEVELOPMENT_AGENT_MATRIX.json` and each app's `PORTABLE_PACKAGE.json`, `HISTORY_LINKS.json`, `LOCALIZATION_CONTRACT.json`. Repo renaming is planned only, never executed without owner approval. Preserve old PR URLs and original comments/reviews with provenance; link them to new PRs via verified bidirectional map after eventual migration. Engineering internals, documentation and code comments are English; target UI languages for every future independent app are English, Turkish and German. Do not imply translations are implemented yet. No extra coding LLM is required to read static JSON/Markdown.

## Complete provenance for copied and incomplete information

At task start read `apps/HISTORY_ORIGIN_FALLBACK_POLICY.md`, `apps/_archives/HISTORY_COVERAGE_AUDIT.json`, `apps/<app>/ORIGIN_FALLBACKS.json`, and `apps/<app>/APPROVED_BRANDING.json`. PR/Issue descriptions have origin links but comments, review submissions, review threads, CI events, missing branches and external ChatGPT requests are NOT yet completely exported. If an item cannot be transferred, preserve its old URL and GitHub repository ID 1447637221, plus an explicit remaining gap and reason. A future repo rename must update resolved aliases without erasing original URLs. Approved logos are separate PNG assets staged in the conversation package, not yet committed or installed in running apps. All engineering content remains English and every eventual app UI supports en/tr/de. Do not change any app code or installer during the documentation audit.

## Destination repository verification and approved logo identity (2026-11-11)

Three app destination shells are now confirmed: `Tihulu/tihulu-media-center`, `Tihulu/tihulu-satellite-center`, `Tihulu/tihulu-rf-geolocation-center`. All were empty on verification. Read `apps/VERIFIED_DESTINATION_REPOSITORIES.json` for immutable GitHub IDs and status before planning any migration. Their creation does NOT make them canonical. Text Center has no chosen separate destination and Flight Radar is already independent.

Brand identity is strictly the **same previously generated and user-approved red/black/white TIHULU mascot badges** documented with SHA256 in `apps/BRANDING_APPROVED_MANIFEST.json`. Do not use newly searched or substitute logos; never claim PNGs are genuine SVG vectors. Approved binaries are not committed to these app repos and none of the existing runtime icons are changed. Continue to preserve original PR/issue origins, partial transfer gaps, model/component/feature matrices and English development with EN/TR/DE UI.
