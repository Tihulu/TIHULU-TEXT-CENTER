import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const read=p=>readFileSync(new URL("../"+p,import.meta.url),"utf8");
test("main map exposes genuine hardware USB picker, saved device list, test, disconnect and GNSS controls",()=>{
 const html=read("index.html"),manager=read("web/hardware_manager.mjs");
 for(const id of ["simple-hardware","hardware-add","hardware-refresh","hardware-list",
  "hardware-message","hardware-rtl-slot","hardware-test-slot","hardware-gnss-slot",
  "hardware-release","hardware-count","radio-connect-rtl","radio-manage-usb"]){
  assert.ok(html.includes('id="'+id+'"'),"Missing hardware UI "+id);
 }
 assert.match(manager,/navigator\.usb\.requestDevice\(\{filters:\[\]\}\)/);
 assert.match(manager,/navigator\.usb\.getDevices\(\)/);
 assert.match(manager,/Connect this RTL-SDR/);
 assert.match(manager,/mount\("usb-select","hardware-rtl-slot"\)/);
 assert.match(manager,/mount\("usb-selftest","hardware-test-slot"\)/);
 assert.match(manager,/mount\("serial-connect","hardware-gnss-slot"\)/);
 assert.match(manager,/mount\("serial-disconnect","hardware-gnss-slot"\)/);
 assert.match(manager,/window\.isSecureContext/);
 assert.match(manager,/DVB driver access is native Linux-only/);
 assert.doesNotMatch(manager,/\.claimInterface\(/,"Enumerating permission must not claim USB interface");
 assert.doesNotMatch(manager,/\.getCurrentPosition\(/,"Hardware picker is not location acquisition");
});
test("permitted RTL-SDR can be opened via existing receiver, generic device cannot be claimed as SDR",()=>{
 const usb=read("web/usb_sdr.mjs"),app=read("web/app.mjs");
 assert.match(usb,/async function connect\(preferredDevice=null\)/);
 assert.match(usb,/preferredDevice\.vendorId!==0x0bda\|\|preferredDevice\.productId!==0x2838/);
 assert.match(usb,/navigator\.usb\.getDevices\(\)/);
 assert.match(usb,/tihulu:hardware-connect-rtl/);
 assert.match(app,/initHardwareManager\(\{setView\}\)/);
});
test("map SVG units match visible map pixels so circular towers and range rings remain round",()=>{
 const app=read("web/app.mjs");
 const html=read("index.html");
 assert.match(app,/const mapWidth=Math\.max\(1,rect\.width\),mapHeight=Math\.max\(1,rect\.height\)/);
 assert.match(app,/setAttribute\("viewBox","0 0 "\+mapWidth\+" "\+mapHeight\)/);
 assert.match(app,/x:v\.x,y:v\.y,inside:v\.x/);
 assert.doesNotMatch(app,/const sx=900\/Math\.max/);
 assert.match(app,/new ResizeObserver/);
 assert.match(app,/drawnTowers\.some\(p=>Math\.hypot/);
 assert.match(html,/id="earth-overlay"/);
});
test("offline and native launcher include actual hardware manager module",()=>{
 const sw=read("sw.js"),native=read("native.py");
 assert.match(sw,/web\/hardware_manager\.mjs/);
 assert.match(native,/web\/hardware_manager\.mjs/);
});
