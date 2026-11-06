# ISS SSTV Series 35 — real RF full-pass receive and automatic Robot36 candidate decoding

**Scope:** This change continues Satellite Center PR #18, based on PR #9, without modifying main, Flight Radar, Survival Kit, DVB-T2/TV drivers, RDS, existing recordings, or unrelated browser functionality.

## Official planned event (checked 6 November 2026)

- ARISS Expedition 75 Series 35 "Space Memories": 9–16 November 2026. **Exact UTC start/end times remain TBD**; some passes during the date range may be silent. Check the [current ARISS event notice](https://www.ariss.org/upcoming-sstv-events.html) and [station status](https://www.ariss.org/current-status-of-iss-stations.html) immediately before use.
- **437.550 MHz FM, roughly ±10 kHz UHF Doppler**. Robot36 image: about 36 s followed by 120 s without transmission.
- Source discrepancy: the event website's latest line says "Robot 35" while the immediately preceding events and current third-party recaps / ARISS announcement graphic specify **Robot36**; do not silently manufacture certainty or auto-upgrade a decoder on the strength of this one typo.
- These are prepared images transmitted as analogue audio via radio, **not live video of Earth**. The predicted satellite pass is only orbital geometry.

## Actual end-to-end workflow

1. Install and start the optional loopback-only *Satellite Center local companion*, with an RTL2832U-compatible IQ receiver and a suitable 437 MHz antenna. `rtl_fm` is required. The Hauppauge WinTV-soloHD DVB-T2 tuner is **not** a substitute. On Pop!_OS, stop/release your own conflicting RTL-SDR service first; the application never kills `readsb` or another tuner owner.
2. In **Satellite Images & Data → Receive**, select **ISS SSTV ONLY · 9–16 Nov Series 35** and **Full pass**. Select ground station via offline place search, manual location, or explicit GPS. Refresh the TLE and calculate the next acceptable ISS pass; prefer high elevation and full visible duration. Each scheduled job is user-approved and uses the existing exclusive receiver lease.
3. The existing native scheduler records the entire feasible line-of-sight window as **actual FM-demodulated, mono 48 kHz signed-16-bit PCM WAV**, up to 900 s and free disk. Recording includes quiet periods by design. It is not limited to the browser's 60 s / 128 MiB CU8 buffer.
4. After acquisition, the SDR process and receiver lease are released. The new `sstv_series35.py` scans overlapping 55-second sections of the genuine WAV, checks repeated 1200 Hz sync bursts aligned at Robot36's 150 ms line rate, rejects clips without at least **200 / 240** valid aligned rows and de-duplicates repeated windows. It writes one PNG per detected candidate, recording its WAV offset, aligned lines, source filename and unverified identity in the persisted job result.
5. On the native local dashboard, choose **2 · Preview Auto-Decoded PNGs / Analyze WAV** to inspect frames (or notice `no_valid_robot36_sync`), then **3 · Extract Results** to export PNG + source/decoder report + metadata/warnings in a bounded ZIP. Long source WAVs exceeding 24 MiB remain as separate downloadable archive recordings. Never remove originals when a decode fails.

The decoder is deliberately experimental and audio quality, signal timing, VIS code, colors, Doppler tracking, and image fidelity require physical validation. Line sync indicates a Robot36-like signal; **no claim is made that ISS actually transmitted it**. Noise, silence, permission errors, stale TLEs, a dormant ARISS radio, a browser asleep or blocked RTL-SDR all produce explicit no-data or blocked outcomes, not fake PNGs.

## Web / platform limits

- The **browser / GitHub Pages / PWA** shows the same ISS-only selection and current known event profile, but direct WebUSB (Chromium-based browsers only) remains foreground-only and capped at 60 s / 128 MiB. It is **not** an unattended full-pass solution. A 60 s clip can land entirely inside the 120 s silent interval.
- **Firefox, Safari and iOS** do not support browser direct WebUSB. On Pop!_OS with Firefox, use the native Python localhost companion instead.
- The optional native companion supports Linux x86/ARM, macOS and Windows subject to actual RTL-SDR driver/tool support. None has real physical RF acceptance from this change. No new transmitter, OS driver modification, background RSS polling, cloud RF uploads, or account credentials.
- The nominal 437.550 MHz center profile is selected automatically; **full kinematic Doppler compensation is not yet implemented**. Edge-of-pass signal quality can suffer at roughly ±10 kHz. Native `rtl_fm` operates at fixed nominal center; signal reception does not imply Doppler tracking.
- Existing Meteor LRPT→SatDump, APRS, audio, manual CU8→FM→Robot36, NASA internet galleries, orbital maps, calendar editor, capture limits and provenance handling remain.

## Verification / release

- Unit tests construct synthetic sync tracks and synthetic Robot36 FM audio to verify PNG extraction and absence of fake output without a valid recording. They are *not* claims of actual ISS reception.
- Run: `python -m unittest discover -s tests -p "test_satellite_*.py" -v`, `python -m compileall -q satellite_center`, `node --check satellite_center/browser/auto_reception_ui.mjs` and `node --test tests/test_satellite_auto_mission.mjs`.
- Evaluate full-pass CPU/disk use, actual NESDR SMArt v5 and Doppler, real decoded ARISS event WAV, PNG correctness, platform drivers, local image access and archive ZIP before merging or claiming the feature fully released.
- **GitHub Pages deployment is separate from committing a draft source branch**; verify source/Pages parity, publication Actions and live browser cache before declaring the public site updated.
