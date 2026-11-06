/* UI for browser-only, read-only, local CU8 analysis.
 * Does not upload RF samples or claim demodulation of satellite traffic.
 */
import { analyzeCu8Blob,parseCu8Filename } from "./iq_analysis.mjs?v=20261106-cuiq-v13";
import { analyzeFullCu8Blob,demodulateCu8Preview } from "./iq_intelligence.mjs?v=20261106-signal-v1";
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
 const {w,h,x0,x1,y0,y1}=prepare(ctx,canvas,"Top: start · bottom: end (stratified windows; not continuous playback)");
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
  caption:"Sampled windows distributed over the file, not gap-free timestamps",
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
 let lastBlob=null,lastName=null,lastMetadata=null,activeRun=0;
 let lastReport=null,lastReportName=null,lastAnalyzedBlob=null,inProgress=false,activeController=null,previewUrl=null;
 function reportStatus(message){$("iq-analysis-status").textContent=String(message);}
 function setControls(){
   $("iq-analyze-last").disabled=!lastBlob||inProgress;
   $("iq-analyze-file").disabled=inProgress;
   $("iq-export-json").disabled=!lastReport||inProgress;
   $("iq-analyze-full").disabled=inProgress;
   $("iq-stop-analysis").disabled=!inProgress;
   $("iq-audio-preview").disabled=!lastAnalyzedBlob||inProgress;
   $("iq-export-metadata").disabled=!lastReport||inProgress;
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
     reportStatus((full?"Processing all complete I/Q FFT windows of ":"Reading scattered I/Q windows from ")+name+" locally… No upload.");
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
   reportStatus("File selected locally. Click Analyze selected file. Nothing is uploaded.");
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
   const info={format:"TIHULU Satellite Center capture metadata v1",
     source_file:lastReportName,created_utc:new Date().toISOString(),
     center_frequency_hz:lastReport.centerFrequencyHz,
     sample_rate_sps:lastReport.sampleRate,iq_datatype:"cu8",
     captured_at_utc:null,rf_source:"recorded CU8 / metadata operator-confirmed",
     notes:"CU8 has no embedded metadata; named satellite candidates are not verified RF sources."};
   const blob=new Blob([JSON.stringify(info,null,2)],{type:"application/json"});
   const url=URL.createObjectURL(blob),a=document.createElement("a");
   a.href=url;a.download=(lastReportName||"capture").replace(/\\.cu8$/i,"")+".metadata.json";
   document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
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
