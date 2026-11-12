/* RQ-098 EXIT-01 Phase 2: synthetic WebUSB receiver lifecycle only.
 * The existing EXIT-01 register-error regression in exit01_contract_review.test.mjs
 * is intentionally unchanged. No real RF, WebUSB, SDR, services or filesystem.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {initUsbSDR} from "../web/usb_sdr.mjs";

function deferred(){
 let resolve,reject;
 const promise=new Promise((yes,no)=>{resolve=yes;reject=no});
 return {promise,resolve,reject};
}
function mockTab(){
 const keys=["window","document","navigator","CustomEvent"];
 const before=new Map(keys.map(key=>[key,Object.getOwnPropertyDescriptor(globalThis,key)]));
 const events=[],buttons=[];
 const chosen={vendorId:0x0bda,productId:0x2838,serialNumber:"fake-tab-lease",opened:false};
 Object.defineProperty(globalThis,"window",{configurable:true,writable:true,value:{
   isSecureContext:true,addEventListener(){},dispatchEvent(event){events.push(event)}
 }});
 Object.defineProperty(globalThis,"document",{configurable:true,writable:true,value:{
   getElementById(){return null},addEventListener(){}
 }});
 Object.defineProperty(globalThis,"navigator",{configurable:true,writable:true,value:{
   usb:{async getDevices(){return [chosen]}}
 }});
 Object.defineProperty(globalThis,"CustomEvent",{configurable:true,writable:true,value:class{
   constructor(type,{detail}={}){this.type=type;this.detail=detail}
 }});
 return {events,buttons,chosen,restore(){
   for(const key of keys){
     const old=before.get(key);
     if(old)Object.defineProperty(globalThis,key,old);
     else delete globalThis[key];
   }
 }};
}
function createUsb(receiver,foreign){
 let providerClaims=0;
 return {
   usb:initUsbSDR(()=>{}, {driverFactory:async()=>({
     RTL2832U_Provider:class{async get(){providerClaims++;return receiver}}
   })}),
   get claims(){return providerClaims},
   foreign
 };
}
function eventsOf(tab,type){
 return tab.events.filter(event=>event.type===type);
}

test("FM control-transfer failure settles own sampling lease, closes once and emits an honest error",async()=>{
 const tab=mockTab();
 try{
   const foreign={lease:"other-app-SDR",stopped:0};
   let closes=0,readCalls=0;
   const receiver={
     async setSampleRate(){},async setCenterFrequency(){},
     async setGain(value){if(value===20)throw Error("synthetic setRegBuffer USB control transfer failed")},
     async resetBuffer(){},async readSamples(){readCalls++;return {data:new Uint8Array(8192)}},
     async close(){closes++}
   };
   const {usb}=createUsb(receiver,foreign);
   await usb.connect(tab.chosen);
   await usb.fmSweep(98.5,98.8,.1);
   assert.equal(readCalls,0);
   assert.equal(closes,1);
   assert.deepEqual(eventsOf(tab,"tihulu:rf-fm-sweep-results"),[]);
   assert.deepEqual(eventsOf(tab,"tihulu:rf-observation"),[]);
   const failed=eventsOf(tab,"tihulu:rf-fm-sweep-failed");
   assert.equal(failed.length,1);
   assert.equal(failed[0].detail.hardwareControlFailed,true);
   assert.equal(failed[0].detail.releaseFailed,false);
   assert.match(failed[0].detail.message,/setRegBuffer USB control transfer failed/);
   assert.match(failed[0].detail.message,/Receiver released/);
   await usb.quit();
   assert.equal(closes,1);
   assert.equal(foreign.stopped,0);
   assert.equal(foreign.lease,"other-app-SDR");
 }finally{tab.restore()}
});

test("FM tuning failure after real mocked samples publishes no partial successful spectrum",async()=>{
 const tab=mockTab();
 try{
   let closeCalls=0,readCalls=0;
   const receiver={
     async setSampleRate(){},
     async setCenterFrequency(hz){
       if(hz===98700000)throw Error("synthetic tuner control transfer error");
     },
     async setGain(){},async resetBuffer(){},
     async readSamples(){readCalls++;return {data:new Uint8Array(8192).fill(125)}},
     async close(){closeCalls++}
   };
   const {usb}=createUsb(receiver);
   await usb.connect(tab.chosen);
   await usb.fmSweep(98.5,98.8,.1);
   assert.ok(readCalls>=1);
   assert.equal(closeCalls,1);
   assert.equal(eventsOf(tab,"tihulu:rf-fm-sweep-results").length,0);
   const failure=eventsOf(tab,"tihulu:rf-fm-sweep-failed");
   assert.equal(failure.length,1);
   assert.equal(failure[0].detail.hardwareControlFailed,true);
   assert.ok(failure[0].detail.completed>0);
   assert.match(failure[0].detail.message,/synthetic tuner control transfer error/);
   await usb.quit();
   assert.equal(closeCalls,1);
 }finally{tab.restore()}
});

test("explicit Disconnect during in-flight I/Q read waits for actual read and emits no late RF",async()=>{
 const tab=mockTab();
 try{
   const readEntered=deferred(),readSettled=deferred();
   let closes=0,reads=0;
   const foreign={lease:"external",closes:0};
   const receiver={
     async setSampleRate(){},async setCenterFrequency(){},async setGain(){},
     async resetBuffer(){},
     async readSamples(){reads++;readEntered.resolve();return readSettled.promise},
     async close(){closes++}
   };
   const {usb}=createUsb(receiver,foreign);
   await usb.connect(tab.chosen);
   const capture=usb.captureRF(98.6,"site-reference");
   await readEntered.promise;
   const disconnect=usb.release(); // explicit owner-only Disconnect; not global Quit
   await Promise.resolve();
   assert.equal(closes,0,"Do not close the active receiver before its pending read finishes");
   readSettled.resolve({data:new Uint8Array(16384).fill(127).buffer});
   await Promise.all([disconnect,capture]);
   assert.equal(reads,1);
   assert.equal(closes,1);
   assert.equal(eventsOf(tab,"tihulu:rf-observation").length,0);
   assert.equal(eventsOf(tab,"tihulu:rf-fm-sweep-results").length,0);
   assert.equal(foreign.closes,0);
   await usb.quit();
   assert.equal(closes,1);
 }finally{tab.restore()}
});

test("concurrent external Quit shares the active read barrier, closes once, blocks restart",async()=>{
 const tab=mockTab();
 try{
   const started=deferred(),gate=deferred();
   let closes=0,claims=0;
   const foreign={jobs:2,stopped:0};
   const receiver={
     async setSampleRate(){},async setCenterFrequency(){},async setGain(){},
     async resetBuffer(){},
     async readSamples(){started.resolve();return gate.promise},
     async close(){closes++}
   };
   const usb=initUsbSDR(()=>{},{driverFactory:async()=>({
     RTL2832U_Provider:class{async get(){claims++;return receiver}}
   })});
   await usb.connect(tab.chosen);
   const pending=usb.scan();
   await started.promise;
   const first=usb.quit(),again=usb.quit(),manual=usb.release();
   assert.strictEqual(first,again,"All concurrent owner cleanup calls await same release promise");
   assert.strictEqual(first,manual);
   await Promise.resolve();
   assert.equal(closes,0);
   gate.resolve({data:new Uint8Array(16384).fill(125).buffer});
   await Promise.all([pending,first,again,manual]);
   assert.equal(closes,1);
   assert.equal(eventsOf(tab,"tihulu:rf-observation").length,0);
   assert.equal(tab.events.filter(e=>e.detail?.status==="RF SAMPLED").length,0);
   await usb.connect(tab.chosen);
   assert.equal(claims,1);
   assert.equal(foreign.stopped,0);
   assert.equal(foreign.jobs,2);
 }finally{tab.restore()}
});

test("repeated Stop and Quit are idempotent even when owned close is delayed",async()=>{
 const tab=mockTab();
 try{
   const closeStarted=deferred(),finishClose=deferred();
   let closeCalls=0;
   const receiver={
     async setSampleRate(){},async setCenterFrequency(){},async setGain(){},
     async resetBuffer(){},
     async close(){closeCalls++;closeStarted.resolve();return finishClose.promise}
   };
   const {usb}=createUsb(receiver);
   await usb.connect(tab.chosen);
   const stop=usb.release(),again=usb.release();
   await closeStarted.promise;
   const quit=usb.quit();
   assert.strictEqual(stop,again);
   assert.strictEqual(stop,quit);
   assert.equal(closeCalls,1);
   finishClose.resolve();
   await Promise.all([stop,again,quit]);
   await usb.quit();
   await usb.release();
   assert.equal(closeCalls,1);
 }finally{tab.restore()}
});

test("failed internal close is STOP_FAILED_PARTIAL, never healed by a second empty-handle Quit",async()=>{
 const tab=mockTab();
 try{
   let closes=0,claims=0;
   const receiver={
     async setSampleRate(){},async setCenterFrequency(){},
     async setGain(gain){if(gain===20)throw Error("synthetic register control transfer failed")},
     async resetBuffer(){},
     async close(){closes++;throw Error("synthetic owned USB close refused")}
   };
   const usb=initUsbSDR(()=>{},{driverFactory:async()=>({
     RTL2832U_Provider:class{async get(){claims++;return receiver}}
   })});
   await usb.connect(tab.chosen);
   await usb.captureRF(98.6,"unverified-site");
   const fail=eventsOf(tab,"tihulu:rf-capture-failed");
   assert.equal(fail.length,1);
   assert.equal(fail[0].detail.releaseFailed,true);
   assert.equal(fail[0].detail.recoverable,false);
   assert.match(fail[0].detail.message,/STOP_FAILED_PARTIAL/);
   assert.equal(eventsOf(tab,"tihulu:rf-observation").length,0);
   await assert.rejects(usb.quit(),/Incomplete app-owned USB release/);
   await assert.rejects(usb.release(),/Incomplete app-owned USB release/);
   await usb.connect(tab.chosen); // not permitted to reacquire an uncertain-owned lease
   assert.equal(claims,1);
   assert.equal(closes,1);
 }finally{tab.restore()}
});
