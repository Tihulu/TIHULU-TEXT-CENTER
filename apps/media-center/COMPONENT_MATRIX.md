# media-center — source component → portable interface map

These are **proposed architecture mappings**, not a Rust port and not a promise that every feature is hardware-tested. Use any framework as long as original behavior is preserved.

| Present source | Responsibility | Portable interface | Example Rust destination |
| --- | --- | --- | --- |
| `kaffeine_next/native_media_panel.h, tv_center/media_ai.py` | Local playback panel, file ASR and caption prepass | `player.local_file_caption` | `ui::local_player + services::media_asr` |
| `kaffeine_next/native_radio_tab.h, tv_center/radio_ai.py` | DAB/radio controller and real speech caption pipeline | `radio.session_and_caption` | `adapters::dab + services::radio_caption` |
| `kaffeine_next/captions_overlay.py, kaffeine_next/caption_timing.py` | TV caption overlay and timing controls | `subtitles.presentation_clock` | `domain::subtitle_clock + ui::subtitle_layer` |
| `kaffeine_next/native_unified_recorder.h, kaffeine_next/live_srt.py` | Media recording, optional audio/video/SRT mux | `recording.export` | `services::recording + adapters::ffmpeg` |
| `tv_center/ai_profiles.py, tv_center/ai_settings.py, tv_center/translation_failover.py` | Model settings, profile readiness and translator fallback | `ai.runtime_registry` | `ai::model_registry + ai::translation_provider` |
| `tv_center/qwen_forced_aligner.py, tv_center/radio_karaoke_router.py` | Karaoke forced alignment separate from spoken ASR | `karaoke.aligner` | `ai::karaoke_aligner` |

For exact behavioral constraints, tested/untested caveats, and non-Rust alternatives read [COMPONENT_MATRIX.json](COMPONENT_MATRIX.json), [FEATURE_MATRIX.json](FEATURE_MATRIX.json), [MODEL_MATRIX.json](MODEL_MATRIX.json), and `apps/PARITY_RELEASE_GATES.md`. Map current code changes onto new modules without forcing any UI theme or implementation language.
