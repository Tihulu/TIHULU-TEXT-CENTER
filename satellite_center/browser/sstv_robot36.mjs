/* Experimental receive-only Robot36 SSTV WAV decoder.
 * Validated 1200 Hz sync train REQUIRED; never interpret random RF IQ as SSTV.
 * Input must be demodulated, narrowband-FM audio (e.g. rtl_fm WAV / SDR audio).
 * Robot36 VIS code 8; 320x240, 150 ms line, Y/R-Y/B-Y alternating.
 * Actual image correctness depends on synchronization and audio fidelity.
 */
const W=320,H=240,MS=0.001,LINE=.150;
const clamp=(x,a=0,b=255)=>Math.max(a,Math.min(b,x));
export function robot36Mode(){return {width:W,height:H,vis:8,approxSeconds:36,lineSeconds:LINE};}
export function frequencyTrace(samples,rate,stepMs=1){
 if(!(samples instanceof Float32Array)||!Number.isFinite(rate)||rate<8000||rate>192000)
  throw Error("Choose a decoded mono PCM audio stream with a valid sample rate.");
 if(samples.length>rate*240)throw Error("Audio too long; limit SSTV file to 4 minutes.");
 const crosses=[];
 for(let i=1;i<samples.length;i++){
  const left=samples[i-1],right=samples[i];
  if(left<0&&right>=0){
    const fraction=-left/(right-left||1);
    crosses.push((i-1+fraction)/rate);
  }
 }
 const step=stepMs/1000,num=Math.floor(samples.length/rate/step),result=new Float32Array(num);
 let lo=0,hi=0;
 for(let index=0;index<num;index++){
  const center=(index+.5)*step,a=center-.003,b=center+.003;
  while(lo<crosses.length&&crosses[lo]<a)lo++;
  if(hi<lo)hi=lo;
  while(hi<crosses.length&&crosses[hi]<=b)hi++;
  result[index]=hi-lo>=5?
    clamp((hi-lo-1)/(crosses[hi-1]-crosses[lo]),400,4000):0;
 }
 return result;
}
export function findRobot36Syncs(trace){
 if(!(trace instanceof Float32Array))throw Error("Invalid demodulated frequency trace.");
 const results=[];
 let from=-1;
 for(let i=0;i<=trace.length;i++){
  const sync=i<trace.length&&trace[i]>1050&&trace[i]<1340;
  if(sync&&from<0)from=i;
  else if(!sync&&from>=0){
   const duration=i-from;
   if(duration>=5&&duration<=16)results.push(from/1000);
   from=-1;
  }
 }
 return results;
}
export function chooseRobot36Start(syncs){
 if(!Array.isArray(syncs)||syncs.length<12)throw Error("No repeated Robot36 1200 Hz synchronization train found.");
 let best=null;
 for(let origin=0;origin<Math.min(syncs.length,130);origin++){
   const start=syncs[origin];let matched=0,drift=0;
   for(let line=0;line<H;line++){
     const expected=start+line*LINE;
     if(expected>syncs[syncs.length-1]+.01)break;
     const found=syncs.find(t=>Math.abs(t-expected)<.0055);
     if(found!==undefined){matched++;drift+=Math.abs(found-expected);}
   }
   if(!best||matched>best.matched||(matched===best.matched&&drift<best.drift))
     best={start,matched,drift};
 }
 if(!best||best.matched<40)throw Error("Robot36 sync validation failed: fewer than 40 aligned scan lines.");
 return best;
}
function toneAt(trace,t){
 const center=Math.floor(t*1000),radius=2;let sum=0,n=0;
 for(let j=center-radius;j<=center+radius;j++){
  if(j>=0&&j<trace.length&&trace[j]>700&&trace[j]<3000){sum+=trace[j];n++;}
 }
 return n?sum/n:0;
}
function tonePixel(trace,t){
 const frequency=toneAt(trace,t);
 return frequency?clamp(Math.round((frequency-1500)*255/800)):127;
}
export function decodeRobot36Trace(trace,{onProgress=null}={}){
 if(!(trace instanceof Float32Array)||trace.length<32000)
   throw Error("Robot36 needs about 36 seconds of real demodulated SSTV audio.");
 const syncs=findRobot36Syncs(trace),alignment=chooseRobot36Start(syncs);
 const Y=Array.from({length:H},()=>new Uint8ClampedArray(W));
 const redDiff=Array.from({length:H},()=>new Float32Array(W));
 const blueDiff=Array.from({length:H},()=>new Float32Array(W));
 let rows=0,seen=0;
 for(let row=0;row<H;row++){
   const expected=alignment.start+row*LINE;
   const near=syncs.find(v=>Math.abs(v-expected)<.006);
   if(near===undefined)continue;
   const t=near;
   if(t+.148>=trace.length/1000)break;
   for(let x=0;x<W;x++){
     Y[row][x]=tonePixel(trace,t+.012+(x+.5)*.088/W);
     const c=tonePixel(trace,t+.106+(x+.5)*.044/W)-128;
     if(row%2===0)redDiff[row][x]=c;
     else blueDiff[row][x]=c;
   }
   rows++;seen++;
   if(onProgress&&row%24===0)onProgress(row,H);
 }
 if(rows<40)throw Error("SSTV audio did not contain enough aligned scan lines for a valid partial image.");
 const pixels=new Uint8ClampedArray(W*H*4);
 for(let y=0;y<H;y++){
  const pair=Math.floor(y/2)*2,ry=redDiff[pair],by=blueDiff[Math.min(H-1,pair+1)];
  for(let x=0;x<W;x++){
    const luminance=Y[y][x],cr=ry[x],cb=by[x],idx=(y*W+x)*4;
    pixels[idx]=clamp(Math.round(luminance+1.403*cr));
    pixels[idx+1]=clamp(Math.round(luminance-.714*cr-.344*cb));
    pixels[idx+2]=clamp(Math.round(luminance+1.773*cb));
    pixels[idx+3]=255;
  }
 }
 return {
   width:W,height:H,rgba:pixels,alignedLines:rows,
   syncCandidates:syncs.length,firstSyncSeconds:Number(alignment.start.toFixed(4)),
   status:rows>=225?"Robot36 candidate decoded":"Partial Robot36 sync candidate (image may be incomplete)",
   warning:"Experimental Robot36 WAV demodulation. Requires a real FM-demodulated SSTV audio signal and clear 1200 Hz line syncs. VIS code and satellite origin are not independently verified; picture quality and colors may be inaccurate."
 };
}

export function decodeRobot36Audio(samples,rate,options={}){
 if(samples.length/rate<32)throw Error("Robot36 needs about 36 seconds of demodulated SSTV audio.");
 const trace=frequencyTrace(samples,rate);
 return decodeRobot36Trace(trace,options);
}
