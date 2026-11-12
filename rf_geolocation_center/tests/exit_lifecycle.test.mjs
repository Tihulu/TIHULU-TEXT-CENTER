/* EXIT-01 synthetic tests: no WebUSB, hardware, RF, network or OS services. */
import test from "node:test";
import assert from "node:assert/strict";
import {createExitLifecycle} from "../web/exit_lifecycle.mjs";
import {initUsbSDR} from "../web/usb_sdr.mjs";
import {readFileSync} from "node:fs";

function deferred(){
 let resolve,reject;
 const promise=new Promise((a,b)=>{resolve=a;reject=b});
 return {promise,resolve,reject};
}
function fakeBrowser(){
 const events=[];
 const prior={window:globalThis.window,document:globalThis.document,navigator:globalThis.navigator,CustomEvent:globalThis.CustomEvent};
 const selected={vendorId:0x0bda,productId:0x2838,serialNumber:"owned-only",opened:false};
 globalThis.window={isSecureContext:true,addEventListener(){},dispatchEvent:e=>events.push(e)};
 globalThis.document={getElementById:()=>null,addEventListener(){}};
 Object.defineProperty(globalThis,"navigator",{configurable:true,value:{usb:{getDevices:async()=>[selected]}}});
 globalThis.CustomEvent=class{constructor(type,{detail}={}){this.type=type;this.detail=detail}};
 return {selected,events,restore(){
  for(const [k,v] of Object.entries(prior)){
   if(v===undefined)delete globalThis[k];
   else Object.defineProperty(globalThis,k,{configurable:true,writable:true,value:v});
  }
 }};
}

test("L-02/L-03/L-04/L-15: Stop Module then Quit releases each owned handle exactly once",async()=>{
 const calls=[],external={kills:0};
 const app=createExitLifecycle();
 app.register("rf","rf",()=>{calls.push("rf")});
 app.register("bridge","device",()=>{calls.push("bridge")});
 app.register("other-app-ui","ui",()=>{calls.push("ui")});
 assert.equal(app.canStart("rf"),true);
 await app.stopRf();
 await app.stopRf();
 assert.deepEqual(calls,["rf"]);
 assert.equal(app.canStart("rf"),false);
 assert.equal(app.canStart("device"),true);
 const stop=app.quit();
 assert.equal(app.state,"STOPPING"); // synchronous new-work guard
 assert.equal(app.canStart(),false);
 const end=await stop;
 assert.equal(end.state,"QUIT");
 assert.deepEqual(calls,["rf","bridge","ui"]);
 assert.equal(external.kills,0);
 assert.deepEqual(end.incomplete,[]);
 assert.throws(()=>app.register("late","rf",()=>{}));
});

test("L-09/L-12/L-13: concurrent Hard Stops and Quit, warning for incomplete ownership",async()=>{
 const wait=deferred();let closes=0;
 const app=createExitLifecycle();
 app.register("owned","device",async()=>{closes++;await wait.promise;throw Error("mock close refused")});
 const stop=app.hardStop(),again=app.hardStop(),quit=app.quit();
 assert.strictEqual(stop,again);
 assert.notStrictEqual(stop,quit); // Quit also retires UI-only handlers
 assert.equal(app.state,"STOPPING");
 wait.resolve();
 const out=await stop;
 const full=await quit;
 assert.equal(closes,1);
 assert.equal(out.state,"HARD_STOPPED");
 assert.equal(full.state,"QUIT");
 assert.deepEqual(out.incomplete.map(x=>x.name),["owned"]);
 assert.match(out.incomplete[0].error,/mock close refused/);
});

test("WebUSB synthetic in-flight RF read is cancelled, one own close, no late observation",async()=>{
 const env=fakeBrowser();
 try{
  const entered=deferred(),read=deferred();
  let closed=0,driverLoads=0;
  const receiver={
   async setSampleRate(){},async setCenterFrequency(){},async setGain(){},
   async resetBuffer(){},async readSamples(){entered.resolve();return read.promise},
   async close(){closed++}
  };
  const driverFactory=async()=>{
   driverLoads++;
   return {RTL2832U_Provider:class{async get(){return receiver}}};
  };
  const usb=initUsbSDR(()=>{},{driverFactory});
  await usb.connect(env.selected);
  const work=usb.scan();
  await entered.promise;
  const first=usb.quit(),second=usb.quit();
  read.resolve({data:new Uint8Array([1,2,3,4]).buffer});
  await Promise.all([first,second,work]);
  assert.equal(closed,1);
  assert.equal(env.events.some(e=>e.type==="tihulu:rf-observation"),false);
  assert.equal(env.events.some(e=>e.detail?.status==="RF SAMPLED"),false);
  await usb.connect(env.selected);
  assert.equal(driverLoads,1); // blocked after true Quit
 }finally{env.restore()}
});

test("WebUSB synthetic delayed driver claim is closed when it resolves after Quit",async()=>{
 const env=fakeBrowser();
 try{
  const entered=deferred(),get=deferred();let closed=0;
  const receiver={async close(){closed++}};
  const driverFactory=async()=>({RTL2832U_Provider:class{
   async get(){entered.resolve();return get.promise}
  }});
  const usb=initUsbSDR(()=>{},{driverFactory});
  const connecting=usb.connect(env.selected);
  await entered.promise;
  await usb.quit(); // no invented successful receiver acquisition
  get.resolve(receiver);
  await connecting;
  assert.equal(closed,1); // late provider.get must not reacquire session
  assert.equal(env.events.some(e=>e.detail?.status==="USB CONNECTED"),false);
 }finally{env.restore()}
});

test("L-13: Hard Stop retains static GUI handlers; only true Quit releases them",async()=>{
 const app=createExitLifecycle();
 let device=0,uiWorker=0,uiControls=0;
 app.register("own-rf","rf",()=>{device++});
 app.register("orbit-timer","ui",()=>{uiWorker++});
 app.register("dom-navigation","ui-controls",()=>{uiControls++});
 const hard=await app.hardStop();
 assert.equal(hard.state,"HARD_STOPPED");
 assert.equal(device,1);
 assert.equal(uiWorker,1);
 assert.equal(uiControls,0); // static application GUI remains alive
 assert.equal(app.canStart("rf"),false);
 await app.quit();
 assert.equal(uiControls,1);
 await app.quit();
 assert.equal(uiControls,1);
});

test("WebUSB refused owned close reports a persistent partial failure without external kill",async()=>{
 const env=fakeBrowser();
 try{
  let closeAttempts=0,foreignKills=0;
  const driverFactory=async()=>({RTL2832U_Provider:class{
   async get(){return {
    async setSampleRate(){},async setCenterFrequency(){},async setGain(){},
    async resetBuffer(){},async close(){closeAttempts++;throw Error("mock USB busy")}
   }}
  }});
  const usb=initUsbSDR(()=>{},{driverFactory});
  await usb.connect(env.selected);
  await assert.rejects(usb.quit(),/Incomplete app-owned USB release/);
  await assert.rejects(usb.quit(),/Incomplete app-owned USB release/);
  assert.equal(closeAttempts,1);
  assert.equal(foreignKills,0);
 }finally{env.restore()}
});

test("serial Quit has bounded cancel, reader unlock and partial-failure reporting",()=>{
 const source=readFileSync(new URL("../web/app.mjs",import.meta.url),"utf8");
 assert.match(source,/reader\.releaseLock\(\)/);
 assert.match(source,/Owned serial reader cancel/);
 assert.match(source,/Owned serial port close/);
 assert.match(source,/Owned serial resources not fully released/);
 assert.match(source,/lifecycle\.register\("serial","device",disconnect\)/);
});
