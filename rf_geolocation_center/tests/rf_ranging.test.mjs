import test from "node:test";
import assert from "node:assert/strict";
import {relativePowerDbFS,calibratedRange,solveCalibratedRF} from "../core/rf_ranging.mjs";
test("actual-format interleaved RTL2832 I/Q sample power metric is deterministic",()=>{
 const v=new Uint8Array(16384);v.fill(127);
 for(let i=0;i<v.length;i+=8){v[i]=210;v[i+1]=235}
 const d=relativePowerDbFS(v.buffer);
 assert.ok(Number.isFinite(d)&&d<10);
 assert.equal(relativePowerDbFS(v.buffer),d);
 assert.throws(()=>relativePowerDbFS(new Uint8Array(12)),/64 pairs/);
});
test("calibration uses independently known distance and same fixed hardware settings",()=>{
 const o={levelDbFS:-20,frequencyMHz:98.6,gainDb:20,sampleRate:1024000};
 const calibration={referenceLevelDbFS:-11,referenceDistanceMeters:1000,pathLossExponent:3,
   referenceFrequencyMHz:98.6,referenceGainDb:20,referenceSampleRate:1024000};
 const result=calibratedRange(o,calibration);
 assert.ok(Math.abs(result.rangeMeters-1995.2623)<.01);
 assert.ok(result.lowerMeters<result.rangeMeters&&result.upperMeters>result.rangeMeters);
 assert.match(result.estimateType,/NOT MEASURED DISTANCE/);
 assert.throws(()=>calibratedRange({...o,gainDb:0},calibration),/same tuning/);
 assert.throws(()=>calibratedRange({...o,frequencyMHz:99.8},calibration),/same tuning/);
});
test("three synthetic model-hypothesis distances exercise solver WITHOUT claiming a radio fix",()=>{
 const center={lat:51,lon:7},rad=Math.PI/180;
 const points=[{lat:51.04,lon:6.94},{lat:50.96,lon:7.04},{lat:51.05,lon:7.05}];
 const stations=points.map(p=>({...p,type:"station",modelType:"CALIBRATED_RSSI_ESTIMATE",
   rangeMeters:Math.hypot((p.lat-center.lat)*111319.49079327358,
     (p.lon-center.lon)*111319.49079327358*Math.cos(center.lat*rad))}));
 const solution=solveCalibratedRF(stations);
 assert.ok(Math.abs(solution.lat-center.lat)<.0001);
 assert.ok(Math.abs(solution.lon-center.lon)<.0001);
 assert.match(solution.quality,/UNVALIDATED/);
 assert.match(solution.method,/RF-ONLY/);
});
test("aircraft or satellite positions cannot be used as fixed-terrestrial 2D ranging sources",()=>{
 const invalid=[{lat:51,lon:7,type:"station",modelType:"CALIBRATED_RSSI_ESTIMATE",rangeMeters:1200},
   {lat:51.01,lon:7,type:"aircraft",modelType:"CALIBRATED_RSSI_ESTIMATE",rangeMeters:1500},
   {lat:51.015,lon:7.02,type:"station",modelType:"CALIBRATED_RSSI_ESTIMATE",rangeMeters:1800}];
 assert.throws(()=>solveCalibratedRF(invalid),/fixed ground/);
 assert.throws(()=>solveCalibratedRF(invalid.slice(0,2)),/3 independently/);
});
