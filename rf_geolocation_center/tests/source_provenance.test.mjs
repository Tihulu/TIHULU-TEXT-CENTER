import test from "node:test";
import assert from "node:assert/strict";
import {positionProvenance,radioProvenance,orbitalProvenance,aircraftProvenance} from "../core/source_provenance.mjs";
import {readFileSync} from "node:fs";
const read=path=>readFileSync(new URL(path,import.meta.url),"utf8");
const now=Date.parse("2026-11-06T09:00:00Z");
test("RTL-SDR RF sampling NEVER claims observer location, even after successful USB acquisition",()=>{
 for(const status of ["NOT CONNECTED","USB CONNECTED","SAMPLING","RF SAMPLED","USB TEST PASS","USB OPEN FAILED"]){
  const result=radioProvenance(status,"I/Q samples available");
  assert.equal(result.hasPosition,false);
  assert.match(result.source,/RTL-SDR/);
 }
 assert.equal(radioProvenance("RF SAMPLED").hasRF,true);
 assert.equal(radioProvenance("USB CONNECTED").hasRF,false);
});
test("browser Geolocation labels OS method unknown rather than antenna or GPS-only",()=>{
 const p=positionProvenance({browser:{lat:51,lon:7,acquiredAt:new Date(now-1000).toISOString()}},now);
 assert.equal(p.kind,"device");
 assert.equal(p.antenna,false);
 assert.equal(p.location,true);
 assert.match(p.detail,/GPS, Wi-Fi, cellular, IP/);
});
test("serial GNSS NMEA is an independent external receiver, not Nooelec RTL-SDR",()=>{
 const p=positionProvenance({serialFix:{lat:51,lon:7},serialAt:now-1000},now);
 assert.equal(p.kind,"receiver");
 assert.equal(p.antenna,false);
 assert.match(p.detail,/NOT the Nooelec RTL-SDR/);
});
test("imported radio ranges, historical location and default center stay distinct",()=>{
 const r=positionProvenance({ranges:{lat:51,lon:7},rangeInputs:[{},{},{}]},now);
 assert.equal(r.kind,"import");assert.equal(r.antenna,false);
 const cached=positionProvenance({cachedPosition:{lat:51,lon:7,recordedAt:"2026-11-05T00:00:00Z"}},now);
 assert.equal(cached.kind,"cached");assert.equal(cached.location,false);
 const def=positionProvenance({},now);
 assert.equal(def.kind,"reference");assert.equal(def.location,false);
});
test("predicted satellite and imported aircraft positions never count as received RF",()=>{
 const orbit=orbitalProvenance(false,30);
 assert.match(orbit.source,/CelesTrak/);assert.equal(orbit.fix,false);
 const imported=orbitalProvenance(true,30);assert.match(imported.source,/SP3/);
 const aircraft=aircraftProvenance([{type:"aircraft",lat:51,lon:7}]);
 assert.match(aircraft.source,/User-imported/);assert.equal(aircraft.hasPosition,false);
});
test("UI shows explicit acquisition channels in Dashboard and Earth Map",()=>{
 const h=read("../index.html"),a=read("../web/app.mjs");
 for(const id of ["origin-position","origin-position-status","origin-position-method","origin-antenna",
  "origin-antenna-status","origin-antenna-method","origin-orbits","origin-orbits-method",
  "origin-aircraft","origin-aircraft-method","source-proof"]){
   assert.ok(h.includes('id="'+id+'"'),"Missing UI ID: "+id);
 }
 assert.match(a,/window\.addEventListener\("tihulu:receiver-status"/);
 assert.match(a,/renderSourceProvenance/);
});
