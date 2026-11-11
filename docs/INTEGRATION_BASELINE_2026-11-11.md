# TIHULU multi-app integration baseline — 2026-11-11

**Status: isolated review candidate only. NOT released, NOT merged to `main`, and NOT hardware-verified.**

## Purpose and non-regression guarantee

Combine **existing application trees without changing any existing application source files**. This is a preservation snapshot, not a feature rewrite or a claim that every application already shares a runtime or installer.

- Do not modify the existing `main` branch, any original feature branch, or existing PR target.
- Do not change runtime defaults, SDR/DVB ownership, tuner lifecycle, configuration paths, on-demand/background behavior, output formats, translations, subtitles or recorded media.
- Do not rewrite the Flight Radar mirror. The canonical source is `Tihulu/tihulu-flight-radar` and its website is separately mirrored via GitHub workflow.
- Keep standalone program launchers/installers distinct until cross-platform verification passes.
- A passing CI run verifies tests/contracts, **not** physical receivers, Qt window behavior, audio DAC output, lip-sync or recording end-to-end.

## Provenance and exact Git tree preservation

This integration branch was created from the existing Media Center / TEXT CENTER feature head:
- Media/text base: `feat/unified-lyrics-caption-refresh-2026-11-10` @ `20b0417aa7edba2f86b297e7cabdd062e9b24291`
- Satellite application source: `fix/satellite-native-scheduler-modes-2026-11-08` @ `670e0ddcf029c8fcc9b0cef403bf76cf37613fcb`, directory `satellite_center/` tree `41d5a38c6c5382d205ea98fd98648b8c7c9c2275`
- RF Geolocation application source: `feature/rf-geolocation-center-2026-11` @ `6664a04a6247826d71f6adeb795b137fd26de213`, directory `rf_geolocation_center/` tree `7be22e93b0138de1efbe6a27b43c8143ead76c49`

The original Media Center tree `kaffeine_next/`, `tv_center/`, `textcenter/`, `web/`, `tests/`, `.github/`, `docs/`, and installer files are unchanged in the initial import commit `133bcc2c3dba3c7f1b1b8c03c1ecd3e14aabdbd3`; only two standalone directories were added. Both new directory trees are exact Git tree SHA matches, not a reconstructed copy.

**Not imported:** satellite/RF feature branch modifications to existing `textcenter/`, `web/`, `tests/`, `.github/`, `docs/` or installers; these have potential overlaps with the Media branch and need explicit tests and conflict resolution. Likewise independent in-flight PRs (e.g. segment capture and experimental model changes) have not been silently squashed or promoted. Do not claim complete integration/parity from an additive tree import.

## App boundaries

| App | Code ownership | Runtime expectations |
| --- | --- | --- |
| TEXT CENTER | `textcenter/`, `web/` | Independent backend/browser; on-demand SDR |
| TIHULU Media Center | `kaffeine_next/`, `tv_center/` | Native Kaffeine player; separate TV, radio, files UI; shared AI components |
| Satellite Center | `satellite_center/` | Standalone satellite UI/native assistant |
| RF Geolocation Center | `rf_geolocation_center/` | Standalone location and RF evidence |
| Flight Radar | canonical `Tihulu/tihulu-flight-radar` | TEXT CENTER's browser mirror must follow canonical site |

## Release gates

1. Existing source tree hashes are preserved in the import commit.
2. Run TEXT CENTER tests, independent Satellite/RF validation, JS and Python syntax tests.
3. Compare all installers and branch pins; no implicit `main` promotion or automatic tuner ownership change.
4. Test real Pop!_OS native Media Center including DVB-T2, DAB+, Audio, Video, subtitle/translation and recording, with SDR acquisition/release and app switching.
5. Run satellite receiver and RF geolocation smoke tests, desktop/browser parity and Flight Radar mirror checks.
6. Only after these checks can a reviewed integration PR be merged or release installers repointed. Existing unmerged PRs remain separate.

## Next work: unified recording/export

Implement as a **separate feature branch based on this integration snapshot**, and preserve this unmodified integration baseline. No live TV/radio complete-before-play option. File audio/video may offer Live and Complete. Live TV/radio may offer Live recording only. Protect existing original media, ASR, Teletext, translation and manual offsets. New recording is opt-in and does not claim exact acoustic/DAC clock without evidence.
