import test from "node:test";
import assert from "node:assert/strict";
import {shouldRegisterPwa,registerSatellitePwa} from "./web_pwa.mjs";

test("PWA only registers on HTTPS or localhost, not file/native custom schemes",()=>{
 assert.equal(shouldRegisterPwa({protocol:"https:",hostname:"example.com"}),true);
 assert.equal(shouldRegisterPwa({protocol:"http:",hostname:"127.0.0.1"}),true);
 assert.equal(shouldRegisterPwa({protocol:"http:",hostname:"localhost"}),true);
 assert.equal(shouldRegisterPwa({protocol:"http:",hostname:"example.com"}),false);
 assert.equal(shouldRegisterPwa({protocol:"file:"}),false);
 assert.equal(shouldRegisterPwa({protocol:"tihulu:"}),false);
});
test("PWA register uses only same relative site scope; never calls USB",async()=>{
 const registrations=[],messages=[];
 const nav={serviceWorker:{async register(url,options){registrations.push([url,options]);return{scope:"safe"};}},usb:{requestDevice(){throw Error("PWA may not open USB");}}};
 const result=await registerSatellitePwa(nav,{protocol:"https:",hostname:"site.example"},s=>messages.push(s));
 assert.equal(result.scope,"safe");
 assert.deepEqual(registrations,[["./satellite-sw.js",{scope:"./"}]]);
 assert.match(messages[0],/never runs in a service worker/);
});
test("offline registration fails closed and preserves online planner",async()=>{
 const notes=[];
 const fail=await registerSatellitePwa({serviceWorker:{register(){throw Error("blocked")}}},
  {protocol:"https:",hostname:"site.example"},s=>notes.push(s));
 assert.equal(fail,null);
 assert.match(notes[0],/blocked/);
 const absent=await registerSatellitePwa({}, {protocol:"file:"},s=>notes.push(s));
 assert.equal(absent,null);
});
