# Satellite Center — Signal Intelligence & RF Source Positioning

Status: incremental implementation on `feature/satellite-signal-intelligence-2026-11-06`, forked from the existing standalone Satellite Center feature branch. No redesign, receiver preemption, automatic RF transmission, or changes to Flight Radar / Text Center / Survival Kit.

## Current integrated slice (v1)

- In **6 · Signal Intelligence**, users can run **Quick analysis** (legacy stratified FFT) or **Analyze full file**. Full mode reads every complete 2048-complex-sample CU8 FFT window using 256 KiB reads and yields between chunks; the output spectrum averages all windows, and the waterfall/time history compress the continuous recording into up to 180 rows to bound memory. It reports actual FFT coverage and any trailing unanalyzed bytes. A stop button cancels the next chunk.
- The **candidate list** groups bins substantially above the global spectral median and offers operator selection of each peak baseband offset. These are *unclassified energy concentrations*, not verified stations, modulations, or satellites. Peak-vs-median is not calibrated SNR. The user can set a manual offset.
- An explicitly operator-triggered **six-second experimental AM/NFM audio preview** is generated as local PCM WAV and played by the browser's audio element. It is not an APRS, SSTV or LRPT decoder, and its simple decimation filter can be inadequate near adjacent channels. Do not label audio alone a positive protocol detection.
- Analysis JSON and optional capture metadata JSON are exported to the user's own device. The manually entered/filename-derived center frequency and sample rate are not invented as radio facts. CU8 itself contains no metadata.
- Browser-based file analysis works on the same standards-capable desktop or mobile browser regardless of WebUSB support. Actual direct RTL-SDR capture still requires compatible Chromium WebUSB, OS permissions and sole ownership of a radio, or the optional local companion. None of this enables hardware capture in Firefox/Safari without a supported native receiver path.

## Cross-platform capability contract

| Operation | Static GitHub Pages / PWA | Optional localhost companion (Linux x64/ARM, macOS, Windows) |
| --- | --- | --- |
| Local CU8 import, quick/full FFT, waterfall, metadata exports | Yes, offline after app resources load | May reuse same browser UI |
| Candidate selection and AM/NFM audio preview | Yes, local only; no Internet/upload | Same browser UI |
| Orbit/TLE predictions and Earth/Sky maps | Yes, offline with imported/cached TLE; online refresh opt-in | Yes |
| New local RTL2832U USB capture | Only Chromium browsers where WebUSB and the USB driver/permissions allow; must explicitly open | Supported only with installed working native RTL-SDR tools; not guaranteed on every OS |
| Browser closed but scheduled capture | No | Explicit opt-in, only while companion remains running |
| Meteor-M LRPT image reconstruction | Not supplied by v1 in-browser FFT / audio | Invoke supported, installed, licensed SatDump workflows with genuine capture data, pass-specific frequency/modulation |
| ISS SSTV / APRS | Existing imported WAV Robot36 functionality as supported; no raw-IQ-to-image claim | Optional authentic audio/packet decoder integration after real reception |
| Source positioning | Existing TLE-derived *predicted* geometry and observer location | Multi-observation RF location solution is a future capability; must not fabricate bearings/ranges |

**Never claim** Windows/macOS/Raspberry Pi/Firefox/Safari/browser-only equal hardware features: provide honest per-capability readiness instead. Tests on emulators/runners do not prove real USB reception.

## Progressive CU8 content discovery (added 2026-11-06)

The **Automatic discovery · sound / image / data** action in the browser now:

1. Checks raw CU8 integrity and sample rate; uses filename/acquisition metadata when available (never guesses missing absolute MHz).
2. Performs an FFT sweep of every complete block with bounded reads and binned waterfall/power timelines.
3. Includes the tuned-center hypothesis even when FFT suppresses DC artifacts; adds strongest energy regions. These are only **unclassified candidates**.
4. Uses the time-frequency waterfall to choose candidate-specific active time intervals; tries six limited, real-sample AM/NFM analog demodulations at up to three candidate offsets and exports local playable WAV previews.
5. For captures long enough for Robot36 (≈36 s), uses actual channelized FM samples from promising time ranges and requires repeatable 1200 Hz scan-line sync before rendering an **unverified image candidate**. A valid-looking picture does not alone prove spacecraft origin. Other SSTV standards cannot be assumed from Robot36 failure.
6. Marks APRS/AX.25, Meteor-M LRPT and other digital systems **not checked** until purpose-built synchronizers and CRC/FEC verification are integrated.
7. Exports a JSON evidence trail without raw audio/image bytes; the recorded CU8 stays local. Stop interrupts both FFT and demodulation steps.

**Known limitations:** Classification is experimental; browser playback from FM/AM is NOT evidence of intelligible voice or music; strong noise can produce audio files. A single recording can contain nothing identifiable or multiple unrelated transmissions. Center frequencies, capture sample rate, correct antenna, capture duration, sufficient SNR, drift, Doppler and IQ gain matter. The boxcar channelizer is a first implementation and may leak adjacent channels; future revisions should use proper channel FIR filtering and selective resampling. Signal overlap, weak packets, and modulation families without decoders remain Unknown.

**Published static UI:** the browser-only files were synchronized to `gh-pages` via PR #19 (merge SHA `0d5e8df7d646a7961616f875c9fa6c4737c2cf68`); the site's actual availability is subject to Pages deployment completion. Source PR #18 remains draft for platform/hardware review and eventual integration into PR #9.

## Next implementation milestones

1. **Capture metadata at acquisition** — preserve capture UTC (device/browser timestamp), tuner center, effective rate, device ID/model, gain/AGC, nominal bandwidth and sample count in a companion sidecar (prefer SigMF-compatible schema when possible; CU8 remains raw). Record acquisition provenance; missing fields remain unknown. Use satellite target only as `candidate_target`, not `rf_verified_source`. Support manual correction with audit trail and association of sidecar by file name.
2. **Interactive spectrum / waterfall** — click-to-select and zoomable RF bandwidth, exact time/frequency hover, true timeline labels, live rolling mode, optional IQ slicing and aligned file playback. Distinguish raw power, waterfall colormap, clipping, DC, AGC effects and calibrated RF metrics. Support memory/CPU quota on Raspberry Pi and mobile browsers. Consider a Worker for large full-file jobs and measured responsiveness.
3. **Protocol identification with evidence** — classify only what signal attributes support. Spectral features produce candidate family and confidence, not fabricated identity. On-demand actual decoders for known, explicitly selected protocols: WAV NFM audio, verified SSTV (from correctly demodulated audio), APRS (if decode checks pass), Meteor LRPT (SatDump), other supported open downlinks. Failed CRC, weak sync and missing decoder are visible states. Never decode private user traffic.
4. **RF observation records and geographic layers** — records include receiver ID, antenna type/orientation, gain, timestamp UTC, observer position with origin (GPS, Wi-Fi/network, manually set, unknown), accuracy radius, center frequency, sample rate, bandwidth, measurements, associated recordings and evidence. Layers: `Hardware RF observations`, `My receiver locations`, `Predicted satellite orbit/footprint`, `Published ground transmitters`, `External Internet sources`, `RF-derived estimates`. Each layer gets a legend, provenance and independently toggleable visibility. Never confuse predicted orbit/online listings with receiver detections.
5. **Ground station localization / source inference** — a single omnidirectional RTL-SDR amplitude sample does **not** determine absolute distance or bearing. Add multiple recorded observer positions, optional directional antenna bearings, calibrated multi-receiver TDOA/FDOA with synchronized timestamps, or user-supplied physically grounded distance constraints. For distance-to-known-beacon measurements, show true annuli and multi-circle intersections with residual/confidence; reject underdetermined geometry. Explain equipment, calibration and timing requirements. Show estimated positions ONLY where inputs support them, not as satellites' orbital subpoints.
6. **Cross-platform deployment and support** — ship static browser resources via existing Pages publication process and native companion via the existing installers. Add release manifests and tests for x86_64 Linux/Windows, ARM64 macOS, Raspberry Pi ARM32/ARM64, browser Chromium/Firefox/Safari. Use source-specific labels and empty/no-data states. No background work/polling without user opt-in.

## Receiver ownership, safe stop, and lifecycle

- Explicit **Acquire**, **Release USB**, and **Hard Stop (this app)** remain separate from other processes. Stop and tab-close release ONLY Satellite Center-owned WebUSB handles, subprocesses and locks, never `readsb`, `dump1090`, `welle.io`, Gqrx, or system device drivers.
- A protected recording must not be removed or overwritten by cache cleanup.
- No automatic privilege escalation, Linux kernel unbind, silent WinUSB driver changes or systemd service stop. Provide read-only diagnostics when hardware is busy.
- GitHub Pages cannot access another computer's localhost nor guarantee closed-tab scheduled recordings.
- Never upload raw IQ, antenna position, recorded audio or derived RF location without a separately consented destination.

## Acceptance gates

1. Known positive/negative CU8 tones yield frequency-correct FFT peak and unchanged source bytes in both quick and full mode.
2. Full scan examines all whole 2048-pair FFT windows, shows coverage, operates with bounded slices, and can be aborted.
3. Unknown center frequency never appears as an absolute RF MHz value.
4. Candidate labels read *unclassified* unless validated decoder evidence exists.
5. Audio WAV header/PCM and mode selection are deterministic on synthetic input, with no external network call.
6. Real RTL-SDR browser capture, OS ownership conflicts, Stop/release and reacquisition require separate hardware validation.
7. Existing Earth/Sky tracking, live orbital animation, imagery, scheduled captures and stand-alone installation regressions remain green.
8. Publish to Pages only after review and static asset synchronization; a feature branch commit is not a deployed website.
