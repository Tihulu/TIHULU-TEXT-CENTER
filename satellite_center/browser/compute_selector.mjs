/* Shared user-facing heterogeneous compute settings.
 * Honest capability checks and explicit stage-by-stage CPU/GPU/NPU reporting.
 * Never store hardware profiles in URLs or pretend a missing NPU runs DSP.
 */
import {probeBrowserCompute,chooseComputePlan} from "./compute_backends.mjs";

export function initComputeSelector(prefix,{capabilitiesProvider=null}={}){
 const el=id=>document.getElementById(prefix+"-compute-"+id);
 const mode=el("mode"),status=el("status");
 const targets=Object.fromEntries(["cpu","gpu","npu"].map(k=>[k,el(k)]));
 if(!mode||!status||Object.values(targets).some(x=>!x))
   throw Error("Compute selector markup missing: "+prefix);
 let caps={cpu:{available:true,name:"CPU"},
           gpu:{available:false,reason:"Probing real GPU adapter…"},
           npu:{available:false,reason:"No compatible SSTV NPU model/kernel"}};
 let loaded=false;
 const describe=()=>{
   for(const name of ["cpu","gpu","npu"]){
     targets[name].disabled=mode.value!=="custom"||!caps[name]?.available;
     if(!caps[name]?.available)targets[name].checked=false;
     targets[name].title=caps[name]?.available?caps[name].name||name:caps[name]?.reason||"Unsupported";
   }
   const auto=chooseComputePlan({mode:"auto",capabilities:caps,seconds:120});
   const chosen=mode.value==="auto"?
     "Auto optimized for this device (long SSTV audio: "+auto.selectedTargets.join(" + ").toUpperCase()+")":
     "Custom: "+Object.entries(targets).filter(([k,v])=>v.checked).map(([k])=>k.toUpperCase()).join(" + ");
   status.textContent=chosen+". "+(loaded?"":"Checking hardware… ")+
     "CPU: "+(caps.cpu?.name||"available")+
     " · GPU: "+(caps.gpu?.available?"real acceleration available":caps.gpu?.reason||"unavailable")+
     " · NPU: "+(caps.npu?.available?"supported":caps.npu?.reason||"no supported SSTV kernel")+
     ". GPU targets SSTV tone-tracing only; FFT, synchronization, pixels and archive may remain on CPU.";
 };
 const getSelection=()=>{
   const list=Object.entries(targets).filter(([k,v])=>v.checked).map(([k])=>k);
   if(mode.value==="custom"&&!list.length)
     throw Error("Choose at least one available CPU or GPU backend");
   return {mode:mode.value,targets:mode.value==="custom"?list:[]};
 };
 mode.addEventListener("change",describe);
 for(const key of Object.keys(targets))targets[key].addEventListener("change",describe);
 describe();
 const ready=(async()=>{
   try{
     const found=capabilitiesProvider?await capabilitiesProvider():await probeBrowserCompute();
     if(found?.cpu?.available){
       caps=found;loaded=true;
     }else throw Error("CPU capability response missing");
   }catch(error){
     caps.gpu={available:false,reason:"Hardware probe failed: "+String(error?.message||error).slice(0,130)};
     loaded=true;
   }
   describe();
   return caps;
 })();
 return {
   ready,
   getSelection,
   async plan(seconds=0){
     await ready;
     return chooseComputePlan({...getSelection(),capabilities:caps,seconds});
   },
   getCapabilities(){return caps;}
 };
}
