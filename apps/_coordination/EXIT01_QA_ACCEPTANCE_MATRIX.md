# EXIT-01 / RQ-098 — independent cross-app shutdown acceptance matrix

**Checkpoint:** 2026-11-12 | **Coordinator QA:** standalone evidence review | **Gate status:** OPEN — **zero hardware/installed RAM, VRAM, NPU, RF or multi-app service acceptance** | **No merges / deployments**.

Primary requirement: [owner-requested full Quit contract](./OWNER_REQUIREMENT_FULL_SHUTDOWN_MEMORY_VRAM_RELEASE.md). Six-agent distribution: [EXIT01 handoffs](./EXIT01_SIX_PARALLEL_IMPLEMENTATION_ASSIGNMENTS.md). Central [Issue #75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75), QA [Issue #81](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/81).

## Source PR inventory checked

| Agent | Source Draft PR and base | Latest exact PR head checked | Changed-path review | Synthetic CI at that head | Known limitations |
|---|---|---|---|---|---|
| A1 Media | [Text repo #91](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/91), stacked on original Media #67 `4e62e21cd5252df8a04f9ceadc429f4b116412ce` | `9186ba3330c0a051f6172d4065687d9e3e059faa` | 3 paths, only CUDA Whisper, Kaffeine overlay and a test file | **PASS** all four source CI workflows (Text tests, Native TV checks, Kaffeine DVB build, Native DVB/Radio build) | Managed CUDA process and own Qt captions only; CPU model, translators, external FFmpeg and real VRAM remain unverified |
| A2 Flight | [Flight repo #16](https://github.com/Tihulu/tihulu-flight-radar/pull/16), stacked on safety Draft #15 `ae8cad04a7061ebfa9112147e7bc5fab25779313` | `7ae8b9b82b622b1d1e3f9914c89326af29da9784` | 6 paths in `tihulu_flight_radar/` and one test | **PASS** Pi ARM64 + cross-OS CI [run 43151459770](https://github.com/Tihulu/tihulu-flight-radar/actions/runs/43151459770): Debian, Ubuntu, Windows and macOS four jobs all completed SUCCESS | Mixed external/app started `readsb/tar1090` must remain protected; manual paired Stop and real sudo/USB acceptance open |
| A3 Satellite | [Text repo #92](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/92), stacked on original Satellite #37 `670e0ddcf029c8fcc9b0cef403bf76cf37613fcb` | `5ba72b575abd89ce716b5b51033a3df11167267d` | 4 paths `satellite_center/` + one test | Text CI PASS; latest [portable workflow 43152107002](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43152107002) QUEUED and [Debian workflow 43152106975](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43152106975) IN PROGRESS; earlier portable workflow **Pages/source parity FAIL** on the unchanged eight-file baseline | Eight existing `gh-pages` vs source bundle content mismatches (listed below), unverified physical RTL-SDR, pending 1.024/2.048 MS/s decoder rate fix |
| A4 RF Geolocation | [owned branch](https://github.com/Tihulu/TIHULU-TEXT-CENTER/tree/fix/exit01-rfgeo-stop-workers-2026-11-12), stacked on original Geo #16 `6664a04a6247826d71f6adeb795b137fd26de213` | Branch ahead 15 / behind 0 at checkpoint; latest commit SHA not yet captured in a Draft PR | 11 `rf_geolocation_center/` files on owned subtree; tests/CI not yet confirmed | **NOT VERIFIED** | PWA tab-close best effort; native worker/SDR lock and no-foreign-service-stop still need mock CI and real installed acceptance |
| A5 Text | [Text repo #93](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/93), based on retained canonical main `1fffb711bfbb7c4abaf55299fa9240e5db3e1cde` | `063975fe9d4492b874c6084d58869ca09d082f92` | 11 files: `textcenter/`, `web/app.js`, `web/index.html`, isolated test | [Python CI 43151850363](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43151850363) **PASS** on Python 3.11, 3.12, 3.13 | Worker can report STOP_FAILED_PARTIAL on blocked in-process ASR; actual loaded CPU/GPU model and HTTP/RF devices not tested |
| A6 QA | This matrix in central coordinator Draft #82 | Source-only acceptance planning | Coordinator-owned docs only | Not a production acceptance test | No independent AI Tools/Survival Kit implementation; those projects remain owner-managed |

### Pages mismatch blocker (A3, observed GitHub CI)

The [Satellite portable workflow's `pages-source-parity` job](https://github.com/Tihulu/TIHULU-TEXT-CENTER/actions/runs/43151842746) fails because **eight** source files are different from their published `gh-pages` versions: `satellite_center/browser/index.html`, `auto_mission.mjs`, `auto_reception_ui.mjs`, `browser.js`, `browser.css`, `location_search.mjs`, `satellite_maps.mjs`, `compute_selector.mjs`. This is a **pre-existing release parity defect**, not evidence that new Exit behavior fails. It must remain red rather than suppressing the gate, and cannot be fixed by automatically deploying an unreviewed Pages branch.

## 15 mandatory exit-case acceptance matrix

State categories: **MOCK-CODE** = source/fixture coverage exists in a draft but no installed acceptance; **PARTIAL** = only some app scopes covered; **NOT VERIFIED** = no sufficient evidence. **All cases remain OPEN** until actual owner-approved feature/device evidence.

| Test ID | Required proof | Current evidence / status | Next verification |
|---|---|---|---|
| EXIT-01-A | GUI Quit with local CPU LLM, Whisper and translation unloads all app-owned CPU worker/model RAM | PARTIAL: Text synthetic ASR and Media GPU worker; shared CPU/translation ownership not verified | Mock each owned model reference and finally installed per-process RSS and no owner PIDs |
| EXIT-01-B | Quit mid-CUDA inference frees owned CUDA process/context/VRAM and spares others | MOCK-CODE A1 #91; all four source CI workflows PASS | GPU-backed own-PID/VRAM before/after and external CUDA client unchanged, separate authorization |
| EXIT-01-C | Metal/MPS/DirectML GPU model exits cleanly on macOS and Windows | NOT VERIFIED; passing software packaging alone insufficient | Native runtime model teardown on each actual installed target |
| EXIT-01-D | Pi 5 + Hailo-10H owned NPU buffers/VDevice released without disrupting another Hailo user | NOT VERIFIED; AI Tools owner project separate | Owner-approved Pi AI HAT+ 2 runtime device lease and process cleanup check |
| EXIT-01-E | Shared model/session refcount unloads on last owning client only | NOT VERIFIED across different apps; AI Tools Registry draft may contain proposed leases | 2-client deterministic acquire/release/close and remote lease mock, real runtime later |
| EXIT-01-F | External Jan/Ollama/model path/remote GPU host survives Quit; own bridge closes | PARTIAL mock/source contracts; no real paired host proof | Owner/non-owner host simulation and explicit no-global-service-stop assertion |
| EXIT-01-G | Flight Exit preserves external `readsb/tar1090` while closing own child | MOCK-CODE A2 #16 stacked on #15, Pi CI PASS and 4-OS partial | Explicit pair matrix with mixed ownership, then scoped host verification |
| EXIT-01-H | Quit during owned SDR/SatDump/FFmpeg capture cancels own work without deleting recordings | MOCK-CODE A3 #92 / A5 #93; no real receiver test | Stateful file/time/lease fixture + physical RF in owner-approved environment |
| EXIT-01-I | Concurrent Start/auto-scheduler vs Quit cannot resurrect owned worker | MOCK-CODE in A2/A3/A5 descriptions; CI not yet audited line-by-line for all | Deterministic adversarial barriers & concurrent Start/Stop tests |
| EXIT-01-J | Bounded stop timeout reports partial failure; no unrelated PID termination | PARTIAL source guards in A1/A2/A3/A5; physical process identity unverified | Fake uncooperative children + PID reuse safety + visible partial status |
| EXIT-01-K | Repeated Quit/Stop/crash/restart is idempotent; no stale lock or zombie | PARTIAL mock/source contracts, no actual crash reboot | Independent crash/restart + old-PID identity fixture and native acceptance |
| EXIT-01-L | Full Quit overrides tray, background or Always-On app-owned work | PARTIAL A1 overlay explicit Exit, A2 native Quit and A5 HTTP explicit Quit | Native per-OS true Quit policy, no retained owned daemon/tray |
| EXIT-01-M | Stop Module releases only that module, other TIHULU modules remain functional | PARTIAL A5 Text module cleanup and A4 geo scoped RF | Two simultaneous modules, owned model and SDR lease fixture |
| EXIT-01-N | Web/PWA tab close documented best-effort; UI has reliable explicit Stop control | PARTIAL A4/A5 proposals | Browser support matrix and native supervisor fallback; never advertise guarantee |
| EXIT-01-O | Linux, Windows, macOS, ARM64 installed smoke: zero *owned* worker/model/device sessions, external unaffected | NOT VERIFIED for any app | Per-process PID start-time, owned GPU/NPU memory, SDR/port lease before/after with signed result and rollback |

**Exit acceptance: 0/15 full accepted**, although several software features have mock/source coverage. Do not convert source tests to verified physical GPU/SDR release. There is no meaningful weighted completion percentage from these heterogeneous unverified cases.

## Mandatory non-interference checks

- Never stop an independently started `readsb.service`, `tar1090.service`, Jan, Ollama, remote GPU host, system GPU driver, another TIHULU process or other user's SDR/model lease merely because the GUI closes.
- Do not delete model files, original recordings, user data, stored settings or externally owned lock files. A cache clear cannot erase another app's data.
- Verify queued work cannot be admitted after STOPPING, owner PID and start-time before any forced termination, bounded worker `terminate -> wait -> kill -> wait` using held handles, warnings if children remain.
- Empty CUDA cache or Python GC alone is not proof VRAM is released. The kernel/device driver may retain cache; measure app-owned process/session state, not total GPU memory.
- Allow explicit Stop Module without globally quitting the app; full Quit stops every app-owned module regardless of optional background modes.
- Shared AI Tools/Survival Kit model interfaces are owner-managed; QA reviews external integration behavior without creating competing code or supervisor repos.

## Remaining critical actions

1. A4 RF Geolocation: create separate Draft PR from original #16, add representative mocked regression tests and verify CI for true Quit, no foreign SDR kill. Branch source exists but not PR-confirmed at this checkpoint.
2. A2 Flight: all four OS jobs and Pi ARM64 CI green on exact #16 head; next independent reviewer must check mixed-service ownership and real installed host behavior before merge (stacked #15 still unmerged).
3. A3 Satellite: separate source/Pages parity correction work from EXIT-01 cleanup (no automatic deployment), keep eight discrepancies explicit. Verify latest portable 43152107002 and Debian 43152106975 when completed.
4. A1 Media, A5 Text: inspect actual CPU/translator/FFmpeg, remaining in-process model unblock and subprocess parenting, ensure full Quit not merely window hide or event loop stop; run later native installed tests.
5. QA: only after all five PR CI and scope checks, review rollback, old Media #67 full 20-commit history, external borrowed model/session survival, native en/tr/de and installer gates.

**Release and platform status:** 17/17 existing broader zero-regression gates OPEN + separate new EXIT-01 P0 gate OPEN. 97 baseline source-audited requirements + 1 new owner RQ-098 = 98 known. 0/3 migrations, 0 merged EXIT-01 PRs, 0 installed tests. No finite ETA grounded in actual release workload.
