# Workstream 01 — Media Center — Audit Only

**Designated GitHub issue:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/76  
**Central coordination:** https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75  
**Dedicated branch:** `audit/ws01-media-zero-regression-2026-11-11`  
**Dedicated scope root:** `apps/_coordination/workstreams/01/`  
**Source of truth:** `Tihulu/TIHULU-TEXT-CENTER`  
**Auditor status:** NOT STARTED (branch and draft planning task prepared by coordinator; no independent conversation is running).

## Guardrails: non-negotiable
- The owner requested **NO CHANGES to any currently working program feature, behavior, setting, device lifecycle, native installer, model, icon, saved data or user-visible interface**. This branch is **documentation and read-only test-planning only**.
- Do not merge, rebase, cherry-pick or close old Draft PRs; do not commit to `main`; do not initialize the three empty user-created app repositories; do not rename original repos or assume GitHub Pages redirects automatically.
- ALL coding-agent instructions, GitHub messages, source and technical documentation **English**. End-user GUI must support `en` default, `tr`, `de`; user may prefer Turkish conversation.
- The only approved badges are the original FIVE user-approved red-black-white TIHULU mascot logos. Do not change current runtime icons or claim PNGs are fully vector SVGs.
- Use original GitHub numeric ID and full PR/Issue permalinks for all migrated history, report missing review/comment bodies instead of inventing or copying confidential chats.
- Re-check full `apps/_coordination/MASTER_REQUIREMENTS.json` and `REQUIREMENT_SOURCE_TEST_CANDIDATES.json` on parent coordinator branch before claiming completeness. A source file candidate is NOT proof of the requested implementation and a listed test file is NOT proof of execution.
- Do not modify any other workstream's root and do not edit coordinator-owned `MASTER_REQUIREMENTS.json`, `PROGRESS.json`, `ISSUES.json`, source history or canonical topology. Cross-workstream dependencies go to the other worker's Issue and central #75.

## Specific first tasks
Inspect chronological #65 → #66 → #67 chain and protect PR #67 recording_export.py and native recorders. Do not make claims of live TV/radio, karaoke or hardware checks from static source-contract tests.

1. Inspect all assigned requirement IDs below **against exact pinned code and candidate tests**, then source branch head differences and user-request provenance.
2. For each ID write one evidence row: `requested | draft-coded | unit-verified | hardware-verified | released | unknown`; link exact source SHA/line, exact test SHA/command/result or missing evidence. Distinguish source-only/fixture/synthetic/live receiver tests.
3. List a non-destructive regression test for every current behavior, proposed new behavior, any 3-language UI gaps and native release/rollback boundaries. Do not run invasive hardware tests automatically.
4. Record missing tests, dependencies, 3+ application preservation constraints, PR ancestry, history links and any other blocked worker Issue.
5. Add `REPORT.md` and `EVIDENCE.json` **only under this branch-owned `workstreams/01/`**. Use Draft PR comments and Issue #76 to communicate (other agents do not share chat memory).
6. Report progress as source-backed counts; estimate hours/minutes **only after** you have audited work sizes and assumptions. Until then, ETA is explicitly unknown.

## Assigned requirement IDs (41)
- **MEDIA-001** (P0): Keep native Kaffeine Next TV channel list, scan, EPG, subtitles, Teletext and channel switching without feature loss.
- **MEDIA-002** (P0): Fix channel scan crash, weak-signal handling, PAT/PMT/HEVC issues, old PID/audio/video state when switching.
- **MEDIA-003** (P0): Maintain real RF SNR, quality, frequency, signal strength and scan progress (no invented telemetry).
- **MEDIA-004** (P0): Fix TV/radio/TV transition crashes and exclusive SDR/DVB device handoff with hard stop.
- **MEDIA-005** (P1): Ensure fullscreen video hides unnecessary bottom bars and preserves playback controls.
- **MEDIA-006** (P0): Keep native TV functionality and native desktop RF input without requiring browser WebUSB.
- **MEDIA-007** (P0): Keep teletext pages/subtitle source selection; compare with spoken dialogue and auto-fallback to Whisper on mismatch.
- **MEDIA-008** (P0): Prevent caption settings/dialog or channel switching from hiding current subtitles, retaining old program PIDs or blocking live playback.
- **MEDIA-009** (P0): Keep TV buffered caption timing stable with enough read-ahead, visible offset and easy-read modes.
- **MEDIA-010** (P1): Show all DAB multiplex blocks by default; scan ensembles and stations, with searchable favorites/channel lists.
- **MEDIA-011** (P1): Support DLS/DLS+, Journaline, MOT slideshow navigation and genuine live spectrum/waterfall and quality widgets.
- **MEDIA-012** (P0): Wait for actual welle-cli API readiness/dynamically selected port; show process/USB/decoder errors and avoid infinite loading.
- **MEDIA-013** (P1): Support FM RDS/RadioText and searchable online/radio station sources, analog tuning where supported.
- **MEDIA-014** (P1): Maintain LW/MW/SW/AM/FM feature choices without inventing unsupported frequencies or demodulators.
- **MEDIA-015** (P0): Prevent radio AI subtitles from stopping/restarting, long expanding buffers, repeating/transcription drift, duplicate provider lines.
- **MEDIA-016** (P0): When radio fails, recover only resources owned by Media Center, never kill user's external readsb/tar1090 services.
- **MEDIA-017** (P1): Expose separate Internet Load / Radio Load, device lease and source details; keep radio/TV fast transition progress.
- **MEDIA-018** (P0): Use one live caption timeline and apply user offset once per segment, never again as reading delay.
- **MEDIA-019** (P0): Keep spoken words visible even if sound labels [music]/[noise]/TESTSEITE or lyric matching is active; labels may use separate lines.
- **MEDIA-020** (P0): Show original spoken text even when optional translation model, Whisper or source fails.
- **MEDIA-021** (P0): Keep independent TV/radio captions, DVB Teletext, DAB DLS, Whisper and lyrics source attribution and no duplicated captions.
- **MEDIA-022** (P1): Maintain optimized easy readability, punctuation and natural chunk boundaries with adjustable font/background/opacity/position.
- **MEDIA-023** (P1): Support selectable source language Auto Detect; default English output; optional Whisper speech→English→configured translation model target pipeline.
- **MEDIA-024** (P1): Keep direct translation options (such as DE→TR) and installed model inventory Argos/NLLB/MADLAD/other model readiness without imaginary capability.
- **MEDIA-025** (P1): Preserve optional speaker labeling and experimental two-speaker overlap separation without allowing failed separation to block ordinary dialogue.
- **MEDIA-026** (P0): Keep adjustable transcription/subtitle delay and buffer policy; audio/video should not drift because of additive repeated waits.
- **MEDIA-027** (P1): Distinguish truly available CPU/GPU/NPU backends from simply detected RTX 5080; support fail-safe fallback and optional paired remote GPU.
- **MEDIA-028** (P0): Separate karaoke lipsync from Whisper speech lipsync and subtitle easy-read pacing.
- **MEDIA-029** (P0): Show LYRICS FOUND distinct from LYRICS MATCHED and allow user-configured confidence thresholds.
- **MEDIA-030** (P1): Provide opt-in lyrics-found preview playback highlighting at lower confidence, clearly marked as estimated.
- **MEDIA-031** (P0): Use installed Qwen forced-aligner where available; fallback to Whisper; never infer a match solely from web lyric lookup.
- **MEDIA-032** (P0): Stop karaoke progress during instrumental/no-vocals and resume at verified sung words rather than clock-based auto-scroll.
- **MEDIA-033** (P0): Fix Lyrics Refresh, Full Lyrics and separate floating blue lyrics window; matched word highlighted and optional yellow translation.
- **MEDIA-034** (P0): Refresh sync from retained recent buffer, not entire growing buffer; allow separately adjustable ~10-second karaoke offset.
- **MEDIA-035** (P1): Preserve lyric sources, legal provider policy, song continuity/metadata cache and transcription when matched lyrics unavailable.
- **MEDIA-036** (P0): Keep single embedded media player: video shares TV settings and audio shares radio settings; do not spawn extra playback windows.
- **MEDIA-037** (P1): Offer optional full-file transcription before playing local audio/video, then replay with completed captions.
- **MEDIA-038** (P0): Preserve live and offline timed transcripts with TXT/SRT/VTT/ASS/JSON and supported verified LRC exports; distinguish complete from live.
- **MEDIA-039** (P0): Preserve TV/radio recording/export, selected subtitle/audio tracks, optional MKV or rendered MP4 subtitle behavior and never overwrite original recordings.
- **MEDIA-040** (P0): Keep separate Start/Stop and Exit; Stop releases own receiver while leaving window and user's external services intact.
- **MEDIA-041** (P0): Preserve legacy rollback, main/PR references, one-line cross-platform installer and user settings on updates.

## Initial source/test candidates — existence only

| Requirement | Existing candidate code | Candidate test source | Verification |
|---|---|---|---|
| `MEDIA-001` | `kaffeine_next/patch_upstream.py`, `tv_center/channels_ui.py` | `tests/test_tv_kaffeine.py`, `tests/test_tv_channel_epoch.py` | Not verified |
| `MEDIA-002` | `kaffeine_next/tv_tune_state.py`, `tv_center/scanner.py` | `tests/test_kaffeine_dvb_scan_import_crash.py`, `tests/test_tv_kaffeine_transport_health.py` | Not verified |
| `MEDIA-003` | `kaffeine_next/dvb_diagnostics.sh`, `tv_center/hardware_status.py` | `tests/test_tv_hardware_status.py` | Not verified |
| `MEDIA-004` | `kaffeine_next/native_radio_tab.h`, `tv_center/runtime.py` | `tests/test_radio_tv_handoff_progress.py`, `tests/test_tv_radio_receiver_release_lifecycle.py` | Not verified |
| `MEDIA-005` | `kaffeine_next/native_media_panel.h`, `kaffeine_next/patch_upstream.py` | `tests/test_native_file_prepass_fullscreen.py` | Not verified |
| `MEDIA-006` | `kaffeine_next/patch_upstream.py`, `tv_center/desktop.py` | `tests/test_tv_no_tuner_playback.py` | Not verified |
| `MEDIA-007` | `kaffeine_next/teletext_match.py`, `kaffeine_next/captions_overlay.py` | `tests/test_tv_teletext_speech_recovery.py` | Not verified |
| `MEDIA-008` | `kaffeine_next/captions_overlay.py`, `kaffeine_next/tv_tune_state.py` | `tests/test_tv_channel_epoch.py`, `tests/test_tv_kaffeine_subtitle_tracks.py` | Not verified |
| `MEDIA-009` | `kaffeine_next/caption_timing.py`, `tv_center/sentence_joiner.py` | `tests/test_tv_caption_readability_clock.py`, `tests/test_tv_natural_caption_sync.py` | Not verified |
| `MEDIA-010` | `kaffeine_next/native_radio_tab.h`, `tv_center/scan_ui.py` | `tests/test_tv_radio_channel_lists_translation_reading.py` | Not verified |
| `MEDIA-011` | `textcenter/dab_bridge.py`, `tv_center/radio_dls_metadata.py` | `tests/test_dab_bridge.py`, `tests/test_radio_dls_lyrics_refresh.py` | Not verified |
| `MEDIA-012` | `kaffeine_next/native_radio_tab.h`, `tv_center/radio_capture.py` | `tests/test_tv_kaffeine_dab_api_recovery.py` | Not verified |
| `MEDIA-013` | `textcenter/fm_rds.py`, `textcenter/fm_survey.py` | `tests/test_fm_rds.py`, `tests/test_fm_survey.py` | Not verified |
| `MEDIA-014` | `kaffeine_next/native_radio_tab.h`, `textcenter/receivers.py` | `tests/test_receivers.py` | Not verified |
| `MEDIA-015` | `tv_center/radio_ai.py`, `kaffeine_next/caption_timing.py` | `tests/test_radio_ai_caption_karaoke_playback.py`, `tests/test_radio_est_caption_continuity.py` | Not verified |
| `MEDIA-016` | `kaffeine_next/native_radio_tab.h`, `textcenter/conflicts.py` | `tests/test_tv_radio_receiver_release_lifecycle.py` | Not verified |
| `MEDIA-017` | `kaffeine_next/native_hardware_tab.h`, `kaffeine_next/native_radio_tab.h` | `tests/test_radio_tv_handoff_progress.py`, `tests/test_tv_radio_frequency_buffer_progress.py` | Not verified |
| `MEDIA-018` | `kaffeine_next/caption_timing.py`, `kaffeine_next/captions_overlay.py` | `tests/test_tv_caption_live_offset.py` | Not verified |
| `MEDIA-019` | `tv_center/sound_event_captions.py`, `kaffeine_next/captions_overlay.py` | `tests/test_tv_sound_labels_teletext_auto.py` | Not verified |
| `MEDIA-020` | `tv_center/translation_failover.py`, `tv_center/captions.py` | `tests/test_tv_multilingual_caption_fallback.py` | Not verified |
| `MEDIA-021` | `kaffeine_next/teletext_match.py`, `tv_center/radio_dls_metadata.py` | `tests/test_tv_sound_labels_teletext_auto.py`, `tests/test_tv_teletext_speech_recovery.py` | Not verified |
| `MEDIA-022` | `tv_center/sentence_joiner.py`, `kaffeine_next/captions_overlay.py` | `tests/test_tv_sentence_joiner.py`, `tests/test_tv_caption_readability_clock.py` | Not verified |
| `MEDIA-023` | `tv_center/translation_failover.py`, `tv_center/language_codes.py` | `tests/test_tv_auto_track_languages.py`, `tests/test_tv_multilingual_caption_fallback.py` | Not verified |
| `MEDIA-024` | `tv_center/direct_de_tr.py`, `tv_center/translation_market.py` | `tests/test_tv_quality_translation.py`, `tests/test_tv_translation_managed_packs.py` | Not verified |
| `MEDIA-025` | `tv_center/overlap_separation.py`, `tv_center/free_speakers.py` | `tests/test_tv_dual_voice_separation.py`, `tests/test_tv_free_speakers_ui.py` | Not verified |
| `MEDIA-026` | `kaffeine_next/caption_timing.py`, `tv_center/radio_ai.py` | `tests/test_tv_natural_caption_sync.py`, `tests/test_radio_separate_lipsync_refresh.py` | Not verified |
| `MEDIA-027` | `tv_center/hardware_status.py`, `tv_center/remote_gpu.py` | `tests/test_tv_ai_hardware_market.py`, `tests/test_tv_ai_profiles_remote_startup.py` | Not verified |
| `MEDIA-028` | `tv_center/radio_karaoke_router.py`, `kaffeine_next/native_radio_tab.h` | `tests/test_radio_karaoke_independent_lipsync.py` | Not verified |
| `MEDIA-029` | `tv_center/lyrics_sync.py`, `kaffeine_next/native_radio_tab.h` | `tests/test_radio_lyrics_found_preview.py`, `tests/test_tv_radio_lyrics_match_status_auto_input.py` | Not verified |
| `MEDIA-030` | `kaffeine_next/native_radio_tab.h`, `tv_center/radio_karaoke_router.py` | `tests/test_radio_lyrics_found_preview.py` | Not verified |
| `MEDIA-031` | `tv_center/qwen_forced_aligner.py`, `tv_center/radio_karaoke_router.py` | `tests/test_radio_whisper_karaoke_refresh.py` | Not verified |
| `MEDIA-032` | `tv_center/radio_karaoke_router.py`, `kaffeine_next/native_radio_tab.h` | `tests/test_radio_karaoke_independent_lipsync.py` | Not verified |
| `MEDIA-033` | `tv_center/lyrics_sync.py`, `kaffeine_next/native_radio_tab.h` | `tests/test_radio_lyrics_refresh_full_window.py`, `tests/test_tv_radio_karaoke_tv_readability.py` | Not verified |
| `MEDIA-034` | `tv_center/radio_karaoke_router.py`, `kaffeine_next/native_radio_tab.h` | `tests/test_radio_separate_lipsync_refresh.py`, `tests/test_radio_sync_refresh_karaoke_fast.py` | Not verified |
| `MEDIA-035` | `tv_center/radio_dls_metadata.py`, `tv_center/lyrics_sync.py` | `tests/test_radio_song_metadata_sources.py`, `tests/test_radio_song_continuity_cache.py` | Not verified |
| `MEDIA-036` | `kaffeine_next/native_media_panel.h`, `tv_center/media_ai.py` | `tests/test_native_file_prepass_fullscreen.py` | Not verified |
| `MEDIA-037` | `kaffeine_next/native_media_panel.h`, `tv_center/media_ai.py` | `tests/test_native_file_prepass_fullscreen.py` | Not verified |
| `MEDIA-038` | `kaffeine_next/live_srt.py`, `tv_center/media_ai.py` | `tests/test_kaffeine_native_srt_controls.py`, `tests/test_transcripts.py` | Not verified |
| `MEDIA-039` | `kaffeine_next/native_unified_recorder.h`, `kaffeine_next/subtitle_tracks.py` | `tests/test_tv_unified_recorder.py`, `tests/test_tv_kaffeine_subtitle_tracks.py` | Not verified |
| `MEDIA-040` | `kaffeine_next/native_radio_tab.h`, `textcenter/receivers.py` | `tests/test_tv_radio_receiver_release_lifecycle.py` | Not verified |
| `MEDIA-041` | `kaffeine_next/install.sh`, `tv_center/install.sh` | `tests/test_tv_standalone_radio_media.py`, `tests/test_media.py` | Not verified |

## Existing audit and coordination documents
- [Master Plan](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/MASTER_PLAN.md)
- [97 requirements](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/MASTER_REQUIREMENTS.json)
- [Candidate mapping](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/REQUIREMENT_SOURCE_TEST_CANDIDATES.json)
- [Early ancestry audit](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/PR_ANCESTRY_AUDIT.json)
- [Test-quality categories](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/TEST_EVIDENCE_QUALITY.md)
- [Original history audit](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/PR_COMMENT_LINK_INDEX.json)
- [Protocol](https://github.com/Tihulu/TIHULU-TEXT-CENTER/blob/chore/master-requirements-zero-regression-coordination-2026-11-11/apps/_coordination/COORDINATION_PROTOCOL.md)

## Completion report format
```md
Audit completion: <audited IDs>/41
Implementation verified: <n>; source-only/draft: <n>; unknown: <n>
Tests checked: <n>; executed with evidence: <n>; hardware tests: <n>
Missing test cases / review-comment archives: <links>
Exact source refs: <SHAs and file links>
Cross-team handoffs: <issue links>
Estimated remaining work: <HHh MMm + assumptions, or unknown>
Safety: 0 active program/installer/device/feature changes; 0 unapproved merges.
```
