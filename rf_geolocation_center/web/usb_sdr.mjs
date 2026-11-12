/* Direct browser RTL-SDR via @jtarrio/webrtlsdr pinned 3.0.7.
 * Sampled RF power is NOT a GNSS fix, signal acquisition or satellite identification.
 * Explicit user gesture only. Never touch readsb/Gqrx or other USB owners.
 */
import {relativePowerDbFS} from "../core/rf_ranging.mjs";
const $=id=>document.getElementById(id);
export function initUsbSDR(report, {driverFactory} = {}){
 let receiver=null,usbDevice=null,busy=false,stopping=false,sampling=false;
 let quitting=false,releasePromise=null,operationSerial=0,terminalFailure=null;
 let configuredRate=0,configuredFrequencyHz=0,configuredGain=null,sweepCancel=false;
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
     lines.push("Linux: run the repository's read-only USB check, then its explicit --release action if appropriate. The website cannot stop host services or unbind kernel drivers.");
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
   if(quitting && !["NOT CONNECTED","RELEASE WARNING"].includes(status))return;
   window.dispatchEvent(new CustomEvent("tihulu:receiver-status",{detail:{status,message}}));
   if($("usb-state"))$("usb-state").textContent=status+": "+message;
   const isOpen=["USB CONNECTED","SAMPLING","RF SAMPLED","SAMPLE ERROR"].includes(status);
   if($("rf-state"))$("rf-state").textContent=isOpen?"RTL-SDR OPEN (THIS TAB)":"NO RF RECEIVER OPEN";
   if($("stage-device"))$("stage-device").textContent=isOpen?"WEBUSB RTL-SDR OPEN":"UNAVAILABLE";
   if(report)report(message);
 };
 function release({permanent=false}={}){
   if(permanent)quitting=true;
   if(releasePromise)return releasePromise;
   if(terminalFailure)return Promise.reject(terminalFailure); // A previously failed close is not a successful release.
   stopping=true;sampling=false;sweepCancel=true;operationSerial++;
 // repeated Stop/Quit shares one device-close
   releasePromise=(async()=>{
     const failures=[];
     const inFlight=pendingSample;
     if(inFlight){
       let timer;
       const drained=await Promise.race([
         inFlight.then(()=>true),
         new Promise(resolve=>{timer=setTimeout(()=>resolve(false),2500)})
       ]);
       clearTimeout(timer);
       if(!drained)failures.push("in-flight RF sample did not drain within 2500 ms");
     }
     const closeOwned=async(handle,label)=>{
       let timer;
       try{
         const done=await Promise.race([
           Promise.resolve().then(()=>handle.close()).then(()=>true),
           new Promise(resolve=>{timer=setTimeout(()=>resolve(false),1600)})
         ]);
         if(!done)throw Error(label+" close did not finish within 1600 ms");
       }catch(e){
         failures.push(label+": "+String(e?.message||e));
         notify("RELEASE WARNING",String(e?.message||e));
       }finally{clearTimeout(timer)}
     };
     const device=receiver;receiver=null;
     configuredRate=0;configuredFrequencyHz=0;configuredGain=null;
     if(device)await closeOwned(device,"owned receiver");
     const chosen=usbDevice;usbDevice=null;
     if(chosen?.opened)await closeOwned(chosen,"owned USB device");
     busy=false;
     if(failures.length)throw Error("Incomplete app-owned USB release: "+failures.join("; ").slice(0,240));
     notify("NOT CONNECTED","Own RTL-SDR session stopped/released; unrelated applications untouched.");
   })().catch(error=>{
     // Do not discard failed handle closure or a timed-out RF read on a later
     // Stop/Quit. The hardware lease state is unknown until a full reload.
     terminalFailure=error;
     throw error;
   }).finally(()=>{releasePromise=null});
   return releasePromise;
 }
 async function connect(preferredDevice=null){
   if(quitting||releasePromise)return;
   if(terminalFailure){
     notify("RELEASE WARNING","Previous owned USB close is unverified; reload the tab before reconnecting. "+terminalFailure.message);
     return;
   }
   if(busy||receiver){notify("BUSY",receiver?"Device already connected.":"A connection attempt is already running.");return}
   if(!navigator.usb||!window.isSecureContext){notify("UNAVAILABLE","WebUSB requires HTTPS and desktop Chrome/Brave/Edge; Firefox/Safari do not support it.");return}
   busy=true;stopping=false;stage="USB permission selection";
   const operation=++operationSerial;
   const active=()=>!quitting&&!stopping&&operation===operationSerial;
   try{
     if(preferredDevice){
       // A user selected a previously PERMITTED device in the hardware panel.
       // Never allow an arbitrary generic USB device to be opened as RTL-SDR.
       if(preferredDevice.vendorId!==0x0bda||preferredDevice.productId!==0x2838)
         throw Error("Selected USB device is not a supported RTL2832U (0bda:2838)");
       const allowed=await navigator.usb.getDevices();
       if(!allowed.some(d=>d.vendorId===0x0bda&&d.productId===0x2838&&
         (d===preferredDevice||(d.serialNumber&&d.serialNumber===preferredDevice.serialNumber))))
         throw Error("RTL-SDR permission is missing or was revoked. Re-select the device through the browser.");
       usbDevice=preferredDevice;
     }else{
       // Fresh user gesture: request permission directly before any network import.
       usbDevice=await navigator.usb.requestDevice({filters:[{vendorId:0x0bda,productId:0x2838}]});
     }
     if(!active()){if(usbDevice?.opened)await usbDevice.close();usbDevice=null;return;}
     stage="WebUSB driver module import";
     notify("CONNECTING","Loading pinned WebUSB driver; device permission granted but hardware not yet opened.");
     const lib=driverFactory?await driverFactory():await import("https://esm.sh/@jtarrio/webrtlsdr@3.0.7/rtlsdr.js?bundle");
     if(!active())return;
     if(typeof lib.RTL2832U_Provider!=="function")throw Error("Browser RTL-SDR driver export is unavailable");
     const provider=new lib.RTL2832U_Provider({webusb:{requestDevice:async()=>usbDevice}});
     stage="USB interface claim / device open";
     const d=await provider.get();
     if(!active()){await d.close();return;}
     receiver=d;
     stage="RF tuner initialization";
     await receiver.setSampleRate(1024000);
     configuredRate=1024000;
     if(!active())return;
     await receiver.setCenterFrequency(1575420000);
     configuredFrequencyHz=1575420000;
     if(!active())return;
     await receiver.setGain(null);
     configuredGain=null;
     await receiver.resetBuffer();
     if(!active()){await release();return;}
     stage="USB connected";
     if($("usb-diagnostics"))$("usb-diagnostics").textContent="Connected. RTL-SDR interface opened successfully; GNSS acquisition remains unavailable.";
     notify("USB CONNECTED","Nooelec/RTL2832U claimed at 1575.420 MHz; receiver open. No GNSS signal decoded or position fix.");
   }catch(error){
     if(!active()){await release();return;}
     const atStage=stage;
     await release();
     const detail=await diagnose(error,atStage);
     notify("USB OPEN FAILED",detail);
   }finally{busy=false}
 }
 async function scan(){
   if(quitting||releasePromise)return;
   if(!receiver){notify("UNAVAILABLE","Connect RTL-SDR first; GNSS L1 scan not started.");return}
   if(busy||sampling){notify("BUSY","USB receiver is already initializing, sampling or performing another operation.");return}
   sampling=true;busy=true;stopping=false;beginSample();
   const operation=operationSerial,current=receiver;
   const active=()=>!quitting&&!stopping&&operation===operationSerial;
   const start=Date.now();let bytes=0,powerSum=0,powerN=0;
   try{
     // Sample rate was set ONCE during connect. Writing demodulator register 0x9f
     // again here is redundant and caused the reported reg=9f20 transfer failure.
     if(configuredRate!==1024000)throw Error("Receiver sample rate no longer configured; release and reconnect");
     if(configuredFrequencyHz!==1575420000){
       await current.setCenterFrequency(1575420000);
       configuredFrequencyHz=1575420000;
     }
     if(configuredGain!==null){
       await current.setGain(null);
       configuredGain=null;
     }
     if(!active())return;
     await current.resetBuffer();
     notify("SAMPLING","Measuring relative raw I/Q level near GNSS L1 for up to 2 s (not GPS acquisition).");
     while(sampling&&active()&&Date.now()-start<2000&&bytes<4*1024*1024){
       const block=await current.readSamples(16384);
       const raw=block?.data;
       const arr=raw instanceof ArrayBuffer?new Uint8Array(raw):ArrayBuffer.isView(raw)?new Uint8Array(raw.buffer,raw.byteOffset,raw.byteLength):null;
       if(!arr||arr.length<2)throw Error("No I/Q sample bytes returned");
       bytes+=arr.length;
       for(let i=0;i+1<arr.length;i+=2){
         const re=(arr[i]-127.5)/127.5,im=(arr[i+1]-127.5)/127.5;
         powerSum+=re*re+im*im;powerN++;
       }
     }
     if(active()){
       if(!powerN)throw Error("No RF samples received");
       const rms=Math.sqrt(powerSum/powerN);
       const db=20*Math.log10(Math.max(1e-9,rms));
       notify("RF SAMPLED",bytes+" actual USB bytes · relative level "+db.toFixed(1)+" dBFS-like at 1575.420 MHz (UNCALIBRATED; NOT GNSS SIGNAL LOCK).");
     }
   }catch(error){
     if(active())notify("SAMPLE ERROR",(error.message||String(error))+
       ". If USB register write failed, check cable/USB power and try Release USB then reconnect. "+
       "No automatic reconfiguration retry will be attempted.");
   }
   finally{sampling=false;busy=false;endSample()}
 }
 async function captureRF(frequencyMHz,sourceId){
   if(quitting||releasePromise)return;
   if(!receiver){notify("RF NOT CONNECTED","Connect RTL-SDR via WebUSB first. No simulated RF readings.");return}
   if(busy||sampling){notify("RF BUSY","Another USB receive operation is in progress.");return}
   if(!Number.isFinite(frequencyMHz)||frequencyMHz<24||frequencyMHz>1766){
     notify("RF INVALID FREQUENCY","Enter a valid RTL-SDR frequency in MHz (24–1766).");return
   }
   busy=true;sampling=true;stopping=false;beginSample();
   const operation=operationSerial,current=receiver;
   const active=()=>!quitting&&!stopping&&operation===operationSerial;
   const gainDb=20,sampleRate=1024000;
   let samples=0,power=0,rfStage="initial checks",captureFailure=null;
   try{
     if(configuredRate!==sampleRate)throw Error("Receiver sample rate not configured; release and reconnect");
     if(configuredGain!==gainDb){
       rfStage="tuner gain configuration (USB control transfer)";
       await current.setGain(gainDb); // fixed gain is essential for level comparisons
       configuredGain=gainDb;
     }
     const targetFrequencyHz=Math.round(frequencyMHz*1e6);
     if(configuredFrequencyHz!==targetFrequencyHz){
       rfStage="tune "+frequencyMHz.toFixed(3)+" MHz (USB control transfer)";
       await current.setCenterFrequency(targetFrequencyHz);
       configuredFrequencyHz=targetFrequencyHz;
     }
     if(!active())return;
     rfStage="reset hardware sample buffer";
     await current.resetBuffer();
     for(let i=0;i<8&&active();i++){
       rfStage="read I/Q sample block "+(i+1)+"/8";
       const block=await current.readSamples(16384);
       const bytes=block?.data;
       if(!(bytes instanceof ArrayBuffer)&&!ArrayBuffer.isView(bytes))throw Error("RTL-SDR did not return I/Q sample block.data");
       const n=bytes.byteLength;
       const db=relativePowerDbFS(bytes);
       power+=Math.pow(10,db/10)*n;samples+=n;
     }
     if(!active()){notify("RF STOPPED","Radio sample was cancelled. No measurement stored.");return}
     if(!active())return;
     if(samples===0)throw Error("No actual radio bytes received");
     const levelDbFS=10*Math.log10(power/samples);
     const record={levelDbFS,frequencyMHz,gainDb,sampleRate,sampleBytes:samples,
       measuredAt:new Date().toISOString(),sourceId:String(sourceId||""),hardwareId:"RTL2832U WebUSB 0bda:2838",
       observation:"REAL HARDWARE I/Q POWER LEVEL · NOT A DISTANCE",
       sourceIdentityVerified:false,decodedSignal:false};
     window.dispatchEvent(new CustomEvent("tihulu:rf-observation",{detail:record}));
     notify("RF IQ CAPTURED",frequencyMHz.toFixed(3)+" MHz · "+samples+" bytes of REAL RTL-SDR I/Q · "+
       levelDbFS.toFixed(2)+" dBFS-like · fixed gain "+gainDb+" dB. Total receiver energy, not an identified stat   }catch(error){
     // Capture the hardware error but DO NOT await release while this operation
     // owns pendingSample: release must wait for genuinely concurrent reads.
     if(active()){
       const detail=String(error?.message||error);
       const transfer=/setRegBuffer|transfer|control|stall|reg=/i.test(detail);
       const explanation=transfer?
         "USB register/control-transfer failure, not a transmitter or radio-range result. "+
         "This browser driver/device session is no longer trusted; release it, then use Recover SDR for ONE reinitialization attempt. "+
         "Check other SDR owners, Linux USB driver, power and browser compatibility.":
         "Hardware sampling failed; no RF measurement was accepted.";
       captureFailure={detail,transfer,explanation,stage:rfStage};
     }
   }finally{
     // Own lease must settle BEFORE an internal release awaits pendingSample.
     sampling=false;busy=false;endSample();
   }
   if(captureFailure&&active()){
     const {detail,transfer,explanation,stage:failedStage}=captureFailure;
     let closeError=null;
     try{
       if(transfer)await release(); // release now sees no self-owned pendingSample
     }catch(error){closeError=String(error?.message||error)}
     // A concurrent real Quit owns the final shutdown; never emit late RF events.
     if(!quitting){
       const releaseDetail=!transfer?"":closeError?
         " · STOP_FAILED_PARTIAL: "+closeError:
         " · Owned receiver release completed; reconnect requires an explicit user action.";
       notify("RF CAPTURE ERROR","Stage: "+failedStage+" · "+detail+" · "+explanation+releaseDetail);
       window.dispatchEvent(new CustomEvent("tihulu:rf-capture-failed",{
         detail:{stage:failedStage,message:detail+releaseDetail,frequencyMHz,
           sourceId:String(sourceId||""),recoverable:transfer&&!closeError,
           releaseFailed:!!closeError}
       }));
     }
   }
 }alse;endSample()}
 }
 async function fmSweep(startMHz=87.5,stopMHz=108,stepMHz=.1){
   if(quitting||releasePromise)return;
   if(!receiver){notify("FM SCAN UNAVAILABLE","Connect the real RTL-SDR first. No synthetic spectrum readings.");window.dispatchEvent(new CustomEvent("tihulu:rf-fm-sweep-failed",{detail:{message:"RTL-SDR not connected"}}));return}
   if(busy||sampling){notify("FM SCAN BUSY","Another USB operation is running.");return}
   if(![startMHz,stopMHz,stepMHz].every(Number.isFinite)||startMHz<87.5||stopMHz>108||stepMHz<.1||stepMHz>.5){
     notify("FM SCAN INVALID","Scan accepts 87.5–108 MHz and 0.1–0.5 MHz spacing.");return
   }
   if(configuredRate!==1024000){notify("FM SCAN BLOCKED","Sample rate not initialized; release and reconnect first.");return}
   busy=true;sampling=true;stopping=false;sweepCancel=false;beginSample();
   const operation=operationSerial,current=receiver;
   const active=()=>!quitting&&!stopping&&operation===operationSerial;
   const oldHz=configuredFrequencyHz,oldGain=configuredGain;
   const readings=[],total=Math.min(220,Math.floor((stopMHz-startMHz)/stepMHz+1.001));
   let scanStage="FM initialization",hardwareControlFailed=false,sweepFailure=null;
   try{
     if(configuredGain!==20){scanStage="set fixed tuner gain";await current.setGain(20);configuredGain=20}
     for(let i=0;i<total&&active()&&!sweepCancel;i++){
       const mhz=Math.round((startMHz+i*stepMHz)*1000)/1000;
       const hz=Math.round(mhz*1000000);
       if(configuredFrequencyHz!==hz){scanStage="tune "+mhz.toFixed(1)+" MHz";await current.setCenterFrequency(hz);configuredFrequencyHz=hz}
       scanStage="flush samples at "+mhz.toFixed(1)+" MHz";
       await current.resetBuffer(); // Flush old frequency's samples
       if(stopping||sweepCancel)break;
       scanStage="read I/Q at "+mhz.toFixed(1)+" MHz";
       const sample=await current.readSamples(8192);
       const raw=sample?.data;
       if(!(raw instanceof ArrayBuffer)&&!ArrayBuffer.isView(raw))throw Error("No actual SampleBlock.data from RTL-SDR");
       const levelDbFS=relativePowerDbFS(raw);
       readings.push({frequencyMHz:mhz,levelDbFS,sampleBytes:raw.byteLength,
         measuredAt:new Date().toISOString(),hardware:"RTL2832U WebUSB",signalDecoded:false,
         statement:"ENERGY ONLY · NOT STATION ID OR DISTANCE"});
       if(active()&&(i%4===0||i===total-1))window.dispatchEvent(new CustomEvent("tihulu:rf-fm-sweep-progress",{
         detail:{completed:readings.length,total,frequencyMHz:mhz}
       }));
     }
     if(active())window.dispatchEvent(new CustomEvent("tihulu:rf-fm-sweep-results",{
       detail:{readings,stopped:sweepCancel,hardware:"RTL2832U"}}
     ));
     if(active())notify(sweepCancel?"FM SWEEP STOPPED":"FM SWEEP COMPLETE",readings.length+
       " REAL RTL-SDR frequency-level samples from "+startMHz.toFixed(3)+"–"+stopMHz.toFixed(3)+" MHz. No RDS station identification, GPS, distance or calibr   }catch(error){
     if(active()){
       const message=String(error?.message||error);
       hardwareControlFailed=/setRegBuffer|control|transfer|reg=/i.test(message);
       sweepFailure={message,stage:scanStage,completed:readings.length};
     }
   }finally{
     if(active()&&!hardwareControlFailed&&receiver===current){
       try{
         if(configuredFrequencyHz!==oldHz&&oldHz>0){
           await current.setCenterFrequency(oldHz);configuredFrequencyHz=oldHz;
         }
         if(configuredGain!==oldGain){await current.setGain(oldGain);configuredGain=oldGain}
       }catch(e){notify("FM SWEEP RESTORE WARNING","Previous tuner setting could not be restored: "+String(e?.message||e))}
     }
     // Settle the FM operation's own lease; an external Quit still has the
     // original bounded wait while an actually unfinished I/Q read is pending.
     sampling=false;busy=false;endSample();
   }
   if(sweepFailure&&active()){
     const {message,stage:failedStage,completed}=sweepFailure;
     let closeError=null;
     try{
       if(hardwareControlFailed)await release(); // never self-wait on FM lease
     }catch(error){closeError=String(error?.message||error)}
     if(!quitting){
       const releaseDetail=!hardwareControlFailed?"":closeError?
         " STOP_FAILED_PARTIAL: "+closeError:
         " Receiver released; reconnect using Recover SDR after checking USB ownership, power and driver.";
       const diagnostic="Step: "+failedStage+" · "+message+" · no invented RF results."+releaseDetail;
       notify("FM SWEEP ERROR",diagnostic);
       window.dispatchEvent(new CustomEvent("tihulu:rf-fm-sweep-failed",{
         detail:{message:diagnostic,stage:failedStage,completed,hardwareControlFailed,
           releaseFailed:!!closeError}
       }));
     }
   }
 }Sample();
   }
 }

 async function recover(){
   if(quitting||releasePromise)return;
   if(sampling||busy){
     notify("RECOVERY BLOCKED","An RF operation is still running. Stop it or use Hard Stop before reconnecting.");
     return;
   }
   if(!navigator.usb?.getDevices||!window.isSecureContext){
     notify("RECOVERY UNAVAILABLE","Use a Chromium-based HTTPS browser with WebUSB.");
     return;
   }
   // Explicit user click: free only this app's handle, then reconnect an
   // already-authorized stick. No driver unload, external service stop or USB reset.
   notify("USB RECOVERY","Releasing this app's SDR control handle before one explicit reconnection. No OS services touched.");
   await release();
   await new Promise(resolve=>setTimeout(resolve,200));
   if(quitting)return;
   let devices=[];
   try{devices=(await navigator.usb.getDevices()).filter(d=>d.vendorId===0x0bda&&d.productId===0x2838)}
   catch(e){notify("RECOVERY BLOCKED","Cannot enumerate permitted RTL-SDR: "+String(e.message||e));return}
   if(devices.length!==1){
     notify("RECOVERY NEEDS DEVICE",devices.length===0?
       "No permitted RTL-SDR. Use Connect RTL-SDR and the browser picker.":
       "Multiple RTL-SDR permissions exist. Choose your intended device in Hardware.");
     return;
   }
   if(quitting)return;
   await connect(devices[0]); // One attempt, no retry loop or invented RF samples.
 }
 async function selfTest(){
   if(quitting||releasePromise)return;
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
 window.addEventListener("tihulu:rf-fm-sweep-request",event=>{void fmSweep(event.detail?.startMHz,event.detail?.stopMHz,event.detail?.stepMHz)});
 window.addEventListener("tihulu:rf-fm-sweep-stop",()=>{sweepCancel=true});
 window.addEventListener("tihulu:hardware-connect-rtl",e=>{void connect(e.detail?.device||null)});
 $("usb-select")?.addEventListener("click",()=>{void connect()});
 $("usb-selftest")?.addEventListener("click",()=>{void selfTest()});
 $("hardware-recover")?.addEventListener("click",()=>{void recover()});
 $("quick-radio-recover")?.addEventListener("click",()=>{void recover()});
 $("live-usb-check")?.addEventListener("click",()=>{void selfTest()});
 $("live-release")?.addEventListener("click",()=>{void release()});
 $("live-scan")?.addEventListener("click",()=>{void scan()});
 $("hard-stop")?.addEventListener("click",()=>{void release()});
 window.addEventListener("pagehide",()=>{void release({permanent:true})});
 document.addEventListener("visibilitychange",()=>{if(document.hidden&&receiver)void release()});
 return {connect,scan,release,selfTest,captureRF,fmSweep,recover,quit:()=>release({permanent:true})};
}
