/* WebUSB WinTV-soloHD diagnostics, no automatic retune/firmware/kernel changes.
 * Every USB operation starts from explicit user interaction.
 */
import {WinTVProbe,WINTV,bulkCandidates} from "./webusb-em28xx.js";
import {TransportAnalyzer} from "./ts-analyzer.js";
import {BrowserTransportCapture} from "./browser-ts-capture.js";
import {classifyUsbFailure,LINUX_SETUP_COMMANDS} from "./webusb-access-guide.js";

const $=id=>document.getElementById(id);
const probe=new WinTVProbe();
let lastReport=null,busy=false,capture=null,lastCapture=null,lastFailure=null;
function showUsbHelp(advice=null){
  const panel=$("webusb-access-help");
  if(!panel)return;
  panel.hidden=!advice;
  panel.open=!!advice;
  if(!advice)return;
  $("webusb-help-title").textContent=advice.title;
  $("webusb-help-explanation").textContent=advice.explanation;
  $("webusb-help-next").textContent=advice.next;
  $("webusb-help-udev-block").hidden=advice.code!=="os_usb_open_denied";
  $("webusb-help-claim-block").hidden=advice.code!=="usb_interface_unavailable";
  $("webusb-help-udev").textContent=LINUX_SETUP_COMMANDS;
}
$("webusb-copy-udev").onclick=async()=>{
  try{
    await navigator.clipboard.writeText(LINUX_SETUP_COMMANDS);
    say("Copied scoped 2040:8268 udev setup commands. Run manually in a local terminal, then replug the tuner.");
  }catch(error){
    say("Clipboard access blocked; select and copy the command text manually.");
  }
};
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
  $("webusb-capture").disabled=!claimed||busy;
  $("webusb-capture-stop").disabled=!capture;
  $("webusb-capture-save").disabled=!lastCapture?.bytes?.length;
}
const formatHex=n=>"0x"+Number(n).toString(16).padStart(2,"0");
function report(extra={}){
  const info={timestamp:new Date().toISOString(),
    browserWebUSB:!!navigator.usb,secureContext:globalThis.isSecureContext,
    ...probe.describe(),
    transport:probe.analyzer.summary(),
    usbAccessError:lastFailure?{code:lastFailure.code,stage:lastFailure.stage,
      original:lastFailure.raw}:null,
    capture:lastCapture?{bytes:lastCapture.bytes.length,
      transfers:lastCapture.transfers,stopped:lastCapture.stopped,
      transportVerified:lastCapture.transportVerified,
      summary:lastCapture.summary}:null,...extra};
  // Never persist user serial numbers, hardware paths, MACs or permission tokens.
  lastReport=info;
  $("webusb-diagnostics").textContent=JSON.stringify(info,null,2);
  setButtons();
}
async function run(action,stage="unknown"){
  if(busy)return;
  busy=true;setButtons();
  try{
    await action();
    lastFailure=null;showUsbHelp();
  }catch(error){
    const root=error?.usbOriginal?
      {name:stage==="open"?"SecurityError":"Error",message:error.usbOriginal}:error;
    const advice=classifyUsbFailure(root,error?.usbStage||stage);
    lastFailure=advice;
    if(advice.code==="user_cancelled"){
      say("USB device chooser was cancelled. No hardware accessed.");
      showUsbHelp();
    }else{
      say(advice.title+". "+advice.next);
      showUsbHelp(advice);
    }
  }finally{busy=false;report();}
}
$("webusb-select").onclick=()=>run(async()=>{
  const selected=await probe.select();
  say("Selected "+selected.model+". USB permission alone does NOT mean DVB tuning is ready.");
},"select");
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
},"open");
$("webusb-read-chip").onclick=()=>run(async()=>{
  const id=await probe.readChipId();
  say("Read-only EM28xx chip ID register 0x0A = "+formatHex(id)+
      ". Demodulator/firmware/TV reception are NOT initialized by this read.");
},"open");
$("webusb-claim").onclick=()=>run(async()=>{
  if(!confirm("Experimental: claim the exposed bulk-IN interface? "+
    "The request should fail while the Linux DVB driver owns the interface. "+
    "This will NOT detach kernel drivers, load firmware or tune a channel."))return;
  const out=await probe.claimBulk();
  say("Claimed USB interface "+out.interfaceClaimed+
      ". This is exclusive access; no DVB-T2 frontend initialization has been performed.");
},"claim");
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
// A finite and explicitly requested read-only capture: NEVER tune, send
// firmware, reset the device or silently detach the Linux DVB driver.
function boundedBulkRead(size){
  // WebUSB has no AbortSignal on transferIn. This is a soft deadline only;
  // a timed-out browser USB operation may remain pending until close/unplug.
  let timer;
  return Promise.race([
    probe.readBulkBytes(size),
    new Promise((_,reject)=>{
      timer=setTimeout(()=>reject(Error(
        "USB bulk-IN stalled for 5 seconds. Stop/release the interface or unplug safely; a USB transfer may still be pending.")),5000);
    })
  ]).finally(()=>clearTimeout(timer));
}
$("webusb-capture").onclick=async()=>{
  if(busy||probe.claimed===null)return;
  if(!confirm("Capture up to 4 MiB from the already-claimed USB bulk-IN endpoint? "+
     "No RF frequency will be tuned and no firmware or USB control writes will be sent. "+
     "Without an already-running TS stream, this may time out."))return;
  busy=true;lastCapture=null;
  capture=new BrowserTransportCapture(boundedBulkRead,{
    maxBytes:4*1024*1024,maxTransfers:256,
    onProgress:({bytes,transfers,summary})=>{
      const named=summary.programs.filter(p=>p.name).map(p=>p.name).slice(0,6);
      say("Captured "+bytes+" real USB bytes / "+transfers+" reads · "+
          summary.packets+" MPEG-TS packets · "+summary.validSections+
          " valid PSI/SI sections"+(named.length?" · "+named.join(", "):""));
    }
  });
  setButtons();
  say("Read-only capture started. Stop requests take effect after the current USB transfer.");
  try{
    lastCapture=await capture.run();
    probe.analyzer=capture.analyzer;
    const s=lastCapture.summary;
    say("Capture ended: "+lastCapture.bytes.length+" bytes, "+s.packets+
      " MPEG-TS packets, "+s.validSections+" valid PSI/SI sections, "+
      s.programs.length+" PAT services. "+
      (lastCapture.transportVerified?
        "Transport stream recognized; download is enabled.":
        "No validated DVB transport tables. The download is raw diagnostic bytes, NOT proof of TV reception."));
  }catch(err){
    say("USB capture failed: "+(err?.message||err)+
      " No tuner writes were attempted.");
  }finally{
    capture=null;busy=false;report();
  }
};
$("webusb-capture-stop").onclick=()=>{
  capture?.stop();
  say("Capture stop requested. Current WebUSB read must finish or time out first.");
};
$("webusb-capture-save").onclick=()=>{
  if(!lastCapture?.bytes.length)return;
  const ts=lastCapture.transportVerified;
  const blob=new Blob([lastCapture.bytes],{
    type:ts?"video/mp2t":"application/octet-stream"
  });
  const url=URL.createObjectURL(blob);
  const link=document.createElement("a");
  link.href=url;
  link.download="tihulu-real-usb-capture."+(ts?"ts":"bin");
  link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1500);
};
$("webusb-release").onclick=()=>run(async()=>{
  await probe.release();
  say("WebUSB interface released and device handle closed. Linux tuner settings were untouched.");
},"release");
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
  const identified=data.programs.filter(p=>p.name).map(p=>p.service+
    " · "+p.name+(p.kind==="radio"?" [Radio]":p.kind==="tv"?" [TV]":"")+
    (p.provider?" · "+p.provider:""));
  say("Analyzed "+size+" local bytes of "+file.name+" — "+data.packets+
      " MPEG-TS packets, "+data.programs.length+" real PAT services, "+
      identified.length+" SDT names. No upload. "+
      (identified.length?"Detected: "+identified.slice(0,12).join(" | "):
       "No broadcaster names found in this sample; SDT may be absent."));
  report({importedTransport:data,importedFileSize:file.size,readBytes:size});
  $("webusb-ts-import").value="";
});
if(navigator.usb){
  navigator.usb.addEventListener("disconnect",evt=>{
    if(probe.onDisconnect(evt.device)){
      capture?.stop();
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
