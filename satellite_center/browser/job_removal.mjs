// Removal routing for native scheduled jobs (web UI and native desktop share it).
//
// A record disappears from the armed-jobs list only when it also disappears from
// the native calendar, so every path ends in one scheduler refresh.
//
// State vocabulary mirrors the Station backend: only a TERMINAL record may be
// removed. A `pending` schedule is a live reservation and a `running` schedule is
// an in-progress RF capture whose result is merged back into the same record when
// the receiver releases it — removing either would silently discard it.

/** States whose capture has finished: safe to remove. */
export const TERMINAL_JOB_STATES = Object.freeze([
  "completed", "cancelled", "blocked", "interrupted", "missed", "error",
]);

/** States that still hold a live reservation or an in-progress capture.
 *  This is the native/serve vocabulary (Station states). */
export const LIVE_JOB_STATES = Object.freeze(["pending", "running"]);

/** Live states of the browser (WebUSB) scheduler, which uses its own names.
 *  Kept separate so a caller never mistakes them for terminal records, and so
 *  `isLiveState()` stays an answer about the native vocabulary only. */
export const BROWSER_LIVE_JOB_STATES = Object.freeze(["armed", "starting"]);

/** True for a live record on the browser (WebUSB) scheduler. */
export function isBrowserLiveState(state) {
  return BROWSER_LIVE_JOB_STATES.includes(String(state || ""));
}

export function isTerminalState(state) {
  return TERMINAL_JOB_STATES.includes(String(state || ""));
}

export function isLiveState(state) {
  return LIVE_JOB_STATES.includes(String(state || ""));
}

/** @returns {{method:"cancel"|"clear", call:()=>Promise<any>}} */
export function dismissAction(job, bridge) {
  if (!bridge) throw new Error("native bridge unavailable");
  if (!job || typeof job.id !== "string" || !job.id) {
    throw new Error("a scheduled job is required");
  }
  if (isLiveState(job.state)) {
    if (typeof bridge.nativeCancelScheduledJob !== "function") {
      throw new Error("native cancellation unavailable");
    }
    return {
      method: "cancel",
      call: () => bridge.nativeCancelScheduledJob(String(job.id)),
    };
  }
  if (!isTerminalState(job.state)) {
    throw new Error("unknown schedule state: " + String(job.state));
  }
  if (typeof bridge.nativeClearScheduledJob !== "function") {
    throw new Error("native record removal unavailable");
  }
  return {
    method: "clear",
    call: () => bridge.nativeClearScheduledJob(String(job.id)),
  };
}

/** Records a bulk clear would remove (terminal only). */
export function finishedJobs(jobs) {
  return (jobs || []).filter((job) => job && isTerminalState(job.state));
}

/** Records a bulk clear must never touch (live reservations and captures). */
export function liveJobs(jobs) {
  return (jobs || []).filter((job) => job && isLiveState(job.state));
}

/** Backwards-compatible alias: records that are not live. */
export function pendingJobs(jobs) {
  return liveJobs(jobs).filter((job) => job.state === "pending");
}
