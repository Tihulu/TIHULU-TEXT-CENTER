# TIHULU Text Center — Consolidated Draft / Acceptance Matrix (2026-11-06)

## Provenance and preservation

This branch begins from current `main` HEAD `45abc5c796b00eafef0462ea875ce204d35231fd`,
not the older bases of PR #8/#10/#11/#12. AI-related owner files
`textcenter/compute.py`, `speech.py`, `transcripts.py`, `postprocess.py`
are preserved. The newer main README's WebUSB-first Satellite Center
decision is retained. This is an independent draft; **main is untouched**.

| Integration source | Included functionality | Acceptance |
|---|---|---|
| PR #8 | Verified FM RDS scan + DAB FIC service discovery, saved station catalog, separate spectrum analysis | Mock CI only; physical RF pending |
| PR #10 | Live FM audio independent of missing ASR, MOT archive and safe Linux installer | CI / RF pending |
| PR #11 | App-owned DAB child lifecycle, Start/Stop/Stop Own RF, browser heartbeat stop, external readsb protection | API/mock only; external owner coexistence to validate |
| PR #12 | Frontend player dock, radar antenna/internet/hybrid source attribution, language pack control, desktop wrappers, static Pages portal | Platform and hardware pending |
| Consolidation | PR #11 overlapping HTTP, UI and HTTP tests merged into PR #12 current versions; Stop Own RF includes the newer FM and DAB auto scanner workers | CI and physical cleanup pending |
| Zero-install Web | Direct WebUSB permission, mono FM AudioWorklet experiment, volume, optional MediaRecorder, bounded real CU8 IQ, satellite browser page | Syntax/mock tests only; no physical USB acceptance |

## Browser/OS capability boundaries

- Chromium-based desktop browser + HTTPS + supported WebUSB + OS USB access
  can attempt direct Nooelec RTL-SDR receive-only use with no local
  Python/application installation. A pinned JavaScript library is downloaded
  over the Internet as code; not a driver installer.
- Firefox/Safari WebUSB unsupported. Windows may need WinUSB binding, Linux
  udev/kernel driver release; a permission prompt cannot bypass them.
- Browser-only FM mono uses a new experimental decoder, not proven reception.
  No RDS/metadata or MOT is synthesized by this engine.
- Raw IQ sample capture at 11D or 1090 MHz is not DAB/ADS-B decoding.
- Full DAB service list, DLS/MOT, DVB-T2, Teletext, satellite decoders,
  CPU/GPU/NPU offline ASR and independent antenna-lease broker remain
  native/browser decoder or authorized local gateway integration tasks.
- GitHub Pages cannot start OS services. The optional Python companion
  remains loopback-only; it is NOT safe to expose unauthenticated on LAN.
- One physical Nooelec tuner cannot serve FM/DAB/ADS-B at the same time.
  This page never terminates other applications' readsb/welle-cli processes.

## Cross-project receiver provenance

- Flight Radar: https://github.com/Tihulu/tihulu-flight-radar/pull/7
- Survival Kit: https://github.com/Tihulu/tihulu-survival-kit/pull/10
- Private Survival Kit plan: https://github.com/Tihulu/tihulu-survival-kit-plan/pull/6

No code from these separate repositories was merged or modified.

## Pages publication instructions

Owner must open repository Settings → Pages → Deploy from a branch,
choose `integration/consolidated-pages-webusb-2026-11-06` and `/docs`,
then Save. Expected preview: https://tihulu.github.io/TIHULU-TEXT-CENTER/
and https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite/ .
**Do not claim publication until the Pages deployment has succeeded.**

## Validation gates

GitHub Actions: Python 3.11/3.12/3.13 tests and static Pages/WebUSB checks,
JS syntax checks, install shell syntax, Windows/macOS/Linux ARM import smoke.
These cannot claim actual SDR reception.

Physical acceptance: FM sound with/without speech models; real radio
recording; RDS, FM auto scan, DAB service list/DLS/MOT, actual DVB lock/TV,
WebUSB FM usability and upload-free IQ download; closing browser and desktop
releases app-owned receiver but does not stop pre-existing readsb; state
and recordings survive installation/update. Windows WinUSB, macOS permissions
and Raspberry Pi board-specific drivers still need actual hardware testing.
