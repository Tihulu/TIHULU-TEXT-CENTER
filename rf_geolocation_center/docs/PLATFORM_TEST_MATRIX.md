# RF Geolocation Center — platform evidence

Code on branch feature/rf-geolocation-center-2026-11, Draft PR #16, is NOT a complete GNSS SDR native product.

Linux x86_64 / Debian / Ubuntu / Pop!_OS: static browser app and optional Python 3.11+ localhost source launcher. GNSS NMEA Web Serial requires a compatible browser and a real receiver. No native GNSS-SDR installed.

Windows x64: source-level Python localhost test in Windows GitHub Actions when green. Native Windows installer, WinUSB driver and RF measurement tests pending.

macOS: source-level Python localhost test in macOS GitHub Actions when green. Apple Silicon native app, menu bar app and actual GNSS receiver tests pending; do not infer M-series package availability from CI runner name.

Raspberry Pi OS ARM64 and ARM32: source portable where Python and a compatible browser exist. No physical Raspberry Pi image, CPU/power test, dedicated GNSS antenna, SDR receiver permission verification or distribution binary yet.

iOS/iPadOS and Android: browser geolocation, offline coordinate map, imported real SP3 and NMEA files and scientific computations are intended to work in secure-context mobile browsers. Native WebUSB is unavailable in iOS Safari; complete Safari/Chrome mobile responsiveness and PWA install still require actual device tests.

GitHub Pages target path /TIHULU-TEXT-CENTER/rf_geolocation_center/: code is statically hostable on feature branch, but existing gh-pages is unchanged. Do not call target URL deployed until a separate reviewed publication and live browser test.

Safety: default Background Mode OFF; only on-click OpenStreetMap tiles may make external network requests; imported observation datasets are never treated as synthetic current data; an unrelated SDR process is never killed. Software unit PASS does NOT replace real GNSS reception or hardware validation.
