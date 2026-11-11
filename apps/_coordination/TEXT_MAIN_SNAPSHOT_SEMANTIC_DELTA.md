# Retained Text Center — active main vs archived audit snapshot

**Read-only source comparison, 2026-11-12. No fixes or feature parity certified.**

## Identity and baseline protection

The existing active [Text Center repository](https://github.com/Tihulu/TIHULU-TEXT-CENTER) retains numeric repo ID **1447637221**. The original main branch's three file blob hashes were independently checked again using the repository default ref and match the pinned source ref **1fffb711bfbb7c4abaf55299fa9240e5db3e1cde**. The archived/pre-audit WS05 snapshot ref is **470eefa12dc4b2d41ecaef7cd422fb9d52abd546**. The active main is **not** interchangeable with the archived code.

The earlier WS05 report verified **21/24 same source blobs** across main and the snapshot. This follow-up compares content semantics of exactly those three differing files, not the full runtime and not installed user settings. All 3 file contents were inspected on both refs. Differences below are additions/changes visible in the archived branch relative to current main; they are not proof the branch implementation works or should be automatically deployed.

| Source file | Active-main blob | Archived snapshot blob | Line-change summary, main → snapshot |
|---|---|---|---|
| textcenter/compute.py | 4fdcb578df622f7776ddf3a2fb80401375a697b2 | d1db4fc8d9e81627e3eef660d29d3dc02ea2edc1 | 162 vs 249 lines, 13 removals and 100 additions under a line-based alignment |
| textcenter/speech.py | bd9d63996e82d19b0b2896c1cb745add9acf2041 | 672ac7a9dff1bcff0a975a1120bc357a3a88f94e | 232 vs 279 lines, 14 removals and 61 additions |
| textcenter/transcripts.py | 9280cfdd30dc5e059ffc94fec70e865bb9ca7193 | d41c635c90ec38c3eb42d77e29d98a3b078a91d6 | 244 vs 279 lines, 11 removals and 46 additions |

The line counts include terminal newline positions; insertion/deletion counts are from a source-line alignment, not changed Git commits. No code was executed to test these differences.

## File-by-file semantic risks

### 1. compute.py — speech language and hardware readiness

- [Current main](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/1fffb711bfbb7c4abaf55299fa9240e5db3e1cde/textcenter/compute.py) exposes a narrow tuple of speech source languages en/de/tr, detects available device types and uses local CPU/GPU/NPU options.
- [Archived snapshot](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/470eefa12dc4b2d41ecaef7cd422fb9d52abd546/textcenter/compute.py#L40-L63) expands the speech source-language list to Whisper tokenizer languages, adds a bounded managed CUDA probe cache, NVIDIA fallback discovery, Pi Hailo architecture/readiness qualification, optional whisper.cpp CUDA and managed Faster-Whisper readiness.
- A wider *speech-recognition language catalog* must **not** be mistaken for full EN(default)/TR/DE **user-interface localization**. Independently verify installed translators, model readiness and CPU fallback before any claim.
- The archived source also references sibling Media/TV modules inside the original monorepo: [tv_center.hardware_market](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/470eefa12dc4b2d41ecaef7cd422fb9d52abd546/textcenter/compute.py#L77-L83), [tv_center.pi_hailo](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/470eefa12dc4b2d41ecaef7cd422fb9d52abd546/textcenter/compute.py#L127-L145), [tv_center.whisper_engine](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/470eefa12dc4b2d41ecaef7cd422fb9d52abd546/textcenter/compute.py#L170-L181) and [tv_center.cuda_faster_whisper](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/470eefa12dc4b2d41ecaef7cd422fb9d52abd546/textcenter/compute.py#L185-L195). This is a **future standalone dependency boundary**: moving Media Center out while blindly restoring the archived Text backend can create unresolved module imports.

### 2. speech.py — PCM sample-rate and model lifecycle

- [Current main](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/1fffb711bfbb7c4abaf55299fa9240e5db3e1cde/textcenter/speech.py) has the existing bounded speech stream and backends.
- [Archived snapshot](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/470eefa12dc4b2d41ecaef7cd422fb9d52abd546/textcenter/speech.py#L31-L76) adds a 32-kHz to 16-kHz conversion helper for CLI WAV, a cached Faster-Whisper CUDA model guarded by a lock, and source-language Auto detection rules (NPU Auto explicitly constrained).
- The archived speech path can [import tv_center.cuda_faster_whisper](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/470eefa12dc4b2d41ecaef7cd422fb9d52abd546/textcenter/speech.py#L145-L152). Check whether dependency is optional/fails safe and remains available after any separate Media Center source migration.
- Preservation acceptance requires waveform sample-rate metadata and real duration parity, command-line vs managed CUDA fallback, preserved original dialog if models fail, bounded stream/queue behavior and no surprise RTL-SDR reacquisition. No live audio/device test was performed here.

### 3. transcripts.py — Argos path selection and external module coupling

- [Current main](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/1fffb711bfbb7c4abaf55299fa9240e5db3e1cde/textcenter/transcripts.py) uses its existing language checks and Argos translation graph handling.
- [Archived snapshot](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/470eefa12dc4b2d41ecaef7cd422fb9d52abd546/textcenter/transcripts.py#L18-L39) imports **tv_center.language_codes** at module import time, uses language_code/translation_language helpers and adds direct-vs-English-pivot Argos translation, stronger missing-pack diagnostics and CPU-first Auto backend selection.
- This module-level tv_center import means blindly restoring the archived snapshot in a Text-only distribution **may fail at import time if tv_center is no longer installed**. That is a dependency concern, not proof that a current deployed Text Center app is broken.
- Compare EN↔TR, EN↔DE and DE↔TR translation paths using controlled installed-pack fixtures, correct missing-model reporting, no false translated text, caption timestamps, existing transcript schema and no private user data exports.

## Non-destructive cross-repo migration gate (REG-02 / REG-10 / REG-16)

1. Freeze active main and archived branch refs with their exact blob identities; never overwrite main with an archived apps/text-center/source snapshot.
2. Inventory all tv_center imports reachable from retained textcenter code and classify **mandatory-at-import**, optional-at-runtime, or isolated fallback. This first pass identifies direct imports in the three archived files; it is **not** a complete import-graph proof.
3. Before considering any source integration, require separate owner approval for a new branch and tests with both Media Center present and absent, and with CUDA/Hailo/Argos packages installed and missing; preserve user settings and raw records.
4. Validate sound/transcript behavior with controlled fixtures, then separately approved native audio/DVB device sessions. Tests must distinguish static, mocked, synthetic, installed and actual hardware outcomes.
5. Preserve English engineering and actual EN(default)/TR/DE user-interface targets, historical PR/Issue pointers, original repo ID and source/Pages/installer URLs. No migration, rename, UI/logo edit, feature change or service restart was made.

**Coordinator document only. This is a concrete dependency and source-drift risk assessment, not a test pass or instruction to merge/restore old code.**
