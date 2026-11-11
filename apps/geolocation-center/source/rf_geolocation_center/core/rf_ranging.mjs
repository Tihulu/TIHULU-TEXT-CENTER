/* RF-only ranging: real RTL-SDR IQ sample levels are device measurements, NOT distances.
 * Emitter coordinates/frequency and reference-distance calibration are external assertions.
 * Single-device RSSI can offer ONLY rough experimental ranges given fixed gain and propagation.
 */
const RAD=Math.PI/180, METERS_PER_DEG=111319.49079327358;
export function relativePowerDbFS(samples){
 const data=samples instanceof ArrayBuffer?new Uint8Array(samples):ArrayBuffer.isView(samples)?
  new Uint8Array(samples.buffer,samples.byteOffset,samples.byteLength):null;
 if(!data||data.byteLength<128||data.byteLength%2!==0)throw Error("Need real interleaved I/Q bytes (at least 64 pairs)");
 let power=0,count=0;
 for(let i=0;i<data.length;i+=2){
  const I=(data[i]-127.5)/127.5,Q=(data[i+1]-127.5)/127.5;
  power+=I*I+Q*Q;count++;
 }
 const p=power/count;
 if(!Number.isFinite(p)||p<=0)throw Error("Invalid RF sample power");
 return 10*Math.log10(p);
}
export function calibratedRange(observation,calibration){
 // RF-level ratio is comparable ONLY at the same frequency, gain/antenna chain and similar signal occupancy.
 const {levelDbFS,frequencyMHz,gainDb,sampleRate}=observation||{};
 const {referenceLevelDbFS,referenceDistanceMeters,pathLossExponent,referenceFrequencyMHz,
   referenceGainDb,referenceSampleRate}=calibration||{};
 if(![levelDbFS,frequencyMHz,gainDb,sampleRate,referenceLevelDbFS,
      referenceDistanceMeters,pathLossExponent,referenceFrequencyMHz,referenceGainDb,
      referenceSampleRate].every(Number.isFinite))
    throw Error("Calibration requires measured reference level, distance, frequency, gain and sample rate");
 if(referenceDistanceMeters<1||referenceDistanceMeters>100000||pathLossExponent<1.5||pathLossExponent>6)
    throw Error("Reference distance must be 1–100000 m, path loss exponent 1.5–6");
 if(frequencyMHz<24||frequencyMHz>1766||Math.abs(frequencyMHz-referenceFrequencyMHz)>.001
    ||Math.abs(gainDb-referenceGainDb)>.01||Math.abs(sampleRate-referenceSampleRate)>1)
    throw Error("Reference and current RF observations must use the same tuning, sample rate and fixed gain");
 const delta=referenceLevelDbFS-levelDbFS;
 if(Math.abs(delta)>90)throw Error("RF level difference too large for a meaningful range hypothesis");
 const distance=referenceDistanceMeters*Math.pow(10,delta/(10*pathLossExponent));
 if(!Number.isFinite(distance)||distance<1||distance>100000)
    throw Error("Extrapolated range outside the allowed 1–100 km experimental domain");
 // Deliberately large heuristic uncertainty: NOT certified coverage or GPS accuracy.
 const min=Math.max(1,distance/3),max=Math.min(100000,distance*3);
 return {rangeMeters:distance,lowerMeters:min,upperMeters:max,
   estimateType:"EXPERIMENTAL CALIBRATED RF RSSI MODEL · NOT MEASURED DISTANCE",
   receiverOrigin:"RTL-SDR WebUSB I/Q",externalReference:true,
   note:"Reference level, source identity, EIRP, antenna pattern, gain stability, fading, multipath and terrain are unverified. Bounds are illustrative sensitivity only, not a statistical confidence interval."};
}
export function solveCalibratedRF(ranges){
 if(!Array.isArray(ranges)||ranges.length<3||ranges.length>32)
   throw Error("RF-only 2D solution needs at least 3 independently calibrated source ranges");
 const ref={lat:ranges.reduce((t,p)=>t+p.lat,0)/ranges.length,
    lon:ranges.reduce((t,p)=>t+p.lon,0)/ranges.length};
 if(!Number.isFinite(ref.lat)||Math.abs(ref.lat)>80||!Number.isFinite(ref.lon)||Math.abs(ref.lon)>175)
   throw Error("RF-only solver unsupported for this reference geometry");
 const cos=Math.cos(ref.lat*RAD);
 const pts=ranges.map(p=>{
  if(!Number.isFinite(p.lat)||!Number.isFinite(p.lon)||!Number.isFinite(p.rangeMeters)
     ||p.rangeMeters<1||p.rangeMeters>100000||p.type!=="station"
     ||p.modelType!=="CALIBRATED_RSSI_ESTIMATE")
   throw Error("Only fixed ground stations with independently calibrated RF hypotheses qualify");
  const x=(p.lon-ref.lon)*METERS_PER_DEG*cos,y=(p.lat-ref.lat)*METERS_PER_DEG;
  if(Math.hypot(x,y)>100000)throw Error("Ground sources must fit in a 100 km local area");
  return {x,y,r:p.rangeMeters};
 });
 let x=pts.reduce((t,p)=>t+p.x,0)/pts.length,y=pts.reduce((t,p)=>t+p.y,0)/pts.length;
 const step=()=>{
  let a=0,b=0,c=0,e=0,f=0;
  for(const p of pts){
   const dx=x-p.x,dy=y-p.y,d=Math.max(.01,Math.hypot(dx,dy)),rx=dx/d,ry=dy/d,r=d-p.r;
   a+=rx*rx;b+=rx*ry;c+=ry*ry;e+=rx*r;f+=ry*r;
  }
  const det=a*c-b*b;if(Math.abs(det)<1e-5)throw Error("Source geometry is degenerate; choose geographically separated stations");
  return [(c*e-b*f)/det,(a*f-b*e)/det];
 };
 for(let i=0;i<80;i++){
  const [dx,dy]=step();if(![dx,dy].every(Number.isFinite)||Math.hypot(dx,dy)>100000)throw Error("RF-only estimate is unstable");
  x-=dx;y-=dy;if(Math.hypot(dx,dy)<.001)break;
 }
 const residual=Math.sqrt(pts.reduce((s,p)=>s+(Math.hypot(x-p.x,y-p.y)-p.r)**2,0)/pts.length);
 if(!Number.isFinite(residual)||residual>100000)throw Error("RF-only range fit is inconsistent");
 return {lat:ref.lat+y/METERS_PER_DEG,lon:ref.lon+x/(METERS_PER_DEG*cos),
   rmsResidualMeters:residual,usedSources:pts.length,
   method:"RF-ONLY EXPERIMENTAL PROPAGATION-MODEL POSITION (NO OS LOCATION)",
   quality:"LOW / UNVALIDATED — NOT GPS AND NOT A VERIFIED POSITION",
   note:"This location is computed only from independently calibrated RTL-SDR signal-level hypotheses and external transmitter coordinates. It may be very inaccurate."};
}
