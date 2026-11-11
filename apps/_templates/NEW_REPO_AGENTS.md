# Canonical development handoff — template for new repository

> This file is installed only AFTER explicit relocation approval and a verified cutover. Do not apply it early.

You are working in the **canonical active repository** for this TIHULU application. The old `Tihulu/TIHULU-TEXT-CENTER` repository contains **historic, read-only application code** for this moved component and an authoritative old-to-new pointer. Read `migration/origin.json`, `migration/PR_MAP.json`, `history/decisions.md`, `history/requests.jsonl` and `models/MATRIX.md` before coding. Only create new application commits and pull requests HERE; do not develop divergent code in the old repo.

Preserve all user-visible features, existing settings, hardware ownership/stop behavior, tested file/signal timing and model selection. A preserved historical review approval is **not** a new GitHub approval. Never fabricate copied review authors/dates or model readiness. All tests and actual device verification required before release. If the transfer status is ambiguous, stop and read canonical `apps/registry.json` in the source repo; never guess.

## Portability and UI extension contract

A maintainer may implement this application in any suitable language/framework
(e.g., Rust) or change the entire visual design, provided every existing
`features/FEATURE_MATRIX.json` behavior and data/settings contract is checked
against the old release and reviewed. The `models/MODEL_MATRIX.json` is an
installed-vs-available-vs-running evidence index, never proof that model weights
are installed or a real SDR/DVB device has been tested. Add new features through
explicitly safe, preferably opt-in extension points. Never delete a feature or
silently alter defaults to accommodate a rewrite. See the original repo's
`apps/LLM_FRAMEWORK_PORTABILITY.md`, `apps/DESIGN_EXTENSIBILITY_POLICY.md`,
`apps/PARITY_RELEASE_GATES.md`. Prior PR comments, user request evidence and
original author/time are kept in history with provenance; do not forge fresh
GitHub approvals.
