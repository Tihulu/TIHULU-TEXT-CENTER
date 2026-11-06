# Satellite Images & Data — operator workflow (2026-11-06)

## One experience, across all platforms
Canonical pages: `satellite_center/browser/reception.html` and `browser/index.html`.
The same source files ship on GitHub Pages/PWA and are served by the optional local
companion on Pop!_OS/Debian/Ubuntu, Raspberry Pi OS, Windows, and macOS.
Not all OS/browser hardware APIs are equivalent: static Pages cannot keep USB
captures alive after the tab closes or run native SatDump.

### Primary path — no engineering screens required
1. **Station**: type and select a Germany/Türkiye city in the offline directory,
   request GPS permission, search the world via opt-in Open-Meteo, or enter
   latitude/longitude manually. Choose horizon (12/24/48 h), content
   (Earth imagery, SSTV, APRS text, FM voice, or combined) and minimum elevation.
   Existing approved schedules retain their original observer and never change
   merely because a form field is edited.
2. **Auto Schedule & Capture**: explicitly arm eligible non-overlapping real
   geometric passes. No SDR is grabbed while waiting; one receiver = one job at
   a time. Native companion persists tasks while its service runs. Browser
   schedules require a visible, awake Chromium WebUSB tab and permission.
   The **full coverage** goal plans the predicted pass window and disk budget
   for the approved image/audio/text format; local native captures can run up
   to 900 seconds/2 GB per raw IQ file with a 200 MB free-disk reserve.
   A 10-minute raw IQ recording at 1.024 MS/s needs about 1.23 GB.
   Quick-sample mode is explicitly capped at 60 seconds. Browser-only
   WebUSB is limited to 60 seconds / 128 MiB, and does not assert a complete
   Meteor LRPT image. When multiple requested formats are eligible, native
   planning prefers a feasible complete visible-window attempt over a partial
   image; image-only requests never silently change media category.
   If one optional decoder is unavailable during a combined request, the
   other operator-approved formats remain eligible and the missing target
   is reported; no unapproved media kind is silently added.
   All estimates refer to received time windows, not every spacecraft dataset.
   The shared 24h calendar shows exact local start–end clock ranges, capture
   duration and spanning hour tracks. Cancelled jobs are omitted from display,
   not deleted from persisted audit JSON. In Step 3, users can preview actual
   decoder candidates, then explicitly export them in a bounded ZIP (PNG/WAV,
   text, analysis JSON, manifest and warnings; large CU8 preserved separately).
   ZIP files have CRC32 integrity but do not establish RF/spacecraft identity.
3. **Calendar**: editable local-date day picker, actual 00:00–23:00 time slots,
   state/target/format labels, per-job cancellation. For a pending native task,
   edit local start time and target's **known protocol** only inside the original
   spacecraft pass with no overlap; receiver and required decoder tools must
   be present. Browser jobs allow manual time, frequency, sample rate and 1–60 s
   duration edits, with the same non-overlap and real hardware limits.
4. **Analyze Recordings**: on-demand, only real user files or actual native
   archive bytes. Full CU8 FFT/waterfall, analog FM/AM previews, experimental
   sync-validated Robot36 candidate; native SatDump tries Meteor LRPT where
   installed; native APRS text is shown with its independent-CRC-status caveat.
5. **Extract Results**: user can inspect/download actual PNG, WAV, decoder text
   and analysis JSON. Separate Internet NASA archives from recorded RF sources.
   Never produce a synthetic image, fabricated text, unsupported decoder result,
   or infer transmitter identity merely from TLE/energy.

### Pass-list UX and library
- On **Calculate passes**, labels show `🖼 IMAGE`, `🔊 AUDIO`, `✉ TEXT`,
  `🎥 VIDEO` for NORAD-matched published protocols. Filter by content and
  expand each pass for frequency, modulation, activity caveat, decoder type and
  published source link. This is capability metadata, **not RF reception**.
- Built-in examples include ISS Robot36 437.550 MHz (announced events only),
  historic ISS PD120 at 145.800 MHz (unsupported by Robot36 decoder), ISS APRS
  437.825 MHz, FM repeater 437.800 MHz, ISS S-band HamTV at 2395 MHz
  (**requires different RF hardware**), and Meteor-M2-3/M2-4 LRPT.
- **Other satellites:** explicitly save NORAD/frequency/protocol/content type
  and HTTPS reference; edit, remove and import/export bounded JSON profiles.
  User profiles are displayed as **UNVERIFIED**, cannot automatically turn
  on new protocol decoders, and never auto-arm arbitrary frequencies.
  For five-digit NORAD IDs, `Load TLEs for my saved NORAD profiles` optionally
  fetches up to 8 public CelesTrak TLE entries on user request; alternatively
  import a real TLE file. Current JS parser does not yet ingest six-digit OMM.
- NOAA-15/18/19 APT are **decommissioned** (2025) and are archive-only.

### Decoder support (honest runtime status)
| Public protocol | In-browser | Optional native companion |
|---|---|---|
| Robot36 SSTV | Experimental, requires actual full WAV/CU8 and sync | Native ISS SSTV auto jobs record real FM WAV (48 kHz PCM, ~96 KB/s) for image decoding; optional alternative IQ capture remains manual |
| PD120 and other SSTV formats | Not yet supported by built-in Robot36 decoder | External compatible SSTV decoder, not automatic here |
| Meteor LRPT | No browser LRPT protocol decoder | SatDump 72k/80k attempt on actual captures, if installed |
| ISS APRS / AX.25 | Not yet CRC-verified in browser | multimon-ng raw text; CRC and spacecraft origin not reverified by app |
| FM analog voice | Candidate audio demodulation, not speech recognition | Native ISS voice auto mission writes real FM WAV (48 kHz PCM) for playback/export; speech or source is not independently verified |
| HamTV 2395 MHz | Requires new S-band hardware | Current NESDR v5 and WinTV-soloHD **not capable** |
| User-defined downlink | Metadata only until an actual decoder adapter exists | Metadata + explicit manual capture; no invented format support |

### Release guards / follow-ups
- Preserve shared HTML/JS/CSS assets byte-identical with `gh-pages` and check
  all portable CI. Verify public Pages/PWA caching independently.
- End-to-end hardware acquisition, voice/SSTV event validation, Doppler-aware
  tuning, and calibrated Earth image provenance still need real physical
  acceptance tests.
- Add more legitimate receive-only protocol decoders as actual verified adapters;
  never equate "published downlink" with supported decoding.
- PR #9 and draft PR #18 remain unmerged pending release review; ensure branch
  reconciliation and hardware acceptance before shipping native installers.
- Avoid auto-starting local/third-party SDRs, stopping readsb/welle.io, or
  uploading IQ/audio/GPS without permission.
