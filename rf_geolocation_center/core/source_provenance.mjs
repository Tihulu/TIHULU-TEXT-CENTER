/* Single source of truth for antenna-vs-device positioning provenance.
 * Never infer native GPS vs Wi-Fi from navigator.geolocation; never equate
 * SDR USB/radio energy or predicted satellite geometry with a position fix.
 */
export function positionProvenance(state={},now=Date.now()){
 const serial=state.serialFix;
 if(serial&&Number.isFinite(state.serialAt)&&now-state.serialAt>=0&&now-state.serialAt<90000){
   return {kind:"receiver",source:"Dedicated USB/serial GNSS receiver",acquisition:"NMEA position reported by an external GNSS receiver",fix:"LIVE GNSS FIX",location:true,antenna:false,
     detail:"External GNSS receiver's own antenna/decoder. NOT the Nooelec RTL-SDR RF measurement."};
 }
 const b=state.browser;
 const date=Date.parse(b?.acquiredAt||"");
 if(b&&Number.isFinite(date)&&now-date>=0&&now-date<300000){
   return {kind:"device",source:"Device / OS location service",acquisition:"Browser Geolocation API",fix:"DEVICE FIX",location:true,antenna:false,
     detail:"GPS, Wi-Fi, cellular, IP or combined location — the browser does NOT disclose the underlying method."};
 }
 const r=state.ranges;
 if(r&&Number.isFinite(r.lat)&&Number.isFinite(r.lon)&&Array.isArray(state.rangeInputs)&&state.rangeInputs.length>=3){
   return {kind:"import",source:"User-imported radio ranging file",acquisition:"Experimental 2D trilateration from entered station/aircraft distances",fix:"EXPERIMENTAL ESTIMATE",location:true,antenna:false,
     detail:"Ranges supplied by user, not automatically measured by the RTL-SDR. Calibration and accuracy unverified."};
 }
 const p=state.cachedPosition;
 if(p&&Number.isFinite(p.lat)&&Number.isFinite(p.lon)){
   return {kind:"cached",source:"Saved earlier position",acquisition:"Browser local storage · "+(p.recordedAt||"timestamp unavailable"),fix:"CACHED / NOT LIVE",location:false,antenna:false,
     detail:"A historical coordinate. No new location was measured."};
 }
 return {kind:"reference",source:"Default Cologne map reference",acquisition:"Built-in static center",fix:"NO POSITION FIX",location:false,antenna:false,
   detail:"This map center is not the receiver location."};
}
export function radioProvenance(status="NOT CONNECTED",message=""){
 const upper=String(status).toUpperCase();
 const physical=["USB CONNECTED","SAMPLING","RF SAMPLED","SAMPLE ERROR"].includes(upper);
 const sampled=upper==="RF SAMPLED"||upper==="SAMPLING";
 return {kind:"antenna",source:"Nooelec RTL-SDR / physical antenna",
   acquisition:physical?(sampled?"Direct WebUSB I/Q sampling":"WebUSB RTL2832U device connected"):"RTL-SDR not capturing",
   status:upper,hasRF:sampled,hasPosition:false,
   detail:sampled?"Actual RF sample is NOT a GNSS lock or a position fix. "+String(message).slice(0,220):
    physical?"The SDR may be open, but it has not produced a geolocation measurement.":String(message||"No RF measurement from this antenna.").slice(0,220)};
}
export function orbitalProvenance(hasSp3=false,predictedCount=0){
 return hasSp3?{source:"User-imported SP3 orbit file",acquisition:"Precise ephemeris geometry",fix:false,
   detail:"Satellite tracks were imported, NOT detected by the RTL-SDR antenna."}:
 predictedCount>0?{source:"Internet CelesTrak TLE catalog (possibly cached)",acquisition:"SGP4 orbit predictions",fix:false,
   detail:"Predicted sky/ground positions, NOT received satellite signals."}:
 {source:"No orbital catalog available",acquisition:"None",fix:false,detail:"No GNSS RF detection or satellite positioning."};
}
export function aircraftProvenance(refs=[]){
 const count=Array.isArray(refs)?refs.filter(x=>x?.type==="aircraft").length:0;
 return {source:count?"User-imported aircraft reference data":"No aircraft data",
   acquisition:count?"Imported JSON coordinates, NOT confirmed as local RTL-SDR ADS-B reception":"None",
   count,hasPosition:false,detail:"Aircraft locations alone do not determine your receiver position."};
}
