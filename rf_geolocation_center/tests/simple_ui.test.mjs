import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {parseDvbV5Scan} from "../core/dvb_scan.mjs";
const read=p=>readFileSync(new URL("../"+p,import.meta.url),"utf8");
test("map-first main view supports three independent hardware options",()=>{
 const html=read("index.html"),app=read("web/app.mjs"),logic=read("web/simple_ui.mjs"),style=read("web/style.css");
 for(const id of ["simple-gps","simple-sdr","simple-tv","simple-ground","simple-aircraft","simple-satellites",
 "simple-find","simple-scan","simple-fit","simple-result","simple-sources","simple-tv-guide",
 "quick-radio-scan","quick-radio-discover","simple-dvb-file","simple-tv-channels","show-advanced-nav"]){
  assert.ok(html.includes('id="'+id+'"'),"missing simple option "+id);
 }
 assert.match(app,/initSimpleUI\(\{state,source,setView/);
 assert.match(app,/setView\("earth"\)/);
 assert.match(style,/\.simple-choice-grid/);
 assert.match(logic,/rf-only/);
 assert.match(logic,/tihulu:find-request/);
 assert.match(logic,/catalog-fm-scan/);
});
test("DVBv5 native scan parser preserves real DVB service frequency and ID provenance",()=>{
 const file=[
 "# user-supplied native DVBv5 channel export",
 "[WDR Fernsehen HD]","DELIVERY_SYSTEM = DVBT2","FREQUENCY = 514000000",
 "SERVICE_ID = 1234","NETWORK_ID = 67","TRANSPORT_ID = 891","",
 "[Second Program]","DELIVERY_SYSTEM = DVBT","FREQUENCY = 498000000","SERVICE_ID = 2222",""
 ].join("\n");
 const rows=parseDvbV5Scan(file);
 assert.equal(rows.length,2);
 assert.equal(rows[0].frequencyMHz,514);
 assert.equal(rows[0].serviceId,1234);
 assert.equal(rows[0].networkId,67);
 assert.equal(rows[0].transmitterIdentified,false);
 assert.equal(rows[0].directBrowserScan,false);
 assert.match(rows[0].provenance,/IMPORTED DVBv5/);
 assert.equal(rows[1].frequencyMHz,498);
});
test("invalid metadata does not create imaginary TV location or stations",()=>{
 assert.deepEqual(parseDvbV5Scan("[Fictional]\nSERVICE_ID=2\n"),[]);
 assert.deepEqual(parseDvbV5Scan(""),[]);
 assert.throws(()=>parseDvbV5Scan("x".repeat(1024*1024+1)),/no larger than 1 MiB/);
 const ui=read("web/simple_ui.mjs");
 assert.doesNotMatch(ui,/getCurrentPosition\s*\(/);
 assert.match(ui,/NOT a browser hardware scan/);
 assert.match(ui,/not a live tuner scan/);
});
test("radio scanner stays independent and original advanced features remain accessible",()=>{
 const html=read("index.html"),sw=read("sw.js");
 assert.match(html,/id="radio-advanced-tools"/);
 assert.match(html,/id="geo-advanced-tools"/);
 assert.match(html,/id="earth-map"/);
 assert.match(html,/id="rf-calibrate"/);
 assert.match(html,/id="catalog-discover"/);
 assert.match(html,/dvb_scan_linux\.sh/);
 assert.match(sw,/core\/dvb_scan\.mjs/);
 assert.match(sw,/web\/simple_ui\.mjs/);
});
