# flight-radar — source-backed LLM/AI/model mapping

**Not an installed-model inventory.** These mappings identify source-level capability, runtime conditions and failure pathways; hardware/runtime verification is still required. The machine-readable source is [MODEL_MATRIX.json](MODEL_MATRIX.json).

| Capability | Current engine / method | Fallback | Evidence |
| --- | --- | --- | --- |
| flight_data | ADS-B / Internet aircraft data (external_canonical_unknown) | Do not fabricate aircraft or model behavior | `AGENTS.md` |

All details: models, resource types, sources, tests, user consent, limitations and unknown installation state are in the JSON. Any LLM performing an architectural rewrite must compare the concrete branch source and test evidence before porting. Do not confuse code-based model support, installed weights and physically tested inference.
