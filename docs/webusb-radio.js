"use strict";
// Browser-only, receive-only RTL2832U experiment. No local services or OS process controls.
// @jtarrio/webrtlsdr is pinned; module download requires Internet on first load.
const usbEl=id=>document.getElementById(id);
const setUsb=(message)=>{usbEl("usb-status").textContent=message};
const setCapture=(message)=>{usbEl("usb-capture-status").textContent=message};
const hasUsb=!!(window.isSecureContext&&navigator.usb);
let Provider=null,receiver=null,capture=null,stopRequested=false;
let context=null,worklet=null,gain=null,destination=null,recorder=null,recordingChunks=[];
const USB_RATE=1024000,MAX_RAW=64*1024*1024;
function refreshUsb(){
  usbEl("usb-connect").disabled=!hasUsb||!Provider||!!receiver||!!capture;
  usbEl("usb-start").disabled=!receiver||!!capture;
  usbEl("usb-stop").disabled=!receiver&&!capture;
  usbEl("usb-connect").textContent=receiver?"USB OWNED BY THIS TAB":"GRANT USB PERMISSION";
}
if(!hasUsb){
  setUsb("Direct USB unavailable: use desktop Chrome/Edge/Brave over HTTPS. Firefox and Safari do not support WebUSB. OS driver/USB permissions can still block access.");
  refreshUsb();
}else{
  setUsb("Preparing a pinned browser SDR driver. No device opened and no RF scan started.");
  import("https://esm.sh/@jtarrio/webrtlsdr@3.0.7/rtlsdr.js?bundle").then(m=>{
    if(typeof m.RTL2832U_Provider!=="function")throw Error("Unexpected receiver driver API");
    Provider=m.RTL2832U_Provider;
    setUsb("Ready. Plug in the Nooelec, release it in any other SDR app, then grant browser permission.");
    refreshUsb();
  }).catch(e=>setUsb("WebUSB driver could not load: "+e.message+". Check network access; no hardware was opened."));
}
async function releaseUsb(){
  const owned=receiver;receiver=null;
  if(owned){
    try{await owned.close();setUsb("Browser-owned USB session closed. No external readsb/welle-cli was stopped.");}
    catch(e){setUsb("USB release requested, but the driver reported: "+e.message);}
  }
  refreshUsb();
}
usbEl("usb-connect").addEventListener("click",async()=>{
  if(!Provider||capture||receiver)return;
  try{
    const provider=new Provider();
    // get() prompts for USB access; this is exclusively a real user click.
    receiver=await provider.get();
    setUsb("USB interface opened by this tab; signal and FM playback are not yet verified.");
  }catch(e){setUsb("USB access refused or busy: "+e.message+". Check kernel/WinUSB permissions or close the other receiver manually.");await releaseUsb();}
  refreshUsb();
});
function makeWorkletSource(){
  return "class TihuluMonoQueue extends AudioWorkletProcessor {"+
    "constructor(){super();this.blocks=[];this.offset=0;this.total=0;this.port.onmessage=e=>{"+
    "if(e.data&&e.data.kind==='samples'){this.blocks.push(e.data.samples);this.total+=e.data.samples.length;"+
    "while(this.total>48000&&this.blocks.length>1){let old=this.blocks.shift();this.total-=old.length;this.offset=0;}}};}"+
    "process(inputs,outputs){let out=outputs[0][0];for(let i=0;i<out.length;i++){"+
    "while(this.blocks.length&&this.offset>=this.blocks[0].length){this.total-=this.blocks[0].length;this.blocks.shift();this.offset=0;}"+
    "out[i]=this.blocks.length?this.blocks[0][this.offset++]:0;}return true;}}"+
    "registerProcessor('tihulu-mono-queue',TihuluMonoQueue);";
}
async function initializeAudio(){
  context=new AudioContext({latencyHint:"interactive"});
  if(!context.audioWorklet)throw Error("AudioWorklet is not available in this browser");
  const url=URL.createObjectURL(new Blob([makeWorkletSource()],{type:"text/javascript"}));
  try{await context.audioWorklet.addModule(url);}finally{URL.revokeObjectURL(url);}
  worklet=new AudioWorkletNode(context,"tihulu-mono-queue");
  gain=context.createGain();gain.gain.value=Number(usbEl("usb-volume").value)/100;
  destination=context.createMediaStreamDestination();
  worklet.connect(gain);gain.connect(context.destination);gain.connect(destination);
  await context.resume();
  if(usbEl("usb-record").checked){
    if(typeof MediaRecorder!=="function")throw Error("This browser cannot record the audio stream");
    const type=["audio/webm;codecs=opus","audio/ogg;codecs=opus"].find(x=>MediaRecorder.isTypeSupported(x));
    recordingChunks=[];
    recorder=type?new MediaRecorder(destination.stream,{mimeType:type}):new MediaRecorder(destination.stream);
    recorder.addEventListener("dataavailable",e=>{if(e.data?.size)recordingChunks.push(e.data)});
    recorder.start(1000);
  }
}
usbEl("usb-volume").addEventListener("input",()=>{
  if(gain)gain.gain.value=Number(usbEl("usb-volume").value)/100;
});
async function finalizeAudio(){
  const current=recorder;recorder=null;
  if(current&&current.state!=="inactive"){
    await new Promise(resolve=>{current.addEventListener("stop",resolve,{once:true});current.stop()});
    if(recordingChunks.length){
      const blob=new Blob(recordingChunks,{type:current.mimeType||"audio/webm"});
      const ext=(current.mimeType||"").includes("ogg")?"ogg":"webm";
      downloadBlob(blob,"TIHULU-FM-"+new Date().toISOString().replaceAll(":","-")+"."+ext);
      recordingChunks=[];
    }
  }
  if(context){try{await context.close()}catch(_){}}
  context=null;worklet=null;gain=null;destination=null;
}
function downloadBlob(blob,name){
  const url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download=name;a.hidden=true;document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),45000);
}
function fmDemodulator(rate){
  let prevRe=0,prevIm=0,prevValid=false,mono=0,emphasis=0;
  let phase=0,sum=0,count=0;
  let dcRe=0,dcIm=0,dcAudio=0;
  const outputRate=context.sampleRate,step=rate/outputRate;
  const audioAlpha=1/(1+outputRate*50e-6);
  return bytes=>{
    const pcm=[];
    for(let i=0;i+1<bytes.length;i+=2){
      const r=(bytes[i]-127.5)/128,im=(bytes[i+1]-127.5)/128;
      dcRe+=0.00015*(r-dcRe);dcIm+=0.00015*(im-dcIm);
      const re=r-dcRe,iq=im-dcIm;
      if(prevValid){
        const demod=Math.atan2(iq*prevRe-re*prevIm,re*prevRe+iq*prevIm);
        mono+=0.11*(demod-mono);
        sum+=mono;count++;
        phase+=1;
        if(phase>=step){
          phase-=step;
          const input=(count?sum/count:0)*2.3;
          sum=0;count=0;
          emphasis+=audioAlpha*(input-emphasis);
          dcAudio+=0.002*(emphasis-dcAudio);
          pcm.push(Math.max(-1,Math.min(1,emphasis-dcAudio)));
        }
      }
      prevRe=re;prevIm=iq;prevValid=true;
    }
    return new Float32Array(pcm);
  };
}
function bytesOf(buffer){
  if(buffer instanceof ArrayBuffer)return new Uint8Array(buffer);
  if(ArrayBuffer.isView(buffer))return new Uint8Array(buffer.buffer,buffer.byteOffset,buffer.byteLength);
  throw Error("RTL-SDR driver did not return USB sample bytes");
}
async function receive(){
  if(!receiver||capture)return;
  const mode=usbEl("usb-mode").value;
  const mhz=Number(usbEl("usb-frequency").value);
  const hz=Math.round(mhz*1e6);
  if(!Number.isFinite(mhz)||mhz<24||mhz>1766||(mode==="fm"&&(mhz<87.5||mhz>108))){
    setCapture(mode==="fm"?"FM frequency must be 87.5–108 MHz.":"Frequency must be 24–1766 MHz.");return;
  }
  stopRequested=false;
  capture=(async()=>{
    let samples=0,rawSize=0,chunks=[],decode=null;
    try{
      await receiver.setSampleRate(USB_RATE);
      await receiver.setCenterFrequency(hz);
      await receiver.setGain(null);
      await receiver.resetBuffer();
      if(mode==="fm"){await initializeAudio();decode=fmDemodulator(USB_RATE);}
      setCapture((mode==="fm"?"EXPERIMENTAL live FM mono":"Raw I/Q")+
        " · "+mhz.toFixed(3)+" MHz · real USB data only");
      const deadline=Date.now()+(mode==="iq"?Number(usbEl("usb-duration").value)*1000:24*3600000);
      while(!stopRequested&&Date.now()<deadline){
        const raw=bytesOf(await receiver.readSamples(32768));
        if(!raw.length)throw Error("No bytes received");
        samples+=raw.length;
        if(mode==="fm"){
          const audio=decode(raw);
          if(audio.length)worklet.port.postMessage({kind:"samples",samples:audio},[audio.buffer]);
        }else{
          if(rawSize+raw.length>MAX_RAW){setCapture("64 MiB raw capture limit reached.");break;}
          chunks.push(new Uint8Array(raw));rawSize+=raw.length;
        }
        if(samples%(32768*32)<32768)setCapture(
          "Received "+(samples/1048576).toFixed(2)+" MiB of real USB I/Q at "+mhz.toFixed(3)+
          " MHz · "+(mode==="fm"?"experimental decoded mono output":"not decoded into a named station or aircraft"));
      }
      if(mode==="iq"&&chunks.length){
        downloadBlob(new Blob(chunks,{type:"application/octet-stream"}),
          "TIHULU-"+hz+"-"+USB_RATE+"-"+new Date().toISOString().replaceAll(":","-")+".cu8");
        setCapture("Saved "+(rawSize/1048576).toFixed(2)+" MiB real CU8 I/Q locally. Not a decoded broadcast.");
      }else if(mode==="fm")setCapture("FM stream ended. Any requested audio recording is saved on Stop.");
    }catch(e){setCapture("Receiver stopped: "+e.message+". No signal or station is assumed.");}
    finally{
      try{await finalizeAudio()}catch(e){setCapture("Audio finalization warning: "+e.message);}
      await releaseUsb();
    }
  })();
  refreshUsb();
  try{await capture;}finally{capture=null;refreshUsb();}
}
usbEl("usb-start").addEventListener("click",()=>{void receive()});
async function stop(hard=false){
  stopRequested=true;
  if(hard && receiver){
    // Try to break an in-flight WebUSB read immediately, rather than
    // waiting for an unresponsive readSamples() promise.
    const owned=receiver;
    try{
      await owned.close();
      receiver=null;
    }catch(error){
      setUsb("HARD STOP could not close USB: "+error.message+"; release unconfirmed.");
      throw error;
    }
    refreshUsb();
  }
  if(capture){
    if(hard){
      let settled=false;
      await Promise.race([
        capture.then(()=>{settled=true;}),
        new Promise(resolve=>setTimeout(resolve,1800))
      ]);
      if(!settled)throw Error("Driver has not confirmed capture shutdown; USB release unconfirmed.");
    }else{
      try{await capture;}catch(_){}
    }
  }else if(!hard){
    await releaseUsb();
  }
}
usbEl("usb-stop").addEventListener("click",()=>{void stop()});
usbEl("pages-hard-stop")?.addEventListener("click",async()=>{
  // This can only release THIS TAB's WebUSB claim, never readsb or another origin.
  const button=usbEl("pages-hard-stop");
  button.disabled=true;
  try{
    await stop(true);
    setUsb("HARD STOP requested for this Pages tab's own WebUSB receiver; other processes and tabs were not touched.");
    setCapture("No browser-owned RF capture requested. If a driver failed to close, verify OS USB status.");
  }catch(error){setUsb("HARD STOP could not confirm release: "+error.message);}
  finally{button.disabled=false;}
});
navigator.usb?.addEventListener("disconnect",()=>{stopRequested=true;setUsb("USB disconnected; browser capture ending.");});
window.addEventListener("pagehide",()=>{
  stopRequested=true;
  if(receiver)void receiver.close().catch(()=>{});
});
document.addEventListener("visibilitychange",()=>{
  if(document.hidden&&receiver){stopRequested=true;void stop();}
});
refreshUsb();
