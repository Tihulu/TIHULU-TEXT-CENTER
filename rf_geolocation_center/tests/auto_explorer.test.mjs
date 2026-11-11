import test from "node:test";
import assert from "node:assert/strict";
import {tleCatalog,constellation} from "../web/auto_explorer.mjs";

const line1="1 25544U 98067A   24001.51805556  .00015698  00000+0  27296-3 0  9993";
const line2="2 25544  51.6421 243.5120 0005180 122.2570 298.6120 15.49930747432091";
test("auto GNSS catalog parser accepts bounded two-line orbital records",()=>{
 const records=tleCatalog("GPS (TEST FIXTURE)\n"+line1+"\n"+line2+"\n");
 assert.equal(records.length,1);
 assert.equal(records[0].id,"25544");
 assert.equal(records[0].name,"GPS (TEST FIXTURE)");
 assert.equal(constellation(records[0].name),"GPS");
 assert.ok(records[0].epoch>=Date.UTC(2024,0,1));
});
test("catalog rejects empty, arbitrary pages and oversized feeds",()=>{
 assert.throws(()=>tleCatalog(""),/No valid/);
 assert.throws(()=>tleCatalog("<html>not an orbit</html>"),/No valid/);
 assert.throws(()=>tleCatalog(" ".repeat(900100)),/size limit/);
});
test("constellations are named from source labels; never inferred to have been received",()=>{
 const fixtures=[["NAVSTAR 80","GPS"],["GALILEO-FOC 32","Galileo"],["GLONASS-M","GLONASS"],["BEIDOU-3","BeiDou"],["QZSS-1","QZSS"],["IRNSS-1J","NavIC"],["EGNOS","SBAS"],["UNKNOWN OBJECT","Other"]];
 for(const [name,expected] of fixtures)assert.equal(constellation(name),expected);
});
