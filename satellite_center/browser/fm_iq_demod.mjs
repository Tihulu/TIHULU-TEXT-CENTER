/* Receive-only FM audio recovery from RTL2832U unsigned CU8.
 * This is an experimental 2-stage decimating FM discriminator intended for
 * SSTV narrowband FM. It is NOT an LRPT, APRS or arbitrary image decoder.
 * Processing is bounded/chunked; no uploaded or fabricated samples.
 */
export async function cu8ToFmAudio(file,{sampleRate=1024000,onProgress=()=>{}}={}){
 if(!file||typeof file.slice!=="function"||!Number.isSafeInteger(file.size))
  throw Error("Select a real local CU8 file or browser recording.");
 if(file.size%2)throw Error("CU8 must contain complete unsigned I/Q byte pairs.");
 if(![1024000,2048000].includes(sampleRate))
  throw Error("FM SSTV decoder supports 1.024 or 2.048 MS/s CU8 only.");
 if(file.size<2*sampleRate*32)
  throw Error("Need at least 32 seconds of RF samples for Robot36 SSTV.");
 const limit=Math.min(2*sampleRate*180,384*1024*1024);
 if(file.size>limit)throw Error("This SSTV FM decoder limits input to three minutes of IQ.");
 const firstDecimate=sampleRate/64000,outputRate=16000;
 const expected=Math.floor(file.size/2/(sampleRate/outputRate));
 const samples=new Float32Array(expected+2);
 let n=0,boxI=0,boxQ=0,boxCount=0;
 let prevI=0,prevQ=0,hasPrev=false;
 let dc=0,phaseAccum=0,phaseCount=0,meanSquare=0;
 const chunkSize=512*1024;
 for(let offset=0;offset<file.size;offset+=chunkSize){
   const bytes=new Uint8Array(await file.slice(offset,Math.min(offset+chunkSize,file.size)).arrayBuffer());
   for(let j=0;j<bytes.length-1;j+=2){
     boxI+=(bytes[j]-127.5)/128;
     boxQ+=(bytes[j+1]-127.5)/128;
     boxCount++;
     if(boxCount<firstDecimate)continue;
     let I=boxI/firstDecimate,Q=boxQ/firstDecimate;
     boxI=0;boxQ=0;boxCount=0;
     if(hasPrev){
       const cross=Q*prevI-I*prevQ,real=I*prevI+Q*prevQ;
       phaseAccum+=Math.atan2(cross,real);
       phaseCount++;
       if(phaseCount===4){
         const value=phaseAccum/4;
         dc+=.0004*(value-dc);
         const normalized=(value-dc);
         if(n<samples.length){samples[n++]=normalized;meanSquare+=normalized*normalized;}
         phaseAccum=0;phaseCount=0;
       }
     }
     hasPrev=true;prevI=I;prevQ=Q;
   }
   if(offset%(chunkSize*16)===0||offset+chunkSize>=file.size){
     onProgress(Math.min(file.size,offset+bytes.length),file.size);
     await new Promise(resolve=>setTimeout(resolve,0));
   }
 }
 if(n<outputRate*32)throw Error("Fewer than 32 seconds of successfully demodulated FM audio.");
 const rms=Math.sqrt(meanSquare/Math.max(n,1));
 if(!Number.isFinite(rms)||rms<1e-8)throw Error("No usable changing FM signal; the file may contain silence or a wrong band.");
 const gain=Math.min(10,0.35/rms),audio=samples.subarray(0,n);
 for(let i=0;i<n;i++)audio[i]=Math.max(-1,Math.min(1,audio[i]*gain));
 return {samples:audio,rate:outputRate,
   diagnostic:{inputBytes:file.size,outputSamples:n,
     seconds:Number((n/outputRate).toFixed(2)),rawRms:Number(rms.toFixed(7)),
     warning:"Uncalibrated narrowband-FM SSTV audio estimate from RF CU8. No guarantee the target ISS transmitted or SSTV synchronization exists."}};
}
