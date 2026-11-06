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
