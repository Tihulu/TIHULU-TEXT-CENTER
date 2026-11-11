/* Simulation clock for satellite-only orbital geometry.
 * Never controls the SDR, downloads, scheduling or wall-clock job timers.
 * Live: current time. Paused/seek: fixed snapshot until user resumes.
 */
export const LIVE_REFRESH_MS=1000;
export const TRACK_REFRESH_MS=15000;
export function createOrbitClock(now=()=>Date.now()){
  let live=true, snapshot=now();
  return {
    get isLive(){return live;},
    time(){return live?now():snapshot;},
    resume(){live=true;return now();},
    pause(){snapshot=live?now():snapshot;live=false;return snapshot;},
    seek(offsetMinutes){
      const offset=Number(offsetMinutes);
      if(!Number.isFinite(offset)||offset < -1440 || offset > 1440)throw Error("Invalid relative simulation offset.");
      snapshot=now()+offset*60000;live=false;return snapshot;
    }
  };
}
export function shouldRefreshLive({live,visible,started,elapsedMs}){
  return !!(live&&visible&&started&&Number.isFinite(elapsedMs)&&elapsedMs>=LIVE_REFRESH_MS-5);
}
export function trackCacheSlot(atMs,stationLat,stationLon,version=""){
  const t=Number(atMs),lat=Number(stationLat),lon=Number(stationLon);
  if(!Number.isFinite(t)||!Number.isFinite(lat)||!Number.isFinite(lon))throw Error("Invalid track cache key.");
  return Math.floor(t/TRACK_REFRESH_MS)+"|"+lat.toFixed(5)+","+lon.toFixed(5)+"|"+String(version);
}
