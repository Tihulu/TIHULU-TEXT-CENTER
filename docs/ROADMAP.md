# Development roadmap and verified boundaries

**Status date:** 2026-11-06. This is a standalone prototype milestone, **not** evidence of a deployed Pi5 receiver.

## Stage A — completed software foundation

| Feature | Status / evidence |
|---|---|
| English responsive browser interface, retro Teletext reading panel | Implemented in vanilla HTML/CSS/JavaScript; no manual mobile screenshots yet |
| Numbered local pages 100–899, on-demand navigation | Implemented, unit-tested |
| Source-specific imported Teletext/Journaline pages and subpages | JSON import + SQLite + HTTP read; **no actual DVB/Journaline decoder wired** |
| General radio text events, including RDS, DLS, NAVTEX, APRS | Versioned JSON import + archive; **no SDR demodulator wired** |
| RSS 2.0 / Atom, owner-driven fetch and local text cache | Implemented with HTTPS restriction and resource bounds; no blanket internet/RSS compatibility guarantee |
| Local offline bulletin board | Implemented as single-owner local notebook; no user accounts or inter-device posting without future authenticated gateway |
| Bookmarks and network directory | Implemented; external sites are linked, not mirrored or guaranteed reachable |
| Default background sync / RF scans / transmission | OFF / absent by design |
| Loopback API and automatic regression suite | Implemented; GitHub Actions exercises Python versions 3.11–3.13 and checks JavaScript syntax |

## Stage B — genuine radio and TV data adapters (not implemented)

- FM RDS/RadioText+ adapter from tested discriminator + RDS decoder, preserving PI/PS/PTY/RT/RT+ only as actually decoded.
- DAB+ DLS/DLS+, Slideshow, EPG and optional Journaline from a receiver/decoder that exposes validated data. Journaline license and transport support need independent review.
- Hauppauge WinTV-soloHD DVB-T2/C: verify Linux firmware/frontend, transport-stream lock, actual Teletext PIDs and decoder output before allowing page import; preserve recordings and shared mux behavior.
- Optional HF NAVTEX/RTTY and weatherfax on suitable receiver + antenna; schedules and propagation are not guaranteed.
- Optional APRS/AX.25 receive-only public messages only where legally receivable; avoid collecting private traffic.
- Connect to the existing Survival Kit Stage4 SDR lease broker, not a second independent retuning loop. Cross-process hardware arbitration must be physically validated.
- All original recordings remain with their respective Radio/TV Recorder, never silently migrated into text cache.

## Stage C — interactive text networks (not implemented except external directory)

- Native read-only Gemini/Gopher clients with bounded fetching, parser safety and offline snapshots.
- Authenticated local LAN BBS with per-owner ACL, invited users, moderation, quotas, edit/delete policies and retention.
- Optional separate Meshtastic / packet-radio network adapter only when hardware, region preset, explicit TX permission and network compliance are verified. Current RTL-SDR cannot transmit.
- News Center and Browser interoperability, translator-first language processing and optional local AI on explicit request.
- A searchable full-text archive with source-specific storage, optional SSD location, quota and export features.

## Stage D — hardening and deployment acceptance

- Proper same-origin authenticated \`tihulu.lan\` routing with a configured app base path, HTTPS and CSRF-compatible proxy headers.
- Per-user accounts, session expiry, access isolation, rate limiting and audit policy before LAN posting.
- Pin DNS/address through an egress network policy before enabling remote untrusted feeds in a multi-user server; current operator-added feed checks are defense in depth, not a complete sandbox.
- Manual acceptance on Pi5 8GB, desktop Pop!_OS, mobile Safari and Chrome; actual RTL-SDR/Hauppauge hardware, antenna reception, power, RAM, recordings and Tihulu portal authentication.
- Signed/verified update policy, packaging and optional progressive web app/offline application shell. The present browser needs its local server to run; it is not a self-contained phone offline app.
- Real official CAP/BBK/AFAD alert adapter through the existing Emergency Center only after validation of alert authority and freshness.

## Release evidence rule

Do not mark Stage B–D complete on the basis of API mocks, advertised receiver specs, published frequencies, example decoder JSON, or a directory URL. Record source, tested equipment, exact decoder and version, measured output, resource cost, authorization and failure behavior.
