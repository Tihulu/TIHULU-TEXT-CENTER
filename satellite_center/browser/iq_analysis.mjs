/* TIHULU CU8 RF analysis — browser-native, receive-only, no uploads.
 * Input: unsigned, interleaved I,Q bytes; zero power is approximately
 * (I=127.5,Q=127.5). Spectrum is UNCALIBRATED relative digital power.
 * This is NOT demodulation, satellite identification, APRS, LRPT or SSTV.
 */
const FFT_N=2048;
const CAPTURE_BLOCK_BYTES=FFT_N*2;
const MAX_WINDOWS=48;
function validRate(rate){return Number.isFinite(rate)&&rate>=200000&&rate<=3200000;}
function dB(power){return 10*Math.log10(Math.max(power,1e-15));}
function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
export function parseCu8Filename(name){
 // v14+: explicitly embedded satellite candidate, UTC, center and sample rate.
 // Legacy TIHULU-<frequency>-<rate>-... recordings are still supported.
 const modern=String(name||"").match(/^TIHULU_[A-Z0-9-]+_\d{8}T\d{6}Z_(\d{7,11})Hz_(\d{6,8})SPS_[A-Z0-9-]+\.cu8$/i);
 const m=modern||String(name||"").match(/(?:^|\/)TIHULU-(?:scheduled-)?(\d{7,11})-(\d{6,8})-[^/]*\.cu8$/i);
 if(!m)return null;
 const centerHz=Number(m[1]),sampleRate=Number(m[2]);
 if(!Number.isFinite(centerHz)||centerHz<24000000||centerHz>1750000000||!validRate(sampleRate))return null;
 return {centerHz,sampleRate};
}
export function fftComplex(re,im){
 const n=re.length;
 if(n<2||(n&(n-1))!==0||n!==im.length)throw Error("FFT requires equal power-of-two complex arrays.");
 for(let i=1,j=0;i<n;i++){
   let bit=n>>1;
   for(;j&bit;bit>>=1)j^=bit;
   j^=bit;
   if(i<j){[re[i],re[j]]=[re[j],re[i]];[im[i],im[j]]=[im[j],im[i]];}
 }
 for(let span=2;span<=n;span*=2){
   const angle=-2*Math.PI/span,wr=Math.cos(angle),wi=Math.sin(angle);
   for(let off=0;off<n;off+=span){
     let ur=1,ui=0;
     for(let j=0;j<span/2;j++){
       const i=off+j,k=i+span/2,vr=ur*re[k]-ui*im[k],vi=ur*im[k]+ui*re[k];
       re[k]=re[i]-vr;im[k]=im[i]-vi;
       re[i]+=vr;im[i]+=vi;
       const nr=ur*wr-ui*wi;ui=ur*wi+ui*wr;ur=nr;
     }
   }
 }
}
function spectrumOfBlock(bytes){
 if(!(bytes instanceof Uint8Array)||bytes.byteLength<CAPTURE_BLOCK_BYTES)throw Error("Need at least 4096 interleaved CU8 bytes per FFT.");
 const re=new Float64Array(FFT_N),im=new Float64Array(FFT_N);
 let meanI=0,meanQ=0,sampleEnergy=0,clipped=0;
 for(let i=0;i<FFT_N;i++){
   const I=bytes[i*2],Q=bytes[i*2+1];
   const ri=(I-127.5)/128,rq=(Q-127.5)/128;
   meanI+=ri;meanQ+=rq;sampleEnergy+=ri*ri+rq*rq;
   if(I<=1||I>=254||Q<=1||Q>=254)clipped++;
   re[i]=ri;im[i]=rq;
 }
 meanI/=FFT_N;meanQ/=FFT_N;
 let windowEnergy=0;
 for(let i=0;i<FFT_N;i++){
   const w=0.5-0.5*Math.cos(2*Math.PI*i/(FFT_N-1));
   windowEnergy+=w*w;
   re[i]=(re[i]-meanI)*w;
   im[i]=(im[i]-meanQ)*w;
 }
 fftComplex(re,im);
 const power=new Float64Array(FFT_N);
 const norm=FFT_N*windowEnergy;
 for(let i=0;i<FFT_N;i++){
   const shifted=(i+FFT_N/2)%FFT_N;
   power[shifted]=(re[i]*re[i]+im[i]*im[i])/norm;
 }
 return {power,energy:sampleEnergy/FFT_N,meanI,meanQ,clipped,complexPairs:FFT_N};
}
function median(values){
 const sorted=Array.from(values).filter(Number.isFinite).sort((a,b)=>a-b);
 if(!sorted.length)return null;
 const mid=Math.floor(sorted.length/2);
 return sorted.length%2?sorted[mid]:(sorted[mid-1]+sorted[mid])/2;
}
export function analyzeIqWindows(chunks,{sampleRate,centerHz=null,totalBytes=null}={}){
 if(!validRate(Number(sampleRate)))throw Error("Enter a valid sample rate in samples/second.");
 if(centerHz!==null&&(!Number.isFinite(centerHz)||centerHz<24000000||centerHz>1750000000))
   throw Error("Center frequency must be a valid RTL-SDR receive frequency or explicitly unknown.");
 if(!Array.isArray(chunks)||!chunks.length)throw Error("No CU8 blocks to analyze.");
 const combined=new Float64Array(FFT_N);
 const powerHistory=[],waterfall=[],dcI=[],dcQ=[];
 let clipped=0,pairs=0;
 for(const raw of chunks){
   const bytes=raw instanceof Uint8Array?raw:new Uint8Array(raw);
   const block=spectrumOfBlock(bytes);
   for(let i=0;i<FFT_N;i++)combined[i]+=block.power[i];
   const level=dB(block.energy);
   powerHistory.push(Number(level.toFixed(2)));
   dcI.push(block.meanI);dcQ.push(block.meanQ);
   clipped+=block.clipped;pairs+=block.complexPairs;
   // 256 pixels per row, averaged over 8 adjacent complex FFT bins.
   const line=[];
   for(let i=0;i<256;i++){
     let sum=0;for(let k=0;k<8;k++)sum+=block.power[i*8+k];
     line.push(Number(dB(sum/8).toFixed(1)));
   }
   waterfall.push(line);
 }
 const spectrum=Array.from(combined,x=>dB(x/chunks.length));
 const rowWidth=Number(sampleRate)/FFT_N;
 const skip=4; // do not misidentify residual center/DC component as RF
 let strongest=-Infinity,peakBin=null;
 for(let i=1;i<FFT_N-1;i++){
   if(Math.abs(i-FFT_N/2)<=skip)continue;
   if(spectrum[i]>strongest){strongest=spectrum[i];peakBin=i;}
 }
 const medianPower=median(spectrum.filter((v,i)=>Math.abs(i-FFT_N/2)>skip));
 const peakOffsetHz=peakBin==null?null:(peakBin-FFT_N/2)*rowWidth;
 const peakFrequencyHz=centerHz!==null&&peakOffsetHz!==null?centerHz+peakOffsetHz:null;
 const nominalBytes=Number.isFinite(totalBytes)?totalBytes:chunks.reduce((n,c)=>n+c.length,0);
 const durationSec=nominalBytes/(Number(sampleRate)*2);
 const dcOffset={
   i:Number((dcI.reduce((a,b)=>a+b,0)/dcI.length).toFixed(5)),
   q:Number((dcQ.reduce((a,b)=>a+b,0)/dcQ.length).toFixed(5))
 };
 return {
   format:"unsigned 8-bit interleaved complex I/Q (CU8)",
   sampleRate:Number(sampleRate),centerFrequencyHz:centerHz,totalBytes:nominalBytes,
   estimatedSeconds:Number(durationSec.toFixed(3)),
   windows:chunks.length,fftSize:FFT_N,frequencyResolutionHz:Number(rowWidth.toFixed(3)),
   averageRelativeLevelDb:Number((powerHistory.reduce((a,b)=>a+b,0)/powerHistory.length).toFixed(2)),
   minRelativeLevelDb:Math.min(...powerHistory),maxRelativeLevelDb:Math.max(...powerHistory),
   peakOffsetHz:peakOffsetHz==null?null:Number(peakOffsetHz.toFixed(1)),
   peakFrequencyHz:peakFrequencyHz==null?null:Number(peakFrequencyHz.toFixed(1)),
   peakVsMedianDb:Number((strongest-medianPower).toFixed(2)),
   clippedComplexPairsPercent:Number((100*clipped/pairs).toFixed(3)),
   meanDcOffset:dcOffset,
   spectrumDb:spectrum.map(x=>Number(x.toFixed(2))),
   powerHistoryDb:powerHistory,waterfallDb:waterfall,
   warning:"Frequency, estimated duration and peak placement depend on correct sample rate and center-frequency metadata. CU8 contains NO embedded frequency, sample rate or timestamps. A narrow spectral peak is NOT a confirmed satellite nor a decoded signal. No absolute dBm, SNR calibration or gap-free timing is claimed."
 };
}
export async function analyzeCu8Blob(file,{sampleRate,centerHz=null,maxWindows=32,onProgress=()=>{}}={}){
 if(!file||typeof file.slice!=="function"||typeof file.arrayBuffer!=="function")
   throw Error("Choose a real CU8 file or use a recent in-browser recording.");
 if(!Number.isFinite(file.size)||file.size<CAPTURE_BLOCK_BYTES)
   throw Error("CU8 file too short for a 2048-point spectrum (minimum 4096 bytes).");
 if(file.size%2!==0)throw Error("CU8 file has an odd number of bytes; missing a complete I/Q pair.");
 if(!validRate(Number(sampleRate)))throw Error("Invalid sample rate; choose 1.024 or 2.048 MS/s for captured files.");
 const windows=Math.min(Math.max(1,Math.floor(maxWindows)),MAX_WINDOWS,
   Math.floor(file.size/CAPTURE_BLOCK_BYTES));
 const pieces=[],maximumOffset=file.size-CAPTURE_BLOCK_BYTES;
 for(let i=0;i<windows;i++){
   // Stratified sampling covers both beginning and end of a large recording;
   // only ~128 KiB is read even for a 128 MiB file.
   let offset=windows===1?0:Math.floor(i*maximumOffset/(windows-1));
   offset-=offset%2;
   const buffer=await file.slice(offset,offset+CAPTURE_BLOCK_BYTES).arrayBuffer();
   if(buffer.byteLength!==CAPTURE_BLOCK_BYTES)throw Error("Unexpected end of CU8 file.");
   pieces.push(new Uint8Array(buffer));
   if(i%8===0||i===windows-1){
     onProgress(i+1,windows);
     await new Promise(resolve=>setTimeout(resolve,0));
   }
 }
 const report=analyzeIqWindows(pieces,{sampleRate:Number(sampleRate),centerHz,totalBytes:file.size});
 report.sampledBytes=windows*CAPTURE_BLOCK_BYTES;
 report.sampledFraction=Number((report.sampledBytes/file.size).toFixed(5));
 return report;
}
