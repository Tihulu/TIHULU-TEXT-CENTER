# TIHULU TEXT CENTER — RF scanning versus Internet sources

Every requested mode has a discovery/readiness entry (Protocols 860), but an antenna cannot open websites, and a radio energy peak cannot decode a message.

## 1. User-approved antenna surveys

Radio Data (400) offers manual, bounded rtl_power energy surveys. It never initiates them automatically, interrupts another application or claims decoded content. Each scan uses a fixed allowlisted frequency range, requires confirmation, enforces the shared Text Center lock and attempts to detect Flight Radar/readsb/dump1090/Gqrx receiver conflicts.

| Scan band | Frequency scope | Protocols represented | Limitation |
| --- | --- | --- | --- |
| FM broadcast | 87.5–108 MHz | FM RDS, RadioText+, TMC | Needs redsea for genuine RDS/RT+ text and additional TMC decoder |
| DAB Band III | 174–240 MHz | DLS/DLS+, Journaline, MOT Slideshow, EPG, TPEG | Needs actual DAB ensemble decoder and optional licenses |
| APRS VHF | 144–146 MHz | AX.25/APRS packet radio in European candidate range | Needs narrow-FM audio and real packet decoder |
| DRM MF/HF | 1–22 MHz | DRM/EWF/Journaline | Needs Q-branch/HF antenna and DRM decoder |
| RTTY HF | 2–18 MHz | RTTY/Radiotelex, DWD maritime weather text | Needs Q-branch/HF antenna and RTTY demodulator |
| NAVTEX LF/MF | 450–560 kHz | NAVTEX at 518/490 kHz | Needs suitable antenna and actual SITOR-B/NAVTEX decoder |
| HF WeatherFAX | 2–18 MHz | Weather charts/facsimile | Needs suitable antenna and HF fax image decoder |

rtl_power scans report only unidentified relative RF power peaks. They do not determine station names, service locks, official warnings or decoded text. Direct sampling uses the -D option from the osmocom rtl_power implementation; installed fork compatibility and real Q-branch reception must be tested separately. A wide band may hit the conservative 18-second timeout. No continuous all-band sweep is enabled.

## 2. DVB-T2 Teletext is a separate hardware path

A DVB frontend path is not reception. dvbv5-scan requires a valid regional channels/initial-tuning file, tuner ownership and real service search. Actual Teletext requires demultiplexing the received transport stream and parsing Teletext PIDs. These are not connected in the standalone app, so the per-feature status is blocked rather than fabricating P100/P200 content. Existing TV recordings and leases must be protected by the Survival Kit broker.

## 3. Internet-only text links

ARD Text website, TRT Telegün website, Gemini, Gopher and online BBS require Internet connectivity. The RTL-SDR cannot receive a URL. The web links in Text Networks (800) are labelled Internet Required.

Offline use is possible only for data previously cached, stored or received: News (200) caches operator-refreshed RSS/Atom/JSON Feed articles, Library (700) displays stored bookmarks/imported pages, and Local Board (600) stores local messages. The ARD Text website itself is not automatically mirrored, and is not equivalent to actual DVB-T2 Teletext from an antenna.

## 4. Separate transceiver or official integration

Meshtastic needs an approved LoRa transceiver. APRS transmit needs an authorized radio transmitter/licence. Neither is available from a receive-only RTL-SDR. Unverified radio text cannot be marked as an official alert; use authenticated CAP/authority integrations.

## 5. Inspection API and required dependencies

- GET /api/scans: all 31 feature scan contracts, RF/network/local/hardware classification and readiness.
- GET /api/scans/status: selected RF survey state and recent unidentified peaks.
- POST /api/scans/start: explicit CSRF-protected fixed-band survey, only when safe; no arbitrary frequencies or commands.
- POST /api/scans/stop: stop the running survey.
- GET /api/discovery/passive: no tuning, just installed tools, receiver paths, conflicts and caches.

Installed binary does not certify decoder capability or capture quality. The local server stays bound to 127.0.0.1; authenticated TLS routing via tihulu.lan and authoritative shared receiver leases remain Survival Kit integration tasks. Do not auto-install packages, retune protected aircraft receiver or enable background polling.

Automated CI tests synthetic RF CSV and API behavior, NOT a real SDR, DAB ensemble, DVB mux, HF antenna or physical decoder.
