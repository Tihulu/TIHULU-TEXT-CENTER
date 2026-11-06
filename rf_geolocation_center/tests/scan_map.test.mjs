import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {matchedBroadcastSources,mapBoundsForSources} from "../core/scan_map.mjs";
const read=path=>readFileSync(new URL("../"+path,import.meta.url),"utf8");
const towers=[
 {id:"osm-node/1",name:"Published FM site",lat:50.91,lon:6.91,frequenciesMHz:[98.6],televisionFrequenciesMHz:[]},
 {id:"osm-node/2",name:"Published TV site",lat:50.92,lon:6.96,frequenciesMHz:[],televisionFrequenciesMHz:[514]},
 {id:"osm-node/3",name:"Unknown frequency mast",lat:50.95,lon:7,frequenciesMHz:[],televisionFrequenciesMHz:[]}
];
test("actual tuner frequencies map ONLY to externally catalogued matching transmitter candidates",()=>{
 const fm=[{frequencyMHz:98.6,levelDbFS:-24,measuredAt:"2026-11-06T08:00:00Z"}];
 const tv=[{name:"WDR Fernsehen",frequencyMHz:514,deliverySystem:"DVBT2",serviceId:11}];
 const found=matchedBroadcastSources(towers,fm,tv);
 assert.equal(found.length,2);
 const radio=found.find(x=>x.kind==="fm"),television=found.find(x=>x.kind==="tv");
 assert.equal(radio.siteId,"osm-node/1");
 assert.equal(television.siteId,"osm-node/2");
 assert.deepEqual(television.serviceNames,["WDR Fernsehen"]);
 for(const s of found){
   assert.equal(s.receiverPosition,false);
   assert.equal(s.distanceMeters,null);
   assert.match(s.match,/FREQUENCY OVERLAP ONLY/);
 }
});
test("catalog-only site or measured RF with unknown broadcast frequency generates no fabricated match",()=>{
 assert.deepEqual(matchedBroadcastSources(towers,[],[]),[]);
 assert.deepEqual(matchedBroadcastSources(towers,[{frequencyMHz:100.3,levelDbFS:-19}],[]),[]);
 assert.deepEqual(matchedBroadcastSources(towers,[{frequencyMHz:98.6}],[]),[]); // no actual measured level
});
test("map fit checks source geometry without inferring receiver position",()=>{
 const bounds=mapBoundsForSources(towers);
 assert.deepEqual(bounds,{south:50.91,north:50.95,west:6.91,east:7,count:3});
 assert.equal(mapBoundsForSources([]),null);
});
test("web app displays tuner evidence, authentic aircraft and accessible marker popup",()=>{
 const app=read("web/app.mjs"),html=read("index.html"),dvb=read("web/dvb_bridge_client.mjs");
 for(const id of ["map-scan-status","map-scan-results","map-focus-scan","map-source-popup",
  "tv-bridge-connect","tv-adapter","tv-profile","tv-start-scan","tv-stop-scan","tv-show-map",
  "quick-open-adsb","quick-online-aircraft"])assert.ok(html.includes('id="'+id+'"'),id);
 assert.match(app,/matchedBroadcastSources\(state\.catalogTowers,state\.catalogFM,state\.dvbChannels\|\|\[\]\)/);
 assert.match(app,/tihulu:tv-channels-updated/);
 assert.match(app,/tihulu:rf-scan-finished/);
 assert.match(app,/map-source-popup/);
 assert.match(dvb,/tihulu:native-dvb-channels/);
 assert.doesNotMatch(dvb,/localStorage/);
 assert.match(read("sw.js"),/core\/scan_map\.mjs/);
 assert.match(read("sw.js"),/web\/dvb_bridge_client\.mjs/);
 assert.match(read("native.py"),/web\/dvb_bridge_client\.mjs/);
});
