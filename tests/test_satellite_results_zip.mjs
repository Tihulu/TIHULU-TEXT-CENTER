import test from "node:test";
import assert from "node:assert/strict";
import {createResultsZip,zipEntryName} from "../satellite_center/browser/results_zip.mjs";

test("ZIP contains real files and a valid stored central directory",async()=>{
 const archive=await createResultsZip([
  {name:"manifest.json",data:'{"source":"user-imported_unverified"}'},
  {name:"text/messages.txt",data:"packet candidate"},
  {name:"images/example.png",blob:new Blob([Uint8Array.of(137,80,78,71)])},
 ]);
 const data=new Uint8Array(await archive.arrayBuffer()),view=new DataView(data.buffer);
 assert.equal(view.getUint32(0,true),0x04034b50);
 assert.equal(view.getUint32(data.length-22,true),0x06054b50);
 assert.equal(view.getUint16(data.length-22+10,true),3);
 const dir=view.getUint32(data.length-22+16,true);
 assert.equal(view.getUint32(dir,true),0x02014b50);
 assert.equal(view.getUint16(8,true),0);
 const name=new TextDecoder().decode(data.slice(30,30+view.getUint16(26,true)));
 assert.equal(name,"manifest.json");
 assert.equal(archive.type,"application/zip");
 assert.ok(data.length>60);
});
test("ZIP rejects duplicate paths, traversal and unbounded exports",async()=>{
 assert.throws(()=>zipEntryName("../secret"),/Unsafe/);
 assert.throws(()=>zipEntryName("a\\secret"),/Unsafe/);
 await assert.rejects(createResultsZip([{name:"same.txt",data:"a"},{name:"same.txt",data:"b"}]),/Duplicate/);
 await assert.rejects(createResultsZip([{name:"raw.cu8",data:"hello world"}],{maxBytes:5}),/exceed/);
});
test("ZIP aborts and does not misstate a successful download",async()=>{
 const controller=new AbortController();controller.abort();
 await assert.rejects(createResultsZip([{name:"manifest.json",data:"actual evidence"}],{
  signal:controller.signal}),/cancelled/);
});
