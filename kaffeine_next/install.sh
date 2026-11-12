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
MODE=--no-ai
WITH_DAB=0
WITH_ANALOG=0
for argument in "$@"; do
  case "$argument" in
    --no-ai) MODE=--no-ai ;;
    --with-ai) MODE=--with-ai ;;
    --with-dab) WITH_DAB=1 ;;
    --with-analog) WITH_ANALOG=1 ;;
    *) echo "Usage: bash install.sh [--no-ai|--with-ai] [--with-dab] [--with-analog]" >&2; exit 2 ;;
  esac
done
# Require a complete, SHA-pinned Media source checkout; never clone Text.
MEDIA_SOURCE_DIR="${TIHULU_MEDIA_SOURCE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
if [[ ! -f "$MEDIA_SOURCE_DIR/tv_center/__main__.py" ||
      ! -f "$MEDIA_SOURCE_DIR/kaffeine_next/patch_upstream.py" ]]; then
  echo "Incomplete Media source; refusing standalone install." >&2; exit 1
fi
ACTUAL_MEDIA_SHA="$(git -C "$MEDIA_SOURCE_DIR" rev-parse HEAD 2>/dev/null || true)"
EXPECTED_MEDIA_SHA="${TIHULU_MEDIA_SOURCE_SHA:-}"
if [[ ! "$EXPECTED_MEDIA_SHA" =~ ^[0-9a-f]{40}$ ||
      "$EXPECTED_MEDIA_SHA" != "$ACTUAL_MEDIA_SHA" ]]; then
  echo "Set TIHULU_MEDIA_SOURCE_SHA to the exact reviewed Media commit." >&2
  exit 1
fi
MEDIA_REVISION="${ACTUAL_MEDIA_SHA:0:12}"
# A pre-existing legacy installation is not ours to overwrite.
# A future migration must have an owner-approved backup/ownership manifest.
OWNED_LAUNCHER_MARKER="$HOME/.local/share/tihulu-media-center/native/.tihulu-owned-launcher"
for existing in "$HOME/.local/bin/tihulu-kaffeine" \
                "$HOME/.local/bin/tihulu-media-center" \
                "$HOME/.local/share/applications/tihulu-media-center.desktop"; do
  if [[ -e "$existing" || -L "$existing" ]]; then
    if [[ ! -f "$OWNED_LAUNCHER_MARKER" ]]; then
      echo "Existing Media/legacy launcher found; preserving it. Manual migration review required." >&2
      exit 1
    fi
  fi
done
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
if (( WITH_ANALOG == 1 )); then
  echo "Installing optional local RTL-SDR analogue tools and ALSA PCM output."
  sudo apt-get install -y --no-install-recommends rtl-sdr alsa-utils
fi

APPROOT="$HOME/.local/share/tihulu-media-center/native"
SOURCE="$APPROOT/upstream-v2.0.19"
PREFIX="$HOME/.local/opt/tihulu-media-center/releases/$MEDIA_REVISION"
BUILD="$APPROOT/build-$MEDIA_REVISION"
LOGDIR="$APPROOT/logs"
mkdir -p "$APPROOT" "$LOGDIR" "$HOME/.local/bin" "$HOME/.local/share/applications"
# Migrate existing tuner/channel definitions ONCE into a distinct TIHULU
# data directory. Never alter the system Kaffeine instance's own files.
LEGACY_DATA="$HOME/.local/share/kaffeine"
TIHULU_DATA="$HOME/.local/share/tihulu-media-center"
if [[ "${TIHULU_MEDIA_IMPORT_STOCK_KAFFEINE:-0}" == 1 &&
      -d "$LEGACY_DATA" && ! -e "$TIHULU_DATA" && ! -L "$LEGACY_DATA" ]]; then
  mkdir -p "$TIHULU_DATA"
  # Copy settings/channels, not user-owned recordings/videos or unknown links.
  find "$LEGACY_DATA" -maxdepth 1 -type f \
    \( -name 'config.dvb' -o -name '*.db' -o -name '*.sqlite' \) \
    -exec cp -n -- {} "$TIHULU_DATA/" \;
  echo "Imported existing Kaffeine channel database/config as independent TIHULU copies."
fi
mkdir -p "$HOME/.config"
if [[ "${TIHULU_MEDIA_IMPORT_STOCK_KAFFEINE:-0}" == 1 &&
      -f "$HOME/.config/kaffeinerc" &&
      ! -e "$HOME/.config/tihulu-media-centerrc" ]]; then
  cp -n -- "$HOME/.config/kaffeinerc" "$HOME/.config/tihulu-media-centerrc"
fi

# A running Conda/Miniconda "base" shell can inject another Qt5 at link time.
# CMake's path search, pkg-config and the ELF linker must all use the same
# distro Qt5 / KF5 libraries. A clean environment also bypasses stale
# LD_LIBRARY_PATH, CMAKE_PREFIX_PATH and QT_PLUGIN_PATH settings.
SYSTEM_BUILD_ENV=(env -i "HOME=$HOME" "USER=$(id -un)"
  "PATH=/usr/bin:/bin:/usr/sbin:/sbin" "LANG=C.UTF-8")
if [[ -n "${CONDA_PREFIX:-}" || -n "${LD_LIBRARY_PATH:-}" ||
      -n "${CMAKE_PREFIX_PATH:-}" || -n "${QT_PLUGIN_PATH:-}" ]]; then
  echo "Conda/custom Qt environment detected; build will use only system Qt5."
fi

qt_link_diagnostics() {
  echo "=== Qt5 link diagnostics (read-only) ===" >&2
  dpkg-query -W -f='${binary:Package} ${Version}\n' \
    libqt5core5a libqt5gui5 libqt5waylandclient5 qtbase5-dev 2>/dev/null || true
  local qtlib
  qtlib="$(/sbin/ldconfig -p 2>/dev/null | awk '$1=="libQt5WaylandClient.so.5" {print $NF; exit}')"
  if [[ -n "$qtlib" ]]; then
    echo "Checking $qtlib against distro Qt5Gui:" >&2
    "${SYSTEM_BUILD_ENV[@]}" /usr/bin/ldd -r "$qtlib" 2>&1 |
      grep -E 'undefined symbol|not found' | head -30 || true
  fi
  echo "If symbols remain unresolved, system Qt5Gui and Qt5WaylandClient" >&2
  echo "may come from incompatible repositories or installed versions." >&2
  echo "Check apt-cache policy libqt5gui5 libqt5waylandclient5." >&2
}
temp="$(mktemp -d)"
BUILDSRC=""
cleanup() {
  if [[ -n "$BUILDSRC" && -e "$BUILDSRC/.git" && -d "$SOURCE/.git" ]]; then
    git -C "$SOURCE" worktree remove --force "$BUILDSRC" >/dev/null 2>&1 || true
  fi
  rm -rf "$temp"
}
trap cleanup EXIT

# The caller supplies a pinned, reviewed Media source checkout.
test -f "$MEDIA_SOURCE_DIR/kaffeine_next/assets/tihulu-media-center.svg"
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
# Never patch a previously modified Kaffeine source tree in-place.
# Users may already have the older patch, and a second patch could
# duplicate scan menus or produce a partially working build.
# Detached worktrees provide a fresh, reproducible upstream checkout
# while preserving local edits and existing user configuration.
BUILDSRC="$temp/kaffeine-source"
git -C "$SOURCE" worktree add --detach "$BUILDSRC" "$UPSTREAM_SHA"
python3 "$MEDIA_SOURCE_DIR/kaffeine_next/patch_upstream.py" "$BUILDSRC"
# Refuse to ship Kaffeine 2.0.19 with the known channel-import crash
# (KDE #503740 / Debian #1110405). The wrong -1 to std::prev(end)
# reads past the QMap end while several scanned channels are inserted.
SQL_HEADER="$BUILDSRC/src/sqlinterface.h"
if grep -Fq 'std::prev(container.constEnd(), -1)' "$SQL_HEADER" ||
   ! grep -Fq 'std::prev(container.constEnd())' "$SQL_HEADER"; then
  echo "FATAL: DVB scan channel-import SQL iterator fix missing." >&2
  exit 1
fi
echo "Verified Kaffeine DVB channel-import SQL iterator fix (no past-end iterator)."
git -C "$BUILDSRC" diff --check
# Keep the user-approved, loopback-only welle.io backend installer on disk
# instead of trying to run an untrusted internet pipe from the native GUI.
cp "$MEDIA_SOURCE_DIR/kaffeine_next/install_welle.sh" "$APPROOT/install_welle.sh"
chmod 755 "$APPROOT/install_welle.sh"
# Read-only frontend ownership check, accessible in the TV menu or CLI.
cp "$MEDIA_SOURCE_DIR/kaffeine_next/dvb_diagnostics.sh" "$APPROOT/dvb_diagnostics.sh"
chmod 755 "$APPROOT/dvb_diagnostics.sh"

echo "Configuring clean Kaffeine native DVB scanner with isolated system Qt5"
if ! "${SYSTEM_BUILD_ENV[@]}" /usr/bin/cmake --fresh -S "$BUILDSRC" -B "$BUILD" \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
  -DCMAKE_INSTALL_PREFIX="$PREFIX" 2>&1 | tee "$LOGDIR/configure.log"; then
  qt_link_diagnostics
  echo "CMake configuration failed; see $LOGDIR/configure.log" >&2
  exit 1
fi
if ! "${SYSTEM_BUILD_ENV[@]}" /usr/bin/cmake --build "$BUILD" --parallel 2 \
    2>&1 | tee "$LOGDIR/build.log"; then
  qt_link_diagnostics
  echo "Kaffeine build failed; see $LOGDIR/build.log" >&2
  echo "The launcher is deliberately not installed until the build succeeds." >&2
  exit 1
fi
"${SYSTEM_BUILD_ENV[@]}" /usr/bin/cmake --install "$BUILD"
test -x "$PREFIX/bin/kaffeine"
# The compiled executable remains attributed to upstream KDE Kaffeine,
# but a standalone installed filename and its QApplication identity
# distinguish TIHULU from /usr/bin/kaffeine.
ln -sfn kaffeine "$PREFIX/bin/tihulu-media-center"
mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"
if [[ ! -e "$HOME/.local/share/icons/hicolor/scalable/apps/tihulu-media-center.svg" ]]; then
  cp -n "$MEDIA_SOURCE_DIR/kaffeine_next/assets/tihulu-media-center.svg" \
    "$HOME/.local/share/icons/hicolor/scalable/apps/tihulu-media-center.svg"
fi

# The standalone PLAY-button player SVG is the new default. The user's
# earlier, unmodified portrait PNG is preserved but is NOT implicitly reused
# on every upgrade. An explicitly provided TIHULU_CUSTOM_LOGO chooses PNG
# for this installation; TIHULU_USE_LEGACY_LOGO=1 restores the saved portrait
# at runtime without modifying its bytes.
DESKTOP_ICON="$HOME/.local/share/icons/hicolor/scalable/apps/tihulu-media-center.svg"
if [[ -n "${TIHULU_CUSTOM_LOGO:-}" ]]; then
  if [[ ! -f "$TIHULU_CUSTOM_LOGO" || -L "$TIHULU_CUSTOM_LOGO" ]]; then
    echo "Custom logo must be a readable regular PNG file." >&2
    exit 1
  fi
  if ! python3 -c 'import pathlib,sys; b=pathlib.Path(sys.argv[1]).read_bytes(); sys.exit(0 if len(b)<4194304 and b.startswith(bytes((137,80,78,71,13,10,26,10))) else 1)' "$TIHULU_CUSTOM_LOGO"; then
    echo "Custom logo failed PNG signature / 4 MiB safety check." >&2
    exit 1
  fi
  mkdir -p "$HOME/.local/share/icons/hicolor/64x64/apps"
  if [[ ! -e "$HOME/.local/share/icons/hicolor/64x64/apps/tihulu-media-center.png" ]]; then
    cp -n -- "$TIHULU_CUSTOM_LOGO" "$HOME/.local/share/icons/hicolor/64x64/apps/tihulu-media-center.png"
  else
    echo "Preserving existing user PNG; requested new custom icon not copied." >&2
  fi
  DESKTOP_ICON="$HOME/.local/share/icons/hicolor/64x64/apps/tihulu-media-center.png"
fi
if [[ -f "$HOME/.local/share/icons/hicolor/64x64/apps/tihulu-media-center.png" &&
      -z "${TIHULU_CUSTOM_LOGO:-}" ]]; then
  echo "Kept legacy user portrait PNG unchanged; player SVG is now the default icon."
  echo "To use the portrait again: TIHULU_USE_LEGACY_LOGO=1 tihulu-media-center"
fi

TIHULU_KAFFEINE_PRIMARY=1 bash "$MEDIA_SOURCE_DIR/tv_center/packaging/build-deb.sh" "$temp/debs"
# A separate Media package must never overwrite the existing TV/Text package.
sudo apt-get install -y "$temp/debs/tihulu-media-center-ai_0.1.0~dev2_all.deb"
# Switch only a proven Media-owned current symlink after version is installed.
BASE_PREFIX="$HOME/.local/opt/tihulu-media-center"
CURRENT_LINK="$BASE_PREFIX/current"
mkdir -p "$BASE_PREFIX/releases"
printf '%s\n' "$ACTUAL_MEDIA_SHA" > "$PREFIX/.tihulu-media-owned-release"
if [[ -e "$CURRENT_LINK" && ! -L "$CURRENT_LINK" ]]; then
  echo "Refusing a non-symlink Media current path." >&2; exit 1
fi
if [[ -L "$CURRENT_LINK" ]]; then
  OLD_LINK="$(readlink -f "$CURRENT_LINK")"
  case "$OLD_LINK" in "$BASE_PREFIX"/releases/*) ;; *) echo "Foreign current link; refusing." >&2; exit 1;; esac
  test -f "$OLD_LINK/.tihulu-media-owned-release" ||
    { echo "Existing Media release is not verified as owned." >&2; exit 1; }
fi
ln -s "$PREFIX" "$CURRENT_LINK.next.${BASHPID}"
mv -T "$CURRENT_LINK.next.${BASHPID}" "$CURRENT_LINK"

cat > "$HOME/.local/bin/tihulu-kaffeine" <<'LAUNCH'
#!/bin/sh
# XWayland avoids the broken NVIDIA / COSMIC embedded surface path.
if [ -n "${WAYLAND_DISPLAY:-}" ]; then export QT_QPA_PLATFORM=xcb; fi
# Native DVB playback uses Kaffeine/libVLC. On the known NVIDIA + Wayland
# combination, safely use software HEVC decoding first; never force this
# CPU-intensive profile on Pi 5 or systems without NVIDIA.
if [ -z "${TIHULU_VLC_PROFILE:-}" ]; then
  if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -r /proc/driver/nvidia/version ]; then
    TIHULU_VLC_PROFILE=software
  else
    TIHULU_VLC_PROFILE=auto
  fi
fi
# Explicit per-session overrides for isolating decoder vs AAC audio faults.
case "${1:-}" in
  --diagnose-tuner) shift; exec /bin/bash "$HOME/.local/share/tihulu-media-center/native/dvb_diagnostics.sh" "$@" ;;
  --software-video) TIHULU_VLC_PROFILE=software; shift ;;
  --auto-video) TIHULU_VLC_PROFILE=auto; shift ;;
  --diagnose-no-audio) TIHULU_VLC_PROFILE=software-no-audio; shift ;;
esac
export TIHULU_VLC_PROFILE
# Fast, on-demand first paint: don't open or tune DVB automatically just
# because the user opened Media Center. Explicitly set the opt-in below
# to restore the former --lastchannel autoplay behavior.
if [ "$#" -eq 0 ] && [ "${TIHULU_AUTOPLAY_LAST_CHANNEL:-0}" = 1 ]; then
  set -- --lastchannel
fi
# KDE Kaffeine already uses KDBusService::Unique and activates the
# existing window on a second launch. Do NOT add an inherited shell flock:
# helper processes may keep its FD alive after the player exits, causing a
# false "already running" error and preventing KDBusService from focusing
# the actual window. Device ownership is handled separately by the receiver.
# Never probe, claim, or require DVB/RTL-SDR hardware at application launch.
# Offline media, web TV, settings and diagnostics must open without antennas.
# Avoid mixing native system libVLC/Qt5 with the user's Conda installation.
exec env -u LD_LIBRARY_PATH -u LD_PRELOAD -u QT_PLUGIN_PATH \
  -u QT_QPA_PLATFORM_PLUGIN_PATH -u QML2_IMPORT_PATH -u QML_IMPORT_PATH \
  "$HOME/.local/opt/tihulu-media-center/current/bin/tihulu-media-center" "$@"
LAUNCH
chmod 755 "$HOME/.local/bin/tihulu-kaffeine"
ln -sfn tihulu-kaffeine "$HOME/.local/bin/tihulu-media-center"
cat > "$HOME/.local/share/applications/tihulu-media-center.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=TIHULU Media Center
GenericName=TV · DAB+ Radio · Local Video/Audio · AI Subtitles
Comment=Standalone native TV and radio player with offline AI, based on KDE Kaffeine
Exec=$HOME/.local/bin/tihulu-media-center
TryExec=$HOME/.local/bin/tihulu-media-center
Icon=$DESKTOP_ICON
StartupWMClass=tihulu-media-center
Terminal=false
Categories=AudioVideo;Video;TV;Audio;Player;
DESKTOP

# Store the exact bytes of launcher created by this installer for future
# collision/upgrade review; do not migrate another application's launcher.
sha256sum "$HOME/.local/bin/tihulu-kaffeine" | awk '{print $1}' > "$OWNED_LAUNCHER_MARKER"

if [[ "$MODE" != --no-ai ]]; then
  echo "Installing baseline offline models for the device: Whisper Tiny,"
  echo "Argos DE/EN/TR/FR and, where hardware permits, starter sound labels,"
  echo "speaker embeddings and Qwen 0.6B lyrics alignment weights."
  echo "Heavy upgrades stay in AI Market; no AI service starts in background."
  # This is the user-triggered install command, NEVER a model download on
  # application startup, radio tuning, background polling or library scan.
  if ! tihulu-media-cli ai install-baseline; then
    echo "Some baseline AI models failed or were skipped; TV and existing" >&2
    echo "Whisper/translation models are preserved. See AI Model Market." >&2
  fi
fi
echo "Open TIHULU Media Center (separate app, icon and channel database):"
echo "  $HOME/.local/bin/tihulu-media-center"
echo "Use TV -> TIHULU AI for Model Market and live subtitles."
echo "Only one DVB frontend owner at a time. Inspect with:"
echo "  $HOME/.local/bin/tihulu-media-center --diagnose-tuner"
echo "Set DVB-T2 Source in Configure Television before the first channel scan."
echo "FM/MW/LW requires a suitable SDR; optional tools: bash install.sh --with-analog"
echo "DAB+ Radio is a native tab. Optional welle.io backend (separate SDR):"
echo "  bash $APPROOT/install_welle.sh"
if (( WITH_DAB == 1 )); then
  echo "User explicitly selected --with-dab: building pinned localhost-only welle-cli."
  bash "$APPROOT/install_welle.sh"
fi
