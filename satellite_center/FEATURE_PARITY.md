# Satellite Center — cross-platform feature parity contract

## Product requirement

**One Satellite Center, no platform-specific feature removals.** Preserve all previously implemented receiver, pass prediction, map, imagery and I/Q analysis functionality while extending it to GitHub Pages, an installable PWA, Linux (Debian/Ubuntu/Pop!_OS), Raspberry Pi OS (ARM32/ARM64), Windows x64, and macOS (Apple Silicon/Intel where dependencies support it).

The browser front end in `satellite_center/browser/` is the canonical shared UI. It is served unchanged by:

- GitHub Pages: `/TIHULU-TEXT-CENTER/satellite_center/browser/`
- Installed PWA: the same page, same JavaScript modules and feature controls
- Native local companion: `http://127.0.0.1:8791/browser/index.html` through `Handler.browser_static`

The native companion also keeps its dedicated receiver/decoder dashboard at `http://127.0.0.1:8791/`. Its controls **must remain reachable from the shared interface** until the native APIs are fully integrated into the common UI. Do not remove or replace this dashboard: it owns features that are not currently possible in a static browser tab.

## Parity and actual runtime boundaries (2026-11-06)

| Feature | Shared Pages/PWA/browser UI | Native Linux/Pi/Windows/macOS |
| --- | --- | --- |
| Pass prediction from real TLEs, sort/filter, ISS/Meteor/CubeSat/Iridium candidate sets | Yes, shared JS | Yes, the **same** JS under `/browser/index.html`; separate Skyfield tools also exist |
| GPS permission, offline Germany/Türkiye city directory, manual/worldwide positions | Yes | Same browser UI (browser/location permission-dependent) |
| LIVE Earth/Sky map, geometry/coverage/tracks and simulation | Yes; OSM tiles require network | Same browser UI |
| Local CU8 full-file spectral/waterfall analysis, AM/NFM audio candidate extraction, experimental verified-sync Robot36 candidate | Yes, local file processing; no uploads | Same browser UI; separate native capture/archive exists |
| NASA/ISS imagery on demand, user-provided SSTV media | Yes, when external services work | Same browser UI |
| Real RTL-SDR receiver acquisition | Direct WebUSB only where the browser/OS supports it | Native tools from the local receiver dashboard; same shared UI also exposes WebUSB where supported |
| Timed unattended capture after the browser tab closes | **Not yet via static Pages/PWA**. Foreground tab-only scheduler. | Available only while the optional local receiver service is running |
| Meteor LRPT with SatDump, APRS with appropriate installed decoder | **Not yet in the browser-only decoder**; do not label orbit/energy as reception | Optional native tools and successful RF recording required; OS/decoder dependencies may limit availability |
| Device access from a phone | No direct access to a different computer's USB via browser. | Authenticated, secure remote companion access remains separate work; localhost is not the remote desktop |
| Background operations, app exit and Hard Stop | Release owned WebUSB; cannot kill another program or OS service | Stop only locally owned receiver tasks; preserve external readsb/welle.io and recordings |

**Difference between feature and dependency:** a feature must be offered through the same navigation and workflow on every supported platform; whether it can execute depends on actual browser APIs, hardware, installed optional decoders and service access. Never display a functioning receiver or decoded image without real supporting data. A static GitHub Pages host cannot run Python, SatDump, readsb or OS-level services.

## Required release gates

1. Preserve one shared canonical `satellite_center/browser/` bundle. The Pages published files must be identical to the reviewed source release bundle; do not maintain divergent UI implementations.
2. Ensure the shared planner heading has **no web-only qualifier**. Preserve ground station, local TLE import, location/GPS and full pass/sky/map/analysis controls on all entry points.
3. Keep the `http://127.0.0.1:8791/` companion link visible and explicitly optional; opening this link must never automatically launch USB capture or send pairing credentials.
4. Provide honest capability and permission feedback when direct WebUSB is unavailable, and a supported local companion route for native workflows. Never silently replace real reception with Internet/catalog data.
5. Test the shared HTML and `/browser/index.html` handler route, Node browser modules, and Python core across Ubuntu x64/ARM, Windows x64 and macOS. Add genuine hardware acceptance testing separately; CI simulation is not an SDR test.
6. Synchronize `gh-pages` with the same source-browser assets for each UI change. Verify the public URL and caching after deployment; don't infer public availability solely from a Git commit.
7. The remaining **not-yet-parity** workflows (native background scheduling, native Meteor/APRS decoder access, secure remote companion access, Firefox/Safari hardware alternatives) must stay clearly tracked and must not be described as implemented until tested end-to-end.

## Non-regression rules

- Never discard a feature that exists on any platform simply because another platform needs an adapter.
- No background scan or device claim without user authorization, and no unsolicited USB process preemption.
- Preserve existing IQ files and explicit UTC satellite-candidate naming.
- No false claims of RF source identification, ISS imagery reception or TLE-pass detection.
- Match capability through shared code plus platform adapters, not by limiting all versions to what static Pages can do.
