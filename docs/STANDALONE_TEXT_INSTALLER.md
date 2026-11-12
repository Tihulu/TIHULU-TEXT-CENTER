# TIHULU Text Center — standalone source installer preparation

**Engineering Draft only. Not a published installer, deployed artifact, actual application installation, or hardware acceptance.**

Canonical repository: **Tihulu/TIHULU-TEXT-CENTER**. This application stays in the original repository, with no source migration and no required Media, Flight, Satellite, RF Geolocation, Survival Kit, AI Tools, Jan or Ollama installation.

## Pinned reproducible Text-only package

The file **packaging/text-only-source-pin.json** pins source commit
**1fffb711bfbb7c4abaf55299fa9240e5db3e1cde**, version **0.6.0**, Python **3.11+** and the exact original Git blob IDs for 20 canonical Text Python modules and four web files. The offline generator checks every byte against those IDs before packaging. A generated archive contains only these 24 files and its generated manifest: source commit, app ID, per-file SHA-256, exact original blob IDs and sizes. ZIP entries have deterministic order, fixed metadata and no compression, so the same source yields identical archive bytes. There are no copied archived snapshots, Media or other TIHULU app files.

The package preserves the existing Text Center capabilities as code: conditional FM RDS/RT+ using rtl_fm and redsea, optional DAB DLS/MOT metadata from an already running external welle-cli, the authorized MPEG-TS TV relay, optional local Whisper/CUDA/Hailo/OpenVINO/Argos processing, Web frontend, recorded media and transcripts. It does not pretend missing native DVB tuning, structured DLS+, Journaline, calibrated SNR or a static API-free PWA have been implemented.

## Preflight and packaging — local, no receiver access

These are examples for a future approved source checkout. They do not control a tuner, run Whisper, install OS dependencies or contact other apps.

    python3 scripts/text_standalone.py check
    python3 scripts/text_standalone.py package --source-root . --output ./text-center-0.6.0-pinned.zip
    python3 scripts/text_standalone.py install --archive ./text-center-0.6.0-pinned.zip

The **check** command only reads Python/OS version and whether optional program executables appear on PATH. Executable presence is not a runnable decoder or valid RF signal. The **package** command intentionally writes only to the explicitly named output file and refuses to overwrite a different file. The **install** command performs cryptographic archive validation and prints its proposed actions, but is **DRY_RUN by default**, makes no directories and starts nothing.

Activation and rollback use an explicit **--apply** switch. **Do not use --apply on a real machine during this task; it is implemented only for later authorized review and synthetic temp-directory tests.**

## Proposed Text-owned install layout

Default runtime prefix: **~/.local/share/tihulu-text-center/runtime/**. Only the following app-specific private entries are created by an explicitly applied install in a future authorized session:

- owner.json, verifying the exact Text-specific application ID.
- state/active.json, atomic current and previous release pointer.
- state/.installer.lock, a private inter-installer lock, NOT an SDR claim.
- releases/ZIP-SHA256/, immutable verified original ZIP, manifest, 20 Python modules and four Web files.
- bin/tihulu-text-center, a foreground Python CLI launcher using the active release and no foreign TIHULU package, shared daemon or global service.

Installed Text Web and backend still run on a local Python HTTP listener, default **127.0.0.1:8787**, overridable with the canonical serve command. This is not an independent static GitHub Pages PWA nor a compiled native GUI executable. No automatic systemd/launchd/Windows service, autostart or global desktop launcher is installed.

The existing canonical database default remains **~/.local/share/tihulu-text-center/text-center.db**, or the explicit **TIHULU_TEXT_DB** environment setting. Recordings and receiver locks remain within that Text data root. An optional **--data-root** points to an explicitly authorized alternate location without copying, deleting, remapping or migrating existing data. Reserved private locations are **~/.config/tihulu-text-center/** and **~/.cache/tihulu-text-center/**; current Text code does not yet implement a separate settings/cache manager there.

Shared AI models and external SSD paths must remain untouched. The installer never modifies the paths set by **TIHULU_WHISPER_MODEL**, **TIHULU_FASTER_WHISPER_MODEL**, **TIHULU_OPENVINO_WHISPER_MODEL**, **TIHULU_HAILO_ENCODER_HEF**, **TIHULU_HAILO_DECODER_HEF**, **TIHULU_HAILO_WHISPER_NPY_DIR**, installed Argos translation pairs or **TIHULU_TV_CHANNELS_FILE**. It never downloads or migrates model weights.

## Safe rollback scope and limitations

A future operator can inspect rollback without changing anything:

    python3 scripts/text_standalone.py rollback

Only a later separately approved **rollback --apply** operation would atomically switch the Text-owned release pointer after verifying the retained previous ZIP and all installed files. Both release folders are kept, as are the Text SQLite database/WAL, user recordings, transcripts, externally stored AI weights and other applications' files.

If there is no previous release, a package is modified, a directory belongs to another app, symlinks are involved, or an installer already owns the local lock, operations fail closed without changing the active pointer. Installer code never kills OS PIDs, stops readsb/tar1090/welle-cli, claims a USB device or removes a shared service.

**Rollback is a source executable pointer rollback, not an SQLite schema downgrade, user-data backup, ASR process shutdown, uninstall or guaranteed repair of a running system.** Before any future real upgrade, obtain a clean owner-controlled Text Quit, preserve the original SQLite DB with its WAL and recordings in a separately verified app-only backup, and confirm both database schemas are compatible. The improved EXIT-01 shutdown remains unmerged Draft PR #93 and has no installed RAM/VRAM/NPU release acceptance. This installer never performs an automatic rollback of schema or a service restart.

## Dependency and support truth table

| Platform/component | Honest current capability |
|---|---|
| Linux x64, Python 3.11–3.13 | Source package, deterministic CI and private temporary activation/rollback tests; **not an installed user release** |
| Pop!_OS / Debian / Ubuntu | Python/Unix CLI candidate. Native app icon, desktop entry, install/upgrade/rollback not independently verified |
| Raspberry Pi OS ARM64 | Linux candidate only; no actual Pi hardware, NPU, RF, ARM install/rollback evidence |
| macOS Apple Silicon | Unix/Python candidate only; no installed test, signed app bundle or receiver/model support certification |
| Windows x64 | **Unsupported current native runtime**: canonical Text backend imports Unix fcntl unconditionally; activation fails closed |
| Hosted static/PWA browser | Text Web assets are bundled; dynamic API still requires Text's own Python backend, no independent static PWA/service worker |
| RTL-SDR | Optional rtl_fm/redsea/rtl_power; never started by installer |
| DAB metadata | Optional pre-running external welle-cli at loopback 7979; never started/tuned by Text installer |
| TV relay | Optional ffmpeg and operator-authorized loopback MPEG-TS stream; no native DVB tuner scan |
| Speech/translation | Optional compatible preinstalled Whisper and Argos directed EN/DE/TR pairs, CUDA/NPU only if configured and independently verified |

## Acceptance boundaries

This installer branch adds packaging preparation and deterministic tests, not real installation. No actual user models, tuners, SDR, DVB, GNSS, welle-cli, readsb, media players, GPU/NPU or other TIHULU applications were accessed. STAND-01..12 installed acceptance remains 0/12; EXIT-01 physical release tests remain 0/15 and REG-10/REG-14 remain open. The earlier Draft PR heads **#93**, **#98** and **#102**, canonical main, original source repo identity and any existing settings or recordings are preserved. Independent QA and separate owner approval are required before release, installer use, native launcher packaging, migration or deployment.
