# TIHULU Media Center — LLM / model / hardware evidence matrix

**Status: source-pointer inventory only, NOT a claim of installed models or completed mappings.**

- `tv_center/ai_profiles.py` — inspect before changing model/translator/device handling; record validated choices and test results here
- `tv_center/model_market.py` — inspect before changing model/translator/device handling; record validated choices and test results here
- `tv_center/translation_failover.py` — inspect before changing model/translator/device handling; record validated choices and test results here
- `tv_center/qwen_forced_aligner.py` — inspect before changing model/translator/device handling; record validated choices and test results here
- `kaffeine_next/AI_LIVE_PERFORMANCE_AND_LANGUAGES.md` — inspect before changing model/translator/device handling; record validated choices and test results here

Model/run matrix to fill from actual existing code/tests and verified hardware: `capability | installed model/backend | source language | output language | device CPU/GPU/NPU | licensing | timestamp fidelity | fallback | evidence path/commit | validation date`.

Preserve explicit `unknown` for unverified combinations. Do not treat model presence as working voice separation, lip-sync or translation. Before a future repo transfer copy **evidence and original decision history**, not merely the current model list.
