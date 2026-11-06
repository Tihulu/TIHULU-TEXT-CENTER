import test from "node:test";
import assert from "node:assert/strict";
import {fmFrequencies,normalizeRadioTowers,normalizeOpenSkyStates,matchFMScanToCatalog} from "../core/source_catalog.mjs";
import {readFileSync} from "node:fs";
const read=path=>readFileSync(new URL("../"+path,import.meta.url),"utf8");
test("OSM tower search normalizes only genuine explicitly radio-tagged source sites",()=>{
 const list=normalizeRadioTowers({elements:[
  {type:"node",id:123,lat:50.9,lon:6.9,tags:{"communication:radio":"yes",name:"Broadcast mast",frequency:"98,6 MHz"}},
  {type:"node",id:124,lat:51,lon:7,tags:{"communication:mobile_phone":"yes",name:"Cell tower"}},
  {type:"way",id:222,center:{lat:51,lon:7.2},tags:{"communication:radio":"yes",operator:"Radio operator"}}
 ]},{lat:50.94,lon:6.96});
 assert.equal(list.length,2);
 assert.equal(list[0].frequencyMHz,98.6);
 assert.equal(list[0].hardwareReceived,false);
 assert.equal(list[0].transmitterIdentityVerified,false);
 assert.equal(list[1].frequencyMHz,null);
 assert.match(list[1].confidence,/NOT LINKED TO RF SIGNAL/);
 assert.ok(!list.some(x=>x.name==="Cell tower"));
});
test("FM scan matches are just overlap and cannot claim station identification",()=>{
 const tower=normalizeRadioTowers({elements:[{type:"node",id:10,lat:50.9,lon:6.9,
  tags:{"communication:radio":"yes",name:"Candidate broadcaster",frequency:"99.2 MHz"}}]}, {lat:50.9,lon:6.9});
 const overlap=matchFMScanToCatalog([{frequencyMHz:99.2,levelDbFS:-21,sampleBytes:8192}],tower);
 assert.equal(overlap.length,1);
 assert.equal(overlap[0].candidateIds.length,1);
 assert.match(overlap[0].matchQuality,/IDENTITY NOT DECODED/);
 assert.deepEqual(fmFrequencies({name:"Random",frequency:"unlisted"}),[]);
});
test("OpenSky internet-only aircraft must have valid ICAO and recent positions",()=>{
 const now=Date.parse("2026-11-06T09:00:00Z");
 const recent=Math.floor(now/1000)-10;
 const rows=normalizeOpenSkyStates({states:[
  ["3c1234","ABC123","Germany",recent,recent,6.9,50.9,1200,false,0,0,0,null,1244],
  ["ZZZZZZ","BAD","Germany",recent,recent,7,51,1200],
  ["3c2345","OLD","Germany",recent-500,recent-500,7,51,1200]
 ].map(a=>[...a,...Array(Math.max(0,17-a.length)).fill(null)])},now);
 assert.equal(rows.length,1);
 assert.equal(rows[0].icao,"3c1234");
 assert.equal(rows[0].hardwareReceived,false);
 assert.match(rows[0].metadataOrigin,/INTERNET/);
});
test("Catalog and FM sweep cannot use device location API or invent airport sources",()=>{
 const m=read("web/catalog_discovery.mjs"),usb=read("web/usb_sdr.mjs"),app=read("web/app.mjs"),html=read("index.html");
 assert.doesNotMatch(m,/navigator\.geolocation/);
 assert.match(m,/overpass-api\.de\/api\/interpreter/);
 assert.match(m,/OpenSky/);
 assert.match(usb,/async function fmSweep\(/);
 assert.match(usb,/relativePowerDbFS\(raw\)/);
 assert.match(usb,/tihulu:rf-fm-sweep-results/);
 assert.match(m,/tihulu:rf-fm-sweep-request/);
 assert.match(m,/tihulu\.rfgeo\.adsb\.v1/);
 assert.match(app,/catalogAntennaAircraft/);
 for(const id of ["catalog-discover","catalog-add-frequencies","catalog-aircraft","catalog-fm-scan",
   "catalog-tower-list","catalog-antenna-aircraft-list","catalog-adsb-status"]){
   assert.ok(html.includes('id="'+id+'"'),"Missing "+id);
 }
 const sw=read("sw.js");assert.match(sw,/core\/source_catalog\.mjs/);assert.match(sw,/web\/catalog_discovery\.mjs/);
});
