// On-demand physical RTL-SDR USB/real-sample check.
// No fabricated samples, no RF identity claim, no external uploads.
// The caller exclusively owns WebUSB open/close and performs cleanup.
export function sampleBytes(raw){
 // Web RTL-SDR v3 returns SampleBlock {frequency,directSampling,data}.
 // Older tools may return an ArrayBuffer or TypedArray directly.
 if(raw && typeof raw==="object" && "data" in raw){
   return sampleBytes(raw.data);
 }
 if(raw instanceof ArrayBuffer)return new Uint8Array(raw);
 if(ArrayBuffer.isView(raw))return new Uint8Array(raw.buffer,raw.byteOffset,raw.byteLength);
 throw Error("Driver returned no raw interleaved USB I/Q bytes.");
}
export function inspectIqBytes(chunks){
 let count=0,sum=0,min=255,max=0,sumSquares=0,numberOfPairs=0;
 for(const data of chunks){
  const bytes=sampleBytes(data);
  if(bytes.length<2||bytes.length%2!==0)throw Error("Invalid USB I/Q block (must contain interleaved I/Q byte pairs).");
  count+=bytes.length;
  for(let i=0;i<bytes.length;i+=32){
   const re=bytes[i]-127.5,im=bytes[i+1]-127.5;
   const energy=(re*re+im*im)/(128*128);
   sumSquares+=energy;
   min=Math.min(min,bytes[i],bytes[i+1]);
   max=Math.max(max,bytes[i],bytes[i+1]);
   sum+=bytes[i]+bytes[i+1];
   numberOfPairs++;
  }
 }
 if(count===0||numberOfPairs===0)throw Error("RTL-SDR returned zero USB sample bytes.");
 const relativeDb=10*Math.log10(Math.max(sumSquares/numberOfPairs,1e-12));
 return {
  rawBytes:count,blocks:chunks.length,approximateComplexPairs:count/2,
  minSample:min,maxSample:max,
  relativeDigitalLevelDb:Number(relativeDb.toFixed(2)),
  sampleSpan:max-min,
  interpretation:"USB I/Q sampling only. Relative power is uncalibrated; no antenna sensitivity, active satellite, weather image or decoded message verified."
 };
}
export async function probeUsbSamples(device,{frequency,rate=1024000,durationMs=3000,onProgress=()=>{}}){
 if(!device||typeof device.readSamples!=="function")throw Error("WebUSB SDR is not opened.");
 if(!Number.isInteger(frequency)||frequency<24000000||frequency>1750000000)throw Error("Invalid RF tuning frequency.");
 if(![1024000,2048000].includes(rate))throw Error("Invalid RTL-SDR test sample rate.");
 const chunks=[],started=Date.now(),deadline=started+Math.max(250,Math.min(3000,durationMs));
 onProgress("Tuning to "+(frequency/1e6).toFixed(3)+" MHz and setting "+(rate/1e6)+" MS/s...");
 await device.setSampleRate(rate);
 await device.setCenterFrequency(frequency);
 await device.setGain(null);
 await device.resetBuffer();
 onProgress("USB interface opened/tuned. Reading actual I/Q samples (not a permission-list check)...");
 while(Date.now()<deadline && chunks.length<80){
  const transfer=device.readSamples(8192);
  let timer;
  const timeout=new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error("USB bulk read timed out after 4 seconds.")),4000);});
  let raw;
  try{raw=await Promise.race([transfer,timeout]);}finally{clearTimeout(timer);}
  const data=sampleBytes(raw);
  if(!data.length)throw Error("RTL-SDR returned empty I/Q samples.");
  chunks.push(new Uint8Array(data));
  if(chunks.length===1||chunks.length%10===0)onProgress("Received "+chunks.reduce((a,x)=>a+x.length,0).toLocaleString()+" real USB bytes...");
  if(chunks.length%8===0)await new Promise(resolve=>setTimeout(resolve,100));
 }
 const result=inspectIqBytes(chunks);
 result.frequencyHz=frequency;
 result.sampleRate=rate;
 result.elapsedSeconds=Number(((Date.now()-started)/1000).toFixed(2));
 return result;
}
