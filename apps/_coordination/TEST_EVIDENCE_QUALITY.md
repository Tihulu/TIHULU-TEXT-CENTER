# TIHULU Test Evidence Quality Audit (English)

**Scope:** Sixteen selected source files inspected on 2026-11-11. This is test-code inspection, **not execution** of these sixteen test files during the inspection. GitHub Actions may exercise separate suites and should be cited by exact current SHA and workflow run; no runner can establish the user's real NooElec/Hauppauge reception, timing, RTL-SDR ownership or cross-platform device parity without actual hardware evidence.

## Confirmed distinctions
- **Static source contracts** look for text, symbol names, UI strings or file configuration in code; they do not exercise live Qt rendering, DVB tuner switch, subtitle clock, karaoke sync or RF service release.
- **Functional synthetic/fixture unit tests** execute mocked/fake input code paths, useful for maths and parser regressions but not evidence of real reception, model quality, authentic aircraft data or timing precision.
- **No original source PR is merged, no receiver was opened**, and no test was run on installed user devices during this review.

| Source test | Type | Scope / limitation |
|---|---|---|
| `Tihulu/TIHULU-TEXT-CENTER/tests/test_radio_karaoke_independent_lipsync.py` | static_source_contract | Karaoke policy strings, found-sync and cue reset checked in source; not actual live karaoke sync. |
| `Tihulu/TIHULU-TEXT-CENTER/tests/test_tv_teletext_speech_recovery.py` | behavioral_unit_with_mock_text | Teletext audit compares same-language text, unknown language and three conflicts; not live tuner. |
| `Tihulu/TIHULU-TEXT-CENTER/tests/test_native_file_prepass_fullscreen.py` | static_source_contract | Source snippets assert fullscreen control visibility and opt-in local file prepass; no graphical display launched. |
| `Tihulu/TIHULU-TEXT-CENTER/tests/test_tv_radio_receiver_release_lifecycle.py` | static_source_contract | Inspects C++ stop/lease flow strings and defaults, does not open/release a real dongle. |
| `Tihulu/TIHULU-TEXT-CENTER/tests/test_tv_sound_labels_teletext_auto.py` | behavioral_unit_with_fixtures | Sound labels and translated speech retained with fixture data; no live radio ASR tested. |
| `Tihulu/TIHULU-TEXT-CENTER/tests/test_tv_unified_recorder.py` | static_source_contract | Checks native record toolbar and existing rec path, not actual DVB recorded file playback. |
| `Tihulu/TIHULU-TEXT-CENTER/tests/test_tv_radio_karaoke_tv_readability.py` | static_source_contract | Asserts karaoke UI strings/renderer structure; not visually examined native fullscreen. |
| `Tihulu/TIHULU-TEXT-CENTER/satellite_center/browser/usb_diagnostics.test.mjs` | behavioral_unit_with_mock_browser | Browser/OS advice and grants measured with stubs, no physical RTL-SDR. |
| `Tihulu/TIHULU-TEXT-CENTER/rf_geolocation_center/tests/rf_ranging.test.mjs` | behavioral_unit_synthetic_measurements | Calibrated-range formulas and three hypothetical distances checked; explicitly UNVALIDATED, no radio fix. |
| `Tihulu/TIHULU-TEXT-CENTER/rf_geolocation_center/tests/provenance.test.mjs` | static_source_contract | Refuses untrusted imported aircraft to set real position via static code inspection. |
| `Tihulu/TIHULU-TEXT-CENTER/tests/test_dab_bridge.py` | behavioral_unit_with_fixtures | DLS and MOT metadata from a fake local welle bridge; not live DAB capture. |
| `Tihulu/TIHULU-TEXT-CENTER/tests/test_fm_rds.py` | behavioral_unit_with_fixtures | RDS/RadioText parser works on fixture JSON; not live FM signal. |
| `Tihulu/tihulu-flight-radar/tests/rf_timing_lab.test.cjs` | behavioral_unit_synthetic_measurements | Actual-format sample index assertions reject internet data but have no calibrated real timestamps. |
| `Tihulu/tihulu-flight-radar/tests/test_tar_focus_sdr_exit.py` | behavioral_unit_with_fixtures | Aircraft map focus/legacy selections using fake JSON positions, not native RF. |
| `Tihulu/tihulu-flight-radar/tests/test_multi_sources.py` | behavioral_unit_mocked_network | Internet provider units/dedup verified with fake network responses; no provider live availability claim. |
| `Tihulu/tihulu-flight-radar/tests/test_version_switch.py` | static_and_noninstall_shell_smoke | Version switch scripts and bash --help/no installation; not full rollback or user-data proof. |

## Outstanding acceptance gates
1. MEDIA: app-started/externally managed SDR handoff, actual DVB/Teletext behavior, active radio karaoke/translation timing and real SRT/MKV/MP4 export.
2. FLIGHT: real readsb packet origin I/R/I-R checks, two public Pages live revision parity, PWA cache and legacy rollback install.
3. SAT: long Meteor CU8 captures, nonzero CADU/Robot36 image, real SDR sample/decoder failure paths, native/wEB feature parity.
4. GEO: real sensor timestamp/calibration, scientifically valid 3+ observations, unit uncertainty, native GNSS backend and platform installers.
5. TEXT: real FM RDS, DAB DLS/MOT, DVB-T2 Teletext, receiver hard stop and optional modules.
6. ALL: three languages fully applied to user-visible UI, approved red badge icon integration, old/new original history link correctness, standalone installers and recoverability.

**Do not report all 97 requirements or all 127 test-file candidate references as tested/implemented.** See `REQUIREMENT_SOURCE_TEST_CANDIDATES.json` and `PROGRESS.json`. The latest GitHub CI success must be recorded by SHA and never described as a real device acceptance test.
