// Browser-only, read-only USB preflight and error guidance.
// No native service, subprocess, device claim, or OS setting is changed here.
export function platformFamily(ua = "") {
  const value=String(ua).toLowerCase();
  if(/windows|win32|win64/.test(value)) return "windows";
  if(/macintosh|mac os|darwin/.test(value)) return "mac";
  if(/linux|x11/.test(value)) return "linux";
  if(/android/.test(value)) return "android";
  return "unknown";
}

export function webUsbHelp(error, platform = "unknown") {
  const name=String(error?.name || "Error");
  const message=String(error?.message || error || "Unknown USB error");
  const text=(name+" "+message).toLowerCase();
  let reason = "The browser could not initialize this RTL-SDR. The USB permission prompt is not proof that the operating system granted exclusive access.";
  if(/notfounderror|no device selected|user cancelled|user canceled/.test(text)) {
    reason = "The USB chooser was cancelled or no suitable RTL2832U receiver was selected. Nothing was opened.";
  } else if(/securityerror|notallowederror|access denied|permission denied/.test(text)) {
    reason = "The operating system or browser denied USB access. WebUSB permission cannot override system USB device permissions.";
  } else if(/could not connect|claiminterface|unable to claim|resource busy|device busy|libusb_error_busy|interface.*claimed/.test(text)) {
    reason = "The USB interface could not be claimed. Most commonly another SDR application or a Linux DVB kernel driver owns the device; missing USB permissions are also possible.";
  }
  const lines=[
    reason,
    "Browser-only app: no Python service, local bridge, app installation, or pairing token needed.",
    "1. Close Flight Radar, Gqrx, SDR++, welle.io, rtl_test, and any other program using this *same* dongle.",
    "2. Unplug the RTL-SDR, reconnect it, reload this HTTPS tab, and choose the Nooelec / Realtek receiver again."
  ];
  if(platform==="linux") {
    lines.push(
      "Pop!_OS / Debian / Raspberry Pi OS (only if readsb is yours and you want to pause it):",
      "   sudo systemctl stop readsb.service",
      "   systemctl is-active readsb.service",
      "   The second command should say inactive. Neither command installs software.",
      "If still blocked, inspect (read-only):",
      "   lsusb -d 0bda:2838",
      "   lsusb -t",
      "If lsusb -t shows Driver=dvb_usb_rtl28xxu, the Linux TV kernel driver owns it.",
      "If there is no conflicting driver, the USB device-file permissions may need a one-time OS-level udev fix.",
      "A website cannot run sudo, unbind a kernel driver, change udev rules, or stop readsb."
    );
  } else if(platform==="windows") {
    lines.push("Windows may require a WinUSB-compatible RTL-SDR driver set up in Windows. No website can install/replace a USB driver.");
  } else if(platform==="mac") {
    lines.push("On macOS, close any existing RTL-SDR application, disconnect/reconnect the receiver, and retry in a Chromium browser.");
  } else {
    lines.push("Check whether another USB owner or device permissions prevent the claim. OS-specific setup may be necessary.");
  }
  lines.push("Original browser-driver error: "+name+": "+message);
  return lines.join("\n");
}

export async function permissionReport(usb, platform = "unknown") {
  if(!usb || typeof usb.getDevices!=="function")
    return "WebUSB is unavailable. Use a supported Chromium browser over HTTPS.";
  try {
    const list=await usb.getDevices();
    const approved=list.filter(d=>d.vendorId===0x0bda &&
      [0x2838,0x2832].includes(d.productId));
    return [
      "Platform: "+platform+". HTTPS WebUSB: available.",
      "Previously permitted USB devices: "+list.length+
        "; RTL2832U candidates: "+approved.length+".",
      ...(approved.map(d=>"Permitted RTL-SDR: "+
        d.vendorId.toString(16).padStart(4,"0")+":"+
        d.productId.toString(16).padStart(4,"0")+
        " — "+String(d.productName || "unnamed").slice(0,80))),
      "This is a read-only list of permission grants, not a USB claim, RF reception test, or proof that the SDR is free.",
      "Click Choose RTL-SDR to request/open the USB device. No background capture starts."
    ].join("\n");
  } catch(error) {
    return "Browser refused the read-only USB permission check: "+
      String(error?.message || error);
  }
}
