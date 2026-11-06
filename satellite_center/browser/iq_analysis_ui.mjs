/* UI for browser-only, read-only, local CU8 analysis.
 * Does not upload RF samples or claim demodulation of satellite traffic.
 */
import { analyzeCu8Blob,parseCu8Filename } from "./iq_analysis.mjs?v=20261106-cuiq-v13";
import { analyzeFullCu8Blob,demodulateCu8Preview } from "./iq_intelligence.mjs?v=20261106-signal-v1";
import {discoverCu8Contents,discoveryReportJson} from "./signal_discovery.mjs?v=20261106-discovery-v1";
import {createResultsZip} from "./results_zip.mjs";
import {initComputeSelector} from "./compute_selector.mjs";
const $=id=>document.getElementById(id);
const clamp=(n,low,high)=>Math.max(low,Math.min(high,n));
const fmt=n=>Number.isFinite(n)?Number(n).toLocaleString(undefined,{maximumFractionDigits:2}):"N/A";
function downloadJson(report,name){
 const blob=new Blob([JSON.stringify({
  app:"TIHULU Satellite Center",analysis:"uncalibrated CU8 I/Q spectral sample analysis",
  sourceFile:name,createdAt:new Date().toISOString(),report
 },null,2)],{type:"application/json"});
 const url=URL.createObjectURL(blob),a=document.createElement("a");
 a.href=url;a.download="TIHULU-CU8-analysis-"+new Date().toISOString().replace(/[:.]/g,"-")+".json";
 document.body.append(a);a.click();a.remove();
 setTimeout(()=>URL.revokeObjectURL(url),60000);
}
function prepare(ctx,canvas,title){
 const w=canvas.width,h=canvas.height;
 ctx.fillStyle="#081727";ctx.fillRect(0,0,w,h);
 ctx.strokeStyle="#294766";ctx.lineWidth=1;
 for(let i=0;i<=4;i++){
   let y=15+i*(h-45)/4;ctx.beginPath();ctx.moveTo(52,y);ctx.lineTo(w-16,y);ctx.stroke();
 }
 ctx.fillStyle="#b0c9e3";ctx.font="13px system-ui";
 ctx.textAlign="left";ctx.fillText(title,12,h-8);
 return {w,h,x0:56,x1:w-18,y0:16,y1:h-30};
}
function graphLine(canvas,points,{caption,yLabel,xLabel,min=null,max=null,color="#5fc9ff"}={}){
 const ctx=canvas.getContext("2d");if(!ctx)return;
 const r=prepare(ctx,canvas,caption||"");
 const values=points.filter(Number.isFinite);
 if(!values.length)return;
 const lo=min??Math.floor((Math.min(...values)-5)/5)*5;
 const hi=max??Math.ceil((Math.max(...values)+5)/5)*5;
 const span=Math.max(0.001,hi-lo),width=Math.max(1,points.length-1);
 ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();
 points.forEach((val,i)=>{
   if(!Number.isFinite(val))return;
   const x=r.x0+(i/width)*(r.x1-r.x0);
   const y=r.y1-clamp((val-lo)/span,0,1)*(r.y1-r.y0);
   if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
 });
 ctx.stroke();
 ctx.fillStyle="#d1e6fa";ctx.font="12px system-ui";ctx.textAlign="right";
 for(let i=0;i<=4;i++)ctx.fillText((hi-i*span/4).toFixed(0),r.x0-10,r.y0+i*(r.y1-r.y0)+4);
 ctx.textAlign="left";ctx.fillText(yLabel||"relative dB",r.x0+5,r.y0+14);
 ctx.textAlign="right";ctx.fillText(xLabel||"",r.x1,r.h-8);
}
function drawSpectrum(report){
 const canvas=$("iq-spectrum"),ctx=canvas.getContext("2d");
 if(!ctx)return;
 const v=report.spectrumDb;
 const label=report.centerFrequencyHz===null?"baseband offset (kHz)":"frequency (MHz)";
 graphLine(canvas,v,{caption:"Complex FFT: 2,048 bins · window-averaged",
   xLabel:label,yLabel:"relative dB"});
 const p=report.peakOffsetHz;
 if(p==null)return;
 const r={x0:56,x1:canvas.width-18,y0:16,y1:canvas.height-30};
 const index=Math.round(p/(report.sampleRate/report.fftSize)+report.fftSize/2);
 const x=r.x0+index/(report.fftSize-1)*(r.x1-r.x0);
 ctx.strokeStyle="#ffce85";ctx.lineWidth=1.4;ctx.setLineDash([5,4]);
 ctx.beginPath();ctx.moveTo(x,r.y0);ctx.lineTo(x,r.y1);ctx.stroke();ctx.setLineDash([]);
 ctx.fillStyle="#f5d99b";ctx.font="13px system-ui";
 const title=report.peakFrequencyHz!=null?(report.peakFrequencyHz/1e6).toFixed(5)+" MHz":
   (report.peakOffsetHz/1000).toFixed(2)+" kHz offset";
 ctx.textAlign=x>canvas.width*.72?"right":"left";
 ctx.fillText("Highest non-DC spectral bin: "+title,
   clamp(x,205,canvas.width-20),r.y0+25);
 ctx.fillStyle="#bed2e6";ctx.textAlign="left";
 for(const f of [-.5,-.25,0,.25,.5]){
   const xpos=r.x0+(f+.5)*(r.x1-r.x0);
   const freq=report.centerFrequencyHz===null?(f*report.sampleRate/1e3).toFixed(0)+"k":
     ((report.centerFrequencyHz+f*report.sampleRate)/1e6).toFixed(3);
   ctx.fillText(freq,xpos-24,r.y1+17);
 }
}
function drawWaterfall(report){
 const canvas=$("iq-waterfall"),ctx=canvas.getContext("2d");
 if(!ctx)return;
 const {w,h,x0,x1,y0,y1}=prepare(ctx,canvas,report.analysisMode?"Top: start · bottom: end (continuous FFT windows binned in time)":"Top: start · bottom: end (stratified windows; not continuous playback)");
 const rows=report.waterfallDb;let lo=Infinity,hi=-Infinity;
 for(const row of rows)for(const v of row){lo=Math.min(lo,v);hi=Math.max(hi,v);}
 if(!Number.isFinite(lo)||!Number.isFinite(hi))return;
 const colWidth=(x1-x0)/256,rowHeight=(y1-y0)/rows.length;
 const span=Math.max(6,hi-lo);
 rows.forEach((line,rowIndex)=>line.forEach((value,column)=>{
   const t=clamp((value-lo)/span,0,1);
   const hue=230-205*t,light=22+48*t;
   ctx.fillStyle="hsl("+hue.toFixed(0)+",90%,"+light.toFixed(0)+"%)";
   ctx.fillRect(x0+column*colWidth,y0+rowIndex*rowHeight,
     colWidth+0.7,rowHeight+0.7);
 }));
 ctx.fillStyle="#e2ecf7";ctx.font="12px system-ui";ctx.textAlign="left";
 ctx.fillText("Lower",x0+5,y0+14);ctx.textAlign="right";
 ctx.fillText("Higher spectral energy",x1-5,y0+14);
}
function drawPower(report){
 graphLine($("iq-power-time"),report.powerHistoryDb,{
  caption:report.analysisMode?"Full-file time bins (assumes gap-free IQ samples)":"Sampled windows distributed over the file, not gap-free timestamps",
  yLabel:"uncalibrated digital level",xLabel:"start → end",
  color:"#65ead3"});
}
function showMetric(label,value){
 const card=document.createElement("div");card.className="iq-metric";
 const title=document.createElement("span");title.textContent=label;
 const strong=document.createElement("strong");strong.textContent=value;
 card.append(title,strong);return card;
}
function renderReport(report,name){
 const parent=$("iq-analysis-summary");parent.replaceChildren();
 const metrics=[
  ["Source",name],["Bytes in file",fmt(report.totalBytes)],
  ["Coverage",report.coveragePercent==null?"Stratified quick sampling":fmt(report.coveragePercent)+"% of complete FFT windows"],
  ["Candidates",report.signalCandidates?.length??"Not classified in quick mode"],
  ["Estimated length",fmt(report.estimatedSeconds)+" s"],
  ["Sampled",fmt(report.sampledBytes)+" bytes / "+report.windows+" windows"],
  ["Sample rate",fmt(report.sampleRate/1e6)+" MS/s"],
  ["FFT resolution",fmt(report.frequencyResolutionHz)+" Hz"],
  ["Average digital level",fmt(report.averageRelativeLevelDb)+" dBFS-like"],
  ["Level range",fmt(report.minRelativeLevelDb)+" … "+fmt(report.maxRelativeLevelDb)+" dBFS-like"],
  ["Peak vs median bin",fmt(report.peakVsMedianDb)+" dB (not calibrated SNR)"],
  ["Strongest peak offset",fmt(report.peakOffsetHz/1000)+" kHz"],
  ["Strongest peak frequency",report.peakFrequencyHz==null?"unknown (enter center MHz)":fmt(report.peakFrequencyHz/1e6)+" MHz"],
  ["Clipped complex pairs (sampled)",fmt(report.clippedComplexPairsPercent)+" %"],
  ["Mean I/Q DC",fmt(report.meanDcOffset.i)+" / "+fmt(report.meanDcOffset.q)]
 ];
 for(const [label,value] of metrics)parent.append(showMetric(label,String(value)));
 drawSpectrum(report);drawWaterfall(report);drawPower(report);
 const candidates=$("iq-candidates");candidates.replaceChildren();
 if(report.signalCandidates){
   if(!report.signalCandidates.length){
     const p=document.createElement("p");p.textContent="No strong spectral energy groups detected at the current threshold. This does not establish absence of RF signals.";candidates.append(p);
   }
   report.signalCandidates.forEach((candidate,index)=>{
     const b=document.createElement("button");b.type="button";b.className="secondary";
     b.textContent=(index+1)+". "+(candidate.peakFrequencyHz==null?
       fmt(candidate.peakOffsetHz/1000)+" kHz offset":
       fmt(candidate.peakFrequencyHz/1e6)+" MHz")+" · "+fmt(candidate.widthHz/1000)+
       " kHz span · +"+fmt(candidate.prominenceDb)+" dB vs median";
     b.title="Unclassified RF energy. Select for experimental AM/NFM audio preview; NOT satellite identification.";
     b.addEventListener("click",()=>{
       $("iq-audio-offset").value=(candidate.peakOffsetHz/1000).toFixed(3);
       $("iq-audio-preview").focus();
     });candidates.append(b);
   });
 }else{
   const p=document.createElement("p");p.textContent="Run Analyze full file to detect candidate spectral regions across the entire recording.";candidates.append(p);
 }
}
export function initIqAnalysisUI({log=()=>{}}={}){
 const computeSelector=initComputeSelector("iq");
 let lastBlob=null,lastName=null,lastMetadata=null,activeRun=0;
 let lastReport=null,lastReportName=null,lastAnalyzedBlob=null,inProgress=false,activeController=null,previewUrl=null;
 let lastDiscovery=null,discoveryObjectUrls=[];
 function reportStatus(message){$("iq-analysis-status").textContent=String(message);}
 function setControls(){
   $("iq-analyze-last").disabled=!lastBlob||inProgress;
   $("iq-analyze-file").disabled=inProgress;
   $("iq-export-json").disabled=!lastReport||inProgress;
   $("iq-analyze-full").disabled=inProgress;
   $("iq-stop-analysis").disabled=!inProgress;
   $("iq-audio-preview").disabled=!lastAnalyzedBlob||inProgress;
   $("iq-export-metadata").disabled=!lastReport||inProgress;
   $("iq-auto-discover").disabled=inProgress;
   $("iq-discovery-export").disabled=!lastDiscovery||inProgress;
   $("iq-discovery-zip").disabled=(!lastReport&&!lastDiscovery)||inProgress;
 }
 function updateMetadata(meta){
   if(!meta)return;
   $("iq-center").value=(meta.centerHz/1e6).toFixed(5);
   const option=Array.from($("iq-rate").options).find(o=>Number(o.value)===meta.sampleRate);
   if(option)$("iq-rate").value=String(meta.sampleRate);
 }
 async function analyze(blob,name,metadata=null,full=false){
   if(inProgress){
     reportStatus("Analysis is already running. Finish it before starting another.");
     return;
   }
   if(!blob){reportStatus("Choose a valid CU8 recording first.");return;}
   const rate=Number($("iq-rate").value);
   const MHz=$("iq-center").value.trim();
   const centerHz=MHz===""?null:Number(MHz)*1e6;
   if(MHz!==""&&(!Number.isFinite(centerHz)||centerHz<24000000||centerHz>1750000000)){
     reportStatus("Enter a valid 24–1750 MHz center frequency. CU8 files do not contain that metadata.");return;
   }
   inProgress=true;lastReport=null;lastReportName=null;activeController=new AbortController();setControls();
   try{
     await computeSelector.ready;
     await computeSelector.plan(blob.size/(2*rate));
     reportStatus((full?"Processing all complete I/Q FFT windows of ":"Reading scattered I/Q windows from ")+name+
       " locally… FFT runs on CPU; selectable WebGPU accelerates the Robot36 audio-trace step when decoding. No upload.");
     const result=full
       ?await analyzeFullCu8Blob(blob,{sampleRate:rate,centerHz,signal:activeController.signal,
         onProgress:(n,total)=>reportStatus("Full file scan · "+n.toLocaleString()+" / "+
           total.toLocaleString()+" FFT windows · "+(100*n/total).toFixed(1)+"%")})
       :await analyzeCu8Blob(blob,{sampleRate:rate,centerHz,
         maxWindows:32,onProgress:(n,total)=>reportStatus(
           "Quick CU8 sample · "+n+"/"+total+" windows read. No upload.")});
     lastReport=result;lastReportName=name;lastAnalyzedBlob=blob;
     renderReport(result,name);
     $("iq-audio-offset").value=(result.peakOffsetHz/1000).toFixed(3);
     reportStatus((full?"Full-file":"Quick-sampled")+" analysis complete · "+result.windows+
       " FFT windows ("+fmt(result.sampledBytes)+" bytes) · peak "+
       fmt(result.peakOffsetHz/1000)+" kHz offset · "+
       fmt(result.peakVsMedianDb)+" dB above median FFT bin.\n"+result.warning);
     log("In-browser CU8 analysis complete ("+name+"). No RF samples uploaded.");
   }catch(error){
     reportStatus("CU8 analysis failed: "+String(error?.message||error));
     log("CU8 analysis error: "+String(error?.message||error));
   }finally{
     inProgress=false;activeController=null;setControls();
   }
 }
 function onFile(){
   const file=$("iq-file").files?.[0];
   if(!file)return;
   const inferred=parseCu8Filename(file.name);
   if(inferred)updateMetadata(inferred);
   else $("iq-center").value=""; // Unknown absolute center: show relative frequency, never invent MHz.
   $("iq-last-info").textContent="Local file selected: "+file.name+" ("+fmt(file.size)+
     " bytes). "+(inferred?"Center/rate inferred from TIHULU filename; confirm before analysis.":
       "CU8 has no embedded frequency/rate: enter the correct capture metadata.");
   reportStatus("File selected locally. Choose Quick analysis or Analyze full file. Nothing is uploaded.");
 }
 $("iq-file").addEventListener("change",onFile);
 $("iq-analyze-file").addEventListener("click",()=>{
   const file=$("iq-file").files?.[0];
   if(!file){reportStatus("First choose a .cu8 file using Local .cu8 file.");return;}
   void analyze(file,file.name);
 });
 $("iq-analyze-full").addEventListener("click",()=>{
   const file=$("iq-file").files?.[0];
   if(file){void analyze(file,file.name,null,true);}
   else if(lastBlob){updateMetadata(lastMetadata);void analyze(lastBlob,lastName||"last-capture.cu8",lastMetadata,true);}
   else reportStatus("Choose a local CU8 file or first record a real WebUSB capture.");
 });
 $("iq-stop-analysis").addEventListener("click",()=>{activeController?.abort();});
 $("iq-spectrum").addEventListener("click",event=>{
   if(!lastReport)return;
   const canvas=$("iq-spectrum"),rect=canvas.getBoundingClientRect();
   const relativeX=(event.clientX-rect.left)*canvas.width/rect.width;
   const fractional=Math.max(0,Math.min(1,(relativeX-56)/(canvas.width-18-56)));
   const selectedOffsetHz=(fractional-0.5)*lastReport.sampleRate;
   $("iq-audio-offset").value=(selectedOffsetHz/1000).toFixed(2);
   reportStatus("Selected "+(lastReport.centerFrequencyHz==null?
     (selectedOffsetHz/1000).toFixed(2)+" kHz baseband offset":
     ((lastReport.centerFrequencyHz+selectedOffsetHz)/1e6).toFixed(6)+" MHz")+
     " from spectrum. Select AM or NFM and generate an experimental audio preview if suitable.");
 });
 $("iq-audio-preview").addEventListener("click",async()=>{
   if(!lastAnalyzedBlob||inProgress)return;
   const rate=Number($("iq-rate").value),offsetHz=Number($("iq-audio-offset").value)*1000;
   const mode=$("iq-audio-mode").value;
   const player=$("iq-audio-player");
   inProgress=true;activeController=new AbortController();setControls();
   try{
     reportStatus("Experimental "+mode.toUpperCase()+" demodulation of 6 seconds of local CU8 samples…");
     const result=await demodulateCu8Preview(lastAnalyzedBlob,{sampleRate:rate,offsetHz,mode,
       durationSec:6,signal:activeController.signal});
     if(previewUrl)URL.revokeObjectURL(previewUrl);
     previewUrl=URL.createObjectURL(result.blob);
     player.src=previewUrl;player.hidden=false;
     reportStatus("Analog audio preview generated locally · "+result.seconds.toFixed(2)+
       " s · "+result.outputSampleRate+" samples/s. "+result.warning);
   }catch(error){reportStatus("Audio preview unavailable: "+String(error?.message||error));}
   finally{inProgress=false;activeController=null;setControls();}
 });
 $("iq-export-metadata").addEventListener("click",()=>{
   if(!lastReport)return;
   const actualCapture=lastAnalyzedBlob===lastBlob&&lastReportName===lastName?lastMetadata:null;
   const info={format:"TIHULU Satellite Center capture metadata v1",
     source_file:lastReportName,metadata_exported_utc:new Date().toISOString(),
     center_frequency_hz:lastReport.centerFrequencyHz,
     sample_rate_sps:lastReport.sampleRate,iq_datatype:"cu8",
     capture_started_utc:actualCapture?.captureStartedUtc??null,
     capture_ended_utc:actualCapture?.captureEndedUtc??null,
     captured_complex_samples:actualCapture?.complexSamples??null,
     receiver_type:actualCapture?.receiverType??null,
     acquisition_method:actualCapture?.acquisition??"Unknown / imported CU8",
     gain_mode:actualCapture?.gainMode??null,
     candidate_target:actualCapture?.targetCandidate??null,
     rf_source_verified:false,
     evidence:"Raw CU8 FFT and relative digital power; not verified transmitter or satellite",
     metadata_provenance:actualCapture?"USB capture settings recorded during acquisition":"Filename inference or operator-entered metadata",
     notes:"CU8 does not embed metadata. This JSON is a separate sidecar for the selected file."};
   const blob=new Blob([JSON.stringify(info,null,2)],{type:"application/json"});
   const url=URL.createObjectURL(blob),a=document.createElement("a");
   a.href=url;a.download=(lastReportName||"capture").replace(/\.cu8$/i,"")+".metadata.json";
   document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
 });

 function clearDiscoveryArtifacts(){
   for(const url of discoveryObjectUrls)URL.revokeObjectURL(url);
   discoveryObjectUrls=[];
   $("iq-discovery-results").replaceChildren();
   lastDiscovery=null;
 }
 function discoveryText(value,container,tag="p"){
   const el=document.createElement(tag);el.textContent=String(value);
   container.append(el);return el;
 }
 function renderDiscovery(result){
   clearDiscoveryArtifacts();
   lastDiscovery=result;
   const target=$("iq-discovery-results");
   discoveryText(result.conclusion,target,"h3");
   discoveryText("Measured: "+result.analysis.windows.toLocaleString()+
     " complete FFT windows · "+result.analysis.coveragePercent+"% file coverage. "+
     "No satellite identity, human speech, music or packet payload confirmed.",target);
   const results=$("iq-discovery-stages");results.replaceChildren();
   for(const stage of result.phases){
     discoveryText(stage.phase.toUpperCase()+" · "+stage.state+" · "+stage.message,results);
   }
   const grid=document.createElement("div");grid.className="discovery-audio-grid";
   target.append(grid);
   for(const probe of result.audioProbes){
     const card=document.createElement("div");card.className="discovery-audio-item";
     const title=probe.mode.toUpperCase()+" · "+
       (probe.frequencyHz==null?(probe.offsetHz/1000).toFixed(2)+" kHz offset":
         (probe.frequencyHz/1e6).toFixed(5)+" MHz");
     discoveryText(title,card,"strong");discoveryText(probe.state,card);
     if(probe.audioBlob){
       const url=URL.createObjectURL(probe.audioBlob);
       discoveryObjectUrls.push(url);
       const player=document.createElement("audio");player.controls=true;player.preload="none";
       player.src=url;player.setAttribute("aria-label","Unverified "+title+" audio candidate");
       card.append(player);
       const a=document.createElement("a");a.href=url;
       a.download="TIHULU_RF-CANDIDATE_"+probe.mode.toUpperCase()+"_"+
         Math.round(probe.offsetHz)+"Hz.wav";a.textContent="Save experimental audio preview";
       card.append(a);
     }else discoveryText(probe.reason||"Unavailable",card);
     grid.append(card);
   }
   for(const frame of result.images){
     const item=document.createElement("div");item.className="discovery-image-item";
     discoveryText("Robot36 SSTV candidate · "+frame.alignedLines+
       "/240 aligned lines · NOT satellite-verified",item,"h3");
     const canvas=document.createElement("canvas");canvas.width=frame.width;
     canvas.height=frame.height;canvas.className="discovery-image";
     const ctx=canvas.getContext("2d");
     if(ctx){
       ctx.putImageData(new ImageData(frame.rgba,frame.width,frame.height),0,0);
       item.append(canvas);
       const button=document.createElement("button");button.type="button";
       button.className="secondary";button.textContent="Save unverified Robot36 candidate PNG";
       button.addEventListener("click",()=>{
         canvas.toBlob(blob=>{
           if(!blob)return;
           const url=URL.createObjectURL(blob),a=document.createElement("a");
           a.href=url;a.download="TIHULU_UNATTRIBUTED_ROBOT36-CANDIDATE_"+
             Math.round(frame.offsetHz)+"Hz_"+new Date().toISOString().replace(/[:.]/g,"-")+".png";
           document.body.append(a);a.click();a.remove();
           setTimeout(()=>URL.revokeObjectURL(url),60000);
         },"image/png");
       });item.append(button);
     }
     target.append(item);
   }
   const packet=document.createElement("div");
   for(const p of result.packetResults)discoveryText(p.protocol+
     " · "+p.status+" · "+p.reason,packet);
   target.append(packet);
   discoveryText("Analysis does not guarantee identification: unsupported formats, missing sample metadata, "+
     "wrong modulation, low SNR, very short recordings and absent transmitters can leave contents Unknown.",target);
 }
 $("iq-auto-discover").addEventListener("click",async()=>{
   if(inProgress)return;
   const file=$("iq-file").files?.[0]||lastBlob;
   if(!file){reportStatus("Select a CU8 recording or capture actual USB IQ first.");return;}
   const name=$("iq-file").files?.[0]?.name||lastName||"capture.cu8";
   const rate=Number($("iq-rate").value),freqText=$("iq-center").value.trim();
   const centerHz=freqText?Number(freqText)*1e6:null;
   if(freqText&&(!Number.isFinite(centerHz)||centerHz<24000000||centerHz>1750000000)){
     reportStatus("Confirm valid center frequency, or clear the field when unknown.");return;
   }
   inProgress=true;activeController=new AbortController();setControls();
   clearDiscoveryArtifacts();
   const stagePanel=$("iq-discovery-stages");stagePanel.replaceChildren();
   try{
     reportStatus("Automatic discovery: spectrum → channels → analog audio → supported image sync → packet readiness.");
     await computeSelector.ready;
     const result=await discoverCu8Contents(file,{sampleRate:rate,centerHz,
       computePolicy:computeSelector.getSelection(),
       signal:activeController.signal,enableImage:true,maxCandidates:3,
       onProgress:evt=>{
         if(evt.state!=="running")discoveryText(evt.phase+" · "+evt.state+" · "+evt.message,stagePanel);
         reportStatus("Automatic discovery · "+evt.phase+": "+evt.message);
       }});
     lastReport=result.analysis;lastReportName=name;lastAnalyzedBlob=file;
     renderReport(result.analysis,name);
     renderDiscovery(result);
     reportStatus("Automatic discovery complete: "+result.conclusion+
       ". All analysis and optional image/audio processing stayed on this device.");
   }catch(error){
     reportStatus("Automatic discovery failed or stopped: "+String(error?.message||error));
   }finally{
     inProgress=false;activeController=null;setControls();
   }
 });
 $("iq-discovery-export").addEventListener("click",()=>{
   if(!lastDiscovery)return;
   downloadJson(discoveryReportJson(lastDiscovery),lastReportName||"CU8-discovery");
 });
 $("iq-discovery-zip").addEventListener("click",async()=>{
   if(inProgress||(!lastReport&&!lastDiscovery))return;
   const btn=$("iq-discovery-zip"),state=$("iq-discovery-zip-status");
   btn.disabled=true;
   const entries=[],manifest={
     format:"tihulu-cu8-analysis-v1",
     sourceRecording:lastReportName||lastName||"unknown",
     createdUtc:new Date().toISOString(),
     rawIqIncluded:false,
     note:"RF measurements and decoder candidates only. No verified spacecraft or complete onboard data.",
     files:[],warnings:[]
   };
   const json=obj=>new Blob([JSON.stringify(obj,null,2)],{type:"application/json"});
   const add=(name,blob,kind,quality)=>{
     entries.push({name,blob});manifest.files.push({name,kind,bytes:blob.size,quality});
   };
   try{
     state.textContent="Preparing local results ZIP (no uploads)…";
     if(lastReport)add("analysis/spectrum.json",json(lastReport),"measured FFT",
                       "Uncalibrated spectral data from supplied CU8");
     if(lastDiscovery){
       add("analysis/discovery.json",json(discoveryReportJson(lastDiscovery)),
           "decoder evidence","Unverified spacecraft origin");
       for(let i=0;i<(lastDiscovery.images||[]).length;i++){
         const frame=lastDiscovery.images[i];
         if(!Number.isInteger(frame.width)||!Number.isInteger(frame.height)||
            frame.width<1||frame.height<1||frame.width*frame.height>8_000_000){
           manifest.warnings.push("Invalid image dimensions for candidate "+(i+1));continue;
         }
         try{
           const canvas=document.createElement("canvas");canvas.width=frame.width;canvas.height=frame.height;
           const ctx=canvas.getContext("2d");if(!ctx)throw Error("Canvas unsupported");
           ctx.putImageData(new ImageData(frame.rgba,frame.width,frame.height),0,0);
           const blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/png"));
           if(!blob)throw Error("PNG conversion failed");
           add("images/robot36_candidate_"+(i+1)+".png",blob,"image candidate",
               "Robot36 line sync measured; spacecraft not independently verified");
         }catch(error){manifest.warnings.push("Image "+(i+1)+" omitted: "+error.message);}
       }
       for(let i=0;i<(lastDiscovery.audioProbes||[]).length&&i<8;i++){
         const probe=lastDiscovery.audioProbes[i];
         if(probe.audioBlob instanceof Blob)
           add("audio/probe_"+(i+1)+".wav",probe.audioBlob,"audio candidate",
               "Real demodulation, speech/content unverified");
       }
     }
     entries.unshift({name:"manifest.json",blob:json(manifest)});
     entries.push({name:"README.txt",data:
       "TIHULU Satellite Center: actual CU8 analysis outputs.\n"+
       "Raw IQ excluded. Decoded media candidates do not prove satellite origin.\n"});
     const zip=await createResultsZip(entries);
     const url=URL.createObjectURL(zip),link=document.createElement("a");
     link.href=url;link.download="TIHULU_CU8_results_"+new Date().toISOString().replace(/[:.]/g,"-")+".zip";
     document.body.append(link);link.click();link.remove();
     setTimeout(()=>URL.revokeObjectURL(url),30000);
     state.textContent="ZIP download requested: "+manifest.files.length+
       " actual output(s). Verify your browser Downloads.";
   }catch(error){
     state.textContent="ZIP unavailable: "+String(error?.message||error)+
       ". Individual results and original CU8 remain available.";
   }finally{setControls();}
 });
 $("iq-analyze-last").addEventListener("click",()=>{
   if(!lastBlob)return;updateMetadata(lastMetadata);
   void analyze(lastBlob,lastName||"last-capture.cu8",lastMetadata);
 });
 $("iq-export-json").addEventListener("click",()=>{
   if(lastReport)downloadJson(lastReport,lastReportName);
 });
 setControls();
 return {
   record(blob,name,metadata){
     if(!blob||blob.size<4096)return;
     lastBlob=blob;lastName=name;lastMetadata=metadata;
     $("iq-last-info").textContent="Latest real local recording: "+name+" · "+fmt(blob.size)+
       " bytes. Analyze it here without re-uploading. This recording remains only while this tab is open.";
     setControls();
     updateMetadata(metadata);
     // After a successful WebUSB capture, perform the requested "last
     // analysis" automatically. A user can still open a previous file.
     void analyze(blob,name,metadata);
   }
 };
}
