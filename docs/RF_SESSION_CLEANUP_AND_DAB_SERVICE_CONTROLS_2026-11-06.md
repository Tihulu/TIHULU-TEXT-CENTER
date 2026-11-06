# Receiver service controls and safe USB release (2026-11-06)

This is the **app-owned receive-only lifecycle** implemented in PR #11,
not a Pi-wide cross-process lease broker and not proof of real RF reception.

## Interface / operation

- In **Radio Data (400)**, receiver readiness includes:
  **START FM RADIO** (navigates to the existing, user-authorized Live
  Radio start control) and **STOP ALL TEXT CENTER RF**.
- In **DAB+ DLS / MOT receiver bridge**:
  **START DAB RECEIVER** explicitly starts a new local welle-cli 11D,
  5C, 8B or 9D session if the single RTL-SDR is available;
  **STOP DAB RECEIVER** stops only the child started by this browser tab.
  Existing externally launched welle-cli on 7979 is detected as a
  conflict; never terminate it or claim ownership.
- STOP ALL RF terminates **only this Text Center server's** live FM,
  TV, RDS, FM audio preview, spectrum scans and managed DAB receiver,
  leaving offline SQLite logs and saved recordings intact. It does
  **not** disable OS services or kill external readsb/tar1090/welle-cli.
- The managed DAB process has a **browser-specific owner token**.
  Closing/reloading the owning tab sends a best-effort same-origin
  CSRF stop; if the browser crashes, its 18-second backend heartbeat
  TTL stops the owned welle-cli child. Users may navigate between
  app pages while it stays owned by that open tab.
- Clean Python server shutdown (including SIGTERM in the foreground
  main thread) closes the managed child. An uncatchable SIGKILL or host
  power loss is outside the guarantee; the future Pi-wide broker must
  handle any orphaned child/service leases.
- This PR does **not** change live radio capture's existing heartbeat,
  app-close hooks, receiver locks, or protected recording semantics.
  Multi-tab ownership for every older FM/TV worker and absolute device
  lease cross-process exclusivity remain shared Survival Kit work.

## How to test without affecting the current Flight Radar

1. **Before starting a radio, see who owns the USB receiver:**
   \`pgrep -af 'readsb|dump1090|welle-cli|rtl_fm|rtl_433'\`.
   Do not stop someone else's receiver automatically.
2. For a dedicated test, explicitly stop app-owned or externally
   started readsb using its owning Flight Radar service controls
   (or \`sudo systemctl stop readsb\` with explicit user permission).
   The passive tar1090 page may remain without a live RF feed.
3. Start Text Center from this feature worktree; visit Radio Data (400).
   Select DAB 11D and click START DAB RECEIVER. Confirm 127.0.0.1:7979
   returns the actual decoded WDR NRW ensemble (when receivable).
4. Close only the owning browser tab; verify the managed welle-cli
   process exits and \`rtl_test -t\` can reopen the USB.
   Repeat by killing the **browser only** and allowing the 18-second
   watchdog. Try a second tab; its unrelated close should not
   stop the first tab's managed DAB.
5. Test the same channel with an independently started welle-cli.
   The app must refuse new managed Start and must not kill the
   external process on Stop/Close.
6. **FM:** stop DAB in its own panel, then use existing START LIVE
   RADIO and STOP RADIO, and STOP ALL TEXT CENTER RF.
7. Recheck persisted radio text/MOT records and recordings after
   session close. Do not claim success from mock tests alone.
8. Confirm all changed code integrates additively with existing
   independent PR #8 (FM/DAB auto scan) and PR #10 (FM/MOT/installer);
   do not overwrite concurrent AI/translation changes.

## Platform/security constraints

- Web server remains loopback-only; POSTs retain same-origin and
  per-server CSRF authorization. No arbitrary service names, shell
  commands, sudo permissions or RF transmit paths are accepted.
- Static GitHub Pages cannot directly supervise USB or OS services.
  A separately installed, authenticated local companion is required
  for Pages, Windows/macOS and eventual Raspberry Pi portal parity.
- Device arbitration via process name/fd discovery is only a
  **best-effort guard** and is not equivalent to an OS-wide broker.
  One RTL2832U is not multiple radios simply because different panels
  offer FM, DAB, RTL-433 or ADS-B.
- Do not advertise a stopped/available receiver unless the backend
  confirms the worker exited. A retained map cache/aircraft JSON
  is not live RF evidence.

## Integration handoff

Cross-project contract:
\`Tihulu/tihulu-survival-kit\` draft architecture PR #10,
\`docs/RECEIVER_SERVICE_LIFECYCLE_2026-11-06.md\`.
Flight Radar service ownership: \`Tihulu/tihulu-flight-radar\` PR #7.
Private planning: \`Tihulu/tihulu-survival-kit-plan\` Plan94 PR #6.

**Status:** implemented in isolated draft branch with mocked CI tests.
Physical USB close/release tests and integrated multi-app broker acceptance
remain pending.
