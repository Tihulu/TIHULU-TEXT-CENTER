import test from "node:test";
import assert from "node:assert/strict";
import {platformFamily, webUsbHelp, permissionReport} from "./usb_diagnostics.mjs";

test("detects browser OS accurately",()=>{
  assert.equal(platformFamily("Mozilla/5.0 (X11; Linux x86_64) Chrome/150"),"linux");
  assert.equal(platformFamily("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15)"),"mac");
  assert.equal(platformFamily("Mozilla/5.0 (Windows NT 10.0; Win64)"),"windows");
  assert.equal(platformFamily("Mozilla/5.0 (Linux; Android 16)"),"android");
});

test("busy USB claim explains readsb and does not offer automatic service control",()=>{
  const advice=webUsbHelp({name:"NetworkError",message:"Could not connect to the RTL-SDR stick"},"linux");
  assert.match(advice,/readsb/);
  assert.match(advice,/systemctl stop readsb.service/);
  assert.match(advice,/No.*service|no Python service/i);
  assert.match(advice,/website cannot run sudo/);
  assert.doesNotMatch(advice,/killall|sudo chmod 777|MODE="0666"/);
});

test("cancelled browser chooser is not treated as a kernel claim failure",()=>{
  const advice=webUsbHelp({name:"NotFoundError",message:"No device selected"},"linux");
  assert.match(advice,/cancelled/);
});

test("reads existing grants only, never claims or opens a receiver",async()=>{
  let called=0;
  const response=await permissionReport({
    async getDevices(){
      called++;
      return [{vendorId:0x0bda,productId:0x2838,productName:"Nooelec NESDR SMArt v5"}];
    },
    async requestDevice(){throw Error("must never request here")},
    async open(){throw Error("must never open here")}
  },"linux");
  assert.equal(called,1);
  assert.match(response,/0bda:2838/);
  assert.match(response,/not a USB claim/);
});

test("no WebUSB API yields honest unsupported message",async()=>{
  const response=await permissionReport(undefined,"linux");
  assert.match(response,/WebUSB is unavailable/);
});
