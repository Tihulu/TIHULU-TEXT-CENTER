# Coding-LLM development matrix (not an AI runtime model matrix)

This documents **how a programming assistant can develop TIHULU**, not which AI models are installed inside the programs. Machine-readable entry: DEVELOPMENT_AGENT_MATRIX.json. No new local LLM, CUDA, NPU, vector database, RAG service or cloud API is required to inspect it.

| Coding assistant | Entry | Loading / setup |
| --- | --- | --- |
| Claude Code | repository-root CLAUDE.md | Project instruction file in Claude Code; then read AGENTS.md and DEVELOPMENT_AGENT_GUIDE.md |
| DeepSeek | repository-root DEEPSEEK_START.md | Copy prompt or use a DeepSeek-enabled coding client with repo file access; auto-loading is **not assumed** |
| ChatGPT / other LLM agents | AGENTS.md + DEVELOPMENT_AGENT_GUIDE.md | Supply files or grant the coding client repository access; available tools depend on client |

Each app's FEATURE_MATRIX identifies behavior and tests, COMPONENT_MATRIX maps code to portable interfaces and example Rust modules, and MODEL_MATRIX documents in-app optional inference engines and fallbacks. Source and actual tests are authoritative; a matrix entry alone never proves a feature is implemented or hardware verified.

Agents may extend features, redesign the UI, or propose a Rust/other framework rewrite on separate review branches while preserving all existing features, defaults, data, captions and receiver ownership. Cross-application claims and merge/cutover require explicit authorization and evidence.

Six chat workstreams and disjoint file scopes: PARALLEL_CHAT_WORKSTREAMS.md. Honest progress by test-gate checklists, and ETA in hours/minutes **only when measured or otherwise reliable**.
