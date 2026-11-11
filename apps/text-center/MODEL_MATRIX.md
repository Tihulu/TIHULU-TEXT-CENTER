# text-center — source-backed LLM/AI/model mapping

**Not an installed-model inventory.** These mappings identify source-level capability, runtime conditions and failure pathways; hardware/runtime verification is still required. The machine-readable source is [MODEL_MATRIX.json](MODEL_MATRIX.json).

| Capability | Current engine / method | Fallback | Evidence |
| --- | --- | --- | --- |
| compute_selection | Text Center CPU/GPU/NPU selection (source_defined) | CPU compute only, not necessarily ASR | `textcenter/compute.py` |
| text_translation | Installed Argos direction inventory (optional_runtime) | Original text, no fabricated translation | `textcenter/transcripts.py` |

All details: models, resource types, sources, tests, user consent, limitations and unknown installation state are in the JSON. Any LLM performing an architectural rewrite must compare the concrete branch source and test evidence before porting. Do not confuse code-based model support, installed weights and physically tested inference.
