/* Explicit positioning methods and overlay provenance.
 * Browser Geolocation does not reveal GPS vs Wi-Fi/cell/IP.
 * Orbits and aircraft coordinates are references, not observer fixes.
 */
export const LOCATION_LAYERS=Object.freeze([
{id:"gnss",name:"GPS / GNSS receiver",description:"Fresh NMEA fix from GNSS hardware",symbol:"◉",tone:"gnss",defaultVisible:true},
{id:"device",name:"Device location · method unknown",description:"Browser coordinates; GPS versus Wi-Fi/cell is not disclosed",symbol:"●",tone:"device",defaultVisible:true},
{id:"gpsfree",name:"GPS-free · Wi-Fi / cellular / IP",description:"Only explicitly verified non-GNSS positioning sources",symbol:"◇",tone:"network",defaultVisible:true},
{id:"radio",name:"Radio station ranging",description:"3+ genuine range measurements; experimental estimate, not certified accuracy",symbol:"◎",tone:"radio",defaultVisible:true},
{id:"aircraft",name:"Aircraft",description:"Aircraft position references, not observer position fixes",symbol:"✈",tone:"aircraft",defaultVisible:true},
{id:"ground",name:"Ground stations",description:"Station location references and measured radio ranges",symbol:"⌁",tone:"ground",defaultVisible:true},
{id:"satellites",name:"Satellite orbit positions",description:"Predicted satellite subpoints, not GNSS reception",symbol:"✧",tone:"satellites",defaultVisible:false},
{id:"cached",name:"Last-known / cached",description:"Historical position only, never live",symbol:"◷",tone:"cached",defaultVisible:true},
{id:"demo",name:"Example rings · simulated",description:"Three fictional stations, not a measurement",symbol:"◌",tone:"demo",defaultVisible:true}
]);
const finiteCoord=p=>p&&Number.isFinite(p.lat)&&Number.isFinite(p.lon)&&Math.abs(p.lat)<=90&&Math.abs(p.lon)<=180;
export const layerById=id=>LOCATION_LAYERS.find(l=>l.id===id)||null;
export function layerReadiness(inputs={},now=Date.now()){
 const age=Date.parse(inputs.browser?.acquiredAt||"");
 const fresh=!!(inputs.serialFix&&Number.isFinite(inputs.serialAt)&&now-inputs.serialAt>=0&&now-inputs.serialAt<90000&&finiteCoord(inputs.serialFix));
 const device=!!(inputs.browser&&Number.isFinite(age)&&now-age<300000&&now-age>=0&&finiteCoord(inputs.browser));
 const network=!!(inputs.networkFix&&finiteCoord(inputs.networkFix)&&inputs.networkFix.verifiedNonGnss===true&&["wifi","cell","ip"].includes(inputs.networkFix.method));
 const radio=!!(inputs.ranges&&finiteCoord(inputs.ranges)&&Array.isArray(inputs.rangeInputs)&&inputs.rangeInputs.length>=3);
 const refs=Array.isArray(inputs.references)?inputs.references:[];
 const orbits=Array.isArray(inputs.orbits)?inputs.orbits:[];
 const aircraft=refs.filter(r=>r.type==="aircraft").length,ground=refs.filter(r=>r.type==="station").length;
 return {
  gnss:{state:fresh?"FIX":"NO FIX",count:fresh?1:0,detail:fresh?"Fresh NMEA receiver fix (NOT RTL-SDR GNSS decoding)":"No fresh dedicated GNSS NMEA fix"},
  device:{state:device?"FIX":"NO FIX",count:device?1:0,detail:device?"Browser location; source could be GPS, Wi-Fi, cellular or IP":"No fresh browser position"},
  gpsfree:{state:network?"VERIFIED":"UNAVAILABLE",count:network?1:0,detail:network?"Explicitly verified non-GNSS "+inputs.networkFix.method:"Browser cannot distinguish GPS from network providers"},
  radio:{state:radio?"ESTIMATED":"NO MEASUREMENT",count:radio?inputs.rangeInputs.length:0,detail:radio?"User-provided unverified ranges; accuracy unknown":"3+ actual ranges needed; RTL-SDR signal level is not distance"},
  aircraft:{state:aircraft?"REFERENCES":"NO DATA",count:aircraft,detail:aircraft?"Aircraft coordinates alone cannot locate observer":"No imported aircraft references"},
  ground:{state:ground?"REFERENCES":"NO DATA",count:ground,detail:ground?"Ground transmitter positions alone cannot locate observer":"No imported stations"},
  satellites:{state:orbits.length?"PREDICTED":"NO DATA",count:orbits.length,detail:orbits.length?"SGP4/SP3 geometry, NOT observed RF":"No orbital dataset"},
  cached:{state:finiteCoord(inputs.cachedPosition)?"CACHED":"NO DATA",count:finiteCoord(inputs.cachedPosition)?1:0,detail:finiteCoord(inputs.cachedPosition)?"Previous fix only, NOT LIVE":"No saved location"},
  demo:{state:"SIMULATED",count:3,detail:"Three fictional stations and dashed example circles"}
 };
}
export function visibleLayerPreferences(saved){
 const v=saved&&typeof saved==="object"&&!Array.isArray(saved)?saved:{};
 return Object.fromEntries(LOCATION_LAYERS.map(l=>[l.id,typeof v[l.id]==="boolean"?v[l.id]:l.defaultVisible]));
}
