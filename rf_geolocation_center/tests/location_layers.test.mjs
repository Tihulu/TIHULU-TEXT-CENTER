import test from "node:test";
import assert from "node:assert/strict";
import {LOCATION_LAYERS,layerReadiness,visibleLayerPreferences} from "../core/location_layers.mjs";
import {readFileSync} from "node:fs";
const read=name=>readFileSync(new URL(name,import.meta.url),"utf8");
test("GPS / GPS-free / radio / aircraft / satellites remain scientifically distinct",()=>{
 assert.deepEqual(LOCATION_LAYERS.map(x=>x.id),["gnss","device","gpsfree","radio","aircraft","ground","satellites","cached","demo"]);
 assert.equal(visibleLayerPreferences(null).satellites,false,"Predicted satellites are off by default");
 assert.equal(visibleLayerPreferences({satellites:true,aircraft:false}).satellites,true);
 assert.equal(visibleLayerPreferences({satellites:true,aircraft:false}).aircraft,false);
});
test("browser coordinates never imply a verified GPS-free Wi-Fi or cellular fix",()=>{
 const now=Date.parse("2026-11-06T08:00:00Z");
 const s=layerReadiness({browser:{lat:50.9,lon:6.9,acquiredAt:new Date(now-3000).toISOString()}},now);
 assert.equal(s.device.state,"FIX");
 assert.equal(s.gpsfree.state,"UNAVAILABLE");
 assert.equal(s.gnss.state,"NO FIX");
 assert.equal(s.satellites.state,"NO DATA");
});
test("a current dedicated NMEA fix is distinct from predicted orbital references",()=>{
 const now=Date.parse("2026-11-06T08:00:00Z");
 const s=layerReadiness({serialFix:{lat:51,lon:7},serialAt:now-3000,orbits:[{lat:0,lon:0}]},now);
 assert.equal(s.gnss.state,"FIX");
 assert.equal(s.satellites.state,"PREDICTED");
 assert.equal(s.device.state,"NO FIX");
});
test("aircraft and ground references alone cannot yield radio position",()=>{
 const s=layerReadiness({references:[{type:"aircraft",lat:50,lon:7},{type:"station",lat:51,lon:8}]});
 assert.equal(s.aircraft.state,"REFERENCES");
 assert.equal(s.ground.state,"REFERENCES");
 assert.equal(s.radio.state,"NO MEASUREMENT");
});
test("experimental measured radio range location remains distinct from GNSS",()=>{
 const s=layerReadiness({ranges:{lat:50.9,lon:7},rangeInputs:[{},{},{}],cachedPosition:{lat:50,lon:7}});
 assert.equal(s.radio.state,"ESTIMATED");
 assert.equal(s.gnss.state,"NO FIX");
 assert.equal(s.cached.state,"CACHED");
 assert.equal(s.demo.state,"SIMULATED");
});
test("source layer toggles and USB self test are accessible without DevTools Console",()=>{
 const html=read("../index.html");
 for(const id of ["layer-gnss","layer-device","layer-gpsfree","layer-ranges","layer-aircraft",
   "layer-stations","layer-orbits","layer-cached","layer-demo",
   "layer-only-fixes","layer-show-references","layer-defaults","usb-selftest","live-usb-check"]){
   assert.ok(html.includes('id="'+id+'"'),"Missing "+id);
 }
 const app=read("../web/app.mjs"),usb=read("../web/usb_sdr.mjs");
 assert.match(app,/renderMethodReadiness/);
 assert.match(app,/layerShown\("aircraft"\)/);
 assert.match(app,/layerShown\("satellites"\)/);
 assert.match(usb,/async function selfTest\(/);
 assert.match(usb,/await device\.claimInterface\(0\)/);
 assert.match(usb,/await device\.releaseInterface\(0\)/);
 assert.match(usb,/await device\.close\(\)/);
});
