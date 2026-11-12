# RQ-098 / EXIT-01 — RF Geolocation owned-resource shutdown

**Scope:** RF Geolocation Draft PR #16 source `6664a04a6247826d71f6adeb795b137fd26de213`. This is a separate *stacked Draft PR* implementation, **not** a release, hardware validation, or a change to PR #16, original audit PR #86 or canonical `main`.

## Ownership and operator actions

| Action | Own resources that stop | What remains |
|---|---|---|
| **Stop RF Module** | This tab's RTL2832U WebUSB capture, sweep, current I/Q reads, experimental RF survey solver/observations, and owned tuner handle | Local maps, independent GNSS/TV/HTTP client, Flight Radar and other programs |
| **Hard Stop** | All tab-owned RF jobs/leases, active Web Serial reader, pending catalog/orbit HTTP fetch, timers, BroadcastChannel receiver, this tab's authorized DVB scan request, WebUSB and native-bridge *client* | The GUI remains open for viewing. Restart device work only via reload; external services and independent localhost server remain running |
| **True Quit** | All Hard Stop resources plus this tab's UI listeners, map observers, in-memory cache/buffers and DOM interaction | User recordings, explicitly saved local preferences, third-party processes/SDR users, independent native services |
| **Native launcher SIGINT/SIGTERM/Quit** | Only this Python launcher listener and its owned `DVBScanBridge` child process/thread (bounded terminate → kill **owned handle only**) | Existing `readsb.service`, `tar1090`, other apps, other users' SDR devices, saved files |

**Guarantee boundary:** Browser tab close/refresh/crash and PWA termination can only trigger **best-effort** `pagehide` cleanup. Browsers may terminate JavaScript before WebUSB `close()` or a localhost HTTP POST completes; the app never promises native-style guaranteed cleanup after a tab close. Use **Stop RF / Hard Stop / Quit** while the page is still responsive. If a separate local native companion was explicitly started, quit it in its own terminal or service control: closing a browser tab does **not** have ownership to kill that independent server.

## Implementation contracts

- `web/exit_lifecycle.mjs`: synchronous STOPPING state, disallow new jobs, per-name once-only resource cleanup, failures reported as incomplete. Stop RF is RF-only; Hard Stop cancels owned workers/devices but retains static GUI controls; true Quit also disposes UI controls.
- `web/usb_sdr.mjs`: all capture, sweep and connect attempts are generation-guarded. Explicit Quit invalidates pending callbacks, blocks reconnection, waits a bounded time for active sampling, releases only the handles returned to **this tab**, closes late `provider.get()` handles, shares simultaneous release promises and reports actual close failures. Its `driverFactory` parameter is synthetic-test-only injection; normal use still loads the original pinned browser driver when the user explicitly connects.
- `web/rf_survey.mjs`: RF-only OFF no longer reruns the solver; module Stop clears volatile observations/solutions and refuses late RF callbacks. Existing saved source entries and calibrations are not deleted.
- `web/auto_explorer.mjs` and `web/catalog_discovery.mjs`: abort their own in-flight network requests, unregister window events, close their own BroadcastChannel, stop polling intervals and forget transient references. No external services or shared antennas touched.
- `web/hardware_manager.mjs`: permission-panel listeners and late device enumeration callbacks are detached/suppressed; this is **permission inventory**, not an owned raw tuner decoder.
- `web/dvb_bridge_client.mjs`: a cryptographically random **48-hex-character per-scan owner ID** is sent only with a specific authenticated scan/start and stop. A tab cannot stop a scan started by another owner. Client Quit waits for an outstanding bounded scan request before issuing its own Stop; then revokes the in-tab pairing token and aborts residual requests. It **does not** stop the separately run Python HTTP server.
- `dvb_bridge.py`: the owner ID is checked server-side, and Stop refuses a different tab's owner. Native true Quit sets a closed admission gate before draining; the app-owned `dvbv5-scan` handle has a scoped bounded graceful terminate/escalation. Late worker completion cannot claim fresh scan success after cancellation.
- `native.py`: SIGINT/SIGTERM and normal serve-loop termination run app-owned bridge shutdown and localhost listener close. No HTTP endpoint accepts a remote *stop-server* command.

The only valid claim is resource ownership/cancellation behavior at the level of deterministic source and CI tests. **No calibrated GNSS-SDR acquisition, pseudorange GPS fix, aircraft TDOA/MLAT or RF hardware accuracy is implemented by EXIT-01.** No GPU, LLM or VRAM context is allocated by this RF Geolocation path, so the app-specific test does **not** establish RAM/VRAM/NPU release for other TIHULU programs or the native drivers.

## Synthetic regression verification

```sh
node --test rf_geolocation_center/tests/*.test.mjs
python -m unittest discover -s rf_geolocation_center/tests -p 'test_*.py' -v
python -m compileall -q rf_geolocation_center
```

The existing `.github/workflows/rf-geolocation.yml` workflow covers these unchanged commands on GitHub Actions, including Linux/Windows/macOS for Python. EXIT-01 tests inject fake receiver promises and `DVBScanBridge` process/thread handles. They assert:
1. Stop RF vs Hard Stop vs Quit ownership and once-only cleanup;
2. Quit racing an I/Q read or an unresolved driver claim, without late RF observation;
3. process termination only for the app's known handle, not a named external service;
4. different client owner token cannot stop someone else's DVB scan;
5. graceful stop/timeout escalation, closed admission after Quit, and explicit `STOP_FAILED_PARTIAL` when cleanup cannot finish.

**Not tested on real hardware:** No actual RTL-SDR WebUSB, Hauppauge DVB, CelesTrak, readsb/tar1090 service, loaded AI model, GPU or native process was started, stopped or measured in this implementation task. Hardware acceptance requires explicit later owner approval, installed-target logs and receiver identities. Browsers cannot reliably complete cleanup after a hard tab kill. CI is software evidence, not a hardware/VRAM guarantee.

## Review and release gates

- Preserve `feature/rf-geolocation-center-2026-11` [Draft PR #16](https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/16) as an immutable review anchor. New implementation branch and Draft PR target that branch. Original WS04 audit PR #86 and central `main` are unchanged.
- Coordinate review with [WS04 Issue #79](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/79) and [Issue #75](https://github.com/Tihulu/TIHULU-TEXT-CENTER/issues/75). No application migration, Pages, icon, installer, service policy or release modifications.
- Maintain engineering English; future user-facing localization **EN default / TR / DE** is still a separate open acceptance gate. The added controls use English text pending that localization work.
- Separate hardware test gate: Linux x64/ARM64/Pi, Windows, macOS and actual browser WebUSB/libusb behavior, delayed/unresponsive `close()`, physically connected DVB, exit/crash/OS-kill scenarios and cross-app lease ownership. Do not claim them complete from mocks.
