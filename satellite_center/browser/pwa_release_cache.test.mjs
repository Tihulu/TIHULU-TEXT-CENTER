/* Deterministic service-worker release and nested GitHub Pages tests.
 * These tests mock Cache Storage and fetch; never open USB, run RF or deploy.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync,existsSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {dirname,resolve} from "node:path";
import vm from "node:vm";

const root=dirname(fileURLToPath(import.meta.url));
const workerCode=readFileSync(resolve(root,"satellite-sw.js"),"utf8");
const scope="https://example.invalid/TIHULU-TEXT-CENTER/satellite_center/browser/";

function response(body,status=200){
 return {body,status,ok:status>=200&&status<300,type:"basic",
  clone(){return response(body,status)}};
}
function fakeWorker({missing=[],offline=false}={}){
 const events={},cachesByName=new Map(),calls=[],state={offline,skip:0,claimed:0};
 const missingNames=new Set(missing);
 class RequestStub {
  constructor(url,options={}){
   this.url=String(url);
   this.method=options.method||"GET";
   this.mode=options.mode||"cors";
  }
 }
 const net=async(request,options={})=>{
  const url=typeof request==="string"?request:request.url;
  calls.push({url,mode:request.mode||"",cache:options.cache||""});
  if(state.offline)throw Error("network unavailable");
  const file=new URL(url).pathname.split("/").pop();
  return response("network:"+url,missingNames.has(file)?404:200);
 };
 const storeFor=name=>{
  if(!cachesByName.has(name)){
   const entries=new Map();
   const instance={
    entries,
    async add(req){
     const res=await net(req);
     if(!res.ok)throw Error("failed core asset "+req.url);
     entries.set(req.url,res.clone());
    },
    async put(key,res){entries.set(typeof key==="string"?key:key.url,res.clone())},
    async match(key){return entries.get(typeof key==="string"?key:key.url)}
   };
   cachesByName.set(name,instance);
  }
  return cachesByName.get(name);
 };
 const caches={
  async open(name){return storeFor(name)},
  async keys(){return [...cachesByName.keys()]},
  async delete(name){return cachesByName.delete(name)}
 };
 const self={
  registration:{scope},
  clients:{async claim(){state.claimed++}},
  async skipWaiting(){state.skip++},
  addEventListener(name,fn){events[name]=fn}
 };
 const context={self,caches,fetch:net,Request:RequestStub,Response:{error:()=>response("network-error",0)},URL,Set};
 vm.createContext(context);
 vm.runInContext(workerCode,context,{filename:"satellite-sw.js"});
 const version=vm.runInContext("VERSION",context);
 const core=Array.from(vm.runInContext("CRITICAL",context));
 const optional=Array.from(vm.runInContext("OPTIONAL",context));
 const fire=async(name,request)=>{
  let pending,responded=false;
  const event={
   request,
   waitUntil(p){pending=Promise.resolve(p)},
   respondWith(p){responded=true;pending=Promise.resolve(p)}
  };
  events[name](event);
  return {responded,result:pending?await pending:undefined};
 };
 const request=(path,{mode="cors",method="GET"}={})=>
  {const r=new RequestStub(new URL(path,scope),{mode,method});return r};
 return {version,core,optional,state,calls,missingNames,fire,request,caches,storeFor};
}
test("PWA core covers static imports and explicitly models optional geography",()=>{
 const app=fakeWorker();
 assert.equal(app.version,"satellite-webusb-shell-20261112-v2");
 assert.ok(app.core.length>=40,"all local entrypoint ESM deps must be precached");
 for(const file of [...app.core,...app.optional]){
  assert.ok(file.startsWith("./"),file);
  assert.ok(existsSync(resolve(root,file)),"Missing source asset: "+file);
 }
 const allowed=new Set([...app.core,...app.optional]);
 for(const file of app.core.filter(name=>/\.(?:js|mjs)$/.test(name))){
  const script=readFileSync(resolve(root,file),"utf8");
  for(const match of script.matchAll(/(?:from\s*|import\s*\()\s*["'](\.[^"']+)["']/g)){
   const local=match[1].split("?")[0];
   assert.ok(allowed.has(local),file+" -> "+local+" not in precache closure");
  }
 }
 for(const file of ["./pass_window.mjs","./pass_candidates.mjs","./webusb_lifecycle.mjs",
  "./satellite_maps.mjs","./compute_selector.mjs","./fm_iq_demod.mjs"]){
  assert.ok(allowed.has(file),"offline navigation would be missing "+file);
 }
});
test("fresh SW install fails closed when a required JS file is 404",async()=>{
 const worker=fakeWorker({missing:["browser.js"]});
 await assert.rejects(worker.fire("install"),/failed core asset.*browser\.js/);
 assert.equal(worker.state.skip,0,"must not activate a broken offline shell");
});
test("optional Leaflet offline failure does not hide working critical app shell",async()=>{
 const worker=fakeWorker({missing:["leaflet.js","leaflet.css"]});
 await worker.fire("install");
 assert.equal(worker.state.skip,1);
 const cache=worker.storeFor(worker.version).entries;
 assert.ok(cache.has(new URL("browser.js",scope).href));
 assert.ok(!cache.has(new URL("leaflet.js",scope).href));
});
test("cache version activates without deleting unrelated caches",async()=>{
 const worker=fakeWorker();
 worker.storeFor("satellite-webusb-shell-20261112-v1");
 worker.storeFor("external-unrelated-cache");
 await worker.fire("install");await worker.fire("activate");
 assert.equal(worker.state.claimed,1);
 const keys=await worker.caches.keys();
 assert.ok(keys.includes(worker.version));
 assert.ok(keys.includes("external-unrelated-cache"));
 assert.ok(!keys.includes("satellite-webusb-shell-20261112-v1"));
});
test("new ?v= JS and CSS bypass stale cached code and refresh exact path only",async()=>{
 const worker=fakeWorker();
 await worker.fire("install");
 const cache=worker.storeFor(worker.version);
 const key=new URL("browser.js",scope).href;
 await cache.put(key,response("OLD"));
 const newFetch=await worker.fire("fetch",worker.request("./browser.js?v=20261112-new"));
 assert.equal(newFetch.responded,true);
 assert.equal(newFetch.result.body,"network:"+new URL("./browser.js?v=20261112-new",scope).href);
 assert.equal((await cache.match(key)).body,newFetch.result.body);
 assert.equal(worker.calls.at(-1).cache,"reload");
 const styles=await worker.fire("fetch",worker.request("./browser.css?v=20261112-new"));
 assert.equal(styles.result.ok,true);
 assert.equal(worker.calls.at(-1).cache,"reload");
});
test("offline nested-scope fallback uses exact cached module, not unrelated page",async()=>{
 const worker=fakeWorker();
 await worker.fire("install");
 worker.state.offline=true;
 const script=await worker.fire("fetch",worker.request("./browser.js?v=offline"));
 assert.equal(script.responded,true);
 assert.ok(script.result.body.includes("/TIHULU-TEXT-CENTER/satellite_center/browser/browser.js"));
 const nav=await worker.fire("fetch",worker.request("./reception.html",{mode:"navigate"}));
 assert.equal(nav.responded,true);
 assert.ok(nav.result.body.includes("/TIHULU-TEXT-CENTER/satellite_center/browser/reception.html"));
});
test("HTTP 404 is observable; no stale-code fallback hides a missing deployed script",async()=>{
 const worker=fakeWorker();
 await worker.fire("install");
 worker.state.offline=false;
 // Simulate a partial publication after a healthy shell was already cached.
 const saved=worker.storeFor(worker.version);
 worker.missingNames.add("pass_candidates.mjs");
 const code=await worker.fire("fetch",worker.request("./pass_candidates.mjs?v=bad"));
 assert.equal(code.responded,true);
 assert.equal(code.result.status,404,"Do not mask a server-side missing script with old cached bytes");
 assert.ok(saved.entries.has(new URL("pass_candidates.mjs",scope).href),
  "Keep old offline copy only for real network failures");
});
test("never intercept RF data, private URLs, unrelated assets, POST or foreign sites",async()=>{
 const worker=fakeWorker();await worker.fire("install");
 const blocked=[
  worker.request("./recording.cu8"),worker.request("./recording.wav"),
  worker.request("./data.zip"),worker.request("./private/image.png"),
  worker.request("./api/archive/example"),worker.request("./browser.js",{method:"POST"}),
  {url:"https://foreign.invalid/TIHULU-TEXT-CENTER/satellite_center/browser/browser.js",
   method:"GET",mode:"cors"}
 ];
 for(const req of blocked){
  const result=await worker.fire("fetch",req);
  assert.equal(result.responded,false,"must not intercept "+req.url);
 }
});
