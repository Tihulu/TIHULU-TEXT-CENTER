#!/usr/bin/env bash
# TIHULU RF Geolocation Center: targeted RTL-SDR USB diagnosis and optional release.
# Usage: bash usb_prepare_linux.sh [--check | --release]
# --check does not alter the system.
# --release explicitly stops readsb (if active) and unbinds only RTL2832U (0bda:2838)
# interfaces currently claimed by dvb_usb_rtl28xxu. No module blacklisting.
set -u
mode="--check"
if [[ $# -gt 0 ]]; then mode="$1"; fi
if [[ "$mode" != "--check" && "$mode" != "--release" ]]; then
  echo "Usage: bash $0 [--check | --release]" >&2
  exit 2
fi
if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Linux-only script. Use browser device diagnostics on this platform." >&2
  exit 2
fi
found=0
echo "TIHULU RTL-SDR USB diagnostics (0bda:2838) — mode: $mode"
echo "User: $(id -un); groups: $(id -nG)"
if command -v systemctl >/dev/null 2>&1; then
  echo "readsb service: $(systemctl is-active readsb 2>/dev/null || true)"
fi
for dev in /sys/bus/usb/devices/*; do
  [[ -f "$dev/idVendor" && -f "$dev/idProduct" ]] || continue
  [[ "$(cat "$dev/idVendor")" == "0bda" && "$(cat "$dev/idProduct")" == "2838" ]] || continue
  found=$((found+1))
  iface_count=0
  name="$(basename "$dev")"
  busnum="$(cat "$dev/busnum")"
  devnum="$(cat "$dev/devnum")"
  node="$(printf '/dev/bus/usb/%03d/%03d' "$((10#$busnum))" "$((10#$devnum))")"
  echo
  echo "Device $name: USB bus node $node"
  if [[ -e "$node" ]]; then
    ls -l "$node"
    if command -v getfacl >/dev/null 2>&1; then
      getfacl -cp "$node" 2>/dev/null || true
    fi
    if command -v fuser >/dev/null 2>&1; then
      echo "Open processes visible to current user (other users may be hidden):"
      fuser -v "$node" 2>&1 || true
    fi
  else
    echo "WARNING: USB device node not found."
  fi
  if [[ "$mode" == "--release" ]]; then
    if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet readsb; then
      echo "Stopping readsb at your explicit --release request..."
      sudo systemctl stop readsb || { echo "Failed to stop readsb." >&2; exit 1; }
    fi
  fi
  for iface in "$dev":*; do
    [[ -d "$iface" ]] || continue
    iface_count=$((iface_count+1))
    driver="none"
    if [[ -L "$iface/driver" ]]; then
      driver="$(basename "$(readlink -f "$iface/driver")")"
    fi
    echo "Interface $(basename "$iface"): driver=$driver"
    if [[ "$mode" == "--release" && "$driver" == "dvb_usb_rtl28xxu" ]]; then
      echo "Releasing $(basename "$iface") from DVB driver..."
      printf '%s\n' "$(basename "$iface")" | sudo tee /sys/bus/usb/drivers/dvb_usb_rtl28xxu/unbind >/dev/null ||
        { echo "DVB driver unbind failed." >&2; exit 1; }
      echo "DVB driver released for $(basename "$iface")."
    fi
  done
  if [[ "$iface_count" -eq 0 ]]; then echo "No USB interfaces listed."; fi
done
if [[ "$found" -eq 0 ]]; then
  echo "No 0bda:2838 device found. Check USB cable/hub and lsusb -d 0bda:2838." >&2
  exit 1
fi
echo
if [[ "$mode" == "--release" ]]; then
  echo "Done. Close all rtl_test/Gqrx/rtl_433 instances, then retry WebUSB in Chrome/Brave/Edge over HTTPS."
  echo "This script does not change permanent kernel rules or restart readsb."
  echo "To resume aircraft service later (if needed): sudo systemctl start readsb"
else
  echo "Read-only check complete. To release readsb and this device's DVB interface on request:"
  echo "  bash $0 --release"
fi
