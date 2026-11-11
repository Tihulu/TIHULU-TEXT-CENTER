# Claude Code — TIHULU project instructions

Read AGENTS.md, DEVELOPMENT_AGENT_GUIDE.md and apps/DEVELOPMENT_AGENT_MATRIX.json before editing. Read apps/registry.json to identify the canonical repo, then the selected application's AGENTS.md, FEATURE_MATRIX.json, COMPONENT_MATRIX.json and MODEL_MATRIX.json.

These are documentation files for coding agents. No extra LLM, inference weights or GPU is required to read them. MODEL_MATRIX describes optional application-internal AI engines; DEVELOPMENT_AGENT_MATRIX describes how Claude Code and other coding assistants develop the program.

Preserve every original feature, setting, default, device lease, subtitle timing and saved recording. Only change application source in a separately approved feature task and preview branch. Porting to Rust or another framework and redesigning the interface are welcome after feature-by-feature parity checks. Never silently merge Draft PRs, repoint installers, move repositories or claim real hardware verification without tests.

Keep this root file concise; AGENTS.md and the app contracts remain the detailed source of truth.

Every app is intended to become a self-contained independent repo, with stable GitHub repo-ID/alias links and original PR provenance; read `apps/SELF_CONTAINED_APP_PORTABILITY.md` and each app's `PORTABLE_PACKAGE.json`, `HISTORY_LINKS.json`, `LOCALIZATION_CONTRACT.json`. Current `apps/<app>/source/` folders are frozen copies, not active code. English developer workflow, EN/TR/DE user interface target; do not alter current app features or pretend localization is complete.
