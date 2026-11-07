#!/usr/bin/env bash
# Native TV Center development installer for Debian-family Linux.
set -Ee -o pipefail
if [[ "$(uname)" != Linux || ! -f /etc/os-release ]]; then
  echo "Requires Debian/Ubuntu/Pop!_OS/Raspberry Pi OS." >&2; exit 1
fi
. /etc/os-release
case " $ID $ID_LIKE " in
  *debian*|*ubuntu*|*pop*|*raspbian*) ;;
  *) echo "Unsupported Linux distribution." >&2; exit 1 ;;
esac
if [[ -n "$1" && "$1" != "--local" ]]; then
  echo "Usage: bash tv_center/install.sh [--local]" >&2; exit 2
fi
root_cmd() { if (( EUID == 0 )); then "$@"; else sudo "$@"; fi; }
echo "Installing native DVB/MPV dependencies; existing TV scans are preserved."
root_cmd apt-get update
root_cmd apt-get install -y --no-install-recommends \
  ca-certificates git python3 python3-pyqt5 dvb-tools mpv ffmpeg psmisc dpkg
tempdir="$(mktemp -d)"
trap 'rm -rf "$tempdir"' EXIT
if [[ "$1" == "--local" ]]; then
  source_root="$(cd "$(dirname "$BASH_SOURCE")/.." && pwd)"
else
  source_root="$tempdir/repo"
  git clone --quiet --depth 1 \
    --branch feature/tv-center-native-teletext-asr-2026-11-07 \
    https://github.com/Tihulu/TIHULU-TEXT-CENTER.git "$source_root"
fi
bash "$source_root/tv_center/packaging/build-deb.sh" "$tempdir"
pkg="$tempdir/tihulu-tv-center_0.1.0~dev1_all.deb"
test -s "$pkg"
root_cmd dpkg -i "$pkg"
echo "Installed. Open TIHULU TV Center from the apps menu or run: tihulu-tv-center"
echo "Diagnostics: tihulu-tv-center doctor"
echo "For iPhone/Android, enable Local Wi-Fi + HLS in the desktop app."
echo "No TV hardware was opened and no AI model was downloaded by the installer."
