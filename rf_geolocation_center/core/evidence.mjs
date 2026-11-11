/* Range-based positioning visuals. Pure math; no inferred ranges from RF power.
 * Rings on Earth maps are actual imported ground-distance constraints or CLEARLY LABELED synthetic demo.
 * GNSS pseudoranges are 3D satellite-space constraints and are never drawn as ground circles.
 */
const EARTH_RADIUS=6371008.8, RAD=Math.PI/180,DEG=180/Math.PI;
export function destination(lat,lon,rangeMeters,bearingDegrees){
 if(![lat,lon,rangeMeters,bearingDegrees].every(Number.isFinite)||Math.abs(lat)>90||Math.abs(lon)>180||rangeMeters<0||rangeMeters>1e7)
  throw Error("Invalid great-circle distance ring");
 const lat1=lat*RAD,lon1=lon*RAD,b=bearingDegrees*RAD,d=rangeMeters/EARTH_RADIUS;
 const lat2=Math.asin(Math.sin(lat1)*Math.cos(d)+Math.cos(lat1)*Math.sin(d)*Math.cos(b));
 const lon2=lon1+Math.atan2(Math.sin(b)*Math.sin(d)*Math.cos(lat1),Math.cos(d)-Math.sin(lat1)*Math.sin(lat2));
 return {lat:lat2*DEG,lon:((lon2*DEG+540)%360)-180};
}
export function ringPoints(lat,lon,rangeMeters,segments=96){
 if(!Number.isInteger(segments)||segments<24||segments>720)throw Error("Ring segments outside 24–720");
 return Array.from({length:segments+1},(_,i)=>destination(lat,lon,rangeMeters,i*360/segments));
}
export function groundDistanceMeters(a,b){
 if(!a||!b||![a.lat,a.lon,b.lat,b.lon].every(Number.isFinite))throw Error("Invalid coordinates");
 const dlat=(b.lat-a.lat)*RAD,dlon=(b.lon-a.lon)*RAD;
 const h=Math.sin(dlat/2)**2+Math.cos(a.lat*RAD)*Math.cos(b.lat*RAD)*Math.sin(dlon/2)**2;
 return 2*EARTH_RADIUS*Math.asin(Math.min(1,Math.sqrt(Math.max(0,h))));
}
export function exampleRings(center){
 if(!center||![center.lat,center.lon].every(Number.isFinite)||Math.abs(center.lat)>80||Math.abs(center.lon)>175)
  throw Error("Demo only supported at nonpolar terrestrial reference");
 // An independent synthetic solution near the selected reference, not a measurement of the user.
 const intersection=destination(center.lat,center.lon,1150,37);
 const stations=[
  destination(intersection.lat,intersection.lon,5600,235),
  destination(intersection.lat,intersection.lon,6200,16),
  destination(intersection.lat,intersection.lon,6800,130)
 ];
 return {
  simulated:true,
  solution:intersection,
  stations:stations.map((p,i)=>({...p,name:"Demo station "+String.fromCharCode(65+i),
     type:"station",rangeMeters:groundDistanceMeters(p,intersection),
     measured:false,source:"SYNTHETIC EXPLANATION — not an antenna measurement"})),
  disclaimer:"SIMULATED geometry only: 3 fictional stations. No position fix is computed from these demo rings."
 };
}
export function validRangeSources(ranges){
 if(!Array.isArray(ranges))return false;
 return ranges.length>=3&&ranges.length<=64&&ranges.every(s=>
  s&&Number.isFinite(s.lat)&&Math.abs(s.lat)<=90&&Number.isFinite(s.lon)&&Math.abs(s.lon)<=180&&
  Number.isFinite(s.rangeMeters)&&s.rangeMeters>=0&&s.rangeMeters<=1e7&&s.measured===true
 );
}
