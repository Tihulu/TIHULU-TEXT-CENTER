#!/usr/bin/env bash
# Native Debian/Ubuntu/Pop!_OS/Raspberry Pi OS installer.
# No changes to Kaffeine, saved channels, or unrelated RTL-SDR devices.
set -Eeuo pipefail
umask 077
REPO="https://github.com/Tihulu/TIHULU-TEXT-CENTER.git"
BRANCH="feature/tv-center-native-teletext-asr-2026-11-07"
MODE="$*"
if [ "$MODE" != "" ] && [ "$MODE" != "--local" ]; then
  echo "Usage: bash tv_center/install.sh [--local]" >&2
  exit 2
fi
if [ "$(uname -s)" != "Linux" ] || [ ! -f /etc/os-release ] || [ ! -x /usr/bin/apt-get ]; then
  echo "Debian/Ubuntu/Pop!_OS/Raspberry Pi OS with apt required." >&2
  exit 1
fi
. /etc/os-release
ID_LIKE=$(grep "^ID_LIKE=" /etc/os-release || true)
case " $ID $ID_LIKE " in
  *debian*|*ubuntu*|*pop*|*raspbian*) ;;
  *) echo "Unsupported distribution (Debian-family required)." >&2; exit 1 ;;
esac
if [ "$(id -u)" -eq 0 ]; then
  ROOTCMD=""
elif command -v sudo >/dev/null 2>&1; then
  ROOTCMD="sudo"
else
  echo "sudo required for APT installation" >&2
  exit 1
fi
echo "TIHULU TV Center — experimental native TV/Teletext/translation client"
echo "GitHub source: $BRANCH"
echo "APT will install system dependencies, including country-aware w-scan-cpp."
echo "Kaffeine settings, existing channel files, firmware and model packs remain untouched."
$ROOTCMD apt-get update
$ROOTCMD apt-get install -y --no-install-recommends ca-certificates git python3 python3-pyqt5 dvb-tools w-scan-cpp mpv ffmpeg psmisc dpkg
TMP=""
OUT=""
cleanup() {
  if [ -n "$TMP" ]; then rm -rf -- "$TMP"; fi
  if [ -n "$OUT" ]; then rm -rf -- "$OUT"; fi
}
trap cleanup EXIT
if [ "$MODE" = "--local" ]; then
  SOURCE="$(cd -- "$(dirname -- "$0")/.." && pwd)"
  test -f "$SOURCE/tv_center/packaging/build-deb.sh" || { echo "Run --local from cloned repository" >&2; exit 1; }
else
  TMP="$(mktemp -d)"
  SOURCE="$TMP/checkout"
  git clone --quiet --depth 1 --single-branch --branch "$BRANCH" "$REPO" "$SOURCE"
fi
OUT="$(mktemp -d)"
bash "$SOURCE/tv_center/packaging/build-deb.sh" "$OUT"
DEB="$OUT/tihulu-tv-center_0.1.0~dev1_all.deb"
test -s "$DEB" || { echo "Debian package build failed" >&2; exit 1; }
$ROOTCMD apt-get install -y "$DEB"
echo "Installed. Start: tihulu-tv-center   Diagnostics: tihulu-tv-center doctor"
echo "Web: https://tihulu.github.io/TIHULU-TEXT-CENTER/tv_center/"
echo "Before scanning, close Kaffeine and Tvheadend to release the DVB tuner."
