/* Real NMEA $GGA/$RMC (optional $GSA) and experimental terrestrial geometry.
 * No simulated receiver data or invented accuracy.
 */
import {DEG,validateLLA,WGS84_A} from "./gnss.mjs";
export function nmeaChecksum(sentence){
 if(typeof sentence!=="string"||sentence.length>200||!sentence.startsWith("$"))return false;
 const star=sentence.indexOf("*");
 if(star<0||star!==sentence.length-3||!/^[\dA-Fa-f]{2}$/.test(sentence.slice(star+1)))return false;
 let c=0;for(let i=1;i<star;i++)c^=sentence.charCodeAt(i);
 return c===parseInt(sentence.slice(star+1),16);
}
function angle(raw,hemis,latitude){
 if(!/^\d{4,5}(?:\.\d+)?$/.test(raw))throw Error("Invalid NMEA angle");
 const degDigits=latitude?2:3;
 const whole=Number(raw.slice(0,degDigits)),minutes=Number(raw.slice(degDigits));
 if(minutes>=60)throw Error("Invalid NMEA minutes");
 const sign=hemis===(latitude?"S":"W")?-1:1;
 if(![latitude?"N":"E",latitude?"S":"W"].includes(hemis))throw Error("Invalid hemisphere");
 return sign*(whole+minutes/60);
}
export function parseNMEA(sentence){
 sentence=String(sentence||"").trim();
 if(!nmeaChecksum(sentence))throw Error("NMEA checksum invalid or missing");
 const cells=sentence.slice(1,-3).split(",");
 const type=cells[0].slice(-3),talker=cells[0].slice(0,2);
 if(!/^[A-Z]{2}$/.test(talker))throw Error("Invalid NMEA talker");
 if(type==="GGA"){
   const quality=Number(cells[6]);
   const sats=Number(cells[7]),hdop=Number(cells[8]);
   if(!Number.isInteger(quality)||quality<0||quality>8||!Number.isInteger(sats)||sats<0||sats>99)throw Error("Invalid GGA fix fields");
   if(!quality)return {kind:"nmea_gga",valid:false,talker,fixQuality:0,usedSatellites:0};
   const lat=angle(cells[2],cells[3],true),lon=angle(cells[4],cells[5],false);
   const msl=Number(cells[9]),sep=cells[11]?Number(cells[11]):null;
   if(cells[10]!=="M"||!Number.isFinite(msl)||msl < -2000||msl>50000)throw Error("GGA altitude invalid");
   if(sep!==null&&(cells[12]!=="M"||!Number.isFinite(sep)))throw Error("GGA geoid separation invalid");
   validateLLA(lat,lon,msl);
   return {kind:"nmea_gga",valid:true,talker,provider:"DEDICATED GNSS NMEA",
     lat,lon,altMSLMeters:msl,altEllipsoidMeters:sep===null?null:msl+sep,
     usedSatellites:sats,hdop:Number.isFinite(hdop)&&hdop>0?hdop:null,
     fixQuality:quality,accuracyMeters:null,receiverUTC:cells[1]||null};
 }
 if(type==="RMC"){
   const valid=cells[2]==="A";
   if(!valid)return {kind:"nmea_rmc",valid:false,talker};
   const lat=angle(cells[3],cells[4],true),lon=angle(cells[5],cells[6],false);
   validateLLA(lat,lon);
   const knots=Number(cells[7]||"0");
   if(!Number.isFinite(knots)||knots<0)throw Error("Invalid RMC speed");
   return {kind:"nmea_rmc",valid:true,talker,provider:"DEDICATED GNSS NMEA",
     lat,lon,speedMps:knots*0.514444444,courseDegrees:cells[8]?Number(cells[8]):null,
     receiverUTC:cells[1]||null,receiverDate:cells[9]||null,accuracyMeters:null};
 }
 if(type==="GSA")return {kind:"nmea_gsa",valid:cells[2]==="3"||cells[2]==="2",
   talker,fixDimension:cells[2],hdop:Number(cells[16])||null,
   pdop:Number(cells[15])||null,vdop:Number(cells[17])||null};
 return {kind:"nmea_other",valid:false,talker,type};
}
function xy(lat,lon,ref){
 const dy=(lat-ref.lat)*DEG*WGS84_A;
 const dx=(lon-ref.lon)*DEG*WGS84_A*Math.cos(ref.lat*DEG);
 return [dx,dy];
}
function llaXY(x,y,ref){
 return {lat:ref.lat+y/WGS84_A/DEG,lon:ref.lon+x/(WGS84_A*Math.cos(ref.lat*DEG))/DEG,alt:0};
}
function solve2(A,B){
 const det=A[0][0]*A[1][1]-A[0][1]*A[1][0];
 if(Math.abs(det)<1e-12)return null;
 return [(B[0]*A[1][1]-B[1]*A[0][1])/det,
         (A[0][0]*B[1]-A[1][0]*B[0])/det];
}
export function trilaterate2D(ranges){
 if(!Array.isArray(ranges)||ranges.length<3||ranges.length>64)throw Error("Need 3-64 genuine calibrated ranges");
 for(const p of ranges){
  validateLLA(p.lat,p.lon);
  if(!Number.isFinite(p.rangeMeters)||p.rangeMeters<0||p.rangeMeters>1e7||p.measured!==true)
    throw Error("Trilateration requires actual measured rangeMeters, no uncalibrated RSSI");
 }
 const ref={lat:ranges.reduce((a,p)=>a+p.lat,0)/ranges.length,
            lon:ranges.reduce((a,p)=>a+p.lon,0)/ranges.length};
 if(Math.abs(ref.lat)>85)throw Error("Planar 2D model unsuitable near polar regions");
 const pts=ranges.map(p=>({xy:xy(p.lat,p.lon,ref),r:p.rangeMeters}));
 if(Math.max(...pts.map(p=>Math.hypot(...p.xy)))>100_000)throw Error("Use local stations within 100 km for planar solution");
 let x=pts.reduce((a,p)=>a+p.xy[0],0)/pts.length;
 let y=pts.reduce((a,p)=>a+p.xy[1],0)/pts.length;
 for(let iter=0;iter<60;iter++){
   const A=[[0,0],[0,0]],B=[0,0];
   for(const p of pts){
     const dx=x-p.xy[0],dy=y-p.xy[1],rho=Math.max(0.001,Math.hypot(dx,dy));
     const residual=rho-p.r, gx=dx/rho,gy=dy/rho;
     A[0][0]+=gx*gx;A[0][1]+=gx*gy;A[1][0]+=gx*gy;A[1][1]+=gy*gy;
     B[0]-=gx*residual;B[1]-=gy*residual;
   }
   const d=solve2(A,B);
   if(!d||Math.hypot(...d)>100_000)throw Error("Ill-conditioned range geometry");
   x+=d[0];y+=d[1];
   if(Math.hypot(...d)<1e-5)break;
 }
 const rms=Math.sqrt(pts.reduce((a,p)=>a+(Math.hypot(x-p.xy[0],y-p.xy[1])-p.r)**2,0)/pts.length);
 if(!Number.isFinite(rms)||rms>100_000)throw Error("Inconsistent radio ranges");
 return {...llaXY(x,y,ref),rmsResidualMeters:rms,method:"EXPERIMENTAL 2D RANGE TRILATERATION",
   quality:"UNVALIDATED CALIBRATION / NO CLAIMED ACCURACY",usedRanges:pts.length,
   note:"Local tangent-plane calculation. Multipath, terrain, station synchronization and range accuracy require separate validation."};
}
export function tdoaConstraints(measurements){
 const C=299_792_458;
 if(!Array.isArray(measurements)||measurements.length<2||measurements.length>32)
   throw Error("At least two synchronized receiver stations required");
 for(const p of measurements){
   validateLLA(p.lat,p.lon);
   if(p.synchronized!==true||p.measured!==true||!Number.isFinite(p.deltaSeconds)||
      Math.abs(p.deltaSeconds)>0.01)throw Error("Actual synchronized TDOA observations required");
 }
 const ref=measurements[0];
 return measurements.slice(1).map(p=>{
   const maxMeters=Math.hypot(...xy(p.lat,p.lon,ref));
   const rangeDifferenceMeters=p.deltaSeconds*C;
   if(Math.abs(rangeDifferenceMeters)>maxMeters+1)
     throw Error("Physically impossible TDOA for receiver baseline");
   return {reference:ref.station||"Receiver 1",other:p.station||"Receiver",
      rangeDifferenceMeters,baselineMeters:maxMeters,
      type:"TDOA HYPERBOLA",positionFix:false,observed:true};
 });
}
