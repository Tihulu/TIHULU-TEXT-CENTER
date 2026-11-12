/* Browser-only EM28178 / Si2168-D60 driver research tools.
 * USB register writes are intentionally NOT armed until hardware replay
 * against a proven-good device validates the firmware and timing. Every
 * operation below is pure JS and stays in the browser.
 */
import {EM28178,boardInitPlan,si2157TunePlan,si2168TunePlan,
        describeFirmware} from "./em28xx-driver-plan.js";

const $=id=>document.getElementById(id);
const result=$("dvb-driver-plan");
const input=$("dvb-driver-fw");
const freq=$("dvb-driver-frequency");
const bw=$("dvb-driver-bandwidth");
const delivery=$("dvb-driver-delivery");
const status=$("dvb-driver-status");
let firmwareReport=null;
const report=text=>{result.textContent=typeof text==="string"?text:JSON.stringify(text,null,2)};
function getPlan(){
  const frequencyHz=Number(freq.value)*1000000;
  const bandwidthHz=Number(bw.value)*1000000;
  return {
    owner:"Hauppauge 2040:8268",
    board:EM28178.board,
    USB:"vendor control, I2C bridge and bulk-IN transport",
    board_gpio:boardInitPlan(),
    i2c_secondary_bus:{select:0x04,demod:0x64,tuner:0x60},
    tuner:si2157TunePlan({frequencyHz,bandwidthHz,delivery:delivery.value})
      .map(c=>({name:c.name,requestLength:c.response,hex:Array.from(c.args,x=>x.toString(16).padStart(2,"0")).join(" ")})),
    demod:si2168TunePlan({bandwidthHz,delivery:delivery.value})
      .map(c=>({name:c.name,requestLength:c.response,hex:Array.from(c.args,x=>x.toString(16).padStart(2,"0")).join(" ")})),
    firmware:firmwareReport,
    hardwareWritesEnabled:false,
    realScanReady:false,
    note:"Offline reconstruction. Commands are NOT executed, and no DVB lock is claimed."
  };
}
$("dvb-driver-preview").onclick=()=>{
  try{report(getPlan());status.textContent="Generated Linux-derived DVB command plan entirely in your browser. No USB writes.";
  }catch(err){status.textContent="Invalid RF profile: "+err.message;}
};
input.onchange=async()=>{
  const file=input.files?.[0];if(!file)return;
  if(file.size>1024*1024){status.textContent="Firmware too large (max 1 MiB).";return;}
  if(!/si2168/i.test(file.name)||!/d60/i.test(file.name)){
    status.textContent="Select the Si2168-D60 firmware for this exact demodulator revision; file not accepted.";
    return;
  }
  try{
    const content=new Uint8Array(await file.arrayBuffer());
    const description=describeFirmware(content);
    const hash=await crypto.subtle.digest("SHA-256",content);
    const sha256=Array.from(new Uint8Array(hash),x=>x.toString(16).padStart(2,"0")).join("");
    firmwareReport={filename:file.name,sha256,...description};
    report(getPlan());
    status.textContent="Firmware format parsed and SHA-256 calculated locally. File was NOT uploaded, saved or sent to the USB tuner.";
  }catch(err){status.textContent="Firmware rejected: "+err.message;firmwareReport=null;}
};
if(!("usb" in navigator)){
  status.textContent="This browser has no WebUSB tuner access. Firmware/command preview still works as a browser-only research tool.";
}else{
  status.textContent="Standalone driver protocol planning ready. No native app, server, token or USB writes required.";
}
