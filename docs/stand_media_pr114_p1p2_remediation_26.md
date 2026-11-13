# STAND-MEDIA-PR114 P1/P2 remediation — isolated acceptance

**Predecessor frozen:** Draft PR #114 exact HEAD
`d91bd2a4a679b37902c2ced284a864b18d046c80`.
This is a new stacked DRAFT only. Stable installer/source, owner machine,
cross-app repositories, model files and physical hardware remain untouched.

## Implemented safeguards (candidate, subject to independent QA)

- **P1-M114-01** — a missing active receipt no longer implies that *every*
  existing standalone tree is foreign. Before any re-install, the guard
  verifies a genuine `rolled_back` per-revision owner journal, exact public
  path/target receipts and complete SHA256 entry inventory of every preserved
  installed release. Reject unknown state, release or pending artifacts.
  Re-activation of the same source SHA uses original verified native release
  bits (not a possibly non-reproducible new binary). Interrupted operations
  must be explicitly recovered/rolled back before reinstallation.
- **P1-M114-02** — the actual native diagnostics menu delegates to the
  installed `~/.local/bin/tihulu-media-standalone --diagnose-tuner`
  wrapper. The wrapper delegates to the release's actual
  `current/aux/dvb_diagnostics.sh` script. No tuner is opened or killed
  by diagnostic menu registration.
- **P1-M114-03** — DVB transport FIFO uses a process identifier plus UUID
  under the Qt application's runtime directory, replacing the shared
  `dvbpipe.m2t` process namespace. The original native object's
  per-instance `fileName` lifecycle owns the generated path; it never
  unlinks the legacy/stable instance's fixed path.
- **P1-M114-04** — a separate user-owned 0600, nlink=1, NOFOLLOW lock inode
  under `~/.local/opt` spans the **entire native build and transaction**
  by descriptor inheritance from the guard's `guarded-script` entrypoint.
  Direct API activate/rollback and CLI recovery acquire the same flock. A
  competing process refuses immediately; SIGKILL releases the descriptor.
  Source verification, ledger, release, managed destinations and callbacks
  continue their pre-existing hash/no-clobber checks.
- **P2-M114-05** — the packaged `aux/install_welle.sh` wrapper
  **unconditionally** forces `TIHULU_MEDIA_STANDALONE=1` and
  delegates to the packaged original helper, which suppresses the legacy
  `sudo apt-get` branch. Direct execution without a desktop
  environment is safe by default. Historical source/welle build scripts are
  preserved, not silently repurposed.
- **P2-M114-06** — native AI menu and Radio model-market actions use
  `QDir::homePath()` to resolve the installed public CLI rather
  than searching an interactive terminal PATH. CLI selects absolute
  `/usr/bin/python3` by default (or its standalone pinned venv).
  The native app initiates only its own standalone process with separately
  namespaced settings, model path, runtime socket and receiver lifecycles.

## Test boundary

New suite `tests/test_stand_media_pr114_remediation_26.py`
covers real disposable Python-worker SIGKILL after a journal phase,
fresh recovery followed by reinstall, verified historical release reentry,
lock contention across independent child processes, lock hijack/symlink
and hardlink rejection, unchanged stable/private sentinel hashes,
unrecognized transaction/path preservation, menu's installed wrapper
execution, per-instance DVB filename source contract, no-PATH companion
execution and packaged no-APT optional DAB launch. Original QA03/QA05
test files are not modified. CI must report executed counts and exact SHA,
not inferred test success.

**Proof boundaries:** standalone synthetic native artifacts and real Python
subprocesses are not proof of installed dual native Qt GUI, KConfig or MPRIS
coexistence. Running the original native Kaffeine compile CI establishes
build syntax, not installed acceptance. No tuner, SDR, service, model,
owner recording or installed application touched.

**Residual security limits:** This is a cooperative **same-owner** transaction
lock. A malicious *same-UID* actor can modify namespace ancestors, receipts,
process environment or replace inodes after verification. Locally stored
SHA256 manifests are **not independently signed production authority**.
Interruptions during journal-temp write and genuine disk power loss can
leave states requiring manual HOLD. No foreign files are auto-adopted,
deleted or overwritten. Actual no-cross-process-cleanup and stable/native
two-application acceptance must be independently reproduced in disposable
Ubuntu before release. Global GPL/model licensing, owner installed parity,
system package migration, physical RF, live AI, merge and release are
**HOLD** pending separate approval.

## Agent 06 acceptance

Inspect the exact-head PR/CI, reproduce negative history and external-FD
lock scenarios, verify Qt native menu click and two app instances with the
same synthetic HOME where CI permits, and report P0/P1/P2 with scoped
PASS/HOLD to PR, Media #76, QA #81 and Coordinator #75.

Packaged source copies inside the standalone release also auto-detect
their installed path and override an unset/false standalone flag.
The historical pinned welle source CI outside an installed release
retains its existing test behavior; installed release cannot enter APT.
