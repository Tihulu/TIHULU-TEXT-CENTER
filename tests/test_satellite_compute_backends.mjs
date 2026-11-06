import test from "node:test";
import assert from "node:assert/strict";
import {chooseComputePlan,probeBrowserCompute,COMPUTE_TARGETS} from "../satellite_center/browser/compute_backends.mjs";
import fs from "node:fs";

const caps={
 cpu:{available:true,name:"Portable CPU"},
 gpu:{available:true,name:"Real WebGPU"},
 npu:{available:false,reason:"No Robot36 accelerator kernel"},
};
test("Automatic optimize mode picks CPU for short and CPU+GPU for long",()=>{
 assert.deepEqual(chooseComputePlan({capabilities:caps,seconds:35}).selectedTargets,["cpu"]);
 assert.deepEqual(chooseComputePlan({capabilities:caps,seconds:140}).selectedTargets,["cpu","gpu"]);
 assert.equal(chooseComputePlan({capabilities:{...caps,gpu:{available:false}},seconds:140}).traceBackend,"cpu");
});
test("CPU+GPU custom multi selection is allowed but NPU cannot fake a result",()=>{
 assert.equal(chooseComputePlan({mode:"custom",targets:["cpu","gpu"],capabilities:caps}).traceBackend,"webgpu");
 assert.equal(chooseComputePlan({mode:"custom",targets:["gpu"],capabilities:caps}).cpuStages.includes("pixel decoding"),true);
 assert.throws(()=>chooseComputePlan({mode:"custom",targets:["cpu","npu"],capabilities:caps}),/NPU/);
 assert.throws(()=>chooseComputePlan({mode:"custom",targets:[],capabilities:caps}),/at least one/);
 assert.deepEqual(COMPUTE_TARGETS,["cpu","gpu","npu"]);
});
test("No WebGPU in Node means no invented GPU or NPU capability",async()=>{
 const capability=await probeBrowserCompute();
 assert.equal(capability.cpu.available,true);
 assert.equal(capability.gpu.available,false);
 assert.equal(capability.npu.available,false);
});
test("Both user-facing analysis routes offer working controls",()=>{
 for(const page of ["index.html","reception.html"]){
  const html=fs.readFileSync(new URL("../satellite_center/browser/"+page,import.meta.url),"utf8");
  const prefix=page==="index.html"?"iq":"auto";
  for(const field of ["mode","cpu","gpu","npu","status"])
   assert.match(html,new RegExp('id="'+prefix+'-compute-'+field+'"'));
  assert.match(html,/Auto — optimized for this device/);
 }
 const signal=fs.readFileSync(new URL("../satellite_center/browser/signal_discovery.mjs",import.meta.url),"utf8");
 assert.match(signal,/decodeRobot36WithCompute/);
 const ui=fs.readFileSync(new URL("../satellite_center/browser/auto_reception_ui.mjs",import.meta.url),"utf8");
 assert.match(ui,/compute_mode:processing.mode/);
});
