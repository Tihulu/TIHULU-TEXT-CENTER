# Phase 3 — isolated test-only implementation evidence

**Date:** 2026-11-12. **Scope:** Test-only, separate Draft PRs from exact canonical source baselines. **No code or hardware changes.**

## Source and review isolation

| Application | Real source baseline | Proposed Draft PR (test file only) | Head at verification | Added tests |
|---|---|---|---|---|
| Text Center | retained canonical Text `main` `1fffb711bfbb7c4abaf55299fa9240e5db3e1cde` | [#89](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/89), `tests/test_textcenter_cleanroom_import.py` | `e1a1382e415e053a2ee939a15751413559ede1df` | 2 |
| Media Center | unmerged original #67 `4e62e21cd5252df8a04f9ceadc429f4b116412ce` | [#90](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/90), `tests/test_recording_export_stage3_isolated.py` | `15d704f2624264d9bc346248d89373188d82d597` | 5 |
| Flight Radar | canonical `Tihulu/tihulu-flight-radar` `main` `059b391280635d9aa4d2ac73c7318af9e135ebf5` | [#14](https://github.com/Tihulu/tihulu-flight-radar/pull/14), `tests/test_stage3_isolated_receiver_ownership.py` | `b6a7510466efd5978b1724b5ce88830c1ecf9d71` | 8 (one strict XFAIL expected) |

All three new branches were created from the exact pinned original source SHA, not coordinator snapshots. Each compare showed exactly **one added test file**, 1 commit ahead, 0 behind relative to its own base. Each PR is **OPEN/DRAFT**, and no original Media #67, active Text main, original Flight main or old preservation-workstream branch was merged, rebased, force-pushed or changed.

## Results and limits (pin every result to its own PR head)

### Text Center

- [Run 43133732602](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43133732602), status **completed SUCCESS**; Python **3.11, 3.12, 3.13** all successful.
- Inspected Python 3.11 job `130903908482`: `test_current_main_imports_without_media_or_side_effects` **ok**, `test_cpu_discovery_does_not_need_media_or_devices` **ok**; whole test suite **80 tests, OK**.
- Child process runs `python -I`, with fresh copied Text-only package and `tv_center` excluded from import resolution. Import-phase process/network side effects are mocked; mocked CPU detection has no external devices/executables/models.
- Verified **only active canonical Text main** independent import and synthetic CPU discovery. The archived snapshot's `tv_center.language_codes` / `pi_hailo` negative controls and Media→Text CUDA worker reverse import still require separate archived source fixtures and acceptance. **Do not claim archived snapshot is independently packageable**.

### Media Center

- [Run 43133737755](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43133737755), status **completed SUCCESS**; Python **3.11, 3.12, 3.13** all successful.
- Inspected Python 3.11 job `130903924236`: **five new `test_recording_export_stage3_isolated` cases each ok**, entire suite **677 tests, OK (skipped=1)**.
- Synthetic SRT linebreak validation, optional no-overwrite export preflight, fake MKV mux argv/language mapping and immutable synthetic media source, `--mode complete` rejection without media and **actual mocked `_run_ffmpeg` argv `-n` assertion**.
- All media and caption files are created under temporary paths; real FFmpeg is **never executed by the new tests**. One preexisting optional real FFmpeg test is skipped, so no native QT/video mux, MP4 burn, audio clock or hardware correctness proven. Original PR #67 source and its 20 commits are preserved, not merged.

### Flight Radar

- [Cross-platform CI run 43133741667](https://github.com/Tihulu/tihulu-flight-radar/actions/runs/43133741667) **completed SUCCESS**. All four jobs (Debian 12 x64, Ubuntu 24.04 x64, Windows 2025 x64, macOS 15 Apple Silicon) completed successfully, including their offline unit-test steps and CI preview builds. These are hosted CI preview artifacts, not installed user-app releases or real RF hardware acceptance.
- Inspected Ubuntu 24.04 x64 job `130903937110` log: **79 passed, 1 xfailed in 6.24s**. The strict XFAIL intentionally preserves evidence that the canonical main exit-release branch still stops externally owned receiver services; the green workflow does not close that functionality gate.
- [Raspberry Pi ARM64 bridge preview run 43133741622](https://github.com/Tihulu/tihulu-flight-radar/actions/runs/43133741622) **completed SUCCESS**.
- Eight new synthetic pytest cases cover external service preserved when exit-release disabled, direct ownership flags for already-active versus app-started readsb, explicit Stop, failed Start, Remote JSON, restricted `sudo -n systemctl stop readsb.service tar1090.service` argv, and a **strict expected failure (XFAIL)** for **pre-existing external readsb being stopped by main when exit-release is enabled**. No systemctl/sudo/readsb/tar1090 subprocess was invoked by these tests.
- **A successful overall CI does not repair that XFAIL** or the main-versus-PR #7 Qt/sudoers/settings mismatch; no RF localization accuracy, receiver ownership release on real Pop!_OS, or signed installer acceptance is claimed.

## Outstanding gate ownership

This is a **test-only milestone**, not any application feature implementation, donor-source migration or release. Continue to track REG-01, REG-02, REG-03, REG-04, REG-10, REG-14 and REG-16 (plus all remaining 17 broader gates). Existing authorizations expressly **exclude** application source edits, installer or workflow modifications, original/other-worker PR merges, receiver services, live SDR/DVB USB access, model installs, archived main restoration and empty destination repo initialization. Test failures/XFAIL cannot be quietly reclassified as feature acceptance. EN engineering; en(default)/tr/de UI acceptance still OPEN.

## Separate next steps (not authorized by this evidence)

- Flight cross-platform workflow and pytest result have now been pinned (all four platform jobs successful; Ubuntu: 79 passed, 1 xfailed). Keep external-service ownership REG-03 OPEN, and require separate approved app source patch and field verification to resolve the XFAIL.
- For future isolated Test-only approval, add temporary archived Text snapshot negative controls and clean Media CUDA inverse control, still with no physical equipment.
- Any actual corrections for external `readsb` ownership, Text import decoupling, FFmpeg fixture or subtitle timing require **separately reviewed app/test scope**; do not cherry-pick old PR #7 or #13 into current Flight without compatibility tests.
- Distinguish software CI from physical receiver, native QT and cross-OS installed app/rollback verification. No credible remaining-hours estimate yet.
