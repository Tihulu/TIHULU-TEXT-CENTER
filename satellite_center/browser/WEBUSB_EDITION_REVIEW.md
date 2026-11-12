# Satellite Center WebUSB Edition — source integrity and website publication review

Engineering status: **Draft browser-only source, NOT published**. Original native Satellite PR [#37](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/37), exact parent `670e0ddcf029c8fcc9b0cef403bf76cf37613fcb`; independent EXIT-01 shutdown PR [#92](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/92) remains **unchanged/unmerged**. This edition uses only browser-owned Chromium WebUSB; it does not call Linux `rtl_sdr`, `systemctl`, SatDump or the Qt hardware bridge on the public site.

## Four-section navigation and UI parity boundaries

1. **Receiver & Planner:** explicit WebUSB chooser, permission/claim diagnostics, device status, honest sample progress, optional CU8 and FM-demodulated WAV or BOTH, TLE pass planner, local candidate and browser scheduler.
2. **Satellite Images & Data:** the same three-step Auto-Capture & Decode sequence, existing real Robot36 audio and local image import paths, explicit verified-source labels versus separate NASA online data. No fabricated decoder image.
3. **Earth / Sky:** existing bundled Natural Earth overview, optional OpenStreetMap/Leaflet tiles, TLE-based satellite ground tracks, Sky view and pass-time previews. Orbit forecast is not RF reception or a receiver geolocation fix.
4. **Signal Analysis:** actual CU8 FFT/spectrum, waterfall, digital level, optional audio preview and progressive local discovery. No imaginary APRS, Iridium, Meteor LRPT or GNSS decoding.

The native Qt v0.3.0 preview10 workflow is the **functional comparison target**. The browser retains the existing native-related source layout and navigation, but no pixel-perfect screenshot-diff or real Chromium responsive screenshot was executed by this code-only task; visual parity remains a release QA gate. New shell labels and primary controls are available in **English (default), Turkish and German**, persisted locally; not all legacy dynamic module messages have been translated. Do not certify full localization until audited.

## Direct WebUSB limits and ownership

- USB permission is opt-in, user initiated in secure Chromium. A granted 0bda:2838 RTL-SDR is **not** proof of an open or working radio. Other applications' `readsb`, `tar1090`, `Gqrx`, `welle.io` and their SDR leases are never stopped or unbound by browser code.
- `browser.js` uses the existing `@jtarrio/webrtlsdr@3.0.7` WebUSB module. Connect epoch + pending tab-owned device references reject late async provider grants after Stop/Disconnect/pagehide and try to close **only this tab's owned USB handles**. A tab or OS crash remains best-effort, not guaranteed physical teardown.
- Capture output selection is **CU8**, **WAV**, or **BOTH**, derived from the **same measured USB sample sequence** where the target supports FM audio. WAV is demodulated audio, **not** proof of Robot36 lock. Mercury/Meteor LRPT still needs real CU8 and a compatible external decoder.
- Browser automatic/scheduled captures use independently saved segments of at most **60 seconds**, with **6 seconds planned buffer gaps**; the actual 128 MiB in-memory CU8 cap reduces the per-segment time from 60s to **32s** at 2.048 MS/s (and **60s** at 1.024 MS/s). File System Access streaming is conditional on a permitted explicit picker and is constrained by a 2 GB raw-IQ safety cap. Existing underlying `captureBudget` also validates 1–900s file-stream scenarios; **the current manual/auto UI schedules longer requests as separate parts, not as a gapless 900s recording**.
- Capture progress displays **elapsed-wall-time percentage as an estimate**, separately from **actual I/Q bytes obtained through `readSamples`**. It does not infer real bitrate, image quality, satellite identity or successful decoding. Browser captures require a **visible awake tab**; service worker is shell cache only and **cannot** receive RF in background.
- PWA registration uses same-origin relative `./satellite-sw.js`. The worker caches the local shell and successfully retrieved same-origin assets, excludes RF/IQ/WAV/ZIP and API endpoints, and never invokes USB. Fresh satellite.js CDN modules, `webrtlsdr` driver and uncached TLE/provider data still require Internet; fully offline, first-run real RF and fresh orbital predictions are **not** claimed.

## Existing REG-08 eight-asset source/Pages divergence: immutable read-only evidence

The published Git branch `gh-pages` remains `854b1109c04c5f8e9a22d1ee3bb999a16d9d4b7d`. The original unmerged native feature parent `670e0ddcf029c8fcc9b0cef403bf76cf37613fcb` differs from it in these browser assets. The following are immutable Git **blob SHA-1**, `source → published`, **prior to this new browser branch**:

| Path under `satellite_center/browser/` | Original PR #37 blob | Published gh-pages blob | Source delta / review note |
| --- | --- | --- | --- |
| `index.html` | `f2a05de924b628ce6f1e2f6d3ccbf2b4e5f3f406` | `4f832342ebcdcf49b57b0c7b85f9c21b0072a3ea` | 72h elevation, station pass/calendar, preview/map UI |
| `auto_mission.mjs` | `8d2cd29f7a30965df037a6be8404866c1561ce4e` | `c2fa4fe18ad24443efdbfe830eea6192bac957b7` | Safer `Object.prototype.hasOwnProperty.call` against older Qt WebEngine |
| `auto_reception_ui.mjs` | `f12066f0a569a68df13816f1edfdae5744d91033` | `290e5fc02c78173b6963e44a5ebd9a51c947b074` | Same one-line capability guard |
| `browser.js` | `74f16367be23a0f84de910040c1293de6d31ece3` | `73dcd6f731539c97222ce0b53a9a0f1687c4b400` | Source adds pass-window/planner, native controls and wider 2.048MS/s options |
| `browser.css` | `4bde086d23fd90e70edb7302bb3101d3eb7ab8f7` | `7442995c8cd5dcaff8ca640c10dbbda62370fa59` | Source pass-preview layout absent on Pages |
| `location_search.mjs` | `095d09c6035a4a12b989a425d8d6f50f8629a4d8` | `285d8a3dc97d18069dcc0f019a70479ef15f4efd` | Native geocode bridge and Sydney alias improvements |
| `satellite_maps.mjs` | `2953d2f65d73a7c90847134f21dd1e363829eb0f` | `8dca91e5a30c111465abcc2b8bd0a115971d9805` | Native Skyfield track and map/coverage preview integration |
| `compute_selector.mjs` | `3a047d7254473cee80f203976df44e32770b6765` | `e1d9738ea367b57ab49c736427687334b4a263b7` | Native GPU inventory and honest capability labels |

New UI edition modifies **source** `index.html`, `browser.js`, `browser.css`; their current blob hashes differ again. This is **not** a copy of older published assets and **does not** itself resolve the Pages/source parity failure. The existing strict 31-asset parity gate is intentionally left unchanged and must remain visibly **RED** until a separate, approved site synchronization.

## Separate owner-controlled safe publication path (NOT EXECUTED)

1. **Freeze** reviewed PR #37, new browser Draft PR, currently published `gh-pages` SHA and its branch protection/rollback. Review all 31 browser manifest assets against a pinned source build; include new JS/CSS, icons, service-worker registration/scope, first-run CDN dependence, and optional map fallback.
2. **Review exact eight-file divergences** separately from new UI changes. Keep the two one-line compatibility changes distinct from larger controller/maps additions; certify that native-only behavior is never invoked on public Pages. Compare and archive source/package and published **SHA-256 + Git blob SHA-1** file inventories under a separate release artifact.
3. **Preview** the site under a disposable local HTTPS or separately approved non-publishing staging origin. Run Chromium real DOM/navigation/mobile/tablet/PWA/desktop tests, keyboard and screen-reader checks, offline shell loads, JS syntax, 3-step actions, station/TLE/asset loading and WebUSB mocks; no actual radio. EN(default)/TR/DE UI coverage is a separate gate.
4. **Only after explicit owner approval**, create a dedicated **publication PR** targeting the approved Pages release flow, preserving provenance, screenshot proof and rollback path. Do not cherry-pick EXIT-01 resource cleanup into a website publication fix, and do not blindly publish unverified full PR #37 native behavior.
5. **Deploy only under separate owner authorization**, then verify live URL cache invalidation, script MIME/relative paths, PWA identity/scope, unchanged external SDR and restored strict 31/31 Pages parity. If any check fails, roll back to pinned `854b1109...` and keep the gate red.

**Not performed:** no `gh-pages` commit, no website deployment, no parity waiver or checksum bypass, no native Qt/Python/backend edits, no real WebUSB/SatDump/SDR, no driver or external process changes, no user recordings moved, no merge, migration or release. References: [Issue #78](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/78), central [#75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75).
