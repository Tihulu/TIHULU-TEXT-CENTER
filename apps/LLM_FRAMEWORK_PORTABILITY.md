# TIHULU portability contracts — framework-agnostic

**Scope: documentation and evidence only. No program source, installer, live feature or default setting changes.** 
Evidence is linked to **current source code and test paths**; the model matrix does not prove real model weights installed, RTL-SDR/DVB operation, exact audio DAC timing or readiness on any user computer. PR #67's newer recording features are in a separate Draft branch and must not be misreported as integrated.

## Contract layers (language-independent)
1. **Capability / behavior**: named feature IDs, user stories, inputs/outputs, default values, failure states, accessibility, integration and test oracle.
2. **Core logic**: deterministic pure functions for frequency, time, geospatial, subtitles and signal math; golden input/output fixtures where possible.
3. **Backend adapter**: RF/DVB/SDR leases, Kaffeine/libVLC, FFmpeg, Whisper, translation, network providers, filesystem. These are replaceable **behind** explicit contracts.
4. **Event/message API**: typed `start/stop`, source `state`, `caption-ready`, `recording-complete`, `error` events with timestamps, source IDs and provenance; specify versioned JSON/CBOR/IPC when actually implemented. Do not invent an API just because this document suggests one.
5. **UI rendering / theme**: user may redesign cards, typography, colors, maps, media panels, window layout, responsive shells, framework choice, CSS, Qt, GTK, egui, Tauri/React etc. Do **not** silently delete controls or repurpose timing/sliders/labels.
6. **Storage and data migrations**: existing channel lists, saved receivers/stations, profile keys, offline model settings, recordings and subtitles remain accessible; migration is reversible or visibly one-way with backup.
7. **Release + hardware tests**: compare original version against port using executable feature tests, recorded signal fixtures and hands-on real SDR/DVB/TV/radio/audio hardware. A CI build or source matrix alone is not acceptance.

### Porting to Rust (example, not a mandate)
- Map Python/Qt/C++/JS modules into Rust `core`, `adapters`, `ui` and `tests` crate layers, or any other language with equivalent separation.
- Start with offline deterministic logic and codecs without changing installed applications. Add conversion fixtures for timestamps, metadata provenance and device lease semantics.
- Implement hardware access through explicit owner IDs + resource locks; no new automatic RF poll, hidden USB opening or sharing a single receiver illegally.
- Implement ASR/translation provider traits and keep existing installed-model catalog, CPU/GPU/NPU readiness checks, language codes, explicit consent and error fallbacks.
- UI can be fully redesigned; confirm feature discoverability, keyboard/touch accessibility, responsive behavior, caption readability, fullscreen, preferences and recording formats with a checklist.
- Do not replace the deployed application until **feature-by-feature parity** and agreed installation migration tests pass.

### Existing feature vs proposed feature
The matrices mark **source_defined_not_hardware_verified**, **partial_in_draft_pr_67**, **external_canonical_no_source_audit_here** and other statuses. Do not interpret a source symbol or test name as proof of shipped functionality. Generate a parity report of **current baseline / port / missing / intentional new feature / test result** and block default rollout if any unapproved regression exists.

### Model/LLM lineage
- Every model mapping must specify capability, model name, backend, supported platform/conditions, source reference, selected vs installed vs running **separately**, fallback, source/target language availability, timestamp fidelity, user consent, failure state, licensing/provenance when verified.
- Distinguish **speech ASR, translation, diarization, acoustic labels, karaoke word alignment, generic LLM inference, deterministic RF/location DSP**. These are **not interchangeable**.
- Preserve evidence and explicit unknowns. Never ship model weights, cloud credentials, private captures or chat exports accidentally.
- `MODEL_MATRIX.json` is an evidence-backed draft inventory; before a real migration a worker must inspect runtime code and tests for the exact source branch and update confidence with citations.

## Mechanical source-to-target mapping

For each app also read `apps/<app>/COMPONENT_MATRIX.json`. It maps actual
source paths to stable framework-neutral interface IDs and **illustrative** Rust
module paths. Porters are free to choose another language, architecture or
visual theme, but must keep each mapped behavioral contract testable. Target
modules are suggestions, not implemented packages and not model weights.
