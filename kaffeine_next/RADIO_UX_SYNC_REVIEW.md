# TIHULU Radio · UX and sync review (2026-11-08)

This is native Qt / Kaffeine code, not a screenshot prototype.

## One window, five radio modes

The Radio page now has a compact station readout and five modes:
- DAB+: real block/service selection, Favorites, library, actual SNR, DLS, slideshow and original live caption canvas. Station library and programme info stack vertically when the window is narrow.
- Internet radio: worldwide country/station search, favourites, stream test and alternate URL; no antenna or USB needed.
- Vintage FM/AM/LW: authentic analogue dial and frequency, volume/mute, PCM VU (not fake RF strength), controlled RTL-SDR. An independent readout shows the selected DAB or Internet station without pretending it is the FM frequency.
- AI subtitles / lyrics: auto/manual speech language, selected translations, singing detection, available language packs, buffer and offset, local/online TXT/LRC and audio-driven LyricSync.
- RF Lab: FFT, spectrum, constellation, waterfall, multiview and advanced decoder options.

The chosen radio mode persists across app launches. Smaller layouts use multi-row controls and resizable RF charts instead of clipped horizontal rows. Existing TV, Hardware, local media, recording, favourites and AI model panels remain in the application.

## Buffer / offset facts

The earlier radio buffer was capped at 20,000 milliseconds. The UI and the actual libVLC per-media network-caching setting now both allow 0–60,000 milliseconds (a finite safety ceiling).

Recommendation = 6,000 ms captured audio + observed p80 Whisper processing + sentence carry delay + 3,000 ms safety margin, rounded to 500 ms. This is a compute estimate, NOT a measurement of audio actually reaching the speakers.

An auto recommendation saves a requested value for NEXT station tune. The active stream has a separately recorded applied value, used for subtitle scheduling and the progress bar. No automatic audio restart by default. If users explicitly allow auto audio restart, it is limited to at most once per 180 seconds and at least 5,000 ms of meaningful increased demand. Manual Apply restarts the live DAB audio and resets the AI worker to prevent using the previous timeline. An interruption is possible.

The 300 ms caption UI tick and periodic buffer estimation do not themselves restart or retune the radio. The regular spoken ASR/translation offset is separate from music lyric offset.

## Singing and lyrics

- Show original plus target-language translations when installed translation models can produce them and Whisper identifies the current vocal language reliably.
- Lyrics-source language is now separately selectable from spoken programme language. Choosing DE / EN / TR / other known song source enables immediate text translation of available LRC lyrics; Auto waits for confident live audio recognition and avoids leaking a presenter's language into the next song.
- A real bug: timed LRC with plain text for audio matching was falsely tagged untimed. Now a retrieved LRC with timestamps stays in timed_lrc mode.
- Plain lyrics remain without fictional timestamps; they appear only after actual ASR matches the line. A verified matching line can carry its own translation back to the player, and timed LRC may reuse that translation only for that exact line.
- LyricSync is now rate-limited: two consistent ≥92% matches, 30 second cooldown and at most 250 ms per change. Outliers over 15 seconds are rejected.
- Unchanged lyrics are not repainted every caption polling tick, reducing visible flicker.

## Testing limitations

Passing source tests and compiling Qt proves these code paths build; it does NOT prove speaker-output sample-accurate lip sync or reliable translations on a physical GPU. Test 800px viewport, real DAB speech/music language changes, manual offsets, cache application and all 5 radio pages on the actual host before calling the PR production-ready. Retain PR #38 in DRAFT.
