# TIHULU — developer LLM onboarding

This guide makes the source understandable to Claude Code, DeepSeek, ChatGPT and other coding agents. It is **documentation**, not an AI runtime, an agent server, a model manager or a reason to download an LLM.

## Two distinct matrices

- DEVELOPMENT_AGENT_MATRIX.json: agent-specific entrypoints, canonical repository, source roots and reading/editing workflow. Used by coding assistants.
- FEATURE_MATRIX.json: original feature IDs, behaviors, invariants and test locations. Used for no-regression development and design changes.
- COMPONENT_MATRIX.json: source module to portable interface mapping, including optional Rust module examples. No Rust implementation is implied.
- MODEL_MATRIX.json: optional application-internal Whisper, Qwen, Argos, NLLB, MADLAD, GPU/NPU or DSP backend evidence. It is NOT a model to install for the coding assistant. Installed and running states remain unknown unless separately checked.

All of these are ordinary JSON or Markdown files. They need no local Whisper, Qwen, DeepSeek, Claude, CUDA or cloud API simply to be read.

## Safe workflow

1. Check apps/registry.json and the current branch/commit. Flight Radar has its own canonical repo; do not edit its mirror as source.
2. Read AGENTS.md, this guide, the chosen app AGENTS.md, FEATURE_MATRIX.json, COMPONENT_MATRIX.json, MODEL_MATRIX.json and PORTING_GUIDE.md.
3. Look up a feature ID and portable component ID. Inspect actual code/tests, PR state, and original requests. Proposed mappings do not prove features are complete.
4. Propose changes on a separate branch. Allow complete visual redesign and any programming language (Rust included), but preserve all old actions, saved data, controls, source labels, accessibility and safe defaults.
5. Keep backend interfaces independent: media and RF receivers, subtitle timing, AI translation, model readiness, storage, export and UI. New features should be additive and opt-in where appropriate.
6. Run source-backed tests and the apps/PARITY_RELEASE_GATES.md checklist. Separate static CI, native compilation and physical hardware results.
7. Open Draft PR, document changed files, feature coverage, original-to-port mapping, test evidence, unresolved gaps and rollback. No auto merge or repo migration.

**No-feature-loss rule:** An existing app must remain usable as before. Do not invent measured decoder PTS, model installations or RF observations. Never overwrite user recordings or silently acquire a shared SDR. Preserve source transcription independently from lyric sync, sound labels and translation.

## Assistant entrypoints

Claude Code: repository CLAUDE.md plus AGENTS.md. Its published documentation supports CLAUDE.md as project instructions.

DeepSeek: DEEPSEEK_START.md is provider-neutral copy-paste context. Auto-reading behavior depends on the chosen DeepSeek editor/agent; do not promise it automatically recognizes this filename.

Other agents: point them to AGENTS.md and this file; repository browsing and write permissions are controlled by their clients, not by our matrix.

Six parallel coding chats: apps/PARALLEL_CHAT_WORKSTREAMS.md and apps/_prompts/. Separate branches, disjoint file ownership and reviewed Draft PRs. No shared chat context is assumed. GitHub PR descriptions do not equal a complete export of all chats.

Progress: use checklist stages. Do not invent remaining hours/minutes; unknown is the correct ETA when no reliable measurement exists.

## Self-contained future application repositories

Every application must have its own exact code snapshot and eventually complete dependency closure, offline-capable tests, build/installer, `AGENTS.md`, `CLAUDE.md`, `DEEPSEEK_START.md`, application/LLM matrices, PR/issue history ledger, and EN/TR/DE UI. Media Center has its own pinned Kaffeine Next source copy under `apps/media-center/source/kaffeine_next/` and shared code snapshots; use original root-level source as the active implementation until approved cutover. Read `apps/SELF_CONTAINED_APP_PORTABILITY.md`, `apps/REPOSITORY_RENAME_LINK_POLICY.md`, `apps/TRILINGUAL_UI_POLICY.md` and each app's portable package, history links and locale contract. Original historical URLs remain preserved if the monorepo is renamed. Do not claim a frozen copy is a standalone working release.
