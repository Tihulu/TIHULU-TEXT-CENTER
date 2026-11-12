/* EXIT-01: per-tab ownership supervisor. No global process or SDR service controls.
 * Hard Stop is terminal for device work until the page is reloaded. True Quit
 * additionally releases UI-owned timers, requests and transient data.
 */
export function createExitLifecycle(onState = () => {}) {
  let state = "RUNNING", rfStopped = false, finished = null;
  const handlers = new Map(), invoked = new Map();
  function register(name, kind, cleanup) {
    if (state !== "RUNNING" || handlers.has(name) || !["rf", "device", "ui"].includes(kind)
        || typeof cleanup !== "function") throw Error("Invalid or late lifecycle registration");
    handlers.set(name, {kind, cleanup});
  }
  function once(name) {
    if (invoked.has(name)) return invoked.get(name);
    const {cleanup} = handlers.get(name);
    const task = Promise.resolve().then(cleanup).then(
      () => ({name, released:true}),
      error => ({name, released:false, error:String(error?.message || error).slice(0,240)})
    );
    invoked.set(name, task);
    return task;
  }
  function stopRf() {
    if (state !== "RUNNING" || rfStopped) return Promise.resolve({state, rfStopped});
    rfStopped = true;
    onState("RF_STOPPING");
    return Promise.all([...handlers].filter(([, entry]) => entry.kind === "rf")
      .map(([name]) => once(name))).then(results => {
      onState("RF_STOPPED");
      return {state, rfStopped, results};
    });
  }
  function beginStop(target) {
    if (finished) return finished;
    state = "STOPPING"; rfStopped = true;
    onState(state); // synchronous: late Start cannot race a pending cleanup
    finished = Promise.all([...handlers.keys()].map(once)).then(results => {
      state = target;
      onState(state);
      return {state, rfStopped, results, incomplete:results.filter(r => !r.released)};
    });
    return finished;
  }
  return {
    register, stopRf, hardStop:() => beginStop("HARD_STOPPED"),
    quit:() => beginStop("QUIT"),
    get state() {return state},
    get rfStopped() {return rfStopped},
    canStart:(kind="ui") => state === "RUNNING" && !(kind === "rf" && rfStopped),
    isQuit:() => state === "STOPPING" || state === "QUIT" || state === "HARD_STOPPED"
  };
}
