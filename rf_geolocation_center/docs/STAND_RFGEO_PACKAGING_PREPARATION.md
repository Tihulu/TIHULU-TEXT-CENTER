# STAND-RFGEO-PACKAGING-01 — Reproducible Linux standalone source preparation

**Review source:** original RFGeo #16, EXIT-01 #94/#97, scientific REG-05 #100, standalone audit #103 and STAND-01..12 / REG-14; coordinator [Issue #75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75) and owner RFGeo [Issue #79](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/79).

**Status:** isolated **source-only Draft**, no user-installed app or destination repository initialization. This is a **Python browser/localhost + static PWA bundle**; it is **not** a compiled native GUI, native RTL-SDR backend, GNSS-SDR pseudorange decoder or independently certified positioning app. The scientific honesty and experimental 2D position bounds of REG-05 stay in force. All cross-app connectors remain optional.

## What has been implemented

- Deterministic source archive \`rf_geolocation_center/packaging/standalone.py\`: sorted files and tar entries, fixed uid/gid/permissions/mtime, gzip timestamp 0, strict root/extension file allowlist, SHA-256 per-file and full archive digest, declared exact 40-character source revision. Rebuilding unchanged input with the same declared revision yields identical tar.gz bytes.
- All actual app-owned assets packaged under \`rf_geolocation_center/\`: Python entry points, science \`core/*.mjs\`, WebUSB/native bridge and map \`web/*.mjs\`, HTML/CSS/SVG/manifest/service worker, offline map grid, NMEA and SP3 file parsers, source provenance, independent range evidence and existing RF-only user interface. The package excludes tests, caches, compiled bytecode and foreign Text/Flight applications.
- Safe read-only archive verification: reject duplicate, symlinked/nonregular, absolute or traversal tar members, unallowlisted files, missing assets, extra files, unexpectedly large decompression, corrupted hashes or changed file modes. No arbitrary archive extraction or post-install execution.
- Linux **x64 and ARM64** Python >=3.11 source installation **preparation**. \`install\` defaults to a JSON dry run. Only an explicit **\`--apply\`** writes app-owned files inside the chosen user home. Versioned releases are immutable/new-only; a package with an identical version+hash never overwrites a release. Refuse symlink/foreign install prefixes and concurrent operation locks; do not change system PATH or global desktop entries.
- Rollback via app-owned \`state.json\` previous-release list, version-scoped \`rollback-manifest.json\` and full SHA-256 bundle history. \`rollback\` defaults to a dry run. Explicit \`rollback --apply\` only points the RFGeo launcher to a hash-verified prior release; **never deletes** past releases, downloaded recordings, config, cache, data or any other app's files.
- Test fixtures: deterministic bytes, complete source closure, foreign file and symlink refusals, malicious tar members, dry-run no writes, fake-HOME app-only staging, copied-only-RFGeo launcher \`--help\`, version-update and rollback preserving user data, tampering detection, active-operation lock, and Windows/macOS apply refusal. All tests are disposable synthetic directories with no USB/network/driver/service access.

### Safe commands for reviewers (read-only until explicit apply)

From the original repository root with Python 3.11+:

\`\`\`sh
python3 -m rf_geolocation_center.packaging.standalone check

# The operator creates this fresh output directory. The packaging code does NOT create
# arbitrary directories and refuses overwriting an existing archive.
mkdir -p ./rfgeo-build-review
python3 -m rf_geolocation_center.packaging.standalone build \
  --revision <REVIEWED_EXACT_40_HEX_GIT_SHA> \
  --output ./rfgeo-build-review/rfgeo-source.tar.gz

python3 -m rf_geolocation_center.packaging.standalone plan \
  --archive ./rfgeo-build-review/rfgeo-source.tar.gz
python3 -m rf_geolocation_center.packaging.standalone install \
  --archive ./rfgeo-build-review/rfgeo-source.tar.gz
python3 -m rf_geolocation_center.packaging.standalone rollback
\`\`\`

The last two commands, without \`--apply\`, perform **no installation or rollback writes**. After build, verify/review the emitted full bundle SHA-256 and exact list of file hashes. The \`--revision\` value is **declared provenance**, not a cryptographic Git signature; reviewers must independently pin and inspect that SHA and the archive. The files are not silently downloaded.

### Future owner-approved Linux user install / rollback (NOT executed in this task)

**Only after a separately approved local-user test/installation:**

\`\`\`sh
# From a reviewed RFGeo source directory; explicit owner operation, not an auto-installer.
python3 -m rf_geolocation_center.packaging.standalone install \
  --archive ./rfgeo-build-review/rfgeo-source.tar.gz --apply

# Private launcher, NOT placed on global PATH:
~/.local/opt/tihulu-rf-geolocation-center/bin/tihulu-rfgeo --help
~/.local/opt/tihulu-rf-geolocation-center/bin/tihulu-rfgeo serve --port 8794

# Check future rollback before touching any state:
python3 -m rf_geolocation_center.packaging.standalone rollback
# After a second version exists and explicit approval to switch:
python3 -m rf_geolocation_center.packaging.standalone rollback --apply
\`\`\`

The \`rollback\` command must be invoked in the **reviewed original source checkout**, or in an installed release directory containing the package code, so \`python -m rf_geolocation_center.packaging.standalone\` is importable; it does not edit PATH/PYTHONPATH for the user. If no prior release exists, rollback refuses. If the previous release was modified, missing or symlinked, rollback refuses and keeps the current version. A failure may leave an app-owned incomplete version to inspect; the code does not delete unknown contents or attempt cleanup of user data.

The future launcher chooses \`state.json.active\`, changes into the selected app-owned release directory, and starts \`python -m rf_geolocation_center\` with the user's command; it **does not claim USB, scan DVB, load AI models, or start other apps**. Opening the local browser UI and attempting any reception still requires separately initiated user actions and permissions. The launcher cannot promise that every browser will support WebUSB or that SDR hardware is free.

### Installed paths — reserved for this app only

| Purpose | User-scoped default Linux path | Semantics |
|---|---|---|
| Versioned read-only-like source | \`~/.local/opt/tihulu-rf-geolocation-center/releases/<version>-<16hex>/\` | New-only; never overwrite older version |
| Version pointer / rollback metadata | \`~/.local/opt/tihulu-rf-geolocation-center/state.json\` | Atomically replace **app-owned** state after exclusive lock |
| Version rollback intent manifest | \`releases/<version>-<16hex>/rollback-manifest.json\` | Records exact source revision, full archive SHA and preceding release; no destructive action |
| Private launcher | \`~/.local/opt/tihulu-rf-geolocation-center/bin/tihulu-rfgeo\` | No global PATH, systemd, desktop menu or sudo |
| Config | \`~/.config/tihulu-rf-geolocation-center/\` | Preserve pre-existing files; currently reserved, not all browser UI settings are migrated |
| Cache | \`~/.cache/tihulu-rf-geolocation-center/\` | Preserve pre-existing files; **does not replace** PWA origin cache |
| Data, exports, future recordings | \`~/.local/share/tihulu-rf-geolocation-center/\` | Preserve pre-existing files; existing browser downloads still go to the user-selected/browser downloads destination |

The packaging launcher exposes \`TIHULU_RFGEO_CONFIG_DIR\`, \`_CACHE_DIR\`, \`_DATA_DIR\` environment hints; **current browser localStorage remains per-origin** and existing browser downloads are not automatically migrated. No model/recording directories are silently moved or deleted. No Windows/macOS XDG path mapping is implemented yet.

The archive includes existing \`scripts/usb_prepare_linux.sh\` as legacy documentation/utility for source preservation. **Its \`--release\` mode may call \`sudo systemctl stop readsb\` and unbind a DVB/RTL kernel interface. It is never run by the packager, installer, launcher, Stop, Quit or tests; it must never be automated.** All foreign/external receiver states remain UNKNOWN and fail closed until the owner independently releases the hardware.

## Platform compatibility and unclosed gates

| Platform | Source bundle and dry-run | Apply installer support | Unknown or missing |
|---|---|---|---|
| Linux x86_64 (Ubuntu/Debian/Pop!_OS) | Python >=3.11 with no PyPI runtime dependencies; isolated Node/Python CI | Explicit user-scoped apply preparation (not physically installed by agent) | No .deb/AppImage/Flatpak, signed/one-line installer, automatic desktop registration, native RTL-SDR, hardware claim/release or installed UI acceptance |
| Linux aarch64 / Raspberry Pi OS ARM64 | Same architecture-neutral source; synthetic \`machine=aarch64\` plan/fixture | Explicit user-scoped apply preparation, **no real Pi execution evidence** | Pi-specific Python/browser, CPU/RAM, USB permissions, native ARM64 packaging and real device acceptance |
| Windows x64 | Python source/local HTTP tests on Windows runner, web static sources | **Blocked**: Linux-only source installer refuses apply | No MSIX/exe, AppData path integration, WinUSB/driver/RTL backend or physical verification |
| macOS (especially Apple Silicon) | Python source/local HTTP tests on macOS runner, web static sources | **Blocked**: Linux-only source installer refuses apply | No .app/DMG, notarization, macOS-specific config paths, Apple Silicon-specific installed acceptance or WebUSB peripheral test |
| Web/PWA | App-owned HTML/CSS/JS/manifest/SW bundled | Future separately authorized HTTPS/static publication | First-load CDN (satellite.js, webrtlsdr), OSM/Overpass/OpenSky, CSP/permission/offline PWA 2-version and nested path acceptance still required |

Required external services **are none** for offline file/geometry work. Optional network sources are still optional: OpenStreetMap tiles/Overpass, CelesTrak orbit catalog, OpenSky and pinned \`esm.sh\` libraries (cache best effort). Flight Radar local antenna overlay (same-origin \`BroadcastChannel\`) and Text Center RDS/DAB snapshot on \`127.0.0.1:8787\` remain optional. Native RFGeo DVB pairing \`127.0.0.1:8794\` also remains optional; not a shared daemon or a startup requirement. Network absence does not turn cached map reference into a GNSS fix.

## STAND-01..12 acceptance accounting (no overclaim)

| Gate | Source-only preparation/evidence | Installed acceptance |
|---|---|---|
| STAND-01 / 03 | Deterministic self-contained Python/ESM source archive and strict asset closure; source-only fake HOME; no other TIHULU imports | **OPEN**: genuine installed clean target clone, platform UI/packaging |
| STAND-02 / 04 | Packaged browser UI, offline coordinate grids, imports and NO POSITION FIX; launcher --help | **OPEN**: full real browser offline launch with no hardware/other apps |
| STAND-05 | Versioned installer scope, separate config/cache/data roots, hashes and rollback manifests; synthetic user-file preservation | **OPEN**: native app settings integration and real saved-data rollback |
| STAND-06 / 07 | No auto service/USB access; explicit BUSY and foreign-owner policy | **OPEN**: two real applications plus real exclusive RTL-SDR/foreign readsb coexistence |
| STAND-08 / 09 | Existing EXIT-01 owned fake-driver cleanup; optional Flight/Text source retained | **OPEN**: installed Stop/Quit FD/RSS/VRAM and optional provider integration verification |
| STAND-10 | Versioned package, launcher and synthetic Linux architecture cases | **OPEN**: signed platform installers, desktop entry, app-local CI after destination migration, rollback artifacts |
| STAND-11 | Existing self-contained SW/PWA shell preserved in source tar | **OPEN**: live nested-path PWA offline/cache update and Pages parity |
| STAND-12 | CI synthetic source-level evidence and unsupported-state disclosure | **OPEN**: independent QA installed/hardware and explicit GO approval |

**0/12 STAND installed sign-offs, 0/15 installed EXIT-01 hardware acceptance, REG-14 P0 and scientific REG-05 remain OPEN.** No ownership claim for unknown/external receivers; no real SDR/WebUSB/DVB capture or setup occurred. This PR is not a release, does not initialize \`Tihulu/tihulu-rf-geolocation-center\`, and does not authorize automatic migration, signed deployment, global installation or user-data changes.
