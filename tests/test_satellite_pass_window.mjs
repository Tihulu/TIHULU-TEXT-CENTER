import test from "node:test";
import assert from "node:assert/strict";
import {validatedWindow,windowContains,windowSummary}
 from "../satellite_center/browser/pass_window.mjs";

const w={az:300,half:30,min:10,max:40};
test("optional pass window validates angles and wraps north",()=>{
 assert.equal(validatedWindow(null),null);
 assert.throws(()=>validatedWindow({...w,half:0}),/Window/);
 assert.equal(windowContains(320,20,w),true);
 assert.equal(windowContains(20,20,w),false);
 assert.equal(windowContains(5,20,{...w,az:355}),true);
});
test("pass windows classify actual sampled geometric overlaps",()=>{
 const inside=Array.from({length:25},(_,i)=>({ms:i*10000,az:300,el:20}));
 const result=windowSummary(inside,w);
 assert.equal(result.seconds,240);
 assert.equal(result.status,"good_geometry");
 assert.equal(result.segments.length,1);
 const outside=windowSummary([{ms:0,az:90,el:20}],w);
 assert.equal(outside.status,"outside");
 assert.equal(outside.seconds,0);
});
