/* EXIT-01 independent contract review: all receivers and metadata are mocked.
 * No WebUSB, RF, OS service, geolocation API, real network or persisted data.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {initUsbSDR} from "../web/usb_sdr.mjs";
import {createExitLifecycle} from "../web/exit_lifecycle.mjs";
import {positionProvenance,radioProvenance,aircraftProvenance,orbitalProvenance}
  from "../core/source_provenance.mjs";
import {matchedBroadcastSources} from "../core/scan_map.mjs";

function deferred(){
 let resolve,reject;
 const promise=new Promise((yes,no)=>{resolve=yes;reject=no});
 return {promise,resolve,reject};
}
function fakeBrowser(){
 const prior={};
 for(const key of ["window","document","navigator","CustomEvent"])
  prior[key]=Object.getOwnPropertyDescriptor(globalThis,key);
 const events=[];
 const device={vendorId:0x0bda,productId:0x2838,serialNumber:"SYNTHETIC-ONLY",opened:false};
 Object.defineProperty(globalThis,"window",{configurable:true,writable:true,
   value:{isSecureContext:true,addEventListener(){},dispatchEvent(e){events.push(e)}}});
 Object.defineProperty(globalThis,"document",{configurable:true,writable:true,
   value:{getElementById(){return null},addEventListener(){}}});
 Object.defineProperty(globalThis,"navigator",{configurable:true,writable:true,
   value:{usb:{async getDevices(){return [device]}}}});
 Object.defineProperty(globalThis,"CustomEvent",{configurable:true,writable:true,
   value:class{constructor(type,{detail}={}){this.type=type;this.detail=detail}}});
 return {events,device,restore(){
   for(const key of Object.keys(prior)){
     if(prior[key])Object.defineProperty(globalThis,key,prior[key]);
     else delete globalThis[key];
   }
 }};
}

test("EXIT-01 provenance: physical I/Q, internet aircraft, OSM and GNSS are distinct",()=>{
 const now=Date.parse("2026-11-12T08:00:00Z");
 const usb=radioProvenance("RF SAMPLED","sampled at 98.6 MHz");
 assert.equal(usb.hasRF,true);
 assert.equal(usb.hasPosition,false);
 assert.match(usb.detail,/NOT a GNSS lock or a position fix/);
 assert.equal(radioProvenance("USB CONNECTED").hasRF,false);
 const device=positionProvenance({browser:{lat:50.9,lon:7,acquiredAt:new Date(now-1000).toISOString()}},now);
 assert.equal(device.kind,"device");
 assert.equal(device.antenna,false);
 assert.match(device.detail,/browser does NOT disclose/);
 const externalGnss=positionProvenance({serialFix:{lat:50.9,lon:7},serialAt:now-1000},now);
 assert.equal(externalGnss.kind,"receiver");
 assert.match(externalGnss.detail,/NOT the Nooelec RTL-SDR/);
 const aircraft=aircraftProvenance([{type:"aircraft",lat:51,lon:7}]);
 assert.equal(aircraft.hasPosition,false);
 assert.match(aircraft.detail,/do not determine your receiver position/);
 assert.equal(orbitalProvenance(false,4).fix,false);
 assert.equal(positionProvenance({cachedPosition:{lat:50.9,lon:7}},now).location,false);
 assert.equal(positionProvenance({},now).fix,"NO POSITION FIX");
 const tower={id:"osm-node/42",name:"Reference only",lat:50.9,lon:7,
              frequenciesMHz:[98.6],televisionFrequenciesMHz:[514]};
 const mapped=matchedBroadcastSources([tower],
   [{frequencyMHz:98.6,levelDbFS:-26,measuredAt:"2026-11-12T08:00:00Z"}],
   [{frequencyMHz:514,name:"Synthetic TV service"}]);
 assert.equal(mapped.length,2);
 for(const entry of mapped){
   assert.equal(entry.siteId,"osm-node/42");
   assert.equal(entry.receiverPosition,false);
   assert.equal(entry.distanceMeters,null);
   assert.match(entry.match,/FREQUENCY OVERLAP ONLY/);
   assert.match(entry.metadataOrigin,/EXTERNAL OSM/);
 }
 assert.deepEqual(matchedBroadcastSources([tower],[{frequencyMHz:98.6}],[]),[]);
});

test("EXIT-01 USB serialized GNSS read rejects simultaneous RF capture and FM sweep",async()=>{
 const env=fakeBrowser();
 try{
   const entered=deferred(),read=deferred();
   const foreign={stopped:0,lease:"foreign-held"},calls={reads:0,closes:0,rates:0};
   const rx={
     async setSampleRate(){calls.rates++},
     async setCenterFrequency(){},
     async setGain(){},
     async resetBuffer(){},
     async readSamples(){calls.reads++;entered.resolve();return read.promise},
     async close(){calls.closes++}
   };
   const usb=initUsbSDR(()=>{}, {driverFactory:async()=>({
     RTL2832U_Provider:class{async get(){return rx}}
   })});
   await usb.connect(env.device);
   const scan=usb.scan();
   await entered.promise;
   await Promise.all([usb.captureRF(98.6,"mapped-source"),usb.fmSweep(98.5,98.7,.1)]);
   const statuses=env.events.filter(e=>e.type==="tihulu:receiver-status").map(e=>e.detail.status);
   assert.ok(statuses.includes("RF BUSY"),"Capture must be rejected while the GNSS I/Q read is pending");
   assert.ok(statuses.includes("FM SCAN BUSY"),"FM scan must not preempt the same device");
   assert.equal(calls.reads,1);
   assert.equal(env.events.some(e=>e.type==="tihulu:rf-observation"),false);
   read.resolve({data:new Uint8Array(4*1024*1024).fill(126).buffer});
   await scan;
   assert.equal(calls.rates,1,"Resampler is set at connection, never by a concurrent read");
   assert.ok(env.events.some(e=>e.detail?.status==="RF SAMPLED"));
   assert.equal(radioProvenance("RF SAMPLED").hasPosition,false);
   await usb.quit();
   assert.equal(calls.closes,1);
   assert.equal(foreign.stopped,0);
   assert.equal(foreign.lease,"foreign-held");
 }finally{env.restore()}
});

test("EXIT-01 full FM sweep reads bounded raw sample blocks and never identifies a station",async()=>{
 const env=fakeBrowser();
 try{
   const calls={rates:[],freqs:[],samples:[],closes:0};
   const chunk=new Uint8Array(8192).fill(126);
   const receiver={
     async setSampleRate(rate){calls.rates.push(rate)},
     async setCenterFrequency(hz){calls.freqs.push(hz)},
     async setGain(){},async resetBuffer(){},
     async readSamples(n){calls.samples.push(n);return {data:chunk}},
     async close(){calls.closes++}
   };
   const usb=initUsbSDR(()=>{},{driverFactory:async()=>({
     RTL2832U_Provider:class{async get(){return receiver}}
   })});
   await usb.connect(env.device);
   await usb.fmSweep();
   const result=env.events.find(e=>e.type==="tihulu:rf-fm-sweep-results");
   assert.ok(result,"Synthetic FM read fixture must publish an energy-only result");
   const readings=result.detail.readings;
   assert.ok(readings.length>=200 && readings.length<=220);
   assert.ok(readings.some(r=>Math.abs(r.frequencyMHz-98.6)<1e-6));
   assert.ok(calls.samples.every(n=>n===8192));
   assert.equal(calls.samples.length,readings.length);
   assert.deepEqual(calls.rates,[1024000]);
   assert.equal(calls.freqs.at(-1),1575420000,"restore original GNSS L1 tuner setting");
   for(const item of readings){
     assert.equal(item.signalDecoded,false);
     assert.match(item.statement,/NOT STATION ID OR DISTANCE/);
     assert.ok(Number.isFinite(item.levelDbFS));
   }
   assert.equal(env.events.some(e=>e.type==="tihulu:rf-observation"),false);
   await usb.quit();
   assert.equal(calls.closes,1);
 }finally{env.restore()}
});

test("EXIT-01 tuner register failure is diagnostic, not an accepted RF observation",async()=>{
 const env=fakeBrowser();
 try{
   let closes=0,reads=0;
   const rx={
     async setSampleRate(){},
     async setCenterFrequency(){},
     async setGain(gain){
       if(gain===20)throw Error("synthetic setRegBuffer control transfer failed");
     },
     async resetBuffer(){},
     async readSamples(){reads++;return {data:new Uint8Array(8192)}},
     async close(){closes++}
   };
   const usb=initUsbSDR(()=>{},{driverFactory:async()=>({
     RTL2832U_Provider:class{async get(){return rx}}
   })});
   await usb.connect(env.device);
   await usb.captureRF(98.6,"osm-node/42");
   assert.equal(reads,0);
   assert.equal(closes,1,"Only the app-owned radio handle closes after register failure");
   assert.equal(env.events.some(e=>e.type==="tihulu:rf-observation"),false);
   const error=env.events.find(e=>e.type==="tihulu:rf-capture-failed");
   assert.ok(error,"User must receive an explicit failed-capture event");
   assert.equal(error.detail.recoverable,true);
   assert.match(error.detail.message,/setRegBuffer control transfer failed/);
   await usb.quit();
   assert.equal(closes,1);
 }finally{env.restore()}
});

test("EXIT-01 RF Stop has immediate gate while Quit drains deferred owned work once",async()=>{
 const rfDrain=deferred(),calls=[];
 const supervisor=createExitLifecycle();
 supervisor.register("tab-owned-rf","rf",async()=>{calls.push("rf");await rfDrain.promise});
 supervisor.register("tab-owned-bridge","device",()=>{calls.push("bridge")});
 supervisor.register("static-ui","ui-controls",()=>{calls.push("ui")});
 const moduleStop=supervisor.stopRf();
 assert.equal(supervisor.rfStopped,true);
 assert.equal(supervisor.canStart("rf"),false);
 assert.equal(supervisor.canStart("device"),true);
 const exit=supervisor.quit();
 assert.equal(supervisor.state,"STOPPING");
 assert.equal(supervisor.canStart("device"),false);
 assert.throws(()=>supervisor.register("late-owned","device",()=>{}));
 rfDrain.resolve();
 const [moduleOutcome,quitOutcome]=await Promise.all([moduleStop,exit]);
 assert.equal(moduleOutcome.results.length,1);
 assert.equal(quitOutcome.state,"QUIT");
 assert.deepEqual(quitOutcome.incomplete,[]);
 assert.deepEqual(calls.sort(),["bridge","rf","ui"]);
 await supervisor.hardStop();
 await supervisor.quit();
 assert.equal(calls.length,3,"Each app-owned resource is released once");
});
