/* Direct browser RTL-SDR via @jtarrio/webrtlsdr pinned 3.0.7.
 * Sampled RF power is NOT a GNSS fix, signal acquisition or satellite identification.
 * Explicit user gesture only. Never touch readsb/Gqrx or other USB owners.
 */
import {relativePowerDbFS} from "../core/rf_ranging.mjs";
const $=id=>document.getElementById(id);
export function initUsbSDR(report){
 let receiver=null,usbDevice=null,busy=false,stopping=false,sampling=false;
 let configuredRate=0,configuredFrequencyHz=0,configuredGain=null;
 let pendingSample=null,finishSample=null;
 const beginSample=()=>{
   pendingSample=new Promise(resolve=>{finishSample=resolve});
 };
 const endSample=()=>{
   const finish=finishSample;finishSample=null;
   if(finish)finish();
   pendingSample=null;
 };
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
   const inFlight=pendingSample;
   if(inFlight){
     // A WebUSB bulk read may be in flight. Wait for its callback before closing the USB handle.
     await Promise.race([inFlight,new Promise(resolve=>setTimeout(resolve,2500))]);
   }
   const device=receiver;receiver=null;
   configuredRate=0;configuredFrequencyHz=0;configuredGain=null;
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
     configuredRate=1024000;
     if(stopping)throw Error("Connection cancelled before tuning");
     await receiver.setCenterFrequency(1575420000);
     configuredFrequencyHz=1575420000;
     if(stopping)throw Error("Connection cancelled before gain setup");
     await receiver.setGain(null);
     configuredGain=null;
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
   if(busy||sampling){notify("BUSY","USB receiver is already initializing, sampling or performing another operation.");return}
   sampling=true;busy=true;stopping=false;beginSample();
   const start=Date.now();let bytes=0,powerSum=0,powerN=0;
   try{
     // Sample rate was set ONCE during connect. Writing demodulator register 0x9f
     // again here is redundant and caused the reported reg=9f20 transfer failure.
     if(configuredRate!==1024000)throw Error("Receiver sample rate no longer configured; release and reconnect");
     if(configuredFrequencyHz!==1575420000){
       await receiver.setCenterFrequency(1575420000);
       configuredFrequencyHz=1575420000;
     }
     if(configuredGain!==null){
       await receiver.setGain(null);
       configuredGain=null;
     }
     if(stopping)return;
     await receiver.resetBuffer();
     notify("SAMPLING","Measuring relative raw I/Q level near GNSS L1 for up to 2 s (not GPS acquisition).");
     while(sampling&&!stopping&&Date.now()-start<2000&&bytes<4*1024*1024){
       const block=await receiver.readSamples(16384);
       const raw=block?.data;
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
   }catch(error){
     if(!stopping)notify("SAMPLE ERROR",(error.message||String(error))+
       ". If USB register write failed, check cable/USB power and try Release USB then reconnect. "+
       "No automatic reconfiguration retry will be attempted.");
   }
   finally{sampling=false;busy=false;endSample()}
 }
 async function captureRF(frequencyMHz,sourceId){
   if(!receiver){notify("RF NOT CONNECTED","Connect RTL-SDR via WebUSB first. No simulated RF readings.");return}
   if(busy||sampling){notify("RF BUSY","Another USB receive operation is in progress.");return}
   if(!Number.isFinite(frequencyMHz)||frequencyMHz<24||frequencyMHz>1766){
     notify("RF INVALID FREQUENCY","Enter a valid RTL-SDR frequency in MHz (24–1766).");return
   }
   busy=true;sampling=true;stopping=false;beginSample();
   const gainDb=20,sampleRate=1024000;
   let samples=0,power=0;
   try{
     if(configuredRate!==sampleRate)throw Error("Receiver sample rate not configured; release and reconnect");
     if(configuredGain!==gainDb){
       await receiver.setGain(gainDb); // fixed gain is essential for level comparisons
       configuredGain=gainDb;
     }
     const targetFrequencyHz=Math.round(frequencyMHz*1e6);
     if(configuredFrequencyHz!==targetFrequencyHz){
       await receiver.setCenterFrequency(targetFrequencyHz);
       configuredFrequencyHz=targetFrequencyHz;
     }
     if(stopping)return;
     await receiver.resetBuffer();
     for(let i=0;i<8&&!stopping;i++){
       const block=await receiver.readSamples(16384);
       const bytes=block?.data;
       if(!(bytes instanceof ArrayBuffer)&&!ArrayBuffer.isView(bytes))throw Error("RTL-SDR did not return I/Q sample block.data");
       const n=bytes.byteLength;
       const db=relativePowerDbFS(bytes);
       power+=Math.pow(10,db/10)*n;samples+=n;
     }
     if(stopping){notify("RF STOPPED","Radio sample was cancelled. No measurement stored.");return}
     if(samples===0)throw Error("No actual radio bytes received");
     const levelDbFS=10*Math.log10(power/samples);
     const record={levelDbFS,frequencyMHz,gainDb,sampleRate,sampleBytes:samples,
       measuredAt:new Date().toISOString(),sourceId:String(sourceId||""),hardwareId:"RTL2832U WebUSB 0bda:2838",
       observation:"REAL HARDWARE I/Q POWER LEVEL · NOT A DISTANCE",
       sourceIdentityVerified:false,decodedSignal:false};
     window.dispatchEvent(new CustomEvent("tihulu:rf-observation",{detail:record}));
     notify("RF IQ CAPTURED",frequencyMHz.toFixed(3)+" MHz · "+samples+" bytes of REAL RTL-SDR I/Q · "+
       levelDbFS.toFixed(2)+" dBFS-like · fixed gain "+gainDb+" dB. Total receiver energy, not an identified station or distance.");
   }catch(error){if(!stopping)notify("RF CAPTURE ERROR",(error?.message||String(error))+
     ". No unverified RF capture has been recorded; if USB transfer fails, release and reconnect.")}
   finally{sampling=false;busy=false;endSample()}
 }
 async function selfTest(){
   if(busy||receiver){notify("USB TEST BUSY","Release this app's receiver or finish the current USB operation before testing.");return}
   if(!navigator.usb||!window.isSecureContext){
     notify("USB TEST UNAVAILABLE","Use an HTTPS page in a desktop Chromium browser with WebUSB support.");return
   }
   busy=true;stopping=false;
   let device=null,opened=false,claimed=false,result="";
   try{
     const permitted=(await navigator.usb.getDevices()).filter(d=>d.vendorId===0x0bda&&d.productId===0x2838);
     if(!permitted.length){
       notify("USB NOT PERMITTED","No permitted RTL2832U device. Click Connect RTL-SDR once to grant browser permission, then rerun this test.");
       return;
     }
     if(permitted.length>1){
       notify("USB TEST AMBIGUOUS","Multiple matching RTL-SDR sticks are permitted. Use Connect to choose the intended receiver.");
       return;
     }
     device=permitted[0];
     if(stopping)throw Error("Cancelled by Hard Stop");
     await device.open();opened=true;
     if(stopping)throw Error("Cancelled by Hard Stop");
     if(!device.configuration)await device.selectConfiguration(1);
     if(stopping)throw Error("Cancelled by Hard Stop");
     if(!device.configuration?.interfaces?.some(x=>x.interfaceNumber===0))
       throw Error("Device configuration has no RTL-SDR control interface 0");
     await device.claimInterface(0);claimed=true;
     if(stopping)throw Error("Cancelled by Hard Stop");
     result="PASS: WebUSB opened the device and claimed interface 0. This is a USB-access test only; no RF capture or GPS fix.";
   }catch(error){
     result="FAIL: "+(error.name||"Error")+" — "+(error.message||String(error))+
       ". If claimInterface failed, check other USB tabs, Linux DVB driver ownership and browser sandbox. No terminal/Console paste required.";
   }finally{
     if(device&&claimed){try{await device.releaseInterface(0)}catch(e){result+=" Warning: releaseInterface failed: "+e.message}}
     if(device&&opened){try{await device.close()}catch(e){result+=" Warning: device.close failed: "+e.message}}
     busy=false;
     if(result){
       notify(result.startsWith("PASS")?"USB TEST PASS":"USB TEST FAIL",result);
       const detail=$("usb-diagnostics");if(detail)detail.textContent=result;
     }
   }
 }
 // Select and claim receiver only when the user chooses it.
 window.addEventListener("tihulu:rf-capture-request",event=>{void captureRF(event.detail?.frequencyMHz,event.detail?.sourceId)});
 $("usb-select")?.addEventListener("click",()=>{void connect()});
 $("usb-selftest")?.addEventListener("click",()=>{void selfTest()});
 $("live-usb-check")?.addEventListener("click",()=>{void selfTest()});
 $("live-release")?.addEventListener("click",()=>{void release()});
 $("live-scan")?.addEventListener("click",()=>{void scan()});
 $("hard-stop")?.addEventListener("click",()=>{void release()});
 window.addEventListener("pagehide",()=>{void release()});
 document.addEventListener("visibilitychange",()=>{if(document.hidden&&receiver)void release()});
 return {connect,scan,release,selfTest,captureRF};
}
