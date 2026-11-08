#!/usr/bin/env bash
# Read-only Hauppauge WinTV-soloHD WebUSB permission diagnostics on Linux.
# No sudo, no kernel unbind, no firmware, no USB transfers, no changes.
set -u
echo "TIHULU · Hauppauge WebUSB permissions (read-only)"
echo "Target: 2040:8268 · UID: $(id -u) · session: ${XDG_SESSION_TYPE:-unknown}"
echo "Note: Chrome's web permission is not Linux /dev/bus/usb permission."
found=0
for sysdev in /sys/bus/usb/devices/*; do
  [[ -r "$sysdev/idVendor" && -r "$sysdev/idProduct" ]] || continue
  IFS= read -r vid < "$sysdev/idVendor" || continue
  IFS= read -r pid < "$sysdev/idProduct" || continue
  [[ "$vid" == "2040" && "$pid" == "8268" ]] || continue
  found=1
  printf '\nDevice: %s (%s:%s)\n' "${sysdev##*/}" "$vid" "$pid"
  IFS= read -r busnum < "$sysdev/busnum" || continue
  IFS= read -r devnum < "$sysdev/devnum" || continue
  printf -v usbnode '/dev/bus/usb/%03d/%03d' "$((10#$busnum))" "$((10#$devnum))"
  echo "USB device node: $usbnode"
  if [[ -e "$usbnode" ]]; then
    ls -l "$usbnode"
    if [[ -r "$usbnode" && -w "$usbnode" ]]; then
      echo "User-level read+write permission: YES"
    else
      echo "User-level read+write permission: NO — USBDevice.open may be denied."
      echo "Use scoped 2040:8268 udev uaccess rule; reload rules and replug."
    fi
    if command -v getfacl >/dev/null 2>&1; then
      echo "ACL summary:"
      getfacl -cp "$usbnode" 2>/dev/null || true
    fi
  else
    echo "Device node missing; check physical USB connection and udev."
  fi
  echo "Bound USB interface drivers:"
  interface_found=0
  for iface in "$sysdev":*; do
    [[ -d "$iface" && -r "$iface/bInterfaceNumber" ]] || continue
    interface_found=1
    if [[ -L "$iface/driver" ]]; then
      echo "  ${iface##*/}: $(basename "$(readlink -f "$iface/driver")")"
    else
      echo "  ${iface##*/}: unbound"
    fi
  done
  [[ "$interface_found" == 1 ]] || echo "  None enumerated"
done
if [[ "$found" == 0 ]]; then
  echo "No currently enumerated USB device with VID:PID 2040:8268."
  echo "Reconnect the Hauppauge tuner; verify it is the intended model."
fi
if command -v snap >/dev/null 2>&1 && snap list chromium >/dev/null 2>&1; then
  echo
  echo "Snap Chromium detected: verify chromium:raw-usb is connected:"
  snap connections chromium 2>/dev/null | grep -E '^(Interface|raw-usb)[[:space:]]' || true
  echo "If disconnected: sudo snap connect chromium:raw-usb"
fi
if command -v flatpak >/dev/null 2>&1; then
  if flatpak list --app --columns=application 2>/dev/null | grep -Eiq 'org\.chromium\.Chromium|com\.google\.Chrome'; then
    echo
    echo "Flatpak browser installation detected; sandbox may block raw USB."
    echo "Try a non-sandboxed Chrome/Chromium package for WebUSB testing."
  fi
fi
echo
echo "Next: retry Open USB in Chromium/Chrome, then separately Claim bulk-IN."
echo "Device-log: chrome://device-log/ or chromium://device-log/"
echo "No device settings, driver binding or permissions were changed."
