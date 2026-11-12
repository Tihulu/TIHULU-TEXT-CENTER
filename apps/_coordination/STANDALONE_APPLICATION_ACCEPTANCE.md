# TIHULU — mandatory standalone application acceptance before repository cutover

**Owner decision:** 2026-11-12. **Release gate:** OPEN / NOT VERIFIED. **Scope:** all five TIHULU applications; native desktop first and web/PWA where supported. **Policy:** each application must install, start, deliver its core functionality and quit in isolation; integration among TIHULU apps remains optional. This is a mandatory acceptance subgate of REG-14 (independent packages), REG-03 (resource ownership), REG-02 (canonical Text separation), REG-12 (web paths), and EXIT-01 (owned resource release), **not** a claim those gates passed or a new count added to the original 17.

## Canonical application topology

| App | Canonical repository / planned target | Source status | Isolation expectation |
|---|---|---|---|
| Text Center | `Tihulu/TIHULU-TEXT-CENTER` (stays, not renamed now) | Existing canonical source | Runs with no Media, Satellite, RFGeo, Flight Radar or AI Tools installed |
| Flight Radar | `Tihulu/tihulu-flight-radar` | Independent today | Own UI/bridge/start/stop and optional receiver provider; no Text Center install or server needed |
| Media Center | `Tihulu/tihulu-media-center` | New repo empty; code remains in Text repo source branches | Standalone native TV/radio/captions/export with packaged resources, not Text runtime |
| Satellite Center | `Tihulu/tihulu-satellite-center` | New repo empty; code remains in Text repo source branches | Standalone native Qt scheduler/capture/decoder; standalone WebUSB PWA/static site without Text host |
| RF Geolocation Center | `Tihulu/tihulu-rf-geolocation-center` | New repo empty; code remains in Text repo source branches | Independent native/web maps, measurements, permissions and device release without Flight Radar or Text server |

Empty destination repositories are **NOT migrated**, even when snapshots or source audit PRs exist. Keep origin PR history and original Text repo. No first commit/cutover/rename/merge/deployment without separate approval.

## Definition of standalone (all are mandatory)

1. **Installation and runtime:** From a fresh virtual machine/user profile containing **only this target application** and its declared platform dependencies, install the app and launch its actual UI/CLI successfully. The other four TIHULU applications and TIHULU Survival Kit, AI Tools, Jan and remote GPU host are absent; the app does not require them for basic features. Optional external systems (WebUSB devices, SatDump, ffmpeg, hardware codecs, online ADS-B providers) are capability-gated and honestly disclosed, never silently assumed bundled.
2. **Independent imports and build:** No required Python/JS/Rust imports, `PYTHONPATH`, `sys.path` hacks, symlinks, implicit absolute filesystem paths, local HTTP endpoint or runtime asset URLs pointing to another TIHULU app's source checkout, installed package, service or GitHub Pages deployment. Copy, vendor or version truly shared components with clear provenance, stable license and tests; avoid silent shared mutable package state. CI builds in an isolated source checkout with only declared dependencies.
3. **Independent configuration, storage and removal:** Per-app settings, cache, DB, archives, user recordings, model files, log and temp roots are uniquely namespaced. Upgrading/reinstalling/removing one app cannot delete/overwrite other apps' user data, ports, installers, registries or model files. Backups/rollback restore exactly the app's owned files. No cross-app overwrite of desktop IDs, protocol handlers or service unit names.
4. **Independent UI, modes and permissions:** EN default, TR/DE where implemented, four app-specific navigation/UI flows and honest device/capability states work when no other TIHULU app is open. Native RF/DVB access is native, and browser WebUSB is opt-in secure-context/user gesture only where supported; never require a localhost bridge or WebUSB for a native application. A PWA can still offer planner/map/file inspection without USB support. Keep offline features usable without internet when such functionality is designed.
5. **Receiver and process ownership:** An app may exclusively claim a shared physical RTL-SDR/DVB tuner **only with consent/available lease**; when another app owns it, show `BUSY/EXTERNAL OWNER`, don't globally stop `readsb`, `tar1090`, `Gqrx`, `welle.io`, OS drivers, Jan/Ollama or a remote GPU. Don't assume two apps can use one exclusive USB device at once. Closing one app drains **only its owned** child workers, HTTP listeners, USB claims, RAM/VRAM/NPU contexts and queues; preserves externally owned services and another app's recordings.
6. **Optional interoperation:** If two apps are installed, they may exchange **explicit versioned** data/API/events through permission-gated integration (e.g., Flight aircraft overlay into RFGeo, Satellite pass into Media capture, translated captions). Disable/disconnect integration and prove each app still works alone. No always-running shared daemon or network account required by default; on-demand/offline-first remains default. Explicit server/paired-host modes are optional.
7. **Portable build/install/rollback:** Target Linux desktop (Pop!_OS/Ubuntu/Debian), Windows x64, macOS Apple Silicon and Raspberry Pi OS where designated. Document known unsupported hardware/software combinations rather than advertising untested parity. Installer/desktop entry/icon/one-line launcher and platform update/uninstall are independently versioned. Validate legacy Flight 0.3.1 rollback without damaging settings.
8. **No synthetic feature substitution:** The existence of a UI, offline source build or mocked device test does not establish real FM RDS/DAB Journaline, DVB tuner lock, GNSS fix, Meteor LRPT decode, aircraft multilateration, VRAM clearing or SDR I/Q reception. Explicit NO DEVICE / NOT VERIFIED / STOP_FAILED_PARTIAL when needed.

## Standalone acceptance matrix — all NOT_VERIFIED until independently reproduced

| ID | Required verification | Evidence needed |
|---|---|---|
| STAND-01 | Build from a clean single-app clone with no other TIHULU checkout or app | CI job logs, package manifest, dependency lock and versions |
| STAND-02 | Install, open correct native UI and/or static PWA as advertised with other TIHULU apps absent | Per-OS screenshot/log and cold-start result |
| STAND-03 | No cross-app import, runtime fetch, symlink, hidden localhost dependency or hardcoded origin-repo path | Automated dependency/import/asset graph check |
| STAND-04 | Core offline/solo paths and honest missing-hardware state | User-facing fallback screenshot and tests |
| STAND-05 | Separate settings, recording/export files, cache, model and logs; uninstall/reinstall/rollback preserves foreign user data | Before/after checksum, paths and rollback artifact |
| STAND-06 | Start two apps side by side without requiring shared app daemon, external provider or network account | Controlled isolated mock and later owner-approved native session |
| STAND-07 | Exclusive SDR/DVB access when shared tuner busy does not steal/kill foreign owner | Synthetic ownership first; physical owner-authorized test later |
| STAND-08 | Quit A releases only A's sessions/workers/ports/model memory while B stays alive | Scoped mock + installed process/FD/RSS/VRAM checks |
| STAND-09 | Optional cross-app connector disabled/removed; both apps remain functional | Connector off/on version and fallback tests |
| STAND-10 | Each app's own CI, installer, readme, version, logo/assets, update path and portable rollback | Platform-specific artifact, provenance/README and installation proof |
| STAND-11 | Browser/Pages PWA scope is self-hosted/self-contained, service worker does not cache RF recordings and new releases are cache-correct | HTTPS nested-path browser smoke, offline shell and asset manifest |
| STAND-12 | Distinguish synthetic PASS from real hardware and installed acceptance; independent QA sign-off | Owner-approved evidence matrix and blocking GO/HOLD decision |

**Status at this checkpoint:** 0/12 standalone acceptance cases independently signed off as installed complete. Existing Flight and Text repos are code-bearing, but that alone does not establish STAND-01..12.

## First migration gate sequence

1. Freeze and hash a reviewed source snapshot **without altering original feature branches**, collect full history provenance and all active fixes; preserve existing source repo numeric ID, PR/issue links, recordings and settings.
2. Use isolated **test-only** standalone build/dependency audits against candidate source trees. Identify missing copied modules or cross-repo hooks. Do not copy archived Text or assume `tv_center/` can be removed from Text when an import still exists.
3. After an explicit separate owner approval, stage the migration to one destination **at a time**: Media, then RFGeo, then Satellite only when its native/WebUSB Pages parity plan is separately reviewed. Keep Flight independent and Text canonical.
4. Run both *alone* and *together* tests for each destination, including device-busy ownership, settings isolation, rollback and cross-platform smoke. Independent QA must verify STAND-01..12 before declaring destination canonical.
5. Publish installers, change GitHub Pages, retire old embedded entry points or remove source ONLY after another explicit owner release decision; no implicit authorization from green software CI.

**Current blockers:** repo migrations 0/3; empty Media/Satellite/RFGeo destination repos; Satellite eight-file Pages/source mismatch; EXIT-01 physical installed acceptance 0/15; original 17 broader regression gates OPEN. Authoring this contract does not alter any production application or deploy anything.
