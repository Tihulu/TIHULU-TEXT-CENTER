/* Site-side, non-privileged WebUSB access diagnostics.
 * The browser cannot change udev permissions, Snap confinement or kernel
 * driver ownership. Never pretend a web permission grants system access.
 */
export const WINTV_UDEV_RULE =
  'SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTR{idVendor}=="2040", ATTR{idProduct}=="8268", MODE="0660", TAG+="uaccess"';

export const LINUX_SETUP_COMMANDS = [
  "printf '%s\\n' '"+WINTV_UDEV_RULE+"' | sudo tee /etc/udev/rules.d/70-tihulu-wintv-webusb.rules",
  "sudo udevadm control --reload-rules",
  "# Unplug and reconnect only the Hauppauge USB tuner, then retry Open USB."
].join("\n");

export function classifyUsbFailure(error,stage="unknown"){
  const raw=String(error?.message||error||"Unknown USB error").slice(0,240);
  const name=String(error?.name||"Error");
  const denied=/access denied|permission denied|not permitted|not allowed|securityerror|eacces|eperm/i.test(raw+" "+name);
  const claimed=/claim|busy|in use|resource|kernel|driver|protected interface/i.test(raw);
  if(stage==="open"&&denied){
    return {
      code:"os_usb_open_denied",stage,raw,
      title:"Linux USB device open was denied",
      explanation:"The website permission succeeded, but Chromium could not open the operating-system USB device. Check the specific 2040:8268 udev access rule and whether Chromium is confined by Snap/Flatpak. This error occurs before DVB tuning or the bulk interface claim.",
      next:"Apply the scoped Linux udev rule, reload rules, physically replug the tuner, close/reopen the Chromium tab, then retry Open USB. If Chromium is a Snap, also check its raw-usb interface."
    };
  }
  if(stage==="claim"&&(denied||claimed)){
    return {
      code:"usb_interface_unavailable",stage,raw,
      title:"USB interface could not be claimed",
      explanation:"USB open completed, but the bulk interface is unavailable. Linux em28xx or another process may own it. A udev rule alone cannot detach a kernel driver.",
      next:"Stop TV programs and check Linux's interface driver binding. Do not automatically unload em28xx or detach an active DVB receiver from the web page."
    };
  }
  if(stage==="select"&&(/notfounderror/i.test(name)||/no device selected|user cancelled|cancelled|canceled/i.test(raw))){
    return {code:"user_cancelled",stage,raw,title:"Device selection cancelled",
      explanation:"No USB device was selected. No hardware action was attempted.",
      next:"Choose the 2040:8268 Hauppauge device in Chromium's USB chooser."};
  }
  return {code:"usb_operation_failed",stage,raw,
    title:"WebUSB operation failed",
    explanation:"The failure alone does not identify an RF, firmware or antenna problem.",
    next:"Check chromium://device-log/ (or chrome://device-log/) for permission and driver errors; export the TV Center diagnostic JSON without serial numbers."};
}
