# media-center — behavior preservation matrix

Source of truth for mapping existing features across languages/frameworks: [FEATURE_MATRIX.json](FEATURE_MATRIX.json).

| Stable feature ID | Behavior | Status | Source |
| --- | --- | --- | --- |
| `media.file.audio` | Local audio playback and caption profile | draft_branch_code | `kaffeine_next/native_media_panel.h` |
| `media.file.video` | Local video playback and caption profile | draft_branch_code | `kaffeine_next/native_media_panel.h` |
| `media.live.tv` | Live DVB-T2 TV | draft_branch_code | `kaffeine_next/native_unified_recorder.h` |
| `media.live.radio` | Live DAB/radio and Whisper | draft_branch_code | `kaffeine_next/native_radio_tab.h` |
| `media.record.export` | Recording and timed export | partial_in_draft_pr_67 | `kaffeine_next/UNIFIED_RECORDING.md` |
| `media.translation` | Speech recognition, translation, sound labels and speaker labels | draft_branch_code | `tv_center/ai_settings.py` |

The JSON also captures must-not-change invariants, source/tests and suggested replaceable extension points. UI is intentionally customizable; behavioral equivalence still requires test evidence and owner approval before rollout. A Draft feature is not a shipped feature.
