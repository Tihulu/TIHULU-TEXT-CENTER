# text-center — source component → portable interface map

These are **proposed architecture mappings**, not a Rust port and not a promise that every feature is hardware-tested. Use any framework as long as original behavior is preserved.

| Present source | Responsibility | Portable interface | Example Rust destination |
| --- | --- | --- | --- |
| `textcenter/http_app.py, textcenter/__main__.py` | Local loopback API and CLI startup | `text.runtime_api` | `api::loopback_server + app::cli` |
| `textcenter/dab_bridge.py, textcenter/fm_rds.py` | Radio metadata decoding and RF ownership boundary | `text.broadcast_ingest` | `adapters::dab + adapters::fm_rds` |
| `textcenter/transcripts.py, textcenter/compute.py` | Translation pairs and CPU/GPU/NPU runtime detection | `text.translation_catalog` | `ai::translator_registry + adapters::compute_probe` |
| `web/app.js, web/styles.css, web/index.html` | Responsive browser UI | `text.ui_shell` | `ui::text_dashboard` |

For exact behavioral constraints, tested/untested caveats, and non-Rust alternatives read [COMPONENT_MATRIX.json](COMPONENT_MATRIX.json), [FEATURE_MATRIX.json](FEATURE_MATRIX.json), [MODEL_MATRIX.json](MODEL_MATRIX.json), and `apps/PARITY_RELEASE_GATES.md`. Map current code changes onto new modules without forcing any UI theme or implementation language.
