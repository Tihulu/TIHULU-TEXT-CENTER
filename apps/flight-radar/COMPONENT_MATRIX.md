# flight-radar — source component → portable interface map

These are **proposed architecture mappings**, not a Rust port and not a promise that every feature is hardware-tested. Use any framework as long as original behavior is preserved.

| Present source | Responsibility | Portable interface | Example Rust destination |
| --- | --- | --- | --- |
| `AGENTS.md, .github/workflows/sync-flight-radar-pages.yml` | External canonical radar and built mirror publication | `radar.publication_sync` | `integration::read_only_mirror` |

For exact behavioral constraints, tested/untested caveats, and non-Rust alternatives read [COMPONENT_MATRIX.json](COMPONENT_MATRIX.json), [FEATURE_MATRIX.json](FEATURE_MATRIX.json), [MODEL_MATRIX.json](MODEL_MATRIX.json), and `apps/PARITY_RELEASE_GATES.md`. Map current code changes onto new modules without forcing any UI theme or implementation language.
