import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {WinTVProbe,WINTV} from "../webusb-em28xx.js";
import {WINTV_UDEV_RULE,LINUX_SETUP_COMMANDS,classifyUsbFailure}
  from "../webusb-access-guide.js";

test("opening USB denied is OS permissions, not an RF/scan error",async()=>{
  const device={vendorId:WINTV.vendorId,productId:WINTV.productId,
    opened:false,configurations:[],async open(){
      const err=new Error("Access denied.");err.name="SecurityError";
      throw err;
    }};
  const probe=new WinTVProbe();probe.device=device;
  await assert.rejects(probe.openForRead(),err=>{
    assert.equal(err.usbStage,"open");
    assert.equal(err.usbReason,"os_usb_open_denied");
    assert.match(err.message,/udev|Linux/i);
    return true;
  });
  assert.equal(probe.lastErrorStage,"open");
  assert.equal(probe.claimed,null);
  assert.equal(probe.device,device);
});
test("kernel-owned interface is a distinct claim error after successful open",async()=>{
  const device={vendorId:WINTV.vendorId,productId:WINTV.productId,
    opened:true,configurations:[{configurationValue:1,interfaces:[{
      interfaceNumber:0,alternates:[{alternateSetting:0,endpoints:[{
        type:"bulk",direction:"in",endpointNumber:2,packetSize:512
      }]}]
    }]}],configuration:{configurationValue:1},
    async claimInterface(){throw Error("Unable to claim interface: busy");}};
  const probe=new WinTVProbe();probe.device=device;
  await assert.rejects(probe.claimBulk(),err=>{
    assert.equal(err.usbStage,"claim");
    assert.equal(err.usbReason,"usb_interface_unavailable");
    assert.match(err.message,/kernel|driver|interface/i);
    return true;
  });
  assert.equal(probe.lastErrorStage,"claim");
  assert.equal(probe.claimed,null);
});
test("only target WinTV device gets Linux uaccess, never MODE 0666",()=>{
  assert.match(WINTV_UDEV_RULE,/ATTR\{idVendor\}=="2040"/);
  assert.match(WINTV_UDEV_RULE,/ATTR\{idProduct\}=="8268"/);
  assert.match(WINTV_UDEV_RULE,/TAG\+="uaccess"/);
  assert.match(WINTV_UDEV_RULE,/MODE="0660"/);
  assert.doesNotMatch(LINUX_SETUP_COMMANDS,/0666|modprobe -r|unbind|chmod 777/);
  assert.match(LINUX_SETUP_COMMANDS,/sudo udevadm control --reload-rules/);
});
test("WebUSB errors do not conflate user cancel, open and claim",()=>{
  assert.equal(classifyUsbFailure({name:"NotFoundError",message:"No device selected"},"select").code,"user_cancelled");
  assert.equal(classifyUsbFailure({name:"SecurityError",message:"Access denied"},"open").code,"os_usb_open_denied");
  assert.equal(classifyUsbFailure({name:"Error",message:"Interface busy"},"claim").code,"usb_interface_unavailable");
  assert.equal(classifyUsbFailure({message:"Unrecognized data"},"control").code,"usb_operation_failed");
});
test("Pages has no-privilege actionable instructions for hardware open errors",()=>{
  const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
  const js=readFileSync(new URL("../webusb-ui.js",import.meta.url),"utf8");
  for(const id of ["webusb-access-help","webusb-help-title","webusb-help-udev",
    "webusb-copy-udev","webusb-help-claim-block"])
    assert.ok(html.includes('id="'+id+'"'));
  assert.match(js,/showUsbHelp/);
  assert.match(js,/classifyUsbFailure/);
  assert.doesNotMatch(js,/detachKernelDriver|modprobe -r|chmod 777/);
});
