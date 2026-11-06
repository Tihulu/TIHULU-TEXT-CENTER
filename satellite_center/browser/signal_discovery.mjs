/* TIHULU Satellite Center — local, bounded, exploratory CU8 payload discovery.
 * A waveform is not a named satellite, speech, or a picture unless a decoder
 * validates structure. Offline, receive-only; never uploads samples.
 */
import {analyzeFullCu8Blob, demodulateCu8Preview} from "./iq_intelligence.mjs";
import {decodeRobot36Audio} from "./sstv_robot36.mjs";

const NUM_AUDIO_PROBES=3, MS=1_000_000;
const checkAbort=(signal)=>{if(signal?.aborted)throw Error("Automatic discovery stopped by user.");};
function validateRate(rate) {
 if (![1024000,2048000].includes(rate)) throw Error(
   "Audio/image detection currently supports 1.024 or 2.048 MS/s CU8. FFT analysis still supports other sample rates.");
}
const delay=()=>new Promise(resolve=>setTimeout(resolve,0));

/* Extract actual channelized NFM discriminator samples, not audio invented from
 * spectrum. Bounded <=256 KiB input reads. IQ RF frequency translated using
 * a recurring oscillator, so oscillator setup need not be repeated per sample.
 * Boxcar anti-aliasing is approximate: adjacent transmitters can leak into
 * recovered audio. This is experimental, not a calibrated decoder.
 */
export async function cu8ToTunedFmAudio(file,{sampleRate,offsetHz=0,
 durationSeconds=75,startSeconds=0,onProgress=()=>{},signal=null}={}){
 validateRate(sampleRate);
 if(!file||typeof file.slice!=="function"||!Number.isSafeInteger(file.size)||file.size%2)
   throw Error("Select a valid unsigned interleaved CU8 file.");
 if(!Number.isFinite(offsetHz)||Math.abs(offsetHz)>sampleRate*.45)
   throw Error("Offset is outside safe recorded bandwidth.");
 if(!Number.isFinite(startSeconds)||startSeconds<0)throw Error("Invalid FM start time.");
 const firstSample=Math.floor(startSeconds*sampleRate);
 const rate=16000,step1=sampleRate/64000,limitSamples=Math.min(
   Math.max(0,Math.floor(file.size/2)-firstSample),
   Math.floor(Math.max(1,Math.min(95,durationSeconds))*sampleRate));
 const audio=new Float32Array(Math.ceil(limitSamples/(sampleRate/rate))+2);
 const step=-2*Math.PI*offsetHz/sampleRate;
 const rotationI=Math.cos(step),rotationQ=Math.sin(step);
 let oscillatorI=1,oscillatorQ=0,boxI=0,boxQ=0,boxN=0;
 let prevI=0,prevQ=0,havePrev=false,phaseAccum=0,phaseN=0,dc=0,outN=0;
 let sumSquares=0,processed=0;
 const inputChunk=128*1024;
 while(processed<limitSamples){
   checkAbort(signal);
   const count=Math.min(inputChunk,limitSamples-processed);
   const bytes=new Uint8Array(await file.slice((firstSample+processed)*2,(firstSample+processed+count)*2).arrayBuffer());
   if(bytes.length!==count*2)throw Error("Incomplete CU8 input.");
   for(let i=0;i<count;i++){
     const inI=(bytes[i*2]-127.5)/128,inQ=(bytes[i*2+1]-127.5)/128;
     boxI+=inI*oscillatorI-inQ*oscillatorQ;
     boxQ+=inI*oscillatorQ+inQ*oscillatorI;boxN++;
     const nI=oscillatorI*rotationI-oscillatorQ*rotationQ;
     oscillatorQ=oscillatorI*rotationQ+oscillatorQ*rotationI;oscillatorI=nI;
     if((processed+i)%4096===0){
       const m=Math.hypot(oscillatorI,oscillatorQ)||1;oscillatorI/=m;oscillatorQ/=m;
     }
     if(boxN<step1)continue;
     const I=boxI/boxN,Q=boxQ/boxN;
     boxI=0;boxQ=0;boxN=0;
     if(havePrev){
       phaseAccum+=Math.atan2(prevI*Q-prevQ*I,prevI*I+prevQ*Q);phaseN++;
       if(phaseN===4){
         const value=phaseAccum/4;dc+=0.0004*(value-dc);
         const sample=value-dc;
         audio[outN++]=sample;sumSquares+=sample*sample;
         phaseAccum=0;phaseN=0;
       }
     }
     prevI=I;prevQ=Q;havePrev=true;
   }
   processed+=count;
   onProgress(processed,limitSamples);
   await delay();
 }
 const output=audio.subarray(0,outN);
 const rms=Math.sqrt(sumSquares/Math.max(1,outN));
 if(outN<rate||!Number.isFinite(rms)||rms<1e-9)
   throw Error("Insufficient changing FM audio signal for image detection.");
 // Decoder uses zero crossings; normalize only after the real IQ discriminator.
 const gain=Math.min(12,0.33/rms);
 for(let i=0;i<output.length;i++)output[i]=Math.max(-1,Math.min(1,output[i]*gain));
 return {samples:output,rate,seconds:Number((output.length/rate).toFixed(3)),
   offsetHz,startSeconds:firstSample/sampleRate,rms:Number(rms.toFixed(8)),
   warning:"Uncalibrated FM audio; simple decimation may suffer adjacent-channel aliasing."};
}

function makeSteps(report){
 const known=report.centerFrequencyHz!==null;
 const candidates=report.signalCandidates.slice(0,8).filter(c=>
   Number.isFinite(c.peakOffsetHz)&&Math.abs(c.peakOffsetHz)<report.sampleRate*.43);
 const chosen=[];
 // The actual tuned center is an important alternate hypothesis even when
 // DC suppression hides a centered analog channel in the peak detector.
 chosen.push({peakOffsetHz:0,peakFrequencyHz:report.centerFrequencyHz,
   widthHz:null,prominenceDb:null,classification:"Operator-tuned center; unverified RF"});
 for(const c of candidates) {
   if(chosen.every(a=>Math.abs(a.peakOffsetHz-c.peakOffsetHz)>Math.max(6000,c.widthHz/2))){
     chosen.push(c);
   }
   if(chosen.length>=NUM_AUDIO_PROBES)break;
 }
 return {known,chosen};
}
function bestWindowStart(report,offsetHz,lengthSeconds){
 const available=report.estimatedSeconds;
 if(!Number.isFinite(lengthSeconds)||available<=lengthSeconds)return 0;
 const rows=report.waterfallDb;
 if(!rows.length)return 0;
 const bin=Math.max(0,Math.min(255,Math.floor(256*(0.5+offsetHz/report.sampleRate))));
 let best=-Infinity,index=0;
 for(let r=0;r<rows.length;r++){
   const local=rows[r];
   // Compare the target band with its own local median, so global gain shifts
   // cannot masquerade as a uniquely active transmitter.
   const noise=local.slice().sort((a,b)=>a-b)[Math.floor(local.length/2)];
   const score=(local[bin]||-Infinity)-noise;
   if(score>best){best=score;index=r;}
 }
 const at=(index+.5)*available/rows.length;
 return Number(Math.max(0,Math.min(available-lengthSeconds,at-lengthSeconds/2)).toFixed(3));
}
function summaryError(e){return String(e?.message||e).slice(0,300);}
export async function discoverCu8Contents(file,{
 sampleRate,centerHz=null,onProgress=()=>{},signal=null,
 maxCandidates=NUM_AUDIO_PROBES,probeSeconds=3,enableImage=true
}={}){
 const startedAt=new Date().toISOString();
 const phases=[];
 const update=(id,state,message)=>{
   const item={phase:id,state,message};phases.push(item);onProgress(item);
 };
 checkAbort(signal);
 update("spectrum","running","Scanning all complete FFT windows, no upload");
 const report=await analyzeFullCu8Blob(file,{sampleRate,centerHz,signal,onProgress:(n,total)=>{
   if(n===total||n%(64*16)===0)onProgress({phase:"spectrum",state:"running",
     message:Math.round(100*n/total)+"% of complete FFT windows scanned"});
 }});
 update("spectrum","complete",report.signalCandidates.length+
   " unclassified RF energy groups; not confirmed transmissions");
 const chosen=makeSteps(report).chosen.slice(0,Math.max(1,Math.min(5,maxCandidates)));
 const stages=[{kind:"RF spectrum",state:"measured",details:report.windows+" complete FFT windows"},
 {kind:"Spectral candidate selection",state:"candidate",details:chosen.length+" energy regions"}];
 const audioProbes=[],images=[],packetResults=[];
 // The user wants a forensic workflow. Audio output means a DEMODULATION
 // attempt, not proof of human speech or a particular satellite.
 if(![1024000,2048000].includes(Number(sampleRate))){
   update("audio","unsupported","Audio/image modes require 1.024 or 2.048 MS/s.");
 }else{
   for(let k=0;k<chosen.length;k++){
     const c=chosen[k];const offset=c.peakOffsetHz;
     for(const mode of ["nfm","am"]){
       checkAbort(signal);
       update("audio","running","Trying "+mode.toUpperCase()+
         " around "+(offset/1000).toFixed(2)+" kHz offset (candidate "+(k+1)+"/"+chosen.length+")");
       try{
         const startSeconds=bestWindowStart(report,offset,Math.max(1,Math.min(9,probeSeconds)));
         const result=await demodulateCu8Preview(file,{sampleRate:Number(sampleRate),
           offsetHz:offset,mode,durationSec:Math.max(1,Math.min(9,probeSeconds)),
           startSeconds,signal});
         audioProbes.push({candidate:k+1,mode,offsetHz:offset,startSeconds,
           frequencyHz:report.centerFrequencyHz===null?null:report.centerFrequencyHz+offset,
           durationSeconds:result.seconds,sampleRateHz:result.outputSampleRate,
           state:"audio preview generated — content not identified",audioBlob:result.blob});
       }catch(e){
         if(signal?.aborted)throw Error("Automatic discovery stopped by user.");
         audioProbes.push({candidate:k+1,mode,offsetHz:offset,state:"no usable preview",
           reason:summaryError(e),audioBlob:null});
       }
     }
   }
   update("audio","complete",audioProbes.filter(p=>p.audioBlob).length+
     " analog demodulation previews; speech/music classification not verified");
   const recordingSeconds=file.size/(2*Number(sampleRate));
   if(enableImage&&recordingSeconds>=33){
     const attempts=chosen.slice(0,2);
     for(let k=0;k<attempts.length;k++){
       checkAbort(signal);
       const offset=attempts[k].peakOffsetHz;
       update("image","running","Checking actual NFM audio for Robot36 1200 Hz line sync at "+
         (offset/1000).toFixed(2)+" kHz");
       try{
         const durationSeconds=Math.min(75,recordingSeconds);
         const startSeconds=bestWindowStart(report,offset,durationSeconds);
         const audio=await cu8ToTunedFmAudio(file,{sampleRate:Number(sampleRate),
           offsetHz:offset,signal,durationSeconds,startSeconds});
         const frame=decodeRobot36Audio(audio.samples,audio.rate);
         images.push({kind:"Robot36 SSTV candidate",offsetHz:offset,startSeconds,
           frequencyHz:centerHz===null?null:centerHz+offset,
           alignedLines:frame.alignedLines,width:frame.width,height:frame.height,
           status:frame.status,rgba:frame.rgba,
           evidence:"Repeated 1200 Hz lines synchronized across Robot36 scan geometry. Satellite and image content unverified."});
         update("image","decoded candidate","Robot36 sync detected: "+
           frame.alignedLines+"/240 aligned lines; verify image visually");
       }catch(e){
         if(signal?.aborted)throw Error("Automatic discovery stopped by user.");
         update("image","not verified","No validated Robot36 frame at this offset: "+summaryError(e));
       }
     }
   }else{
     update("image","skipped",enableImage?
       "Robot36 requires approximately 36 seconds of continuous CU8; this recording is "+
       recordingSeconds.toFixed(1)+" seconds.":"Image test disabled by user");
   }
 }
 // A named packet decoder must actually validate frame sync + CRC before
 // declaring telemetry/text. Never reinterpret arbitrary CU8 bytes as text.
 packetResults.push({protocol:"APRS / AX.25",status:"not checked",
   reason:"No CRC-validated packet decoder connected to this browser discovery pass."});
 packetResults.push({protocol:"Meteor-M LRPT",status:"not checked",
   reason:"Needs purpose-built demodulation, synchronization, FEC and image reconstruction; no in-browser decoder connected."});
 update("data","not decoded","No supported CRC-verified packet output from this discovery run");
 checkAbort(signal);
 const found=images.length?"Possible Robot36 image with synchronized lines":
   audioProbes.some(p=>p.audioBlob)?"Analog audio previews available, contents unclassified":
   "Unidentified RF energy only";
 update("done","complete",found);
 return {format:"TIHULU CU8 progressive signal discovery v1",createdUtc:startedAt,
   sourceBytes:file.size,analysis:report,phases,stages,audioProbes,images,
   packetResults,conclusion:found,
   notes:"CU8 does not embed modulation, satellite identity or timestamp. Audio is only a demodulated candidate and is not proof of speech, music or a transmitter. Robot36 requires validated line synchronization, but visual image/satellite still requires review. Data protocols are not claimed decoded. Real RF measurements are uncalibrated."};
}

export function discoveryReportJson(result){
 if(!result)return null;
 return {format:result.format,createdUtc:result.createdUtc,sourceBytes:result.sourceBytes,
  conclusion:result.conclusion,phases:result.phases,stages:result.stages,
  analysis:{...result.analysis},
  audioProbes:result.audioProbes.map(({audioBlob,...info})=>({...info,
    hasAudioPreview:Boolean(audioBlob)})),
  images:result.images.map(({rgba,...info})=>({...info,pixelDataIncluded:false})),
  packetResults:result.packetResults,notes:result.notes};
}
