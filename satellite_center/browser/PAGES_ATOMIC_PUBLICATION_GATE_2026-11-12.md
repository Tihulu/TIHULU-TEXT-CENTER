# Satellite Center — SHA-pinned atomic Pages publication gate

**Disposition:** REVIEW ONLY / NO PUBLISH. This is an operational *proposal* and an immutable Git-object manifest, **not** deployment authorization, a Pages PR, a website recovery confirmation or source CI waiver. For [Issue #78](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/78), cross-referenced to [central Issue #75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75). Separate [WebUSB Draft #95](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/95), [PWA cache Draft #101](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/101) and [native EXIT-01 Draft #92](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/92) are unchanged.

## 0. Freeze and provenance — immutable source only

| Role | Commit / release reference |
| --- | --- |
| Original Satellite native feature Draft #37 | `670e0ddcf029c8fcc9b0cef403bf76cf37613fcb` |
| WebUSB visual/runtime Draft #95 | `f2be8f210ce10e0c1462cc2a3edaba854d424311` |
| Approved-for-review *candidate* PWA Draft #101 | `558dcb359b13eedafdc303fa9f321deab9d3ae94` |
| Existing published `gh-pages` baseline / rollback tree | `854b1109c04c5f8e9a22d1ee3bb999a16d9d4b7d` |
| Strict checker `scripts/verify_satellite_pages_bundle.py` | Git blob `4beac5d1eb0e0bc1638cf85dca3532bf68578035` at candidate source |
| Proposed service worker `satellite-sw.js` | Git blob `ed5a0b78475beb2a4c723c657f5599fef7d54dd8` at candidate source |

**Machine-readable 50-file manifest:** [`PAGES_ATOMIC_ASSET_MANIFEST_2026-11-12.json`](./PAGES_ATOMIC_ASSET_MANIFEST_2026-11-12.json). Each of the 50 rows has the **full repository path, total copy order 01–50, stage, source Git blob SHA-1, pinned published blob SHA-1 or explicit ABSENT, and 31-file strict-parity membership**. It records original #95 hashes for **all 50** assets: ten directly retrieved and the other 40 verified byte-identical across #95→#101 by the exact commit comparison (which changed only the two HTML files and SW among publication assets). These are measured Git object hashes, **not fabricated SHA-256 values**. A future authorized staging step must additionally compute reproducible byte-level SHA-256, file sizes and signed artifact hashes from the actual stage and compare them with the archived release manifest.

**Branch safety:** `gh-pages` was checked identical to the pinned baseline; any move of either source Draft head or `gh-pages` **invalidates this release candidate**. The GitHub Pages URL must be verified against actual repository Pages settings/custom domain; expected project-scoped origin is `https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/browser/`, not independently measured as live and healthy here.

## 1. Exact differences: nine of 31 parity-checked shared files

All paths below are exact repository paths. The old eight-file list was against #37. **`reception.html` becomes the ninth against current #95/#101.** The #101 PWA changes only `index.html`, `reception.html`, `satellite-sw.js` relative to #95 among these ten inspected browser runtime paths. The other seven differing shared file blobs are identical on #95 and #101. Hashes are Git blob SHA-1 (40 hex digits).

| Path | #95 blob | #101 target blob | published `gh-pages` baseline blob |
| --- | --- | --- | --- |
| `satellite_center/browser/index.html` | `202669682fed6787607f6a808b80008a91c0ed3b` | `659aa4ce28404e19ec89888cf28814dafec510ba` | `4f832342ebcdcf49b57b0c7b85f9c21b0072a3ea` |
| `satellite_center/browser/reception.html` | `44b4f2a62a3ac3a0ec47eba57becb93b274822ba` | `ac1fb0335e84536fc6115e127af91fff339938eb` | `2ea220432afe208c741ce9187101b97831453abf` |
| `satellite_center/browser/auto_mission.mjs` | `8d2cd29f7a30965df037a6be8404866c1561ce4e` | `8d2cd29f7a30965df037a6be8404866c1561ce4e` | `c2fa4fe18ad24443efdbfe830eea6192bac957b7` |
| `satellite_center/browser/auto_reception_ui.mjs` | `f12066f0a569a68df13816f1edfdae5744d91033` | `f12066f0a569a68df13816f1edfdae5744d91033` | `290e5fc02c78173b6963e44a5ebd9a51c947b074` |
| `satellite_center/browser/browser.js` | `8c6e51df6552f424b3ff269d226322ef1dec7795` | `8c6e51df6552f424b3ff269d226322ef1dec7795` | `73dcd6f731539c97222ce0b53a9a0f1687c4b400` |
| `satellite_center/browser/browser.css` | `643e3e3db249fa37873ff89f4751d4e94b2797f8` | `643e3e3db249fa37873ff89f4751d4e94b2797f8` | `7442995c8cd5dcaff8ca640c10dbbda62370fa59` |
| `satellite_center/browser/location_search.mjs` | `095d09c6035a4a12b989a425d8d6f50f8629a4d8` | `095d09c6035a4a12b989a425d8d6f50f8629a4d8` | `285d8a3dc97d18069dcc0f019a70479ef15f4efd` |
| `satellite_center/browser/satellite_maps.mjs` | `2953d2f65d73a7c90847134f21dd1e363829eb0f` | `2953d2f65d73a7c90847134f21dd1e363829eb0f` | `8dca91e5a30c111465abcc2b8bd0a115971d9805` |
| `satellite_center/browser/compute_selector.mjs` | `3a047d7254473cee80f203976df44e32770b6765` | `3a047d7254473cee80f203976df44e32770b6765` | `e1d9738ea367b57ab49c736427687334b4a263b7` |

Source-relative published line-diff counts and review meaning, independently verified in [previous detailed recovery review](./PAGES_RECOVERY_REVIEW_2026-11-12.md):

- `index.html`: +84/−18 lines; 4 sections, 3-step UI, PWA launch, responsive labels/styles.
- `reception.html`: +14/−14; Images & Data navigation, language/3-step shell and CSS key.
- `auto_mission.mjs`: +1/−1; older Qt WebEngine-safe property check.
- `auto_reception_ui.mjs`: +1/−1; same property-check compatibility.
- `browser.js`: +521/−59; pass-window/candidates, WebUSB lifecycle, RF/browser schedule and local capability boundaries.
- `browser.css`: +126/−0; four-section responsive layouts, scoped chart CSS preserving Leaflet internals.
- `location_search.mjs`: +17/−6; country/city aliases and optional native-vs-web location behavior.
- `satellite_maps.mjs`: +340/−33; Earth/Sky tracking and coverage/source fallback.
- `compute_selector.mjs`: +37/−1; GPU/NPU capability descriptions, never in-browser compute claims.

**No cherry-picking individual changed lines.** The source-selected 31 files are **byte-equality release contract**; copy the exact reviewed file blobs, not reconstructed/diff-applied snippets.

## 2. Missing published assets — separate from strict parity list

The complete 50-path tree contains **33 matching existing files, nine different existing files, eight missing on current `gh-pages`**. The eight absent files lie **outside** the strict 31 shared asset checker: that gate can be green without a healthy new WebUSB/PWA import graph. Their source SHA-1 and required staging status:

| Missing exact path | #101 source Git blob | Role |
| --- | --- | --- |
| `satellite_center/browser/leaflet.css` | `2961b7618a57617d1015d31d2094c425c3d86ce9` | Optional map/Leaflet asset |
| `satellite_center/browser/leaflet.js` | `a3bf693d0fcaff885cc5f21b3a699aaa567b3533` | Optional map/Leaflet asset |
| `satellite_center/browser/pass_candidates.mjs` | `ea10c0e2b122a35fdef8c05e09919c7201c885b9` | Required local ESM / SW asset |
| `satellite_center/browser/pass_window.mjs` | `63804809f31cf55d065200b926d2eb5eb2853b60` | Required local ESM / SW asset |
| `satellite_center/browser/web_pwa.mjs` | `e1eaf4a88588b19a41e5df51abc5efdd087b4d70` | Required local ESM / SW asset |
| `satellite_center/browser/web_shell.mjs` | `719265fb79c1e5d68132601392c4979a02da7e31` | Required local ESM / SW asset |
| `satellite_center/browser/webusb_lifecycle.mjs` | `e6e8eb50877ec6cff7393f1c6a39735d540f71ac` | Required local ESM / SW asset |
| `satellite_center/browser/satellite-sw.js` | `ed5a0b78475beb2a4c723c657f5599fef7d54dd8` | Service worker |

**Failure chain if only nine shared files are copied:** static `browser.js` imports `pass_candidates.mjs`, `pass_window.mjs`, `webusb_lifecycle.mjs`; their absence prevents entrypoint execution. HTML imports `web_shell.mjs` and `web_pwa.mjs` and registers `satellite-sw.js`. Optional Leaflet JS/CSS provides a raster street-map option; world-outline `natural-earth-land-110m.geojson` and `cities-de-tr.json` already match their source blobs and must remain bundled for offline fallback.

No live-browser 404 is inferred from Git object absence alone. Verify the actual published origin and network console separately.

## 3. Complete 50-asset copy sequence — plan for a **single tree commit**

The phase ordering below is **preparation order within a disposable staging tree only**. **There must be no incremental pushes to `gh-pages`.** No native Qt/Python, RF recordings, tests, JS fixtures, documentation, Text modules, user secrets, or other apps are copied to production.

#### 01-optional-assets — 7 files

```text
01  satellite_center/browser/cities-de-tr.json
02  satellite_center/browser/icon-192.png
03  satellite_center/browser/icon-512.png
04  satellite_center/browser/icon.svg
05  satellite_center/browser/leaflet.css
06  satellite_center/browser/leaflet.js
07  satellite_center/browser/natural-earth-land-110m.geojson
```

#### 02-required-esm-dependencies — 35 files

```text
08  satellite_center/browser/auto_mission.mjs
09  satellite_center/browser/auto_reception_ui.mjs
10  satellite_center/browser/capture_duration.mjs
11  satellite_center/browser/chained_capture.mjs
12  satellite_center/browser/compute_backends.mjs
13  satellite_center/browser/compute_selector.mjs
14  satellite_center/browser/file_format_inspector.mjs
15  satellite_center/browser/fm_iq_demod.mjs
16  satellite_center/browser/fm_wav_record.mjs
17  satellite_center/browser/iq_analysis.mjs
18  satellite_center/browser/iq_analysis_ui.mjs
19  satellite_center/browser/iq_intelligence.mjs
20  satellite_center/browser/location_search.mjs
21  satellite_center/browser/orbit_clock.mjs
22  satellite_center/browser/pass_candidates.mjs
23  satellite_center/browser/pass_protocol_catalog.mjs
24  satellite_center/browser/pass_sort.mjs
25  satellite_center/browser/pass_window.mjs
26  satellite_center/browser/reception_catalog.mjs
27  satellite_center/browser/results_zip.mjs
28  satellite_center/browser/satellite_calendar.mjs
29  satellite_center/browser/satellite_imagery.mjs
30  satellite_center/browser/satellite_images_ui.mjs
31  satellite_center/browser/satellite_maps.mjs
32  satellite_center/browser/saved_satellite_protocols.mjs
33  satellite_center/browser/schedule_controller.mjs
34  satellite_center/browser/signal_discovery.mjs
35  satellite_center/browser/sstv_capture_diagnostics.mjs
36  satellite_center/browser/sstv_robot36.mjs
37  satellite_center/browser/usb_diagnostics.mjs
38  satellite_center/browser/usb_live_probe.mjs
39  satellite_center/browser/user_protocol_ui.mjs
40  satellite_center/browser/web_pwa.mjs
41  satellite_center/browser/web_shell.mjs
42  satellite_center/browser/webusb_lifecycle.mjs
```

#### 03-entrypoints-css — 4 files

```text
43  satellite_center/browser/browser.css
44  satellite_center/browser/browser.js
45  satellite_center/browser/reception.css
46  satellite_center/browser/reception.mjs
```

#### 04-html-and-manifest — 3 files

```text
47  satellite_center/browser/index.html
48  satellite_center/browser/manifest.webmanifest
49  satellite_center/browser/reception.html
```

#### 05-sw-last — 1 files

```text
50  satellite_center/browser/satellite-sw.js
```

Stages 1–4 prepare all static dependencies and leaf entrypoints; stage 5 writes the worker **last**, so it does not activate a mixed asset graph during staging. **Only one subsequent, explicitly approved publish commit/push** can switch the branch. Git commits change a tree atomically; CDN/page caches and existing tabs **are not atomic** and require rollout observation.

The exact stage copy contract is the ordered `files[]` in the companion JSON. Expected staged Git change against the frozen `gh-pages` baseline is **9 modified** plus **8 added** paths (33 already-matching files remain byte-identical). Do not modify or delete unrelated paths.

### Illustrative *future* nonpublishing stage commands — NOT EXECUTED

Run only in an isolated temporary checkout **after separate review authorization** (not in a working repository with uncommitted user files). Provide the actual reviewed JSON file path as `MANIFEST`; `jq`, Git and an isolated destination are required.

```bash
set -euo pipefail
SRC=558dcb359b13eedafdc303fa9f321deab9d3ae94
BASE=854b1109c04c5f8e9a22d1ee3bb999a16d9d4b7d
MANIFEST=/absolute/path/to/PAGES_ATOMIC_ASSET_MANIFEST_2026-11-12.json
git fetch origin gh-pages fix/satellite-pwa-cache-asset-sync-2026-11-12
test "$(git rev-parse origin/gh-pages)" = "$BASE"
test "$(git rev-parse origin/fix/satellite-pwa-cache-asset-sync-2026-11-12)" = "$SRC"
STAGE=/absolute/path/to/fresh-empty-review-worktree
git worktree add --detach "$STAGE" "$BASE"

jq -r '.files | sort_by(.order)[] | .path' "$MANIFEST" |
while IFS= read -r path; do
  mkdir -p "$STAGE/$(dirname "$path")"
  git show "$SRC:$path" > "$STAGE/$path"
  expected="$(jq -r --arg path "$path" '.files[] | select(.path==$path) | .source_pr101_blob_sha1' "$MANIFEST")"
  actual="$(git -C "$STAGE" hash-object "$path")"
  test "$expected" = "$actual" || { echo "STOP: SHA mismatch $path" >&2; exit 1; }
done

git -C "$STAGE" add -- satellite_center/browser/
git -C "$STAGE" diff --cached --name-status
# Must show precisely 9 M and 8 A among the 50 paths.
# Additional SHA-256, file sizes and MIME asset manifest: archive for reviewer.
(cd "$STAGE"; jq -r '.files[].path' "$MANIFEST" | xargs -r sha256sum)
# NO COMMIT, NO PUSH, NO DEPLOY IN THIS TASK.
```

Important: review-stage `git show` reads **Git objects at the exact immutable source SHA**; never source files from an unpinned branch working tree. The source PR itself is NOT a publication branch. If Pages is branch-protected, use its owner-approved review procedure rather than bypassing controls. Do not claim release until reviewers validate the complete staged byte hash manifest, static ESM closure and active service worker on an HTTPS staging origin.

## 4. Cache v1 → v2, worker scope and noninterference

- #95 includes `satellite-sw.js` Git blob `bea82f417e0c05b525765e6ad6a776d270147ce2`, version **`satellite-webusb-shell-20261112-v1`**. It used cache-first/path-normalized retrieval; stale JS could survive URL `?v=` changes.
- #101 changes it to exact source blob `ed5a0b78475beb2a4c723c657f5599fef7d54dd8`, version **`satellite-webusb-shell-20261112-v2`**. It requires all **42 critical** app-shell files to precache or abort SW install (old worker remains active); treats the seven icons/Leaflet/geography items as optional offline additions; and uses **network-first, `cache:"reload"`** for allowlisted app assets, with offline fallback only after a genuine network error. HTTP 404/500 responses must not be silently masked by old cached bytes.
- #101 additionally changes the two HTML pages' `browser.css?v=20261112-cache-v2` key. The root manifest scopes `id` to `/TIHULU-TEXT-CENTER/satellite_center/browser/` with `start_url` and `scope` = `./`; `web_pwa.mjs` registers `./satellite-sw.js` only on supported same-origin HTTP(S) locations, and does not register in the native companion mode.
- On activate, v2 deletes **only** CacheStorage keys beginning with `satellite-webusb-shell-` whose name is not v2, and calls `clients.claim()`. Never clear the whole origin's CacheStorage, cookies, IndexedDB, localStorage, File System Access handles, downloaded IQ/WAV/PNG, browser permissions, or another TIHULU app's data.
- The worker has **no WebUSB RF scheduler**; no capture/decoder jobs are admitted in SW, and `.cu8/.iq/.wav/.zip/.bin`, `/api/`, cross-origin tiles/TLE/CDN data are **not cached**. Browser on-demand jobs require an awake client tab and deliberate Connect/Stop/Disconnect. A browser crash cannot guarantee device lease release.
- First site visit after a new publication should allow a normal version update. For a **stuck preexisting v1 controller**, only *after the user has explicitly stopped/disconnected their own WebUSB capture*, a browser reviewer may run a scoped `registration.update()` for the exact Satellite scope, confirm v2 is activated, then manually reload the Satellite pages. **Never force reload or call `skipWaiting` from another app during active capture.** No global service-worker unregister during normal forward upgrade.
- Even with the v2 shell cached, fresh TLE data, OSM tiles, the remote `esm.sh` `@jtarrio/webrtlsdr@3.0.7` driver and `satellite.js@6.0.1` require Internet; first-run airplane-mode full orbit/RF is not guaranteed.

## 5. Exact preview / acceptance matrix before *any* publication authorization

1. **Branch/asset provenance:** confirm baseline and both PR refs match pinned commits. Validate **all 50 Git blobs** from companion JSON plus freshly computed SHA-256; verify expected **9 M + 8 A**, no other changed paths, no source-to-Pages byte diff after a *staged* copy. Check third-party JS/Leaflet/Natural Earth/city data licenses and bundled icon identity.
2. **Static HTTP(S):** serve a **private** nested project-path HTTPS preview (not public Pages). Verify 200 for **all 50** exact URLs, correct JS/MJS, CSS, manifest, GeoJSON, PNG, SVG types, relative query keys, no console import/DOM/MIME/CORS errors. Explicitly fail preview when any of the **42 required** files is missing. Verify the optional missing Leaflet tile renderer fails back to bundled world outlines without an invented offline street map.
3. **Four modules:** verify Receiver & Planner at `index.html`, Images & Data at `reception.html`, Earth / Sky at `index.html#satellite-tracking-maps`, and Signal Analysis at `index.html#iq-analysis`. Check forward/back navigation, real map/sky UI, TLE imports, no mandatory `127.0.0.1:8791` service and no dead `../../` app-center dependency.
4. **UI and accessibility:** compare desktop/tablet/mobile Chromium screenshots against the owner's native Qt 0.3.0 preview10 design; differentiate accurate "Chromium WebUSB Edition" from native OS SDR. Test three-step auto-capture UI, keyboard focus, screen reader state, default English and shell Turkish/German, and audit untranslated dynamic messages. **Pixel-perfect screenshot parity has not been measured by this review**.
5. **WebUSB synthetic:** HTTPS secure-context and direct user gesture; mock chooser deny/close, external/busy receiver and delayed USB open/Stop/Disconnect; no native driver unbind, `readsb`/`tar1090`/Gqrx/welle.io stops, or worker-owned RF. Unsupported Firefox/Safari must retain file/planner/map modes without fake WebUSB.
6. **Capture honesty:** WAV, CU8 and BOTH where compatible; **128 MiB in-memory raw IQ cap** and segmented simple capture ≤60 seconds; at 2.048 MS/s raw CU8 needs ≤32 seconds per 128 MiB segment; planned **6s gaps** are not continuous Meteor LRPT; optional File System Access streaming is separately opt-in and bounded **2,000,000,000 bytes / 900s**. Progress measures actual USB bytes separately from elapsed-time estimates; no synthesized RF, SSTV images, SatDump or Meteor lock.
7. **SW update/rollback preview:** first-install v2, offline after *previous* online load, existing v1 → v2 upgrade (with cache keys checked), missing **required** ESM fail-closed, optional Leaflet fail-safe, changed `?v=` JS/CSS online refresh, HTTP 404 visible, blocked CDN/offline limitations, nested scope, no RF byte caching, no background start or unsolicited reload.
8. **Existing CI gating:** [#101 browser suite 30/30 SUCCESS](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43160403870); [Text Python 3.11–3.13 SUCCESS](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43160404011); [Debian no-hardware SUCCESS](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43160403949); [Linux/Windows/macOS portable 4/4 runtime SUCCESS, entire workflow FAIL](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43160403892) on **strict source/Pages parity**. These do **not** constitute a successful live website, physical SDR or actual installed PWA screenshot test.

**Mandatory parity contract, no waivers:** `scripts/verify_satellite_pages_bundle.py` performs direct byte comparison of all **31** selected local source files to `refs/remotes/origin/gh-pages`; it exits nonzero on any missing/differing asset. Before publication while the old Pages branch remains active this MUST be red (nine differences). A disposable staged-tree byte check can demonstrate candidate parity **without falsely reporting GitHub branch parity green**. Only *after* a separately approved and completed publication, refresh `origin/gh-pages` and run the original script unchanged on reviewed source #101; it must say **31/31**. Independently recheck the **other 19** manifest files, especially 8 previously missing dependencies. Neither gate substitutes for HTTPS/PWA QA.

## 6. Owner-only publication checkpoint and exact rollback

**Not authorized in this task.** A later release owner must sign the source SHA, 50-asset SHA-256/Blob manifest, rendered preview, CSS/ESM closure, service-worker transition, EN/TR/DE UI, recording-safety and data-protection results. Reviewer creates a **separate publication review PR**, not a source merge. The final approved tree should be **one Git commit** on `gh-pages`, not multi-push partial assets. Reject a branch HEAD drift or protections conflict; **never force-push or bypass checks**. GitHub Pages CDN propagation is still not instantaneous or atomic across independent clients. Record the final live commit `RELEASE` and resulting URLs before monitoring/rollback.

### Exact byte-restoring rollback commands (FUTURE ONLY, NOT RUN)

If a separately authorized publication fails, stop further release changes, communicate HOLD, stop/disconnect app-owned WebUSB jobs *before reloading client pages*, and restore the **previous pinned Pages tree** for all 50 manifest assets. This example assumes `RELEASE` is the exact commit currently at origin/gh-pages, a clean repository, owner approval and available `MANIFEST` from this review.

```bash
set -euo pipefail
BASE=854b1109c04c5f8e9a22d1ee3bb999a16d9d4b7d
MANIFEST=/absolute/path/to/PAGES_ATOMIC_ASSET_MANIFEST_2026-11-12.json
RELEASE=REPLACE_WITH_VERIFIED_40_HEX_PUBLICATION_COMMIT
[[ "$RELEASE" =~ ^[a-f0-9]{40}$ ]] || { echo "STOP: replace RELEASE with exact published SHA" >&2; exit 1; }
git fetch origin gh-pages
test "$(git rev-parse origin/gh-pages)" = "$RELEASE"
git cat-file -e "$BASE^{commit}"
ROLL=/absolute/path/to/fresh-empty-rollback-worktree
git worktree add --detach "$ROLL" "$RELEASE"

jq -r '.files | sort_by(.order)[] | [.path, (.baseline_pages_blob_sha1 // "ABSENT")] | @tsv' "$MANIFEST" |
while IFS="$(printf '\t')" read -r path old_blob; do
  if [ "$old_blob" = "ABSENT" ]; then
    git -C "$ROLL" rm -- "$path"
  else
    git -C "$ROLL" restore --source="$BASE" --staged --worktree -- "$path"
    test "$(git -C "$ROLL" hash-object "$path")" = "$old_blob"
  fi
done

git -C "$ROLL" diff --cached --name-status
# Expected reversal: 9 modified back + 8 new files deleted.
# Require independent review and written rollback approval BEFORE next lines.
# git -C "$ROLL" commit -m "rollback(satellite pages): restore pinned pre-WebUSB Pages tree"
# git -C "$ROLL" push origin HEAD:refs/heads/gh-pages
# NO FORCE; remote must still equal RELEASE. DO NOT EXECUTE WITHOUT APPROVAL.
```

**Service-worker rollback caveat:** baseline `gh-pages` did not have `satellite-sw.js`. A byte-exact rollback removes that file, **but does not automatically unregister an already-installed v2 service worker** on clients. To retire it safely for an affected user, the user/reviewer must first stop and disconnect their own USB session, then use a **scoped** browser cleanup on this Satellite site only:

```js
const target = new URL("/TIHULU-TEXT-CENTER/satellite_center/browser/", location.origin).href;
const reg = await navigator.serviceWorker?.getRegistration(target);
if (reg?.scope === target) await reg.unregister();
for (const key of await caches.keys())
  if (key.startsWith("satellite-webusb-shell-")) await caches.delete(key);
// Reload ONLY Satellite Center after user confirms no ongoing capture.
// Never clear the whole origin's site data or another app's caches/settings.
```

If broad installed-PWA cleanup must work without end-user DevTools, **separately approve a tiny v3 retirement/tombstone SW** served at the *same* `satellite-sw.js` URL and scope, clearing only `satellite-webusb-shell-*` caches, calling `registration.unregister()` and never opening hardware. That optional tombstone is **an explicitly documented exception to byte-exact restored baseline** and requires its own preview/rollback review; do NOT silently include it in the baseline restore or treat a missing worker file as reliably removing a previously installed client registration. The original 31 shared pages remain the original bytes, while the source #101 vs the rolled-back site intentionally fails parity again.

### Rollback confirmation

1. Check current remote branch commit is the rollback commit; ensure every formerly present baseline blob SHA equals this manifest's `baseline_pages_blob_sha1` and all eight new extras are absent (unless a separately approved tombstone exception).
2. Verify HTTPS content/MIME and old website navigation with new/incognito **and old installed client** after targeted SW cleanup and controlled reload; do not claim v1/v2 cache removal by Git alone.
3. Confirm no change to user IQ/WAV/PNG archives, browser localStorage, device permissions, other-app caches or native EXIT-01 code. Record browser old/new controller versions and real 404 results.
4. Keep #101 source vs rolled-back Pages **strict parity red** until a newly approved aligned release; **no test waiver or false green**. Log the original release SHA, rollback commit SHA, owner, impacted assets and verified client recovery on #78/#75.

**Hard stop:** no Pages branch write, no main/PR #37/#92/#95/#101 source edit, no private recordings change, no real SDR, SatDump, deployment, merge or release was performed to produce this document.
