#!/usr/bin/env bash
# TIHULU Geolocation Center — user-requested Linux DVB-T/T2/C scan.
# Usage: bash dvb_scan_linux.sh [regional-dvbv5-initial-file] [adapter-index]
# This uses the Linux DVB driver for Hauppauge WinTV-soloHD, NOT RTL-SDR WebUSB.
set -eo pipefail
file="$1";adapter="$2"
[[ -n "$adapter" ]] || adapter=0
if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Linux-only scan. GitHub Pages cannot directly tune DVB hardware." >&2;exit 2
fi
if ! command -v dvbv5-scan >/dev/null 2>&1; then
  echo "dvbv5-scan missing. Install the distribution's dvb-tools package." >&2;exit 2
fi
if [[ ! "$adapter" =~ ^[0-9]{1,2}$ ]]; then
  echo "Invalid adapter index" >&2;exit 2
fi
if [[ ! -e "/dev/dvb/adapter$adapter/frontend0" ]]; then
  echo "DVB tuner /dev/dvb/adapter$adapter/frontend0 not found." >&2
  echo "Check USB recognition/firmware. Do NOT unbind the TV tuner's Linux DVB kernel driver." >&2
  exit 1
fi
if [[ -z "$file" ]]; then
  echo "A real regional initial tuning table is needed. Check /usr/share/dvb/." >&2
  echo "Candidate tuning files:"
  if [[ -d /usr/share/dvb ]]; then
    find /usr/share/dvb -type f \( -iname 'de*' -o -iname '*NRW*' -o -iname '*koeln*' \) -print 2>/dev/null | head -25 || true
  fi
  echo "Usage: bash dvb_scan_linux.sh /path/to/real/initial-tuning-file $adapter" >&2
  exit 2
fi
if [[ ! -f "$file" || ! -r "$file" ]]; then
  echo "Tuning table cannot be read: $file" >&2;exit 2
fi
output="tihulu-native-dvb-$(date -u +%Y%m%dT%H%M%SZ).conf"
echo "Scanning actual Linux DVB adapter $adapter using: $file"
dvbv5-scan -a "$adapter" -O dvbv5 -o "$output" "$file"
if [[ ! -s "$output" ]]; then
  echo "No DVB channel metadata saved. Check hardware, antenna and regional frequency plan." >&2;exit 1
fi
echo "Saved DVB channel metadata: $output"
echo "Import it through Geolocation Center -> Radio / TV Scan."
echo "DVB services do not themselves encode receiver coordinates or a unique broadcast tower."
