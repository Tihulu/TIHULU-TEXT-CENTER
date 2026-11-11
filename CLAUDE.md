# Claude Code — TIHULU project instructions

Read AGENTS.md, DEVELOPMENT_AGENT_GUIDE.md and apps/DEVELOPMENT_AGENT_MATRIX.json before editing. Read apps/registry.json to identify the canonical repo, then the selected application's AGENTS.md, FEATURE_MATRIX.json, COMPONENT_MATRIX.json and MODEL_MATRIX.json.

These are documentation files for coding agents. No extra LLM, inference weights or GPU is required to read them. MODEL_MATRIX describes optional application-internal AI engines; DEVELOPMENT_AGENT_MATRIX describes how Claude Code and other coding assistants develop the program.

Preserve every original feature, setting, default, device lease, subtitle timing and saved recording. Only change application source in a separately approved feature task and preview branch. Porting to Rust or another framework and redesigning the interface are welcome after feature-by-feature parity checks. Never silently merge Draft PRs, repoint installers, move repositories or claim real hardware verification without tests.

Keep this root file concise; AGENTS.md and the app contracts remain the detailed source of truth.
