#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Install TIHULU's Kaffeine-based TV application alongside system Kaffeine.
set -Eeuo pipefail
if [[ "$(uname -s)" != Linux || ! -f /etc/os-release ]]; then
  echo "Native Kaffeine DVB requires Linux." >&2; exit 1
fi
. /etc/os-release
case " $ID $ID_LIKE " in
  *debian*|*ubuntu*|*pop*|*raspbian*) ;;
  *) echo "Requires Debian/Ubuntu/Pop!_OS/Raspberry Pi OS with APT." >&2; exit 1 ;;
esac
if (( EUID == 0 )); then
  echo "Run as your desktop user. Only APT system dependencies use sudo." >&2
  exit 1
fi
# Explicit opt out for users who only want Kaffeine's DVB reception.
MODE=default
if (( $# > 0 )); then MODE="$1"; fi
if [[ "$MODE" != default && "$MODE" != --no-ai ]]; then
  echo "Usage: bash install.sh [--no-ai]" >&2; exit 2
fi
echo "Building a separate GPL-compatible Kaffeine v2.0.19 fork."
echo "This preserves system Kaffeine, channel lists, other SDR programs and AI models."
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
 git ca-certificates cmake g++ make pkg-config extra-cmake-modules \
 qtbase5-dev libqt5x11extras5-dev libkf5coreaddons-dev \
 libkf5dbusaddons-dev libkf5i18n-dev libkf5kio-dev \
 libkf5solid-dev libkf5widgetsaddons-dev libkf5windowsystem-dev \
 libkf5xmlgui-dev libvlc-dev libx11-dev libxss-dev \
 libdvbv5-dev libudev-dev libqt5sql5-sqlite vlc \
 python3 python3-venv python3-pip python3-pyqt5 ffmpeg \
 dvb-tools psmisc

APPROOT="$HOME/.local/share/tihulu-kaffeine"
SOURCE="$APPROOT/upstream-v2.0.19"
PREFIX="$HOME/.local/opt/tihulu-kaffeine"
mkdir -p "$APPROOT" "$HOME/.local/bin" "$HOME/.local/share/applications"
temp="$(mktemp -d)"
trap 'rm -rf "$temp"' EXIT

git clone --depth 1 --branch architecture/kaffeine-core-tv-2026-11-07 \
  https://github.com/Tihulu/TIHULU-TEXT-CENTER.git "$temp/tihulu"
if [[ ! -d "$SOURCE/.git" ]]; then
  git clone --depth 1 --branch v2.0.19 \
    https://github.com/KDE/kaffeine.git "$SOURCE"
fi
UPSTREAM_SHA=e7ea15b86dafed3b20b151cbcb080578ab8e2d5c
CURRENT_SHA="$(git -C "$SOURCE" rev-parse HEAD)"
if [[ "$CURRENT_SHA" != "$UPSTREAM_SHA" ]]; then
  echo "Unexpected upstream revision: $CURRENT_SHA (expected $UPSTREAM_SHA)" >&2
  exit 1
fi
python3 "$temp/tihulu/kaffeine_next/patch_upstream.py" "$SOURCE"
git -C "$SOURCE" diff --check

cmake -S "$SOURCE" -B "$APPROOT/build" -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=OFF -DCMAKE_INSTALL_PREFIX="$PREFIX"
cmake --build "$APPROOT/build" --parallel 2
cmake --install "$APPROOT/build"
test -x "$PREFIX/bin/kaffeine"

bash "$temp/tihulu/tv_center/packaging/build-deb.sh" "$temp/debs"
sudo apt-get install -y "$temp/debs/tihulu-tv-center_0.1.0~dev1_all.deb"

cat > "$HOME/.local/bin/tihulu-kaffeine" <<'LAUNCH'
#!/bin/sh
# XWayland avoids the broken NVIDIA / COSMIC embedded surface path.
if [ -n "$WAYLAND_DISPLAY" ]; then export QT_QPA_PLATFORM=xcb; fi
exec "$HOME/.local/opt/tihulu-kaffeine/bin/kaffeine" "$@"
LAUNCH
chmod 755 "$HOME/.local/bin/tihulu-kaffeine"
cat > "$HOME/.local/share/applications/tihulu-kaffeine.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=TIHULU TV (Kaffeine)
Comment=Native Kaffeine DVB TV plus optional Whisper and Translator
Exec=$HOME/.local/bin/tihulu-kaffeine
Icon=kaffeine
Terminal=false
Categories=AudioVideo;Video;TV;
DESKTOP

if [[ "$MODE" != --no-ai ]]; then
  echo "Installing requested offline Whisper Tiny and DE/EN/TR Argos starter."
  if ! tihulu-tv-center ai install; then
    echo "AI setup incomplete; TV itself is installed. Retry from AI Model Market." >&2
  fi
fi
echo "Open TIHULU TV (Kaffeine) from applications or run:"
echo "  $HOME/.local/bin/tihulu-kaffeine"
echo "Use TV -> TIHULU AI for Model Market and live subtitles."
echo "Close the other Kaffeine instance first; only one frontend owner at a time."
