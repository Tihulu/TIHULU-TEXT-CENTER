# Live FM, TV, Recording, Translation and Compute

## Real operation versus connected hardware

FM live streaming uses an explicitly tuned RTL-SDR through rtl_fm and ffmpeg to produce browser MP3. TV live streaming uses a previously authorized local MPEG-TS stream, converted by ffmpeg to fragmented MP4. The TV feature does not itself scan, tune, or extract DVB-T2 from the not-yet-validated Hauppauge WinTV-soloHD 01589. Both offer Start, Stop and optional local recording. The current player requires an active browser listener and heartbeat, and stops its own capture upon disconnect. Nothing auto-records or tunes at startup.

## Startup

    cd ~/TIHULU-TEXT-CENTER
    git pull --ff-only
    python3 -m unittest discover -s tests -q
    python3 -m textcenter receivers
    python3 -m textcenter dvb-diagnose
    command -v ffmpeg
    command -v rtl_fm
    python3 -m textcenter serve

Open http://127.0.0.1:8787/ and select Radio Data (400). Continuous playback is different from the legacy 10–20-second FM listening preview. Recording must be explicitly requested and has an enforced 1 GiB local size limit.

## Live subtitles, original-language transcription and translation

Choose original speech language and translated subtitle language from English (en), German (de), Turkish (tr), in all directions. Choose Auto, CPU, GPU, or NPU for ASR; each selection shows the detected hardware name and whether a matching runtime and offline model are really ready. Device presence is NOT proof of model compatibility.

Local ASR backends are whisper.cpp with a configured TIHULU_WHISPER_MODEL (CPU), faster-whisper/CTranslate2 plus CUDA and TIHULU_FASTER_WHISPER_MODEL (NVIDIA GPU), and verified OpenVINO GenAI NPU or compatible locally provisioned Hailo Whisper HEF/NPY runtime. A Hailo, Apple or NVIDIA device by itself does not automatically run a model. No model downloads or installations are automatic.

Offline translation uses installed Argos Translate EN/DE/TR directed language pairs. CPU and verified CTranslate2 CUDA translation paths are supported where available; there is no automatically assumed generic NPU translation model. The translator and ASR backend are distinct requirements. Speech is processed in bounded chunks, currently around eight seconds, so captions may lag live broadcasts and can be inaccurate on noisy or musical audio.

Original and translated captions are retained separately with medium, language, source session, times and compute selection in SQLite. Download SRT or VTT; an unavailable translator must leave original text intact. Translating an existing saved caption later requires its original speech language and the proper installed offline directed language pair.

## Later transcription of recordings

Radio Data (400) includes a manual saved-recording transcription panel. Select an existing Text Center FM MP3 or TV MP4 recording, original language, optional translated language, and Auto/CPU/GPU/NPU device. The worker reads only an existing managed archive file, never a freely supplied external filesystem path, and opens no tuner. The initial cap is 10 minutes per job, with cancellation and source-attributed text archive. Later translation can be performed without listening to the radio again.

## TV setup and Hauppauge constraint

Hauppauge WinTV-soloHD 01589 is DVB-T/T2/C, separate from the Nooelec RTL-SDR. After connecting it, run python3 -m textcenter dvb-diagnose, lsusb and check kernel DVB/firmware logs. A DVB frontend path does not establish device identity, tuned signal, usable firmware or actual Teletext decoding.

An independent authorized TV service must expose a dedicated local MPEG-TS endpoint on http://127.0.0.1:PORT/stream/CHANNEL. Put fixed known channels in a version-1 JSON file, then set TIHULU_TV_CHANNELS_FILE to its pathname. Example format (illustrative, NOT an actual TV stream):

    {"version":1,"channels":[{"id":"local_tv","name":"Authorized local TV stream","url":"http://127.0.0.1:9981/stream/authorized_channel"}]}

Text Center never submits arbitrary Internet URLs or silently tunes the upstream TV tuner. It requires a user declaration that the upstream has a dedicated tuner lease. A real tuner-owner and DVB transport stream are prerequisites for actual terrestrial reception; importing a channel-list file alone does not provide TV service.

## Concurrency and safety

The single Nooelec cannot independently receive ADS-B 1090 MHz and FM concurrently. Existing Flight Radar, readsb, dump1090, welle.io, Gqrx or recording ownership may block the FM receiver. The current cooperative lock and process detection are conservative but not a shared authoritative broker. Never stop or retune protected services. The standalone web server remains loopback-only; authenticated TLS and device leasing are required for mobile or remote access through tihulu.lan.

All worker, encoder and UI tests in CI use software fixtures. Real SDR reception, DVB-T2 channel tuning, browser playback, full-bitrate recordings, Turkish/German ASR quality and individual GPU/NPU performance still need physical acceptance testing. Default background scanning, AI and recording stay OFF.