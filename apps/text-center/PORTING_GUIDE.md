# text-center — framework-port and extension guide

This application is **not moved**; source ownership is defined in `apps/registry.json`. No existing source path is rewritten here.

1. Use stable feature IDs from `FEATURE_MATRIX.json` as a mapping contract; do **not** depend on C++/Qt/JS/Python as permanent design.
2. Use `MODEL_MATRIX.json` only as an evidence-backed capability/engine inventory, not proof of local installation. Preserve original/default/fallback behavior when replacing the engine.
3. Use adapters/interfaces for hardware, AI inference, media encoding, storage and network. Do not silently open SDR/DVB, change ownership or enable background polling.
4. Move presentation into replaceable UI/view modules. Theme/layout may change freely *in isolated proposed builds* when all actions and accessibility remain discoverable.
5. Compare original and port with automated parity tests and real hardware tests where required. Preserve original recordings, playlists/settings/models; don't overwrite or delete.
6. Add features via documented extension points with opt-in defaults and migration paths. Write down user requests, decisions, test results and exact source PR links.
7. Keep original repository authoritative until verified migration and explicit `apps/registry.json` cutover. Then new repo root AGENTS.md explicitly routes all further work to the new repo.

See `apps/LLM_FRAMEWORK_PORTABILITY.md`, `apps/DESIGN_EXTENSIBILITY_POLICY.md` and `apps/PARITY_RELEASE_GATES.md` for shared rules.
