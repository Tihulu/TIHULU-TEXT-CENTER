/* Direct browser RTL-SDR via @jtarrio/webrtlsdr pinned 3.0.7.
 * Sampled RF power is NOT a GNSS fix, signal acquisition or satellite identification.
 * Explicit user gesture only. Never touch readsb/Gqrx or other USB owners.
 */
const $=id=>document.getElementById(id);
export function initUsbSDR(report){
 let receiver=null,usbDevice=null,busy=false,stopping=false,sampling=false;
 let stage="not started";
 const diagnose=async(error,atStage)=>{
   const type=String(error?.name||"Error");
   const original=String(error?.message||error||"Unknown USB error");
   const underlying=String(error?.cause?.message||"").slice(0,260);
   let allowed="unknown";
   try{
     if(navigator.usb?.getDevices){
       const devices=await navigator.usb.getDevices();
       allowed=String(devices.filter(d=>d.vendorId===0x0bda&&d.productId===0x2838).length);
     }
   }catch{}
   const lines=["Connection stage: "+atStage,"Browser error: "+type+" — "+original,
     "Previously granted RTL-SDR devices: "+allowed];
   if(underlying&&underlying!==original)lines.push("Underlying error: "+underlying);
   if(type==="NotFoundError"&&atStage==="USB permission selection")
     lines.push("No device chosen. Reopen the chooser and select the Nooelec RTL2832U stick.");
   else if(type==="SecurityError"||type==="NotAllowedError")
     lines.push("Browser permission/policy blocked WebUSB. Use a supported browser on HTTPS and check device permission settings.");
   else if(atStage==="USB interface claim / device open"||/Could not connect|busy|claim|access|LIBUSB_ERROR|device is open/i.test(original)){
     lines.push("A USB device was selected, but opening/claiming its interface failed. This often means readsb/Gqrx, the Linux DVB kernel driver, udev access rules, or browser sandbox permissions.");
     lines.push("Linux: run the repository's read-only USB check, then its explicit --release action if appropriate. The website cannot run systemctl or unbind kernel drivers.");
   }else if(atStage==="WebUSB driver module import")
     lines.push("Driver could not load from esm.sh. First visit online; CDN or CSP may block its JavaScript import.");
   else if(atStage==="RF tuner initialization")
     lines.push("USB interface may have opened but tuner initialization failed; confirm compatible RTL2832U/R820T hardware.");
   else lines.push("Check Linux OS device ownership/permissions and close other SDR applications.");
   const details=$("usb-diagnostics");
   if(details){details.replaceChildren();
      const box=document.createElement("pre");box.textContent=lines.join("\n");details.append(box);
   }
   return lines.join(" | ");
 };

 const notify=(status,message)=>{
   window.dispatchEvent(new CustomEvent("tihulu:receiver-status",{detail:{status,message}}));
   if($("usb-state"))$("usb-state").textContent=status+": "+message;
   const isOpen=["USB CONNECTED","SAMPLING","RF SAMPLED","SAMPLE ERROR"].includes(status);
   if($("rf-state"))$("rf-state").textContent=isOpen?"RTL-SDR OPEN (THIS TAB)":"NO RF RECEIVER OPEN";
   if($("stage-device"))$("stage-device").textContent=isOpen?"WEBUSB RTL-SDR OPEN":"UNAVAILABLE";
   if(report)report(message);
 };
 async function release(){
   stopping=true;sampling=false;
   // Close only this module's own handles; never stop OS services or other tabs.
   const device=receiver;receiver=null;
   if(device){try{await device.close()}catch(e){notify("RELEASE WARNING",e.message)}}
   const chosen=usbDevice;usbDevice=null;
   if(chosen?.opened){try{await chosen.close()}catch(e){notify("RELEASE WARNING",e.message)}}
   busy=false;
   notify("NOT CONNECTED","Own RTL-SDR session stopped/released; unrelated applications untouched.");
 }
 async function connect(){
   if(busy||receiver){notify("BUSY",receiver?"Device already connected.":"A connection attempt is already running.");return}
   if(!navigator.usb||!window.isSecureContext){notify("UNAVAILABLE","WebUSB requires HTTPS and desktop Chrome/Brave/Edge; Firefox/Safari do not support it.");return}
   busy=true;stopping=false;stage="USB permission selection";
   try{
     // Request USB permission directly within the user gesture, before any network import.
     usbDevice=await navigator.usb.requestDevice({filters:[{vendorId:0x0bda,productId:0x2838}]});
     if(stopping)throw Error("Connection cancelled by Hard Stop");
     stage="WebUSB driver module import";
     notify("CONNECTING","Loading pinned WebUSB driver; device permission granted but hardware not yet opened.");
     const lib=await import("https://esm.sh/@jtarrio/webrtlsdr@3.0.7/rtlsdr.js?bundle");
     if(typeof lib.RTL2832U_Provider!=="function")throw Error("Browser RTL-SDR driver export is unavailable");
     const provider=new lib.RTL2832U_Provider({webusb:{requestDevice:async()=>usbDevice}});
     stage="USB interface claim / device open";
     const d=await provider.get();
     if(stopping){await d.close();throw Error("Connection cancelled by Hard Stop")}
     receiver=d;
     stage="RF tuner initialization";
     await receiver.setSampleRate(1024000);
     await receiver.setCenterFrequency(1575420000);
     await receiver.setGain(null);
     await receiver.resetBuffer();
     if(stopping){await release();return}
     stage="USB connected";
     if($("usb-diagnostics"))$("usb-diagnostics").textContent="Connected. RTL-SDR interface opened successfully; GNSS acquisition remains unavailable.";
     notify("USB CONNECTED","Nooelec/RTL2832U claimed at 1575.420 MHz; receiver open. No GNSS signal decoded or position fix.");
   }catch(error){
     const atStage=stage;
     await release();
     const detail=await diagnose(error,atStage);
     notify("USB OPEN FAILED",detail);
   }finally{busy=false}
 }
 async function scan(){
   if(!receiver){notify("UNAVAILABLE","Connect RTL-SDR first; GNSS L1 scan not started.");return}
   if(sampling){notify("BUSY","A bounded RF energy sample is already running.");return}
   sampling=true;stopping=false;
   const start=Date.now();let bytes=0,powerSum=0,powerN=0;
   try{
     await receiver.setSampleRate(1024000);
     await receiver.setCenterFrequency(1575420000);
     await receiver.resetBuffer();
     notify("SAMPLING","Measuring relative raw I/Q level near GNSS L1 for up to 2 s (not GPS acquisition).");
     while(sampling&&!stopping&&Date.now()-start<2000&&bytes<4*1024*1024){
       const raw=await receiver.readSamples(16384);
       const arr=raw instanceof ArrayBuffer?new Uint8Array(raw):ArrayBuffer.isView(raw)?new Uint8Array(raw.buffer,raw.byteOffset,raw.byteLength):null;
       if(!arr||arr.length<2)throw Error("No I/Q sample bytes returned");
       bytes+=arr.length;
       for(let i=0;i+1<arr.length;i+=2){
         const re=(arr[i]-127.5)/127.5,im=(arr[i+1]-127.5)/127.5;
         powerSum+=re*re+im*im;powerN++;
       }
     }
     if(!stopping){
       if(!powerN)throw Error("No RF samples received");
       const rms=Math.sqrt(powerSum/powerN);
       const db=20*Math.log10(Math.max(1e-9,rms));
       notify("RF SAMPLED",bytes+" actual USB bytes · relative level "+db.toFixed(1)+" dBFS-like at 1575.420 MHz (UNCALIBRATED; NOT GNSS SIGNAL LOCK).");
     }
   }catch(error){notify("SAMPLE ERROR",error.message||String(error))}
   finally{sampling=false}
 }
 // Select and claim receiver only when the user chooses it.
 $("usb-select")?.addEventListener("click",()=>{void connect()});
 $("live-release")?.addEventListener("click",()=>{void release()});
 $("live-scan")?.addEventListener("click",()=>{void scan()});
 $("hard-stop")?.addEventListener("click",()=>{void release()});
 window.addEventListener("pagehide",()=>{void release()});
 document.addEventListener("visibilitychange",()=>{if(document.hidden&&receiver)void release()});
 return {connect,scan,release};
}
