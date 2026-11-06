import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const base=new URL("../satellite_center/browser/",import.meta.url);
const css=readFileSync(new URL("browser.css",base),"utf8");
const map=readFileSync(new URL("satellite_maps.mjs",base),"utf8");

test("page canvas rules do not cover Leaflet raster tiles",()=>{
  // Page charts are scoped: generic canvas{} made Leaflet's own renderer opaque.
  assert.doesNotMatch(css,/(?:^|\})\s*canvas\s*\{/m);
  assert.match(css,/#level-chart\s*\{/);
  assert.match(css,/#earth-map\s+\.leaflet-pane\s+canvas\s*\{/);
  assert.match(css,/background:\s*transparent\s*!important/);
  assert.match(css,/margin:\s*0\s*!important/);
  assert.match(css,/width:\s*auto\s*!important/);
});

test("Leaflet uses SVG vectors, not a page-owned opaque Canvas",()=>{
  assert.match(map,/preferCanvas:false/);
  assert.doesNotMatch(map,/preferCanvas:true/);
  assert.match(map,/leaflet\.svg\(\{pane:"world-outline"/);
});

test("Leaflet map initializes only after optional details becomes visible",()=>{
  assert.match(map,/\$\("earth-street-details"\)\.open=true/);
  assert.match(map,/requestAnimationFrame\(\(\)=>requestAnimationFrame\(resolve\)\)/);
  assert.match(map,/invalidateSize\(\{pan:false,debounceMoveend:true\}\)/);
});

test("diagnostics test rendered tiles without switching to outline mode",()=>{
  const diag=map.slice(map.indexOf('\$("map-diagnose").addEventListener'),map.indexOf('\$("map-recenter").addEventListener'));
  assert.match(diag,/naturalWidth>0/);
  assert.match(diag,/opaque\.length/);
  assert.match(diag,/getComputedStyle\(canvas\)/);
  assert.doesNotMatch(diag,/changeBasemap\("outline"\)/);
});
