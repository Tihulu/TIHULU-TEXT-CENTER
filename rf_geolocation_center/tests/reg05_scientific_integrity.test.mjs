/* REG-05 ONLY: synthetic fixtures, never real radio/GNSS reception or claimed accuracy. */
import test from "node:test";
import assert from "node:assert/strict";
import {parseNMEA,nmeaChecksum,trilaterate2D,tdoaConstraints} from "../core/positioning.mjs";
import {validRangeSources} from "../core/evidence.mjs";
import {layerReadiness} from "../core/location_layers.mjs";
import {positionProvenance,radioProvenance,aircraftProvenance,orbitalProvenance} from "../core/source_provenance.mjs";
import {relativePowerDbFS,calibratedRange,solveCalibratedRF} from "../core/rf_ranging.mjs";
import {matchedBroadcastSources} from "../core/scan_map.mjs";
const now=Date.UTC(2026,10,12,10,0,0);
function checksum(body){
 let sum=0;
 for(const ch of body)sum^=ch.charCodeAt(0);
 return "$"+body+"*"+sum.toString(16).toUpperCase().padStart(2,"0");
}
test("REG05: synthetic I/Q and three aircraft reference coordinates never establish observer GPS",()=>{
 const bytes=new Uint8Array(4096).fill(127);
 for(let i=0;i<bytes.length;i+=128){bytes[i]=204;bytes[i+1]=194}
 const level=relativePowerDbFS(bytes);
 assert.ok(Number.isFinite(level));
 const radio=radioProvenance("RF SAMPLED","SYNTHETIC fixture power "+level.toFixed(2));
 assert.equal(radio.hasRF,true);
 assert.equal(radio.hasPosition,false);
 const aircraft=aircraftProvenance([1,2,3].map(i=>({type:"aircraft",lat:51+i/100,lon:7,observedByReceiver:true})));
 assert.equal(aircraft.count,3);
 assert.equal(aircraft.hasPosition,false);
 assert.equal(orbitalProvenance(false,8).fix,false);
 assert.equal(positionProvenance({},now).fix,"NO POSITION FIX");
 assert.equal(layerReadiness({references:[{type:"aircraft",lat:50,lon:7}]},now).radio.state,"NO MEASUREMENT");
});
test("REG05: exact 90-second and 5-minute live expiry, future sources and cached-only fallbacks",()=>{
 const serial={lat:51,lon:7};
 const browser={lat:50.9,lon:6.9,acquiredAt:new Date(now-299999).toISOString()};
 const fresh={serialFix:serial,serialAt:now-89999,browser};
 assert.equal(positionProvenance(fresh,now).kind,"receiver");
 assert.equal(layerReadiness(fresh,now).gnss.state,"FIX");
 const stale={...fresh,serialAt:now-90000};
 assert.equal(positionProvenance(stale,now).kind,"device");
 assert.equal(layerReadiness(stale,now).gnss.state,"NO FIX");
 const old={...stale,browser:{...browser,acquiredAt:new Date(now-300000).toISOString()}};
 assert.equal(positionProvenance(old,now).fix,"NO POSITION FIX");
 assert.equal(layerReadiness(old,now).device.state,"NO FIX");
 const cached={...old,cachedPosition:{lat:51,lon:7,recordedAt:"2026-11-11T10:00:00Z"}};
 assert.equal(positionProvenance(cached,now).kind,"cached");
 assert.equal(positionProvenance(cached,now).location,false);
 const future={serialFix:serial,serialAt:now+1,browser:{...browser,acquiredAt:new Date(now+1).toISOString()}};
 assert.equal(positionProvenance(future,now).fix,"NO POSITION FIX");
 assert.equal(layerReadiness(future,now).gnss.state,"NO FIX");
 assert.equal(layerReadiness(future,now).device.state,"NO FIX");
});
test("REG05: checksum-valid NMEA no-fix sentences cannot become coordinates or accuracy",()=>{
 for(const body of ["GPGGA,123519,,,,,0,00,99.9,,,,,,","GPRMC,123519,V,,,,,,,230394,,,N"]){
  const raw=checksum(body);
  assert.equal(nmeaChecksum(raw),true);
  const parsed=parseNMEA(raw);
  assert.equal(parsed.valid,false);
  assert.equal(parsed.lat,undefined);
  assert.equal(parsed.accuracyMeters,undefined);
 }
 const valid=checksum("GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,");
 const parsed=parseNMEA(valid);
 assert.equal(parsed.valid,true);
 assert.equal(parsed.accuracyMeters,null);
 assert.equal(parsed.usedSatellites,8);
 assert.equal(parsed.hdop,0.9);
 assert.throws(()=>parseNMEA(valid.replace("545.4","546.4")),/checksum/);
});
test("REG05: TDOA booleans produce geometry only; no MLAT fix or confidence",()=>{
 const stations=[
  {station:"A",lat:50,lon:7,synchronized:true,measured:true,deltaSeconds:0},
  {station:"B",lat:50,lon:7.01,synchronized:true,measured:true,deltaSeconds:1e-7}
 ];
 const [c]=tdoaConstraints(stations);
 assert.equal(c.type,"TDOA HYPERBOLA");
 assert.equal(c.positionFix,false);
 assert.ok(Math.abs(c.rangeDifferenceMeters-29.9792458)<1e-7);
 assert.ok(c.baselineMeters>c.rangeDifferenceMeters);
 assert.equal(c.lat,undefined);
 assert.equal(c.confidence,undefined);
 assert.throws(()=>tdoaConstraints(stations.map(x=>({...x,synchronized:false}))),/synchronized/);
 assert.throws(()=>tdoaConstraints([stations[0],{...stations[1],deltaSeconds:.001}]),/impossible/);
});
test("REG05: zero-residual imported synthetic ranges still lack location accuracy",()=>{
 const metersPerDegree=6378137*Math.PI/180;
 const points=[[0,.01],[0,-.01],[.01,0],[-.01,0]].map(([lat,lon],i)=>({
  lat,lon,rangeMeters:Math.hypot(lat,lon)*metersPerDegree,measured:true,
  source:"SYNTHETIC GEOMETRY NOT RF",station:"SYNTHETIC-"+i
 }));
 assert.equal(validRangeSources(points),true);
 const out=trilaterate2D(points);
 assert.ok(Math.abs(out.lat)<1e-7 && Math.abs(out.lon)<1e-7);
 assert.ok(out.rmsResidualMeters<.1);
 assert.match(out.quality,/NO CLAIMED ACCURACY/);
 for(const key of ["accuracyMeters","covariance","confidence95"])assert.equal(out[key],undefined);
 assert.equal(validRangeSources(points.map(p=>({...p,measured:false}))),false);
 assert.throws(()=>trilaterate2D(points.map(p=>({...p,measured:false}))),/measured/);
});
test("REG05: RSSI is an unvalidated ratio model, never Gaussian covariance or calibrated 95%",()=>{
 const obs={levelDbFS:-20,frequencyMHz:98.6,gainDb:20,sampleRate:1024000};
 const cal={referenceLevelDbFS:-11,referenceDistanceMeters:1000,pathLossExponent:3,
   referenceFrequencyMHz:98.6,referenceGainDb:20,referenceSampleRate:1024000};
 const output=calibratedRange(obs,cal);
 assert.equal(output.externalReference,true);
 assert.match(output.estimateType,/NOT MEASURED DISTANCE/);
 assert.match(output.note,/not a statistical confidence interval/);
 for(const k of ["accuracyMeters","covariance","confidence95","gaussianSigmaMeters"])assert.equal(output[k],undefined);
 assert.throws(()=>calibratedRange({...obs,sampleRate:2048000},cal),/same tuning/);
 assert.throws(()=>calibratedRange({...obs,frequencyMHz:99.5},cal),/same tuning/);
 assert.throws(()=>calibratedRange({...obs,gainDb:0},cal),/same tuning/);
 assert.throws(()=>calibratedRange({...obs,levelDbFS:-110},cal),/too large/);
});
test("REG05: moving transmitters and degenerate fixed stations cannot yield verified RF position",()=>{
 const a={lat:51.0,lon:7.0,type:"station",modelType:"CALIBRATED_RSSI_ESTIMATE",rangeMeters:1500};
 const b={lat:51.01,lon:7.0,type:"station",modelType:"CALIBRATED_RSSI_ESTIMATE",rangeMeters:1600};
 const c={lat:51.0,lon:7.02,type:"station",modelType:"CALIBRATED_RSSI_ESTIMATE",rangeMeters:1700};
 assert.throws(()=>solveCalibratedRF([a,b,{...c,type:"aircraft"}]),/fixed ground/);
 assert.throws(()=>solveCalibratedRF([a,b,{...c,type:"satellite"}]),/fixed ground/);
 assert.throws(()=>solveCalibratedRF([a,a,a]),/degenerate/);
 const estimate=solveCalibratedRF([a,b,c]);
 assert.match(estimate.quality,/NOT GPS AND NOT A VERIFIED POSITION/);
 assert.equal(estimate.accuracyMeters,undefined);
 assert.equal(estimate.covariance,undefined);
});
test("REG05: frequency-matched OSM metadata is not identified emitter or receiver location",()=>{
 const tower={id:"osm-node/99",name:"EXTERNAL TEST SITE",lat:50.9,lon:7,
   frequenciesMHz:[98.6],televisionFrequenciesMHz:[514]};
 const matches=matchedBroadcastSources([tower],
  [{frequencyMHz:98.6,levelDbFS:-20,measuredAt:"2026-11-12T10:00:00Z"}],
  [{frequencyMHz:514,name:"Synthetic DVB frequency",deliverySystem:"DVBT2"}]);
 assert.equal(matches.length,2);
 for(const entry of matches){
  assert.equal(entry.receiverPosition,false);
  assert.equal(entry.distanceMeters,null);
  assert.match(entry.match,/FREQUENCY OVERLAP ONLY/);
  assert.equal(entry.sourceIdentityVerified,undefined);
 }
 assert.deepEqual(matchedBroadcastSources([tower],[{frequencyMHz:98.6}],[]),[]);
 assert.deepEqual(matchedBroadcastSources([{...tower,frequenciesMHz:[],televisionFrequenciesMHz:[]}],
  [{frequencyMHz:98.6,levelDbFS:-20}],[]),[]);
});
