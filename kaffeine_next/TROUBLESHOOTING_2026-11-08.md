# TV / Radio recovery — 2026-11-08

Experimental branch: no claim of a verified hardware fix until physical testing. The original system Kaffeine installation is preserved.

## DVB-T2 source and busy frontend

The log has both `Found dvb device : Silicon Labs Si2168` and `Device or resource busy while opening /dev/dvb/adapter0/frontend0`. The driver detected the USB receiver, but another process or unreleased operation may hold the exclusive frontend.

1. Close other TV/SDR applications **normally**; never force-kill unrelated programs.
2. Run `~/.local/bin/tihulu-media-center --diagnose-tuner` or open **Television → Receiver / tuner diagnostics...**. This read-only command prints frontend files, ownership, and user permissions.
3. In **Television → Configure Television → Device 1 → DVB-T2**, select a genuine regional DVB-T2 **Source** instead of **No Source**, then save.
4. Use **Television → Full Antenna Scan...**; the native scanner stops live playback first when requested. Found channels require real tuner lock and broadcast tables.

A process lock prevents duplicate TIHULU app instances. It does not bypass independent Kaffeine/VLC/SDR access or Linux permissions.

## Independent internet playback

- Radio: **Internet radio** searches the Radio Browser API on request; double-click a station or paste an HTTP(S) stream. Saved favorites use a separate list from DAB.
- TV: **Television → Web TV / Internet channels...** downloads a country M3U catalog from iptv-org only when requested, filters names, supports favorites, and plays through the application's libVLC engine. The list is not proof of stream availability.
- DAB still requires the optional welle-cli runtime and a compatible RTL-SDR/Soapy device. DVB-T2 does not automatically supply DAB, FM, AM, or LW tuning.

## Single-line launcher

`~/.local/bin/tihulu-media-center --software-video`

Do not paste a trailing backslash. The previously supplied shell input joined two commands, causing an Unknown options error.

## Preview-branch installation

```bash
git clone --depth 1 --single-branch --branch fix/tihulu-media-radio-dvb-2026-11-08 https://github.com/Tihulu/TIHULU-TEXT-CENTER.git tihulu-media-fix
cd tihulu-media-fix
bash kaffeine_next/install.sh
```

Review the installer first; it uses APT for system dependencies and builds a separate pinned Kaffeine v2.0.19 fork. This code has not yet been exercised on the user's computer.

Unresolved items in this PR: live subtitle flicker/offset, NLLB model testing, model-market selection badges, dedicated analogue tuning and replacing the installed icon with the supplied portrait logo.
