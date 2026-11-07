/* WebUSB WinTV-soloHD diagnostics, no automatic retune/firmware/kernel changes.
 * Every USB operation starts from explicit user interaction.
 */
import {WinTVProbe,WINTV,bulkCandidates} from "./webusb-em28xx.js";
import {TransportAnalyzer} from "./ts-analyzer.js";

const $=id=>document.getElementById(id);
const probe=new WinTVProbe();
let lastReport=null,busy=false;
const say=text=>{$("usb-status").textContent=text};
function setButtons(){
  const supported=!!navigator.usb&&globalThis.isSecureContext===true;
  const selected=!!probe.device;
  const opened=!!probe.device?.opened;
  const claimed=probe.claimed!==null;
  for(const id of ["webusb-select","webusb-check"])$(id).disabled=!supported||busy;
  $("webusb-inspect").disabled=!selected||busy;
  $("webusb-open").disabled=!selected||busy;
  $("webusb-read-chip").disabled=!opened||busy;
  $("webusb-claim").disabled=!opened||claimed||busy;
  $("webusb-bulk").disabled=!claimed||busy;
  $("webusb-release").disabled=!selected||busy;
  $("webusb-export").disabled=!lastReport;
}
const formatHex=n=>"0x"+Number(n).toString(16).padStart(2,"0");
function report(extra={}){
  const info={timestamp:new Date().toISOString(),
    browserWebUSB:!!navigator.usb,secureContext:globalThis.isSecureContext,
    ...probe.describe(),
    transport:probe.analyzer.summary(),...extra};
  // Never persist user serial numbers, hardware paths, MACs or permission tokens.
  lastReport=info;
  $("webusb-diagnostics").textContent=JSON.stringify(info,null,2);
  setButtons();
}
async function run(action){
  if(busy)return;
  busy=true;setButtons();
  try{await action();}
  catch(e){say(e?.message||String(e))}
  finally{busy=false;report();}
}
$("webusb-select").onclick=()=>run(async()=>{
  const selected=await probe.select();
  say("Selected "+selected.model+". USB permission alone does NOT mean DVB tuning is ready.");
});
$("webusb-check").onclick=()=>run(async()=>{
  const count=await probe.permitted();
  say(count+" previously permitted WinTV 2040:8268 device(s)."+
      (probe.device?" One selected for inspection.":" Click Select USB tuner."));
});
$("webusb-inspect").onclick=()=>run(async()=>{
  if(!probe.device)throw Error("Select a device first");
  const candidates=bulkCandidates(probe.device);
  say("Found "+candidates.length+" bulk-IN USB endpoint(s). This is descriptor information only.");
});
$("webusb-open").onclick=()=>run(async()=>{
  await probe.openForRead();
  say("USB open succeeded. Linux em28xx may still own the data interface. No tuner was touched.");
});
$("webusb-read-chip").onclick=()=>run(async()=>{
  const id=await probe.readChipId();
  say("Read-only EM28xx chip ID register 0x0A = "+formatHex(id)+
      ". Demodulator/firmware/TV reception are NOT initialized by this read.");
});
$("webusb-claim").onclick=()=>run(async()=>{
  if(!confirm("Experimental: claim the exposed bulk-IN interface? "+
    "The request should fail while the Linux DVB driver owns the interface. "+
    "This will NOT detach kernel drivers, load firmware or tune a channel."))return;
  const out=await probe.claimBulk();
  say("Claimed USB interface "+out.interfaceClaimed+
      ". This is exclusive access; no DVB-T2 frontend initialization has been performed.");
});
$("webusb-bulk").onclick=()=>run(async()=>{
  if(!confirm("Read at most one 16 KiB bulk transfer as an experimental diagnostic? "+
              "Without firmware and tuner initialization this may return nothing or stall. "+
              "This does not start television."))return;
  say("Reading one USB transfer. This may block if no active TS stream.");
  // WebUSB does not provide an AbortSignal for transferIn; soft timeout only.
  let timeout;
  try{
    const data=await Promise.race([
      probe.readBulkOnce(),
      new Promise((_,reject)=>{
        timeout=setTimeout(()=>reject(Error("Bulk read did not complete in 4 seconds. "+
          "The browser may still have a pending USB transfer; release or unplug safely.")),4000);
      })
    ]);
    say("Bulk received "+data.readBytes+" actual bytes; parsed "+
        data.summary.packets+" MPEG-TS packets so far. Zero packets means NO confirmed TV stream.");
  }finally{clearTimeout(timeout);}
});
$("webusb-release").onclick=()=>run(async()=>{
  await probe.release();
  say("WebUSB interface released and device handle closed. Linux tuner settings were untouched.");
});
$("webusb-export").onclick=()=>{
  if(!lastReport)return;
  const data=new Blob([JSON.stringify(lastReport,null,2)+"\n"],{type:"application/json"});
  const url=URL.createObjectURL(data);
  const link=document.createElement("a");
  link.href=url;link.download="tihulu-webusb-wintv-diagnostics.json";
  link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1500);
};
$("webusb-ts-import").onchange=()=>run(async()=>{
  const file=$("webusb-ts-import").files?.[0];
  if(!file)return;
  const ts=new TransportAnalyzer();
  const size=Math.min(file.size,2*1024*1024);
  for(let at=0;at<size;at+=65536){
    const chunk=new Uint8Array(await file.slice(at,Math.min(size,at+65536)).arrayBuffer());
    ts.feed(chunk);
  }
  const data=ts.summary();
  say("Analyzed "+size+" local bytes of "+file.name+" — "+data.packets+
      " TS packets, "+data.programs.length+" PAT service ID(s). Local analysis only; file not uploaded.");
  report({importedTransport:data,importedFileSize:file.size,readBytes:size});
  $("webusb-ts-import").value="";
});
if(navigator.usb){
  navigator.usb.addEventListener("disconnect",evt=>{
    if(probe.onDisconnect(evt.device)){
      say("WinTV tuner unplugged. Browser USB access ended.");
      report();
    }
  });
}
if(!navigator.usb){
  say("WebUSB is unavailable. Open the HTTPS Pages app in Chromium; Firefox does not offer WebUSB.");
}else if(!globalThis.isSecureContext){
  say("WebUSB requires HTTPS or another secure context.");
}else{
  say("WebUSB transport probe ready. Select the Hauppauge device; no device commands have been sent.");
}
report();
