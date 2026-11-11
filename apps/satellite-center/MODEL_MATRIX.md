# satellite-center — source-backed LLM/AI/model mapping

**Not an installed-model inventory.** These mappings identify source-level capability, runtime conditions and failure pathways; hardware/runtime verification is still required. The machine-readable source is [MODEL_MATRIX.json](MODEL_MATRIX.json).

| Capability | Current engine / method | Fallback | Evidence |
| --- | --- | --- | --- |
| robot36_signal_processing | CPU NumPy (supported_code_path) | Report unavailable without fake decode | `satellite_center/compute_backends.py` |
| robot36_tone_trace | CUDA CuPy (optional_runtime) | CPU waveform pipeline | `satellite_center/compute_backends.py` |
| robot36_npu | Intel OpenVINO / Hailo detection (not_supported_without_kernel) | CPU | `satellite_center/compute_backends.py` |

All details: models, resource types, sources, tests, user consent, limitations and unknown installation state are in the JSON. Any LLM performing an architectural rewrite must compare the concrete branch source and test evidence before porting. Do not confuse code-based model support, installed weights and physically tested inference.
