# TIHULU SURVIVAL KIT — TEXT & DATA CENTER

MASTER INTEGRATION HANDOFF / ENGLISH-ONLY UI / MOBILE + DESKTOP / OFFLINE FIRST

## Context and non-destructive continuation

Continue the EXISTING Tihulu Survival Kit architecture and feature branches. This is NOT a new project, a rewrite, or permission to remove, reset, merge or redesign previously approved hardware, services, storage, frontend, region setup, local AI, Browser, News & Politics Center, Emergency Center, Radio Center, TV Center, Flight Radar, power policies or stages. Preserve their ownership and existing interfaces. Standalone reference repository: https://github.com/Tihulu/TIHULU-TEXT-CENTER. Use live HEAD and existing checkpoints; verify claims in code and tests, not documentation. Integrate additively through reviewed interfaces and PRs.

## Product goal

Expose a unified TEXT & DATA CENTER inside the Tihulu Survival Kit, accessible from responsive desktop and tablet/phone browsers on the authenticated tihulu.lan portal. Do not directly expose the standalone unauthenticated loopback-only server. Keep UI and all technical copy in English. Support modern and optional authentic retro Teletext visual modes, numbered pages/subpages, keyboard number-entry and accessible touch controls. Page layout: 100 Index; 200 News; 300 Weather; 400 Radio & Broadcast Data; 500 Emergency; 600 Blogs & BBS; 700 Offline Wiki/Library; 800 Utilities/Text Networks; 850 About; 860 Protocols/Service Status. Preserve all current standalone features and no-feature-loss rules.

## Never misrepresent data

Every item must record the real source, service/medium, station or feed, capture timestamp, locale, original text/payload provenance, decoder and parser version, receiver identity where verified, freshness, and source state: LIVE RF, INTERNET, CACHED, OFFLINE or VERIFIED OFFICIAL ALERT. USB detected != hardware acquired; energy peak != station identified; imported data != authenticated warning. On missing data show genuine empty/error states rather than invented stations, headlines, meteorology or alerts.

## Receiver ownership: critical priority

Use the existing Survival Kit Radio Center Stage-4 hardware/lease broker as the sole authority to allocate SDR, DAB and DVB devices. Existing Flight Radar ADS-B/readsb and recordings have priority. NEVER stop readsb, dump1090, welle.io, gqrx, RTL-433 or protected recordings, and NEVER silently retune a shared Nooelec receiver. One RTL-SDR cannot independently cover ADS-B at 1090 MHz, FM at 88–108 MHz, DAB Band III and APRS simultaneously. Provide sharing of a confirmed compatible source stream only when supported, otherwise explicit Busy/Unavailable and a safe suggestion for a second receiver or user-controlled service stop. Treat the current Text Center's /proc conflict checks and flock as a temporary conservative fallback, NOT an authoritative cross-app lease.

## Auto Discover and scans

At page open, do PASSIVE automatic discovery: USB/DVB/RTL device IDs, installed decoder dependencies, compatible external radio/network endpoints, existing feeds, cached pages, configured region presets, running/busy receiver services and tested capability readiness. No RF tuning or network polling by default. Separate manual user-approved scan actions by protocol. First FM spectrum survey via rtl_power (energy candidates only), then user-triggered RDS validation via rtl_fm + redsea; integrate DAB ensemble scanning, DVB mux/service/Teletext PID scanning, and later HF/APRS scans only after decoder support and cross-service lease tests. Never mark a detected spectral peak as a radio station until actual decoding verifies it. Every scan has progress, cancellation, timeout, resource limits and provenance.

## Complete RF and broadcast modes — none may disappear from the scope

- FM RDS / RadioText / RadioText+ (RT+ artist, song, station, PTY, traffic flags, announcements and history): rtl_fm + redsea newline-delimited JSON; show real RT+ item.artist/item.title only when decoded. RDS TMC traffic requires appropriate location tables/rights.
- DAB+ DLS and DLS+ station labels, news, presenter/program metadata; use validated metadata from welle-compatible decoders, not fake journaline.
- DAB+ Journaline hierarchical interactive text; verify a genuine broadcast service, decoder transport, intellectual-property licensing and Fraunhofer terms before enabling.
- DAB+ MOT Slideshow, service images, EPG/SPI and TPEG traffic; maintain bounded image caching and metadata provenance.
- DVB-T2 real Teletext numbered pages and subpages from actual transport streams and Teletext PIDs using a confirmed DVB tuner. Include genuine source selection and HbbTV external companion links separately. Do not substitute ARD Text internet pages and label them as antenna reception.
- DRM Digital Radio including available program labels, images and EWF, provided suitable HF receiver path and decoder exist; raw radio EWF is not automatically a verified official CAP warning.
- RTTY / Radiotelex weather and maritime messages, including DWD Pinneberg as a possible reception target when published schedules and signal permit; HF WeatherFAX maps with source/time.
- NAVTEX on 518 kHz and supported alternate frequencies (including 490 kHz) using an appropriate LF/HF antenna and compatible SITOR-B decoder.
- APRS and AX.25 receive-only public packet messages/locations with privacy controls. No unauthorized packet TX.
- Nooelec NESDR SMArt v5 may offer direct-sampling Q-branch 0.1–25 MHz where hardware, drivers and antennas support it; do NOT assume reliable HF tuning or that an upconverter is mandatory. Verify on physical device. A separate suitable antenna is often necessary.

## Text internet and local messaging

- Keep RSS 2.0, Atom and JSON Feed 1/1.1 with opt-in fetch, searchable SQLite/SSD text archives, bookmarks, filtering, category/region tags and source freshness. Reuse existing News & Politics Center's DE/TR source registry and its independent, mainstream, opposition, critical and official sources instead of duplicating fetching/caches.
- Add safe bounded read-only native Gemini and Gopher clients with TLS/cert controls, MIME limits and offline snapshots; keep browser PDF/basic-page access and official external links. Do not build unrestricted SSRF proxy.
- Add external BBS directory and sandboxed authenticated SSH/HTTP BBS clients; Telnet only with explicit plaintext insecurity notice. Do not run shell commands from untrusted remote messages.
- Extend single-user offline local bulletin notes to optional multi-user authenticated local BBS through the Survival Kit account/session/ACL system, with quotas, moderation/retention and offline caching. The existing loopback note store is NOT already a secure multi-user LAN BBS.
- Provide Message Center support contracts for Meshtastic LoRa via an approved separate LoRa transceiver and explicit legal/configuration/TX controls; RTL-SDR cannot transmit. Amateurs' APRS/AX.25 TX requires distinct hardware and applicable licensing.

## Emergency, wiki, AI and regional datasets

Route verified CAP/BBK/NINA/AFAD and other authoritative public alerts through the existing Emergency Center with signature/source validation, issue/expiry timestamps and critical stale-alert warnings; unverified RF text stays marked informational. Reuse offline Wikipedia, courses and docs through existing Wiki/Files/Browser rather than duplicating ZIM indexing. Support translator-first processing across user-selected languages before optional AI summarization/Q&A; source originals remain accessible. AI workers obey CPU/AI HAT+2/remote RTX and SSD model placement policies already chosen in the Kit. Region-aware DE/TR presets including Köln/NRW FM, DAB and DVB and İzmir can be shipped as small versioned data, with optional signed download for larger per-city lists; presets are frequency hints, not reception evidence.

## Responsive operation and low resource use

Mobile/iOS/Android Safari/Chrome, desktop Firefox/Chromium and Pi browser must show equal functionality at the portal URL and use no unauthenticated direct backend. No hard-coded localhost URLs in portal frontend. Implement correct authenticated same-origin prefix or dedicated hostname with TLS, CSRF, strict CSP, websocket/SSE constraints if needed, per-user isolation and egress security. Default background polling/scanning/AI is OFF; entering a panel may perform a bounded passive check, but no ongoing workload after leaving. When ON by choice, use explicit quotas and energy/RAM limits; optional external SSD archive location, no deletion of source recordings.

## Implementation and acceptance instructions

Inspect live GitHub repository/branches, identify how the current Kit frontend, shared receiver lease API, news service, database, authentication portal and Radio/Flight Radar work. Produce a dependency/feature inventory and additive integration design. Implement staged PRs with targeted tests and checkpoints, preserving main and other agents' branches. Priority 1: safe portal integration + shared SDR broker + Auto Discover + FM RDS/RT+ + RSS/Atom/JSON cache. Priority 2: confirmed DVB Teletext + DAB DLS/DLS+ (+ MOT/EPG where decoder can output) and local authenticated BBS. Priority 3: Gemini/Gopher, Journaline licensing, DRM/RTTY/NAVTEX/WeatherFAX/APRS + separate Meshtastic adapter. For each item maintain implemented / dependency missing / blocked / planned status; no feature is silently removed. Tests must cover no tuner preemption, no synthetic RF claims, RSS SSRF limits, multiuser ACLs, mobile responsiveness, cache source/freshness and stop/power behavior. Physical reception on actual Nooelec/DVB/Raspberry Pi must be validated separately; CI alone is not proof. Publish a clear DONE/PENDING/BLOCKED ledger, reproducible setup guide, dependency package checks, real user-visible screenshots where possible and GitHub links.

## Final constraints

Integrate the standalone TIHULU-TEXT-CENTER as a distinct maintained module rather than copying it into unrelated Radio/Flight Radar repos. Do not create duplicate station, feed, AI, wiki or emergency data sources. Do not auto-install packages, disable protected services or auto-enable background scanning. Preserve all historical Survival Kit design decisions, responsive UI elements, and previously approved installation wizard/region/storage and energy controls. If a requested mode needs hardware or licensing, implement honest capability/adapter interfaces and explicitly mark the gate rather than falsely claiming it works.


### Additional all-source scanning requirement

Treat RF scanning, DVB service discovery, online network fetching and offline cache inspection as distinct operations. UI must offer a truthful per-feature scan/readiness action for all 31 tracked services; never imply that Gemini, Gopher, ARD Text web or Internet BBS is available through the RTL-SDR. Add actual decoder-specific DAB, DVB, HF and APRS adapters behind the existing Radio Center/Flight Radar/TV shared lease authority, preserving recordings and no-preemption. The current standalone implementation has seven manual RF energy-band profiles but does NOT yet decode all protocols. Implement real off-air Teletext only after DVB transport-stream and Teletext PID acceptance, and offline Internet reading only after a real user-requested cache operation.


### Receiver playback / slideshow / Hauppauge update (Nov 6 2026)

The standalone module now has an opt-in real RTL-SDR FM WAV preview backend, opt-in redsea RDS2/RFT logo extraction (CPU-heavy, no auto enable), a bounded PNG/JPEG offline media archive for real RDS2 and DAB MOT decoder images, and passive Hauppauge WinTV-soloHD 01589 USB/firmware/frontend checks. Integrate these without regressions: share the Radio Center SDR/tuner leases; never retune Flight Radar or TV recording; support proper continuous low-latency radio audio later using an authorized resource-sharing pipeline, without falsely calling the finite WAV preview live streaming. Connect a real welle-cli/receiver DLS/MOT/EPG decoder only after testing and presence of genuine broadcast data. Hauppauge model 01589 covers DVB-T/T2/C, with region-specific tuning and real Teletext PID decoding required. Handle all thumbnail/image MIME and data-size limits, retention and user-requested offline storage. Source badges must differentiate RF-broadcast images from Internet cover artwork.
