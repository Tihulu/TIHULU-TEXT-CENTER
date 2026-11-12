/* Ownership admission for this browser tab only.
 * Tokens invalidate asynchronous WebUSB provider.get()/driver setup after Stop,
 * Disconnect, visibility loss or pagehide. No OS services or foreign USB are touched.
 */
export function createOwnedWebUsbGate(){
  let epoch=0,disposed=false;
  return Object.freeze({
    begin(){
      if(disposed)throw Error("This browser receiver session has closed; reload before connecting");
      return epoch;
    },
    current(ticket){return !disposed&&ticket===epoch;},
    assert(ticket){
      if(disposed||ticket!==epoch)throw Error("WebUSB connection cancelled; the tab owns no new receiver lease");
    },
    cancel(){epoch+=1;return epoch;},
    close(){disposed=true;epoch+=1;return epoch;},
    get epoch(){return epoch;},
    get closed(){return disposed;}
  });
}

/* Pure capture indicators; never claim hardware measurements from timer time.
 * observedBytes comes only from actual RTL-SDR readSamples data.
 */
export function captureProgress({startedAt,now,seconds,observedBytes=0,rate}){
  if(!Number.isFinite(seconds)||seconds<=0||!Number.isFinite(rate)||rate<=0)
    throw Error("Invalid WebUSB capture duration or rate");
  const elapsed=Math.max(0,(now-startedAt)/1000);
  const fraction=Math.max(0,Math.min(1,elapsed/seconds));
  return {
    elapsedSeconds:elapsed,
    requestedSeconds:seconds,
    percentage:Math.round(fraction*100),
    observedBytes:Math.max(0,observedBytes),
    expectedIqBytes:seconds*rate*2,
    estimateOnly:true,
    complete:false
  };
}
