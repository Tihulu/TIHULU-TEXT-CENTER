#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Read-only DVB receiver diagnostics. Does not stop processes or retune devices.
set -u
printf 'TIHULU Media Center · DVB frontend diagnostics\n'
printf 'User: %s | Groups: %s\n' "$(id -un)" "$(id -nG)"
printf 'Date: %s\n\n' "$(date --iso-8601=seconds)"
shopt -s nullglob
frontends=(/dev/dvb/adapter*/frontend*)
if (( ${#frontends[@]} == 0 )); then
  printf 'No /dev/dvb/adapter*/frontend* devices found. Check USB, kernel driver and firmware.\n'
  exit 0
fi
for frontend in "${frontends[@]}"; do
  printf 'Frontend: %s\n' "$frontend"
  ls -l -- "$frontend" || true
  if [[ -r "$frontend" && -w "$frontend" ]]; then
    printf '  Permissions: user can read and write\n'
  else
    printf '  Permissions: missing read/write access; check video group and udev rules\n'
  fi
  if command -v fuser >/dev/null 2>&1; then
    owners="$(fuser -- "$frontend" 2>/dev/null || true)"
    if [[ -n "$owners" ]]; then
      printf '  OPEN by PID(s): %s\n' "$owners"
      for pid in $owners; do
        case "$pid" in
          *[!0-9]*|'') continue ;;
        esac
        ps -p "$pid" -o pid=,comm=,args= || true
      done
    else
      printf '  No owner visible to this user (permission limits may hide another process).\n'
    fi
  else
    printf '  fuser unavailable (install psmisc to inspect process ownership).\n'
  fi
  if command -v udevadm >/dev/null 2>&1; then
    udevadm info --query=property --name="$frontend" 2>/dev/null |
      grep -E '^(ID_VENDOR_ID|ID_MODEL_ID|ID_MODEL|DEVNAME)=' || true
  fi
  printf '\n'
done
printf 'A busy frontend cannot be used by two independent programs.\n'
printf 'Exit the other TV/SDR application normally; do not kill arbitrary processes.\n'
printf 'A detected DVB frontend with read/write permission is not proof of RF lock.\n'
printf 'TIHULU defaults an UNCONFIGURED DVB-T2 frontend to native AUTO-T2-Normal.\n'
printf 'If you previously saved No Source, change it explicitly to AUTO-T2-Normal or a suitable regional list.\n'
printf 'Then run Television > Full Antenna Scan; inspect live lock/SNR in the scan UI.\n'
printf 'DAB Band III scanning is separate from DVB-T2 and needs a compatible SDR/welle receiver.\n'