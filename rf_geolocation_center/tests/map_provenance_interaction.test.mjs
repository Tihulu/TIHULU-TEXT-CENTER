import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const read=path=>readFileSync(new URL("../"+path,import.meta.url),"utf8");
test("T tower markers receive hover/click/keyboard with original source facts",()=>{
 const app=read("web/app.mjs"),html=read("index.html"),css=read("web/style.css");
 for(const id of ["map-source-popup","map-source-facts","map-hover-tip","map-source-measure",
   "map-source-catalog-link","map-source-popup-close","rf-blind-status"]){
  assert.ok(html.includes('id="'+id+'"'),"Missing "+id);
 }
 assert.match(css,/#earth-markers g\[data-map-marker\]\{pointer-events:all/);
 assert.match(app,/group\.setAttribute\("data-map-marker",kind\)/);
 assert.match(app,/group\.addEventListener\("pointerenter"/);
 assert.match(app,/group\.addEventListener\("click",show\)/);
 assert.match(app,/group\.addEventListener\("keydown"/);
 assert.match(app,/e\.target\.closest\("\[data-map-marker\], #map-source-popup, #map-hover-tip"\)/);
 assert.match(app,/OPENSTREETMAP CATALOG \/ EXTERNAL MAPPED SITE/);
 assert.match(app,/NO verified direct receipt from this tower/);
 assert.match(app,/tihulu:rf-select-source/);
 assert.match(app,/mapMatches\(\)/);
});
test("FM reference probe preserves evidence of actual I/Q and covers all band frequencies",()=>{
 const html=read("index.html"),ui=read("web/simple_ui.mjs");
 const usb=read("web/usb_sdr.mjs"),catalog=read("web/catalog_discovery.mjs");
 const catalogCore=read("core/source_catalog.mjs");
 assert.match(html,/id="fm-reference-channel"/);
 assert.match(html,/id="fm-reference-probe"/);
 for(const freq of [98.6,87.6,99.2,100.4,95.1])
  assert.ok(html.includes('value="'+freq+'"'),"Missing published FM channel "+freq);
 assert.match(ui,/tihulu:rf-fm-sweep-request/);
 assert.match(ui,/REAL Nooelec RTL-SDR I\/Q energy/);
 assert.match(usb,/const readings=\[\],total=Math\.min\(220/);
 assert.match(usb,/startMHz=87\.5,stopMHz=108,stepMHz=\.1/);
 assert.match(catalog,/startMHz:87\.5,stopMHz:108,stepMHz:\.1/);
 assert.match(catalogCore,/Math\.abs\(f-r\.frequencyMHz\)<\.015/);
});
test("map projection caches DOM viewport instead of re-reading it for each circle sample",()=>{
 const app=read("web/app.mjs");
 assert.match(app,/const worldWidth=256\*Math\.pow\(2,state\.map\.zoom\)/);
 assert.match(app,/const pt=\(lat,lon\)=>\{/);
 assert.match(app,/let dx=p\.x-center\.x/);
 assert.match(app,/if\(moved<4\)\{drag=null;return\}/);
});
test("antenna-only unknown-position screen never disguises references as a fix",()=>{
 const app=read("web/app.mjs");
 assert.match(app,/RF-ONLY · NO FIX:/);
 assert.match(app,/user-calibrated source-range HYPOTHESES/);
 assert.match(app,/Catalog towers, FM power peaks, TV services or ADS-B aircraft positions alone/);
});
