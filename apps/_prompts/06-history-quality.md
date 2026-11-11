# Shared instructions — all 6 parallel TIHULU LLM chats

You are auditing a MULTI-APP monorepo and preparing future framework-agnostic portability. Repo `Tihulu/TIHULU-TEXT-CENTER`. Start from `chore/llm-framework-portability-matrices-2026-11-11`, do not touch `main`, PR #65/#66/#67/#68 or another agent's branch. **No program feature, behavior, default, existing installer or application source code may be changed.** Only edit the files assigned to your workstream, on a uniquely named branch; open a separate Draft PR targeting the shared portability branch. **No merge/rebase/force push** unless explicitly approved.

At start read `AGENTS.md`, `apps/registry.json`, `apps/LLM_FRAMEWORK_PORTABILITY.md`, `apps/DESIGN_EXTENSIBILITY_POLICY.md`, `apps/PARITY_RELEASE_GATES.md`, `apps/_archives/pr-index.json`, app AGENTS/MODEL/FEATURE matrices and relevant existing application source tests. Your output: concrete feature IDs, exact file/branch/SHA source evidence, runnable read-only tests, model/backend fallback and limitations, unknowns, future extension points. Distinguish requirements vs code vs CI vs real device tests and legacy vs Draft-only features. Do not invent device readings, external PR comments, models installed, historical chats or completion ETA. Future implementations can be in Rust, Qt, GTK, Tauri, Flutter etc with full feature parity and optional redesign.

**Collaboration:** Own only the assigned path set. Report branch, Draft PR URL, changed files, original source SHA, CI status, unresolved questions and approximate completion percentage by checklist (not hours). If touching a shared path is necessary, record the requested change without editing it. Never overwrite other chat's files. If the base branch advances, coordinate the SHA and review a follow-on PR; do not silently rebase active work.

## Your unique task: Historical requests, review evidence and no-regression gates

**Owned paths:** `apps/_archives/**, apps/MIGRATION_PROTOCOL.md, tests/test_portability_contracts.py`

Audit PR metadata completeness, review/issue discussions, author/date/old URL evidence, decision ledger and GH history archiver; no invented ChatGPT history. Add read-only matrix validation and cutover acceptance tests. Do not mutate PRs or any existing program code.

Required deliverables: updated evidence-backed app matrix (or shared schema), exact compatibility checklist, unknown/missing evidence list, read-only tests if within owned paths, and Draft PR. Current source code, installers, settings and active application runtime remain unchanged. Do not move any repository or invent GitHub history.
