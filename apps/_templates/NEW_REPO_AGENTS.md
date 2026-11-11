# Canonical development handoff — template for new repository

> This file is installed only AFTER explicit relocation approval and a verified cutover. Do not apply it early.

You are working in the **canonical active repository** for this TIHULU application. The old `Tihulu/TIHULU-TEXT-CENTER` repository contains **historic, read-only application code** for this moved component and an authoritative old-to-new pointer. Read `migration/origin.json`, `migration/PR_MAP.json`, `history/decisions.md`, `history/requests.jsonl` and `models/MATRIX.md` before coding. Only create new application commits and pull requests HERE; do not develop divergent code in the old repo.

Preserve all user-visible features, existing settings, hardware ownership/stop behavior, tested file/signal timing and model selection. A preserved historical review approval is **not** a new GitHub approval. Never fabricate copied review authors/dates or model readiness. All tests and actual device verification required before release. If the transfer status is ambiguous, stop and read canonical `apps/registry.json` in the source repo; never guess.
