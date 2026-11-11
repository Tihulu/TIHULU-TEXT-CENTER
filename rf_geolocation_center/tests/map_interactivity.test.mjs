import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const read=p=>readFileSync(new URL("../"+p,import.meta.url),"utf8");
test("map marker hit areas accessible via hover, click, keyboard and touch",()=>{
 const js=read("web/app.mjs"),css=read("web/style.css"),html=read("index.html");
 assert.match(js,/"data-marker-hitbox":"true"/);
 assert.match(js,/r:19,fill:"transparent"/);
 assert.match(js,/group\.addEventListener\("pointerenter"/);
 assert.match(js,/group\.addEventListener\("click",show\)/);
 assert.match(js,/group\.addEventListener\("pointerup"/);
 assert.match(js,/group\.addEventListener\("keydown"/);
 assert.match(js,/addFact\("Location provenance","OPENSTREETMAP CATALOG/);
 assert.match(js,/addFact\("RF\/TV link"/);
 assert.match(js,/addFact\("Receiver position contribution"/);
 assert.match(js,/tihulu:rf-select-source/);
 assert.match(css,/#earth-markers \[data-marker-hitbox\]/);
 for(const id of ["map-hover-tip","map-source-popup","map-source-facts","map-source-measure","map-source-catalog-link"])
   assert.ok(html.includes('id="'+id+'"'),id);
});
test("FM calibration candidate selector never fabricates station frequencies or measured ranges",()=>{
 const html=read("index.html"),ui=read("web/simple_ui.mjs");
 assert.match(html,/id="fm-calibration-candidates"/);
 assert.match(html,/id="fm-calibration-source-list"/);
 assert.match(ui,/\.filter\(freq=>Number\.isFinite\(freq\)&&freq>=87\.5&&freq<=108\)/);
 assert.match(ui,/tihulu:rf-autosource/);
 assert.match(ui,/tihulu:rf-select-source/);
 assert.match(ui,/independently known reference distance/);
 assert.match(read("web/rf_survey.mjs"),/First measure actual RF with the connected RTL-SDR/);
});
