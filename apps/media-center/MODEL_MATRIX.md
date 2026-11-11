# media-center — source-backed LLM/AI/model mapping

**Not an installed-model inventory.** These mappings identify source-level capability, runtime conditions and failure pathways; hardware/runtime verification is still required. The machine-readable source is [MODEL_MATRIX.json](MODEL_MATRIX.json).

| Capability | Current engine / method | Fallback | Evidence |
| --- | --- | --- | --- |
| speech_to_text | Whisper Tiny / Small (catalogued_not_installed_claim) | No ASR if model unavailable | `tv_center/ai_profiles.py` |
| speech_to_text | Faster-Whisper Large-v3 Turbo (optional_runtime) | Installed CPU Whisper when configured | `tv_center/ai_profiles.py` |
| speech_to_text | Whisper on Hailo AI HAT+ 2 (conditional_experimental) | CPU Tiny opt-in fallback | `tv_center/ai_profiles.py` |
| translation | Argos Translate (configured_option) | Preserve original on failure | `tv_center/ai_settings.py` |
| translation | NLLB (optional_runtime) | Argos if pack installed, else original | `tv_center/translation_failover.py` |
| translation | MADLAD-400 3B and DeepL (optional_not_default) | Use verified configured offline alternative or original | `tv_center/ai_settings.py` |
| karaoke_word_alignment | Qwen3 ForcedAligner 0.6B (optional_runtime) | Whisper audio-based matching fallback | `tv_center/qwen_forced_aligner.py` |

All details: models, resource types, sources, tests, user consent, limitations and unknown installation state are in the JSON. Any LLM performing an architectural rewrite must compare the concrete branch source and test evidence before porting. Do not confuse code-based model support, installed weights and physically tested inference.
