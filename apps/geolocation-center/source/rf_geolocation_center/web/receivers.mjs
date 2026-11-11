/* Browser GNSS receiver interfaces. Does not tune RF or calculate SDR fixes.
 * Serial reader is explicitly user-opened; WebUSB is permission only.
 */
import {parseNMEA} from "../core/positioning.mjs";
const $=id=>document.getElementById(id);
export function createReceiver(onFix,report){
 let serialPort=null,reader=null,running=false,usb=null,pending="";
 const useLine=(line)=>{
  try{
   const x=parseNMEA(line.trim());
   if(!x.valid||!["nmea_gga","nmea_rmc"].includes(x.kind))return false;
   const pos={lat:x.lat,lon:x.lon,alt:x.altEllipsoidMeters??0,
    provider:"DEDICATED GNSS NMEA",accuracyMeters:null,
    sourceTimestamp:x.receiverUTC||null,
    fixQuality:x.fixQuality??null,hdop:x.hdop??null,
    satellitesUsed:x.usedSatellites??null,speedMps:x.speedMps??null};
   $("stage-device").textContent="NMEA VERIFIED";
   $("stage-fix").textContent="FIX VALID (NMEA RECEIVER)";
   onFix(pos);return true;
  }catch(_){return false;}
 };
 const consume=(str)=>{
  pending+=str;if(pending.length>8192)pending=pending.slice(-4096);
  const lines=pending.split(/\r?\n/);pending=lines.pop()||"";
  let n=0;for(const line of lines)if(line.startsWith("$")&&useLine(line))n++;
  return n;
 };
 async function stop(){
  running=false;
  if(reader){try{await reader.cancel();}catch(_){}try{reader.releaseLock();}catch(_){}reader=null;}
  if(serialPort){try{await serialPort.close();}catch(_){}serialPort=null;}
  usb=null;$("serial-state").textContent="DISCONNECTED / NO SERIAL HANDLE";
  $("usb-state").textContent="No WebUSB device owned by this application.";
 }
 $("serial-connect").addEventListener("click",async()=>{
  if(!navigator.serial||!window.isSecureContext){report("Web Serial requires a compatible HTTPS/localhost Chromium browser.");return;}
  if(serialPort){report("GNSS receiver serial port already open.");return;}
  try{
   const p=await navigator.serial.requestPort();
   await p.open({baudRate:9600});
   serialPort=p;running=true;
   $("serial-state").textContent="OPEN — receiving checksum-verified NMEA";
   void(async()=>{
    try{
     while(running&&p.readable){
      const localReader=p.readable.getReader();reader=localReader;
      try{
       const decoder=new TextDecoder();
       while(running){
        const item=await localReader.read();
        if(item.done)break;
        consume(decoder.decode(item.value,{stream:true}));
       }
      }finally{try{localReader.releaseLock();}catch(_){}if(reader===localReader)reader=null;}
      break;
     }
    }catch(err){report("Serial read stopped: "+err.message);}
    finally{await stop();}
   })();
  }catch(err){report("Serial receiver unavailable: "+err.message);await stop();}
 });
 $("serial-disconnect").addEventListener("click",stop);
 $("usb-select").addEventListener("click",async()=>{
  if(!navigator.usb||!window.isSecureContext){report("WebUSB unavailable in this browser. No RTL-SDR access.");return;}
  try{
   usb=await navigator.usb.requestDevice({filters:[{vendorId:0x0bda,productId:0x2838}]});
   $("usb-state").textContent="PERMISSION SELECTED: "+(usb.productName||"RTL2832U")+
    " — USB INTERFACE NOT OPEN; NO RF/GNSS DECODE.";
   report("WebUSB permission selected only. No tuner acquisition or sample collection.");
  }catch(err){report("WebUSB permission unavailable or cancelled: "+err.message);}
 });
 window.addEventListener("pagehide",()=>{void stop();});
 document.addEventListener("visibilitychange",()=>{if(document.hidden)void stop();});
 return {stop,consume,useLine,hasSerial:()=>Boolean(serialPort)};
}
