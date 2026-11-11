# TIHULU Text Center — LLM / model / hardware evidence matrix

**Status: source-pointer inventory only, NOT a claim of installed models or completed mappings.**

- `textcenter/compute.py` — inspect before changing model/translator/device handling; record validated choices and test results here
- `tv_center/installed_languages.py` — inspect before changing model/translator/device handling; record validated choices and test results here

Model/run matrix to fill from actual existing code/tests and verified hardware: `capability | installed model/backend | source language | output language | device CPU/GPU/NPU | licensing | timestamp fidelity | fallback | evidence path/commit | validation date`.

Preserve explicit `unknown` for unverified combinations. Do not treat model presence as working voice separation, lip-sync or translation. Before a future repo transfer copy **evidence and original decision history**, not merely the current model list.
