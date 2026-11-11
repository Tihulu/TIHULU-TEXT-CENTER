# Shared instructions — all 6 parallel TIHULU LLM chats

You are auditing a MULTI-APP monorepo and preparing future framework-agnostic portability. Repo `Tihulu/TIHULU-TEXT-CENTER`. Start from `chore/llm-framework-portability-matrices-2026-11-11`, do not touch `main`, PR #65/#66/#67/#68 or another agent's branch. **No program feature, behavior, default, existing installer or application source code may be changed.** Only edit the files assigned to your workstream, on a uniquely named branch; open a separate Draft PR targeting the shared portability branch. **No merge/rebase/force push** unless explicitly approved.

At start read `AGENTS.md`, `apps/registry.json`, `apps/LLM_FRAMEWORK_PORTABILITY.md`, `apps/DESIGN_EXTENSIBILITY_POLICY.md`, `apps/PARITY_RELEASE_GATES.md`, `apps/_archives/pr-index.json`, app AGENTS/MODEL/FEATURE matrices and relevant existing application source tests. Your output: concrete feature IDs, exact file/branch/SHA source evidence, runnable read-only tests, model/backend fallback and limitations, unknowns, future extension points. Distinguish requirements vs code vs CI vs real device tests and legacy vs Draft-only features. Do not invent device readings, external PR comments, models installed, historical chats or completion ETA. Future implementations can be in Rust, Qt, GTK, Tauri, Flutter etc with full feature parity and optional redesign.

**Collaboration:** Own only the assigned path set. Report branch, Draft PR URL, changed files, original source SHA, CI status, unresolved questions and approximate completion percentage by checklist (not hours). If touching a shared path is necessary, record the requested change without editing it. Never overwrite other chat's files. If the base branch advances, coordinate the SHA and review a follow-on PR; do not silently rebase active work.

## Your unique task: Geolocation math and UI contract audit

**Owned paths:** `apps/geolocation-center/**`

Map evidence sources, PSF/Gaussian/circles, live/best fit, GNSS/NMEA, on-demand RF role and location privacy. Separate mathematical core, hardware interface and map UI. Distinguish implemented features from requested ones and never invent RF accuracy.

Required deliverables: updated evidence-backed app matrix (or shared schema), exact compatibility checklist, unknown/missing evidence list, read-only tests if within owned paths, and Draft PR. Current source code, installers, settings and active application runtime remain unchanged. Do not move any repository or invent GitHub history.

## Coding-agent development context (updated)

Read repo-root DEVELOPMENT_AGENT_GUIDE.md and apps/DEVELOPMENT_AGENT_MATRIX.json before work. These files guide Claude Code, DeepSeek and other coding LLMs; do **not** install or run extra models just to read them. The app MODEL_MATRIX covers optional **in-application** speech/translation/alignment engines, while FEATURE_MATRIX and COMPONENT_MATRIX cover safe extension, redesign and Rust/other-framework porting. Continue to use only your assigned file scope and Draft PR.
