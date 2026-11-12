# Phase 5 — prioritized remediation and acceptance entry decision

**Date:** 2026-11-12. **Status:** PROPOSED. Completing source audits does not authorize production source modifications or release. All six Phase 4 reports are committed and source-path-scoped; 17 wider regression gates remain OPEN.

## Baseline

- Six owned Phase 4 audit reports: Media [#83](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/83) head `a3ed7bc99cffd0dc80159bf73245e911fdbe81ad`; Flight [#84](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/84) head `7aa8a7e9b138761c93c022d6d56d7f4c7a1a69c8`; Satellite [#85](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/85) head `6dc3ba6818f6e01f98d4782b1e8149b7eb2efd93`; Geolocation [#86](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/86) head `c70fe6bbf86571147f4b835a7004997101c9b490`; Text [#87](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/87) head `818b2f45c25cf1cc90fc710aff76c3fe07a61196`; QA [#88](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/88) head `75bf1a24133afea2dc93502ea8c0c249b5b16464`.
- Already-authorized synthetic tests were added in separate Draft PRs: Text [#89](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/89) on retained Text main, Media [#90](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/90) on original unmerged #67, Flight [#14](https://github.com/Tihulu/tihulu-flight-radar/pull/14) on canonical Flight main. Hosted CI passed at these test heads; Flight **79 passed, 1 strict XFAIL**. No test-only PR was merged, no real receiver/installed-app validation occurred.
- The six audits, as of the recorded heads, are evidence and preservation inventories, **not production changes or a feature release**. Software CI on source/audit PRs is not evidence of real radio/device compatibility.

## Highest priority — stop external-service interference (Flight REG-03 P0)

Existing canonical Flight `ReceiverController.close(release_local_service=True)` can issue a shared service stop even if `readsb.service` or `tar1090.service` was started outside Flight. Existing Flight test #14 contains a strict XFAIL on this scenario. An unexpected passive Exit must not stop externally owned services or another SDR user's stream.

**Proposed separate owner-approved work:** create a new app-source-fix Draft PR from latest canonical Flight main (never change #14, #7 or #13 in place), preserving native+classic Qt entrypoints, existing `release_sdr_on_exit` setting, device ownership and sudoers least privilege. Add a deterministic full independent two-unit fake service matrix for external readsb, external tar1090, app-owned readsb, partial start, unknown unit status, start/exit races and direct-child cleanup. An intentional explicit Stop is a separate UX/authorization contract from a passive Exit. Make existing strict XFAIL convert to a real pass only after an reviewed source fix and appropriate test adjustment; do not hide it with skip/xfail. Verify all four OS jobs; any real device/service test is **a separate explicit authorization**.

No production Flight source was modified under Phase 4. Owner must separately approve this app-source fix before execution.

## Secondary in parallel — still test-only

1. **Text REG-02/REG-10/REG-16:** Extend isolated tests on reviewable test-only branches to include archived snapshot top-level `tv_center.language_codes` missing negative, `compute.detect_devices()` unguarded `tv_center.pi_hailo` missing negative, Media CUDA worker `--serve` reverse import missing negative. Observe expected failures with `python -I` and synthetic modules; never copy old `compute/speech/transcripts` into canonical Text main. Source decoupling is a distinct later approval.
2. **Media REG-01/REG-16:** Extend test-only synthetic FFmpeg test oracles for no-overwrite race, partial sidecars, malformed SRT, correctly mocked argv and true `--mode live`/`complete` input contract. The original optional real-FFmpeg fixture is malformed and skipped; changing existing tests or running actual FFmpeg should be a separately scoped test-only change. Preserve all original 20 #67 commits and eight paths in any later migration; no native feature pass assumed.
3. **Satellite REG-06/07/08/09:** Plan tests against original PR #37: capture 1.024/2.048 MS/s to SatDump sample-rate propagation, explicit 60s/128MiB segment gaps and UTC/byte provenance, failed or stale image/zero-CADU classification and eight source-vs-Pages mismatches. No deploy or actual RF before independent authorization.
4. **Geolocation REG-04/05:** Use source-pinned deterministic fixtures for unique genuine RF ICAOs, provenance/time and null confidence/invalid ranging. Do not equate ADS-B aircraft locations or RSSI rings with calibrated receiver GPS/MLAT; no pseudo-accuracy in UI.
5. **QA REG-11/12/13/14/17:** Preserve original PR #72–#74 and #65–#67 ancestry, original PR comments, the five owner-approved logo binaries, EN(default)/TR/DE installed runtime UI, dual Pages URLs, native per-OS installers and Flight 0.3.1 rollback. Actual binary/hash, publicly deployed revision and physical release acceptance remain unverified.

## Phased permission model

**Now, without new source authorization:** coordination/documentation, read-only source comparison, approved synthetic test-only changes on independent test branches within prior owner test-only scope, CI comparison and error triage. All test changes require exact branch/path isolation and no live systemctl/SDR/user data activity.

**Requires separately explicit owner approval:** any Flight receiver controller/Qt/installer runtime fix, archived Text/Media decoupling source code, Satellite decoder/source/Pages changes, other app-feature modifications, physical SDR/DVB/TV capture, native install/rollback on the user's device, releases, PR merges, initializing destination repos or migration.

## Exit criteria

- P0 receiver ownership invariant proven by *passing* mocks (not XFAIL) on a new approved source branch; then later separately approved real service/device validation.
- Original test-only and audit PRs preserved unmerged; source SHA and changed-path inventories reconciled before any integration.
- No false reduction of 17 release gates from documentation or CI alone. Closure requires target-specific actual measured acceptance evidence.
- Remaining engineering ETA is unknown until hardware/runner scope, risks and rollback acceptance can be measured.

Engineering source documentation: English. Required installed UI: EN(default), TR, DE, not currently certified.
