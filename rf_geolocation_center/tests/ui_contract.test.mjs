import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const root=new URL("../",import.meta.url);
const read=path=>readFileSync(new URL(path,root),"utf8");
test("visible Earth Map contains offline grid, real rings and honest demo toggle",()=>{
 const html=read("index.html");
 for(const id of ["earth-map","earth-grid","earth-rings","earth-markers","evidence-report","evidence-sources",
  "layer-demo","layer-ranges","layer-stations","layer-orbits","earth-fit-evidence","evidence-clear"]){
    assert.match(html,new RegExp("id=\""+id+"\""));
 }
 const app=read("web/app.mjs");
 assert.match(app,/ringPoints\(/);
 assert.match(app,/rangeInputs/);
 assert.match(app,/SIMULATED/);
 assert.match(app,/USER-IMPORTED UNVERIFIED RANGES/);
});
test("offline app shell includes range module and saved location behavior",()=>{
 const sw=read("sw.js"),app=read("web/app.mjs"),html=read("index.html");
 assert.match(sw,/core\/evidence\.mjs/);
 assert.match(app,/tihulu\.rfgeo\.last-known-position\.v1/);
 assert.match(app,/localStorage\.setItem/);
 assert.match(app,/localStorage\.removeItem/);
 assert.match(html,/id="live-offline-grid"/);
 assert.match(html,/id="live-rings"/);
});

test("one-click position view explicitly separates device uncertainty from radio station ranges",()=>{
 const html=read("index.html"),app=read("web/app.mjs"),css=read("web/style.css");
 assert.match(html,/id="earth-find"/);
 assert.match(html,/id="fix-evidence"/);
 assert.match(html,/legend-device/);
 assert.match(html,/legend-ranges/);
 assert.match(html,/legend-demo/);
 assert.match(app,/function renderFixEvidence/);
 assert.match(app,/browser-reported uncertainty, not a radio station range/i);
 assert.match(app,/ringPoints\(browserAccuracy\.lat,browserAccuracy\.lon,browserAccuracy\.accuracy/);
 assert.match(app,/5\*60\*1000/);
 assert.match(css,/\.fix-evidence/);
});
