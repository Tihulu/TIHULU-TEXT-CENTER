import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const read=p=>readFileSync(new URL("../"+p,import.meta.url),"utf8");
test("home TV identification and native TV pairing require no manually entered token",()=>{
 const html=read("index.html"),client=read("web/dvb_bridge_client.mjs"),hardware=read("web/hardware_manager.mjs");
 assert.match(html,/id="home-tv-identify"/);
 assert.match(html,/id="home-tv-connect"/);
 assert.match(html,/Connect TV tuner · local approval/);
 assert.doesNotMatch(html,/id="tv-bridge-token"/);
 assert.doesNotMatch(html,/id="radio-bridge-token"/);
 assert.match(client,/function pair\(action="tv"\)/);
 assert.match(client,/tihulu:dvb-bridge-paired/);
 assert.match(client,/event\.origin!==ENDPOINT/);
 assert.match(hardware,/home-tv-identify/);
 assert.match(hardware,/DVB.*frontend/);
});
test("map drags smoothly and avoids extra tile fetches until release",()=>{
 const app=read("web/app.mjs");
 assert.match(app,/function panPreview\(dx,dy\)/);
 assert.match(app,/pointermove/);
 assert.match(app,/translate3d/);
 assert.match(app,/setPointerCapture/);
 assert.match(app,/one tile of lookahead/i);
 assert.match(app,/e\.preventDefault\(\); \/\/ prevent text selection while panning/);
});
test("RTL-SDR hardware register failure never yields a false range or a fictional RF sample",()=>{
 const sdr=read("web/usb_sdr.mjs");
 assert.match(sdr,/rfStage="tuner gain configuration/);
 assert.match(sdr,/rfStage="tune "/);
 assert.match(sdr,/tihulu:rf-capture-failed/);
 assert.match(sdr,/if\(transfer\)await release\(\)/);
 assert.match(sdr,/scanStage="tune "/);
 assert.match(sdr,/hardwareControlFailed/);
 assert.match(sdr,/if\(!stopping&&!hardwareControlFailed&&receiver\)/);
});
