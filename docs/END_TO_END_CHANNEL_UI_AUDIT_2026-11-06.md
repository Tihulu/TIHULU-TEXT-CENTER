# TIHULU Text Center — End-to-End UI / Channel Discovery Audit
Date: 2026-11-06
Branch: feature/unified-channel-center-full-scan-ui-2026-11-06
Base: PR #14 (which is based on PR #13). No main merge.

## Why the existing UX failed

1. Page 400 mixed passive USB detection, RF spectrum, FM preview, live FM, DAB metadata, live TV, recording postprocess and diagnostics. Duplicate live players existed across page 400/410/420.
2. welle-cli displayed genuine 11D WDR NRW FIC service entries (e.g. 1LIVE, WDR 3, WDR 5), but items were only labels and metadata; no in-app service playback was bound.
3. DAB receiver selection was limited to four preset blocks even though the real discovery engine supports 38 DAB Band III blocks 5A–13F.
4. The FM scan offered Quick and Extended but not a clearly described whole-band Full scan; scan results were not conveniently actionable from Radio Center.
5. TV only enumerated preauthorized MPEG-TS relay channels, with passive DVB hardware diagnostics but no real DVB service scan.
6. Station names from real decoders were mixed with GUI labels; there was no persistent editable favorites/hidden/sort layer.

## Consolidated workflow and navigation

- Page 410 **Radio Center**: search/filter verified FM/DAB services, favorite, edit local display name, hide, sort order, launch real Play (FM or DAB), choose optional FM recording, import current welle mux, Full FM scan, Full DAB Band III scan, receiver management, live RDS and MOT metadata. Details-heavy RDS/image/recording controls remain behind an explicit Advanced section.
- Page 420 **TV Center**: channel search/favorites/edit, real regional DVB-T/T2 service scan via dvbv5-scan if a frontend and installed regional plan exist, local MPEG-TS playback and recording for *separately configured* relay channels, DVB device diagnostics in Advanced.
- Page 400 **Advanced RF**: passive inventory, rtl_power survey, manual FM preview, passive DVB diagnostics, imported protocol events. Duplicated full players have moved to their dedicated centers, not been deleted.
- All other Text/News/AI/Translator/Flight Radar/Survival Kit integrations and the persistent media dock remain unchanged, including the owned-only HARD STOP.

## Real reception rules

**FM:** Full does one real 87.5–108 MHz rtl_power band survey and tests up to 128 candidate 100-kHz positions via existing redsea RDS verification. Only actual RDS labels become verified catalog entries. It may take 20+ minutes depending on results. Weak stations or those without decodable RDS can still be missed. Not a guaranteed authoritative list of every station in coverage.

**DAB+:** Existing welle-cli decoder must be started or explicitly owned first. Full scans 5A–13F, saving only actually parsed FIC ensembles/services. The DAB metadata reader also now saves real service entries on a user-approved Refresh (so a current decoded mux becomes selectable without full rescan). App's PLAY opens a same-origin MP3 stream proxied *only* from fixed localhost:7979 at /mp3/<decoder-verified SID>. Explicit tuner retune /api/dab/select requires a previously verified audio SID and consent; never assumes a stored station is currently received. Packet-data-only services have no Play action. DLS/MOT remains genuine and preserved. External readsb/welle-cli are not terminated.

**DVB-T/T2 TV:** When installed, Linux dvbv5-scan can scan the selected regional DVB multiplex plan (for example installed Germany/NRW table), using a specified /dev/dvb frontend, explicit consent, no auto background operation, and client heartbeat expiration. It reads successful scanner-generated DVBv5 services only and stores them with source "verified_dvb_scan". Discovery is **not** a decoded video stream: the Play action is disabled until an authorized local MPEG-TS relay is independently configured. A distinct Hauppauge frontend may scan while a separate RTL-SDR receives FM/DAB, but no cross-process ownership is assumed. On Windows/macOS/unsupported hosts, service scan remains unavailable without a tested frontend-specific adapter.

**All stations:** User preferences (favorite, custom label, hidden, position) are separate from immutable decoder/source truth and persist in SQLite. A scan never overwrites favorites or user names. Configured TV relay entries are labelled operator-configured, not RF verified.

## Browser/installation boundary

GitHub Pages is a static frontend with experimental WebUSB mono FM / raw IQ from PR #13; this new verified DAB/TV tuner integration is implemented in the optional loopback local Text Center backend. The Pages permission popup alone **cannot** install system drivers, launch dvbv5-scan/ffmpeg/welle-cli, or decode DAB/MOT/TV protocols. Firefox lacks WebUSB. No service is exposed on the LAN merely to support Pages. Desktop, Windows and Raspberry Pi compatibility requires per-backend testing.

## Regression and hardware acceptance

Required checks:
- Python 3.11–3.13 tests, JS syntax, Windows/macOS/Linux ARM import smoke, and old RF/ASR/Flight Radar tests.
- FM RDS full scan on real Nooelec with single-owner lease, select and hear audio, record and retain, stop without killing readsb.
- DAB 11D service list and actual selectable playback (WDR 5/1LIVE); verify audio stream and DLS/MOT only when transmitted; scan all Band III blocks with original channel restoration.
- TV regional scan on separate Hauppauge frontend, service list, MPEG-TS relay handoff, real watched/recorded video; no claim that scan alone enables playback.
- Browser close/Hard Stop release owned workers (FM, DAB and DVB), preserve external receiver users and archived data.
- Search/favorites/custom labels/hidden/sort/restart persistence and no synthetic results.

Mock CI success never implies the physical hardware tests passed.
