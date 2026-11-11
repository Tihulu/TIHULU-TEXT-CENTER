# TIHULU design freedom / behavioral stability policy

The project encourages community redesigns and additions while insisting on **no surprise behavior regressions**.

**Free to change in an isolated new branch:** layout hierarchy, theme tokens, colors, fonts, icons, drag interaction, animations, panel arrangement, charts, map rendering, keyboard shortcuts *when old shortcuts are preserved or transparently remapped*, framework (e.g. Flutter, Qt, GTK, Rust egui, Tauri, React).

**Must remain discoverable and behaviorally equivalent unless user opts in:** playback and hardware Start/Stop, source ownership indicators, recordings and original media access, AI caption/translation settings and manual offset semantics, speaker/sound labels that never suppress spoken text, live-vs-complete mode restrictions, provenance/source labels, offline operation, authentication/privacy boundaries and all installed model preferences.

**New features:** add under feature flags or new UI surfaces with safe defaults; no automatic background RF, ASR, model download or cloud upload. Existing UI can be replaced only after tests and explicit migration approval.

**Accessibility and responsive checks:** desktop, tablet and mobile; keyboard/touch focus order; readable font scaling; contrast; screen-reader labels; localization and preferred languages; fullscreen viewport; non-overlapping dialogs and long titles. Visual snapshot tests complement, not replace, behavior/interaction tests. Pixel identity is NOT required: the goal is feature parity with design freedom.

### Mandatory before/after review
For every `feature_id` in each app's `FEATURE_MATRIX.json`: classify old behavior and default; implement/reuse compatible new behavior; attach source test, adapted test and actual hardware test evidence when relevant. Show explicit unmet/unknown rows. Do not declare 100% merely because a build passes.
