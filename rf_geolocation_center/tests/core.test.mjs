import test from "node:test";
import assert from "node:assert/strict";
import {GNSS,ecefFromLLA,llaFromECEF,azElRange,parseSP3,positionAt,visibleSatellites,rtlSignalClass} from "../core/gnss.mjs";
import {parseNMEA,nmeaChecksum,trilaterate2D,tdoaConstraints} from "../core/positioning.mjs";

test("all seven regional/global/SBAS registry groups have honest nominal signals",()=>{
 assert.deepEqual(GNSS.map(x=>x.id),["G","E","R","C","J","I","S"]);
 assert.equal(rtlSignalClass(2492.028),"Outside approximate tuner range");
 assert.match(rtlSignalClass(1575.42),/NOT verified/);
});
test("WGS84 ECEF/geodetic conversions roundtrip latitude longitude altitude",()=>{
 for(const p of [[0,0,0],[50.938,6.96,90],[-33.9,151.2,127],[89.99,-170,30]]){
  const q=llaFromECEF(...ecefFromLLA(...p));
  assert.ok(Math.abs(q.lat-p[0])<1e-8);
  assert.ok(Math.abs(q.lon-p[1])<1e-8);
  assert.ok(Math.abs(q.alt-p[2])<0.01);
 }
 assert.throws(()=>ecefFromLLA(100,0),/Invalid/);
});
test("actual importable SP3 epochs produce only within-interval PREDICTED geometry",()=>{
 const file=[
 "#cP2026 11 06 00 00 00.00000000      4 ORBIT IGS",
 "*  2026 11 06 00 00 00.00000000","PG01  26560.000000  100.000000 1000.000000  0.000000",
 "*  2026 11 06 00 15 00.00000000","PG01  26520.000000  900.000000 1000.000000  0.000000",
 "*  2026 11 06 00 30 00.00000000","PG01  26460.000000 1700.000000 1000.000000  0.000000",
 "*  2026 11 06 00 45 00.00000000","PG01  26380.000000 2500.000000 1000.000000  0.000000",
 "EOF"
 ].join("\n");
 const orbit=parseSP3(file);
 assert.equal(orbit.satelliteCount,1);
 const middle=Date.UTC(2026,10,6,0,22,30);
 assert.equal(positionAt(orbit.data.get("G01"),middle).method,"SP3 INTERPOLATED (CUBIC)");
 assert.equal(positionAt(orbit.data.get("G01"),middle-100_000_000),null);
 const v=visibleSatellites(orbit,middle,{lat:50.938,lon:6.96,alt:0});
 assert.equal(v.length,1);
 assert.equal(v[0].observedRF,false);
 assert.equal(v[0].state,"PREDICTED ORBIT GEOMETRY");
 assert.equal(visibleSatellites(orbit,orbit.last+1000,{lat:0,lon:0,alt:0}).length,0);
 assert.throws(()=>parseSP3("not orbit data"),/No valid/);
});
test("known NMEA GGA/RMC fixtures validate checksums and never invent accuracy meters",()=>{
 const gga="$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47";
 const rmc="$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A";
 assert.equal(nmeaChecksum(gga),true);
 const p=parseNMEA(gga);
 assert.equal(p.valid,true);
 assert.equal(p.provider,"DEDICATED GNSS NMEA");
 assert.ok(Math.abs(p.lat-48.1173)<1e-5);
 assert.ok(Math.abs(p.lon-11.51666667)<1e-5);
 assert.ok(Math.abs(p.altEllipsoidMeters-592.3)<0.01);
 assert.equal(p.accuracyMeters,null);
 assert.equal(parseNMEA(rmc).valid,true);
 assert.throws(()=>parseNMEA(gga.replace("545.4","545.5")),/checksum/);
});
test("unverified RSSI ranges cannot create an artificial fix",()=>{
 assert.throws(()=>trilaterate2D([{lat:0,lon:0,rangeMeters:2}]),/Need/);
 assert.throws(()=>trilaterate2D([
  {lat:0,lon:0,rangeMeters:100,measured:false},
  {lat:0,lon:.01,rangeMeters:100,measured:false},
  {lat:.01,lon:0,rangeMeters:100,measured:false}
 ]),/measured/);
});
test("measured range trilateration recovers a known planar test geometry",()=>{
 const p=[[0,.01],[0,-.01],[.01,0],[-.01,0]].map(([lat,lon])=>({
  lat,lon,measured:true,rangeMeters:Math.hypot(lat,lon)*Math.PI/180*6378137
 }));
 const result=trilaterate2D(p);
 assert.ok(Math.abs(result.lat)<1e-7);
 assert.ok(Math.abs(result.lon)<1e-7);
 assert.ok(result.rmsResidualMeters<0.01);
 assert.match(result.quality,/UNVALIDATED/);
});
test("TDOA hyperbolas require genuine synchronized data and baseline constraints",()=>{
 const a=[{lat:50,lon:7,synchronized:true,measured:true,deltaSeconds:0,station:"A"},
          {lat:50,lon:7.01,synchronized:true,measured:true,deltaSeconds:1e-6,station:"B"}];
 assert.equal(tdoaConstraints(a)[0].positionFix,false);
 assert.equal(tdoaConstraints(a)[0].type,"TDOA HYPERBOLA");
 assert.throws(()=>tdoaConstraints(a.map(p=>({...p,synchronized:false}))),/synchronized/);
 assert.throws(()=>tdoaConstraints([a[0],{...a[1],deltaSeconds:.01}]),/impossible/);
});
