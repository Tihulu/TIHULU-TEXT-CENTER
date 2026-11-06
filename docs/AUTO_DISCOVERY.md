# Automatic discovery & controlled RF scanning

The user-facing application is English-language. Its protocol catalogue preserves every agreed technology, but a listed feature is NOT proof of implemented decoding or actual reception.

## Two-level discovery

1. **AUTO DISCOVER (safe and passive):** inspect local RTL2832U USB candidates and DVB frontend paths, installed decoder executables, potentially competing processes (including readsb/dump1090/Gqrx/rtl_433), archive counts, cached RSS/Atom/JSON Feed items, and the complete protocol catalogue. This action opens no radio device, makes no internet requests and changes no frequency.
2. **SCAN FM BAND (opt-in real RF operation):** requires rtl_power, one available compatible RTL-SDR and confirmation that the device is not used by a plane tracker or protected recording. A single sweep reads 87.5–108 MHz (125-kHz maximum FFT bin request) with an 18-second hard deadline, local cooperative lock, limited CSV buffer and stop button. No automatic rescan or background sweep.
3. Spectrum peaks are always marked *unidentified_rf_energy*. They are NOT identified stations, official frequencies, RDS lock, radio text or calibrated reception quality. The user can put a frequency into the separate RDS field and run a new explicit rtl_fm + redsea session, if the receiver is available.
4. The user can stop a scan. It also stops if the browser stops polling. Another known SDR/Flight Radar process blocks the scan: no kill, service stop, recording deletion or silent retune is permitted.

## Linux commands

    cd ~/TIHULU-TEXT-CENTER
    git pull --ff-only
    python3 -m textcenter receivers
    command -v rtl_power
    command -v redsea
    pgrep -a -f 'readsb|dump1090|rtl_|gqrx|welle' || true

Run python3 -m textcenter serve; open Radio Data (400). If rtl_power is missing, check availability through your system's rtl-sdr package. redsea is needed for FM RDS/Radiotext+, not for spectrum survey.

## Architecture and truthful limitations

- One Nooelec RTL-SDR cannot independently follow 1090-MHz ADS-B and FM in the 88–108-MHz band simultaneously. Existing readsb/dump1090/Flight Radar, protected recordings, welle.io and Radio Center sessions must never be preempted. A common per-device lease broker is mandatory for Survival Kit integration. The current /proc and cooperative-lock checks are conservative but NOT cross-application ownership guarantees.
- FM scanning is the ONLY implemented live *power survey*. There is NO generic automatic decode of DAB, Journaline, TV Teletext, DRM, RTTY, NAVTEX, WeatherFAX or APRS. Each requires its specific hardware mode, decoder, actual signal, licensing/privacy checks and separate acceptance tests.
- RTL-SDR v5 HF Q-branch support does not imply usable HF reception with the attached FM antenna. Suitable LF/HF antennas, direct-sampling configuration, band propagation and a protocol-specific decoder are required.
- The DAB/Journaline decoder may require separate Fraunhofer licenses. A DAB device or welle-cli executable does not establish Journaline support.
- DVB frontend nodes can appear/disappear when devices are unplugged, drivers reset or frontends are unavailable. A path alone does not prove DVB lock or actual Teletext PIDs.
- No received RF text is a verified official emergency alert. Only verified authority services and authenticated CAP integrations may be given emergency status.

## Protocols and dependency checks

Page 860 and GET /api/capabilities enumerate all 31 protocol/service contracts. Required software and missing hardware are kept visible rather than omitted or marked active. The default Background mode is OFF; the app is loopback-only. Full mobile/desktop access via tihulu.lan requires an authenticated TLS-enabled Survival Kit portal and per-user isolation.

## Verification

GitHub CI uses synthetic decoder data and mock rtl_power subprocesses. CI cannot prove real RTL reception, FM RDS/RT+ tags, DAB metadata, DVB Teletext, HF direct-sampling, concurrent flight tracking, Raspberry Pi power use or phone accessibility. Acceptance must include measured, source-attributed output from actual hardware.
