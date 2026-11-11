import test from "node:test";
import assert from "node:assert/strict";
import {destination,ringPoints,exampleRings,groundDistanceMeters,validRangeSources} from "../core/evidence.mjs";
import {trilaterate2D} from "../core/positioning.mjs";
test("three range circles intersect at independently defined simulated point",()=>{
 const example=exampleRings({lat:51.26,lon:7.18});
 assert.equal(example.simulated,true);
 assert.equal(example.stations.length,3);
 assert.ok(example.stations.every(s=>s.measured===false&&s.source.includes("SYNTHETIC")));
 for(const station of example.stations){
   const d=groundDistanceMeters(station,example.solution);
   assert.ok(Math.abs(station.rangeMeters-d)<.001);
   const ring=ringPoints(station.lat,station.lon,station.rangeMeters);
   assert.equal(ring.length,97);
   for(const pt of ring.filter((_,i)=>i%12===0))
     assert.ok(Math.abs(groundDistanceMeters(station,pt)-station.rangeMeters)<.1);
 }
 assert.equal(validRangeSources(example.stations),false);
});
test("trilateration requires real measured input and returns a labeled experiment",()=>{
 const example=exampleRings({lat:51.26,lon:7.18});
 const data=example.stations.map(s=>({...s,measured:true,source:"SYNTHETIC TEST FIXTURE - NOT RADIO"}));
 assert.ok(validRangeSources(data));
 const solution=trilaterate2D(data);
 assert.ok(groundDistanceMeters(solution,example.solution)<50);
 assert.match(solution.quality,/UNVALIDATED/);
});
test("ring and source validation rejects invented, missing or malformed measurements",()=>{
 assert.equal(validRangeSources([{lat:51,lon:7,rangeMeters:100,measured:true}]),false);
 assert.equal(validRangeSources(Array.from({length:3},()=>({lat:51,lon:7,rangeMeters:100,measured:false}))),false);
 assert.equal(validRangeSources(Array.from({length:3},()=>({lat:NaN,lon:7,rangeMeters:100,measured:true}))),false);
 assert.throws(()=>ringPoints(91,7,2000));
 assert.throws(()=>destination(50,7,-50,0));
 assert.throws(()=>ringPoints(50,7,2000,7));
});