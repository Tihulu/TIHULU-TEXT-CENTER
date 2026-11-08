/* Optional window sector assessment shared by offline/browser predictions.
 * No inference of actual radio transmission, wall shielding or antenna gain. */
export function validatedWindow(v){
 if(v==null||v===false)return null;
 const az=Number(v.az),half=Number(v.half),min=Number(v.min),max=Number(v.max);
 if(![az,half,min,max].every(Number.isFinite)||!(az>=0&&az<360&&
    half>=1&&half<=90&&min>=0&&min<max&&max<=90))
   throw Error("Window: azimuth 0–359°, half-width 1–90°, elevation 0–90° with min below max");
 return {az,half,min,max};
}
export function windowContains(az,el,w){
 if(!w||![az,el].every(Number.isFinite))return false;
 const d=Math.abs(((az-w.az+540)%360)-180);
 return d<=w.half&&el>=w.min&&el<=w.max;
}
export function windowSummary(samples,profile){
 const w=validatedWindow(profile);
 if(!w)return null;
 const segments=[];let current=[],highest=-90;
 for(const p of samples){
  if(windowContains(p.az,p.el,w)){
   highest=Math.max(highest,p.el);
   if(current.length&&p.ms-current[current.length-1].ms>15000){
    segments.push(current);current=[];
   }
   current.push(p);
  }else if(current.length){segments.push(current);current=[];}
 }
 if(current.length)segments.push(current);
 if(!segments.length)return {status:"outside",seconds:0,peak_elevation:null,segments:[],
   note:"No predicted samples inside assumed window sector"};
 const seconds=Math.round(segments.reduce((n,list)=>n+
   (list.length>1?(list[list.length-1].ms-list[0].ms)/1000:0),0));
 return {status:seconds>=180?"good_geometry":seconds>=60?"short_window":"very_short",
  seconds,peak_elevation:+highest.toFixed(1),
  segments:segments.map(list=>({start:list[0].ms,end:list[list.length-1].ms})),
  note:"Estimated geometric overlap; transmitter and obstruction status unknown"};
}
