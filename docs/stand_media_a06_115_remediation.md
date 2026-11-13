# STAND-MEDIA — Agent 06 PR #115 P1/P2 remediation

Frozen parent: PR #115 efb2beea4f73bb81f4dd67f4bb41753fed29185b.
Independent source: https://github.com/Tihulu/TIHULU-TEXT-CENTER/pull/115#issuecomment-6844143742
New branch is a stacked Draft only. No merge, release, owner machine, hardware or global service operations. PUBLIC RELEASE HOLD.

## P1-A06-115-01 — malicious journal deletion

Rollback may recursively remove ONLY its exact canonical releases/.pending-<SHA12> staging directory; raw untrusted JSON is never passed as deletion authority.
Validation checks exact lexical path (not silently normalized), SHA and release/current receipts, owner and non-writable/no-symlink release ancestors, and the inode/device/UID receipt durably stored after exclusive mkdir and before copying. Missing or legacy unsealed receipts fail closed.
Each present pending entry must match the recorded native release manifest. The path and inode are revalidated before fd-pinned symlink-safe shutil.rmtree; a completed rename is recognized only by the original inode and entire verified release manifest.
A crash before the pending inode has been committed may require manual HOLD, rather than guessing ownership and deleting a folder. Hostile same-UID edits or true power loss are not certified.

Full actual-module negative tests cover forged outside-HOME empty and manifest-matching directories, ../ escapes, symlink leaf and releases ancestor, replaced owner inode, missing receipt, injected foreign bytes, incorrect SHA/receipt and foreign data preservation.
Original strict QA05 test names and assertions are preserved; two synthetic setups now provide the mandatory pre-created pending inode receipt. Exact-head workflow checks test names/assertions against frozen original. All original QA03, QA05 and PR115 suites are rerun.

## P2-A06-115-02 — DVB FIFO lifecycle

Unique PID+UUID FIFO is exclusively created, never removed before mkfifo. lstat and fstat bind owner, type, link count, device and inode; reads and writes use O_NOFOLLOW.
The native destructor unlinks only if the path still names its own original opened FIFO inode with the same owner. A crash cannot execute a destructor; orphan FIFOs are never blindly scavenged. Real physical transport and multi-process tuned TS remain untested.

## P2-A06-115-03 — companion PATH

All formerly bare CLI QProcess starts in native Radio, lyrics, media captions, language packs, recording AI, exports and Remote Hub resolve through one app-owned absolute path helper.
The helper rejects symlinked/insecure parents and non-regular, wrong-owner, hardlinked, group/world-accessible or non-owner-executable CLI files. Empty resolution fails closed without using PATH.
Static callsite checks and compiled Qt QProcess smoke with PATH=/usr/bin:/bin are in CI. Each optional real GUI feature (and actual offline model inference) is not yet independently functionally accepted.

## Native identity and evidence boundary

New standalone executable is built and launched in disposable GitHub-hosted Ubuntu HOME. Install, rollback, recovery and reinstall plus synthetic stable settings/recording/model SHA256 preservation are checked. The workflow does not claim stock /usr/bin/kaffeine is the original customized TIHULU stable app.
An immutable, exact original customized stable TIHULU Media executable has not been supplied or verified in the available CI evidence. Therefore authentic two-application KConfig, MPRIS/DBus, recording, process ownership and independent stop/start acceptance is HOLD, not passed using stock KDE Kaffeine.
Physical tuner/SDR, real Pop!_OS COSMIC Wayland, licensed third-party distribution, owner acceptance, genuine power loss, hostile same UID, model migrations and public release also remain HOLD.

## Agent 06 re-review gate

Independently recheck the new Draft exact HEAD, all five CI workflows and their logs. Reproduce forged-journal negatives, FIFO identity and teardown, every native bare CLI callsite, and preserve real foreign data sentinels. Authentic frozen customized stable binary must be supplied and tested in a disposable VM before full parity acceptance.
No PR merge, release, deployment, hardware use or original stable installation changes. PUBLIC RELEASE HOLD.
