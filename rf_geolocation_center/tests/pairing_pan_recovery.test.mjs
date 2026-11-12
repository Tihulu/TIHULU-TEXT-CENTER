import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const read=p=>readFileSync(new URL("../"+p,import.meta.url),"utf8");
test("home TV tuner is real native DVB adapter, not a made-up WebUSB driver",()=>{
 const html=read("index.html"),js=read("web/dvb_bridge_client.mjs"),native=read("native.py");
 for(const id of ["home-tv-connect","home-tv-scan","home-tv-state",
   "tv-bridge-connect","tv-start-scan","tv-stop-scan","tv-adapter","tv-profile"])
  assert.ok(html.includes('id="'+id+'"'),id);
 assert.match(js,/window\.open\(url,"tihulu_tv_pair"/);
 assert.match(js,/crypto\.getRandomValues\(rand\)/);
 assert.match(js,/event\.origin!==ENDPOINT/);
 assert.match(js,/event\.source!==pairPopup/);
 assert.match(js,/event\.data\?\.nonce!==pairNonce/);
 assert.match(js,/window\.addEventListener\("message"/);
 assert.match(js,/home-tv-connect/);
 assert.match(js,/home-tv-scan/);
 assert.match(js,/native-dvb-channels/);
 assert.doesNotMatch(js,/localStorage|sessionStorage/);
 assert.match(native,/def _pair_page\(self\)/);
 assert.match(native,/self\._pair_page\(\)/);
 assert.match(native,/PAGES_BRIDGE_ENABLED/);
 assert.match(native,/postMessage/);
 assert.match(html,/Secure one-click pairing/);
 assert.doesNotMatch(html,/id="tv-bridge-token"/);
});
test("natural map dragging previews visual layers without repainting on every pointermove",()=>{
 const app=read("web/app.mjs"),css=read("web/style.css");
 assert.match(app,/panPreview\(drag\.dx,drag\.dy\)/);
 assert.match(app,/translate3d\(/);
 assert.match(app,/addEventListener\("pointermove"/);
 assert.match(app,/addEventListener\("pointerup"/);
 assert.match(app,/addEventListener\("pointercancel"/);
 assert.match(app,/const center=unmerc\(anchored\.x,anchored\.y,newZoom\)/);
 assert.match(app,/addEventListener\("wheel"/);
 assert.match(app,/addEventListener\("dblclick"/);
 assert.match(css,/#osm-tiles\{overflow:visible\}/);
});
test("a USB register error has a user-initiated one-shot release/reconnect, never an OS driver takeover",()=>{
 const usb=read("web/usb_sdr.mjs"),html=read("index.html");
 assert.match(usb,/async function recover\(\)/);
 assert.match(usb,/await release\(\)/);
 assert.match(usb,/await connect\(devices\[0\]\)/);
 assert.match(usb,/tihulu:hardware-connect-rtl/);
 assert.doesNotMatch(usb,/systemctl|modprobe|\/sys\/bus\/usb/);
 for(const id of ["hardware-recover","quick-radio-recover"])
  assert.ok(html.includes('id="'+id+'"'),"missing "+id);
 assert.match(read("sw.js"),/shell-v23/);
 assert.match(read("sw.js"),/web\/exit_lifecycle\.mjs/);
});
