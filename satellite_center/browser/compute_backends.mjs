/* Real, auditable SSTV compute backends. NPU remains unavailable until
 * a compatible SSTV DSP kernel/model exists. A browser's GPU adapter does
 * not imply CUDA, and a chipset NPU does not imply Robot36 acceleration.
 * All audio/frames stay on this device. */
import {frequencyTrace, decodeRobot36Trace} from "./sstv_robot36.mjs";

export const COMPUTE_TARGETS=Object.freeze(["cpu","gpu","npu"]);
export function chooseComputePlan({mode="auto",targets=["cpu"],capabilities,seconds=0}={}){
 if(!capabilities||!capabilities.cpu?.available)throw Error("CPU SSTV decoder not available");
 if(!["auto","custom"].includes(mode))throw Error("Invalid compute mode");
 if(!Array.isArray(targets)||new Set(targets).size!==targets.length||
     targets.some(x=>!COMPUTE_TARGETS.includes(x)))throw Error("Invalid CPU/GPU/NPU selection");
 if(mode==="custom"&&!targets.length)throw Error("Select at least one compute backend");
 let selected=mode==="auto"?
   (seconds>=50&&capabilities.gpu?.available?["cpu","gpu"]:["cpu"]):[...targets];
 const missing=selected.filter(x=>!capabilities[x]?.available);
 if(missing.length)throw Error("Unsupported decoder backend: "+missing.map(x=>
   x.toUpperCase()+" — "+(capabilities[x]?.reason||"No working decoder")).join("; "));
 return {mode,selectedTargets:selected,traceBackend:selected.includes("gpu")?"webgpu":"cpu",
   cpuStages:["file I/O","Robot36 synchronization","pixel decoding","PNG generation"],
   note:selected.includes("gpu")?"WebGPU accelerates tone tracing; CPU still validates scanlines and builds pixels.":
     "All decoded samples are processed by the CPU; no GPU/NPU use is claimed."};
}
let cachedProbe=null;
export async function probeBrowserCompute({refresh=false}={}){
 if(!refresh&&cachedProbe)return cachedProbe;
 const cpu={available:true,name:"CPU",reason:"Portable Robot36 decoder"};
 const gpu={available:false,name:"WebGPU",reason:"No usable WebGPU compute adapter"};
 const npu={available:false,name:"NPU",reason:"No compatible Robot36 NPU DSP kernel/model implemented"};
 try{
   if(globalThis.navigator?.gpu){
     const adapter=await globalThis.navigator.gpu.requestAdapter({powerPreference:"high-performance"});
     if(adapter){
       const device=await adapter.requestDevice();
       // Device capability is checked again against audio buffer limits at run time.
       gpu.available=true;gpu.reason="";
       gpu.maxBindingBytes=device.limits.maxStorageBufferBindingSize;
       device.destroy();
     }
   }
 }catch(error){gpu.reason="WebGPU cannot start: "+String(error?.message||error).slice(0,100);}
 cachedProbe={cpu,gpu,npu};
 return cachedProbe;
}

// 64 work items per workgroup; each item calculates one 1ms audio-frequency
// cell from actual PCM zero crossings over +/-3ms. Never generates test audio.
const WGSL=`
struct Config { rate:u32, sampleCount:u32, traceCount:u32, pad:u32 };
@group(0) @binding(0) var<storage,read> pcm:array<f32>;
@group(0) @binding(1) var<storage,read_write> trace:array<f32>;
@group(0) @binding(2) var<uniform> cfg:Config;
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid:vec3<u32>){
 let n=gid.x;
 if(n>=cfg.traceCount){return;}
 let center=(f32(n)+0.5)/1000.0;
 let a=center-0.003;
 let b=center+0.003;
 let beginning=max(1,i32(floor(a*f32(cfg.rate)))-2);
 let ending=min(i32(cfg.sampleCount)-1,i32(ceil(b*f32(cfg.rate)))+2);
 var count:u32=0u;
 var first:f32=0.0;
 var last:f32=0.0;
 for(var i=beginning;i<=ending;i=i+1){
   let left=pcm[u32(i-1)];
   let right=pcm[u32(i)];
   if(left<0.0&&right>=0.0){
     let fraction=-left/max(0.00000001,right-left);
     let at=(f32(i-1)+fraction)/f32(cfg.rate);
     if(at>=a&&at<=b){
       if(count==0u){first=at;}
       last=at;
       count=count+1u;
     }
   }
 }
 if(count>=5u&&last>first){
   let hz=(f32(count)-1.0)/(last-first);
   trace[n]=clamp(hz,400.0,4000.0);
 }else{trace[n]=0.0;}
}
`;
export async function frequencyTraceWebGpu(samples,rate,{signal=null}={}){
 if(!(samples instanceof Float32Array)||!Number.isFinite(rate)||rate<8000||rate>192000)
   throw Error("WebGPU needs actual Float32 PCM and 8–192 kHz sample rate");
 if(samples.length/rate>240)throw Error("Robot36 audio input longer than 4 minutes");
 if(signal?.aborted)throw Error("GPU processing cancelled");
 const gpu=globalThis.navigator?.gpu;
 if(!gpu)throw Error("WebGPU unavailable; use CPU or local native companion");
 const adapter=await gpu.requestAdapter({powerPreference:"high-performance"});
 if(!adapter)throw Error("No WebGPU compute adapter");
 const device=await adapter.requestDevice();
 const buffers=[];
 try{
   const count=Math.floor(samples.length/rate*1000),srcBytes=samples.byteLength,dstBytes=count*4;
   if(srcBytes>device.limits.maxStorageBufferBindingSize||dstBytes>device.limits.maxStorageBufferBindingSize)
     throw Error("WebGPU PCM buffer exceeds device storage limit; choose CPU or native GPU processing");
   if(!count)throw Error("No audio samples");
   const BU=globalThis.GPUBufferUsage;
   if(!BU)throw Error("WebGPU buffer constants unavailable");
   const make=(size,usage)=>{const b=device.createBuffer({size,usage});buffers.push(b);return b;};
   const input=make(srcBytes,BU.STORAGE|BU.COPY_DST),
         output=make(dstBytes,BU.STORAGE|BU.COPY_SRC),
         settings=make(16,BU.UNIFORM|BU.COPY_DST),
         readback=make(dstBytes,BU.COPY_DST|BU.MAP_READ);
   device.queue.writeBuffer(input,0,samples);
   device.queue.writeBuffer(settings,0,new Uint32Array([rate,samples.length,count,0]));
   const module=device.createShaderModule({code:WGSL});
   const pipeline=device.createComputePipeline({layout:"auto",compute:{module,entryPoint:"main"}});
   const group=device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:[
     {binding:0,resource:{buffer:input}},{binding:1,resource:{buffer:output}},
     {binding:2,resource:{buffer:settings}}]});
   const encoder=device.createCommandEncoder(),pass=encoder.beginComputePass();
   pass.setPipeline(pipeline);pass.setBindGroup(0,group);
   pass.dispatchWorkgroups(Math.ceil(count/64));pass.end();
   encoder.copyBufferToBuffer(output,0,readback,0,dstBytes);
   device.queue.submit([encoder.finish()]);
   await readback.mapAsync(globalThis.GPUMapMode.READ);
   if(signal?.aborted)throw Error("GPU processing cancelled");
   const trace=new Float32Array(readback.getMappedRange().slice(0));
   readback.unmap();
   return trace;
 }finally{
   for(const b of buffers){try{b.destroy();}catch{}}
   device.destroy();
 }
}
export async function decodeRobot36WithCompute(samples,rate,
    {mode="auto",targets=["cpu"],capabilities=null,signal=null}={}){
 const caps=capabilities||await probeBrowserCompute();
 let plan=chooseComputePlan({mode,targets,capabilities:caps,seconds:samples.length/rate});
 let trace;
 if(plan.traceBackend==="webgpu"){
   try{trace=await frequencyTraceWebGpu(samples,rate,{signal});}
   catch(error){
     if(mode!=="auto")throw error;
     plan={...plan,selectedTargets:["cpu"],traceBackend:"cpu",
       fallbackReason:String(error?.message||error).slice(0,200),
       note:"WebGPU failed; actual CPU trace fallback used."};
   }
 }
 if(!trace)trace=frequencyTrace(samples,rate);
 if(signal?.aborted)throw Error("SSTV processing cancelled");
 return {...decodeRobot36Trace(trace),compute:plan};
}
