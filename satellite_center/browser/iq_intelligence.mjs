/* TIHULU Satellite Center — bounded-memory FULL CU8 analysis and experimental
 * receive-only AM/NFM audio preview. No network, hardware claims or satellite identity.
 */
import {fftComplex} from "./iq_analysis.mjs";
const N=2048, BLOCK=N*2, EPS=1e-15;
const hann=Float64Array.from({length:N},(_,i)=>0.5-0.5*Math.cos(2*Math.PI*i/(N-1)));
const norm=N*hann.reduce((v,w)=>v+w*w,0);
const db=v=>10*Math.log10(Math.max(v,EPS));
const median=values=>{const a=Array.from(values).filter(Number.isFinite).sort((x,y)=>x-y);return a.length?a[Math.floor(a.length/2)]:-Infinity;};
function validate(blob,rate,centerHz){
 if(!blob||typeof blob.slice!=="function"||!Number.isFinite(blob.size)||blob.size<BLOCK)throw Error("A valid CU8 file of at least 4096 bytes is required.");
 if(blob.size%2)throw Error("CU8 is missing a complete I/Q byte pair.");
 if(!Number.isFinite(rate)||rate<200000||rate>3200000)throw Error("Sample rate must be 200000–3200000 samples/s.");
 if(centerHz!==null&&(!Number.isFinite(centerHz)||centerHz<24000000||centerHz>1750000000))throw Error("Invalid or unknown RTL-SDR center frequency.");
}
function powerSpectrum(bytes,offset,re,im,power){
 let dcI=0,dcQ=0,energy=0,clipping=0;
 for(let k=0;k<N;k++){
   const i=bytes[offset+k*2],q=bytes[offset+k*2+1];
   const x=(i-127.5)/128,y=(q-127.5)/128;
   re[k]=x;im[k]=y;dcI+=x;dcQ+=y;energy+=x*x+y*y;
   if(i<=1||i>=254||q<=1||q>=254)clipping++;
 }
 dcI/=N;dcQ/=N;
 for(let k=0;k<N;k++){re[k]=(re[k]-dcI)*hann[k];im[k]=(im[k]-dcQ)*hann[k];}
 fftComplex(re,im);
 for(let k=0;k<N;k++){
   const j=(k+N/2)%N;
   power[j]=(re[k]*re[k]+im[k]*im[k])/norm;
 }
 return {energy:energy/N,dcI,dcQ,clipping};
}
/* Candidates are energy features, NEVER positive modulation / spacecraft IDs. */
export function detectSpectralCandidates(spectrumDb,sampleRate,centerHz=null,thresholdDb=5.5){
 if(!spectrumDb?.length||!Number.isFinite(sampleRate))return [];
 const size=spectrumDb.length,mid=size/2,binHz=sampleRate/size;
 const noise=median(spectrumDb.filter((_,i)=>Math.abs(i-mid)>6));
 const smoothed=Array.from({length:size},(_,i)=>{
   let v=0,n=0;
   for(let j=Math.max(0,i-3);j<=Math.min(size-1,i+3);j++){
     if(Math.abs(j-mid)<=6)continue;v+=spectrumDb[j];n++;
   }
   return n?v/n:-Infinity;
 });
 const groups=[];let start=-1,end=-1;
 const add=()=>{
   if(start<0)return;
   if(end-start+1>=3){
     let best=start;for(let k=start+1;k<=end;k++)if(spectrumDb[k]>spectrumDb[best])best=k;
     const offset=(best-mid)*binHz;
     groups.push({startOffsetHz:Math.round((start-mid)*binHz),
       endOffsetHz:Math.round((end+1-mid)*binHz),
       peakOffsetHz:Math.round(offset),
       peakFrequencyHz:centerHz===null?null:Math.round(centerHz+offset),
       widthHz:Math.round((end+1-start)*binHz),
       prominenceDb:Number((spectrumDb[best]-noise).toFixed(2)),
       classification:"Unclassified spectral energy",
       evidence:"FFT power above file-wide median; no signal or satellite identity verified"});
   }
   start=-1;end=-1;
 };
 for(let i=0;i<size;i++){
   const active=Math.abs(i-mid)>7&&smoothed[i]>noise+thresholdDb;
   if(active){if(start<0)start=i;end=i;}
   else add();
 }
 add();
 return groups.sort((a,b)=>b.prominenceDb-a.prominenceDb).slice(0,12);
}
export async function analyzeFullCu8Blob(blob,{sampleRate,centerHz=null,maxWaterfallRows=180,
  onProgress=()=>{},signal=null}={}){
 const rate=Number(sampleRate);validate(blob,rate,centerHz);
 const windows=Math.floor(blob.size/BLOCK);
 const rows=Math.max(1,Math.min(256,Math.floor(maxWaterfallRows),windows));
 const sum=new Float64Array(N),waterSum=new Float64Array(rows*256);
 const timePower=new Float64Array(rows),counts=new Uint32Array(rows);
 const re=new Float64Array(N),im=new Float64Array(N),power=new Float64Array(N);
 let clipped=0,dcI=0,dcQ=0,energySum=0,done=0;
 const chunkWindows=64; // 256 KiB maximum input chunk; no whole-file buffering
 while(done<windows){
   if(signal?.aborted)throw Error("Full analysis stopped by user.");
   const count=Math.min(chunkWindows,windows-done);
   const data=new Uint8Array(await blob.slice(done*BLOCK,(done+count)*BLOCK).arrayBuffer());
   if(data.length!==count*BLOCK)throw Error("Incomplete CU8 file read.");
   for(let k=0;k<count;k++){
     const result=powerSpectrum(data,k*BLOCK,re,im,power);
     const row=Math.min(rows-1,Math.floor((done+k)*rows/windows));
     counts[row]++;energySum+=result.energy;timePower[row]+=result.energy;
     dcI+=result.dcI;dcQ+=result.dcQ;clipped+=result.clipping;
     for(let j=0;j<N;j++)sum[j]+=power[j];
     for(let c=0;c<256;c++){
       let v=0;for(let t=0;t<8;t++)v+=power[c*8+t];
       waterSum[row*256+c]+=v/8;
     }
   }
   done+=count;onProgress(done,windows);
   // Yield so browsers remain responsive and Abort button can interrupt.
   await new Promise(resolve=>setTimeout(resolve,0));
 }
 const spectrumDb=Array.from(sum,x=>Number(db(x/windows).toFixed(2)));
 const waterfallDb=Array.from({length:rows},(_,r)=>
   Array.from({length:256},(_,c)=>Number(db(waterSum[r*256+c]/counts[r]).toFixed(1))));
 const powerHistoryDb=Array.from({length:rows},(_,r)=>Number(db(timePower[r]/counts[r]).toFixed(2)));
 const noise=median(spectrumDb.filter((_,i)=>Math.abs(i-N/2)>6));
 const strongest=spectrumDb.reduce((best,v,i)=>Math.abs(i-N/2)>6&&v>spectrumDb[best]?i:best,0);
 const peakOffsetHz=(strongest-N/2)*rate/N;
 const report={
   format:"unsigned 8-bit interleaved complex I/Q (CU8)",analysisMode:"full-file FFT / binned waterfall",
   sampleRate:rate,centerFrequencyHz:centerHz,totalBytes:blob.size,
   estimatedSeconds:Number((blob.size/(2*rate)).toFixed(3)),
   windows,fftSize:N,frequencyResolutionHz:Number((rate/N).toFixed(3)),
   averageRelativeLevelDb:Number(db(energySum/windows).toFixed(2)),
   minRelativeLevelDb:Math.min(...powerHistoryDb),maxRelativeLevelDb:Math.max(...powerHistoryDb),
   peakOffsetHz:Number(peakOffsetHz.toFixed(1)),
   peakFrequencyHz:centerHz===null?null:Number((centerHz+peakOffsetHz).toFixed(1)),
   peakVsMedianDb:Number((spectrumDb[strongest]-noise).toFixed(2)),
   clippedComplexPairsPercent:Number((100*clipped/(windows*N)).toFixed(3)),
   meanDcOffset:{i:Number((dcI/windows).toFixed(5)),q:Number((dcQ/windows).toFixed(5))},
   spectrumDb,waterfallDb,powerHistoryDb,
   signalCandidates:detectSpectralCandidates(spectrumDb,rate,centerHz),
   sampledBytes:done*BLOCK,processedBytes:done*BLOCK,
   coveragePercent:Number((100*done*BLOCK/blob.size).toFixed(4)),
   ignoredTrailingBytes:blob.size-done*BLOCK,
   waterfallTimeBinSeconds:Number((windows*N/rate/rows).toFixed(6)),
   warning:"All complete 2048-pair windows were analyzed; a final partial window was ignored. CU8 does not store device identity, frequency, time or gain. Frequency requires confirmed metadata. Spectrum is uncalibrated relative digital power. Candidates are NOT decoded signals, radio-source positions or verified satellites. Time-axis assumes continuous samples without missing USB transfers."
 };
 return report;
}
function wavPcm16(samples,sampleRate){
 const buffer=new ArrayBuffer(44+samples.length*2),view=new DataView(buffer);
 const put=(o,s)=>{for(let i=0;i<s.length;i++)view.setUint8(o+i,s.charCodeAt(i));};
 put(0,"RIFF");view.setUint32(4,36+samples.length*2,true);put(8,"WAVE");put(12,"fmt ");
 view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);
 view.setUint32(24,sampleRate,true);view.setUint32(28,sampleRate*2,true);
 view.setUint16(32,2,true);view.setUint16(34,16,true);put(36,"data");
 view.setUint32(40,samples.length*2,true);
 for(let k=0;k<samples.length;k++)view.setInt16(44+k*2,Math.max(-32768,Math.min(32767,Math.round(samples[k]*32767))),true);
 return new Blob([buffer],{type:"audio/wav"});
}
export async function demodulateCu8Preview(blob,{sampleRate,offsetHz=0,mode="nfm",
 durationSec=6,signal=null,onProgress=()=>{}}={}){
 const rate=Number(sampleRate);validate(blob,rate,null);
 if(!["am","nfm"].includes(mode))throw Error("Select AM or NFM.");
 if(!Number.isFinite(offsetHz)||Math.abs(offsetHz)>rate/2)throw Error("Tune offset lies outside captured IQ bandwidth.");
 const decimation=Math.max(1,Math.floor(rate/48000)),outRate=rate/decimation;
 const maxSamples=Math.min(Math.floor(blob.size/2),Math.floor(Math.max(1,Math.min(durationSec,10))*rate));
 const length=Math.floor(maxSamples/decimation);
 if(length<100)throw Error("Not enough I/Q samples to preview.");
 const audio=new Float32Array(length);
 let out=0,pos=0,phase=0,accI=0,accQ=0,count=0,prevI=0,prevQ=0;
 let average=0,dc=0,deemphasis=0;
 const phaseStep=-2*Math.PI*offsetHz/rate;
 while(pos<maxSamples){
   if(signal?.aborted)throw Error("Audio processing stopped.");
   const n=Math.min(65536,maxSamples-pos);
   const data=new Uint8Array(await blob.slice(pos*2,(pos+n)*2).arrayBuffer());
   for(let k=0;k<n;k++){
     const i=(data[k*2]-127.5)/128,q=(data[k*2+1]-127.5)/128;
     const cs=Math.cos(phase),sn=Math.sin(phase);
     accI+=i*cs-q*sn;accQ+=i*sn+q*cs;count++;
     phase+=phaseStep;if(phase>Math.PI)phase-=2*Math.PI;if(phase< -Math.PI)phase+=2*Math.PI;
     if(count===decimation){
       const vI=accI/decimation,vQ=accQ/decimation;
       let val;
       if(mode==="am")val=Math.hypot(vI,vQ);
       else val=out===0?0:Math.atan2(prevI*vQ-prevQ*vI,prevI*vI+prevQ*vQ);
       prevI=vI;prevQ=vQ;accI=0;accQ=0;count=0;
       // Audio-only DC blocker, and simple narrow FM deemphasis smoothing.
       dc=0.998*dc+0.002*val;val-=dc;
       if(mode==="nfm"){deemphasis=0.85*deemphasis+0.15*val;val=deemphasis;}
       audio[out++]=val;average+=val*val;
     }
   }
   pos+=n;onProgress(pos,maxSamples);
   await new Promise(resolve=>setTimeout(resolve,0));
 }
 const rms=Math.sqrt(average/Math.max(1,out));
 if(rms<1e-7)throw Error("No usable demodulated audio level.");
 const gain=Math.min(8,0.22/rms);
 for(let i=0;i<out;i++)audio[i]=Math.tanh(audio[i]*gain);
 return {blob:wavPcm16(audio.subarray(0,out),Math.round(outRate)),
  outputSampleRate:Math.round(outRate),seconds:out/outRate,mode,offsetHz,
  warning:"Experimental analog AM/NFM audio only. Demodulation does not identify a transmitter, decode a satellite protocol, or verify RF source position."};
}
