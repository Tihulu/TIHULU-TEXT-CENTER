#!/usr/bin/env bash
# User-local install: Debian/Ubuntu/Pop!_OS, Raspberry Pi OS, macOS arm64/x86_64.
set -euo pipefail
REPO="https://github.com/Tihulu/TIHULU-TEXT-CENTER.git"
CHANNEL="${TIHULU_CHANNEL:-feature/satellite-auto-discovery-integrated-2026-11-06}"
APP_DIR="${TIHULU_APP_DIR:-$HOME/.local/share/tihulu-satellite-center-app}"
BIN_DIR="$HOME/.local/bin"
if ! command -v git >/dev/null; then echo "git is required; install git and rerun." >&2; exit 1; fi
if ! command -v python3 >/dev/null; then echo "Python 3.11+ is required." >&2; exit 1; fi
python3 -c 'import sys;assert sys.version_info >= (3,11), "Python 3.11+ required"'
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --depth 1 origin "$CHANNEL"
  git -C "$APP_DIR" checkout -B satellite-install FETCH_HEAD
elif [[ -e "$APP_DIR" ]]; then
  echo "Refusing to replace non-git directory: $APP_DIR" >&2; exit 1
else
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --depth 1 --branch "$CHANNEL" "$REPO" "$APP_DIR"
fi
if ! python3 -m venv "$APP_DIR/.venv-satellite"; then
  echo "Python venv missing. Debian/Raspberry Pi OS: sudo apt install python3-venv" >&2; exit 1
fi
"$APP_DIR/.venv-satellite/bin/python" -m pip install --disable-pip-version-check 'skyfield>=1.49,<2' 'PyQt5>=5.15,<6' 'numpy>=1.24,<3'
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/tihulu-satellite" <<EOF
#!/bin/sh
cd "$APP_DIR"
exec "$APP_DIR/.venv-satellite/bin/python" -m satellite_center desktop
EOF
chmod 755 "$BIN_DIR/tihulu-satellite"

# Browser-only WebUSB is secondary. On Debian/Firefox the PRIMARY launcher
# starts the native loopback SDR backend; this avoids File System Access limits.
WEB_URL="https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/browser/"
WEB_LAUNCH="$BIN_DIR/tihulu-satellite-web"
cat > "$WEB_LAUNCH" <<'EOF'
#!/bin/sh
set -eu
url="https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/browser/"
if [ "$(uname -s)" = "Darwin" ]; then
  for app in "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
             "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
             "/Applications/Chromium.app/Contents/MacOS/Chromium"; do
    if [ -x "$app" ]; then exec "$app" --app="$url"; fi
  done
  echo "No Chromium browser found for direct WebUSB. Install Chrome/Brave or use the optional local companion." >&2
  exec open "$url"
fi
for app in brave-browser brave-browser-stable chromium chromium-browser google-chrome google-chrome-stable microsoft-edge; do
  if command -v "$app" >/dev/null 2>&1; then
    exec "$app" --app="$url" --class=tihulu-satellite-web
  fi
done
echo "For WebUSB install a supported Chromium-based browser (Brave, Chromium, Chrome or Edge)." >&2
if command -v firefox >/dev/null 2>&1; then
  echo "Opening the satellite orbit planner in Firefox. Direct RTL-SDR USB access is NOT available in Firefox." >&2
  exec firefox --new-window "$url"
fi
if command -v xdg-open >/dev/null 2>&1; then exec xdg-open "$url"; fi
exit 1
EOF
chmod 755 "$WEB_LAUNCH"

case "$(uname -s)" in
  Linux)
    icon_dir="$HOME/.local/share/icons/hicolor/scalable/apps"
    png_dir="$HOME/.local/share/icons/hicolor/512x512/apps"
    mkdir -p "$HOME/.local/share/applications" "$icon_dir" "$png_dir"
    cp "$APP_DIR/satellite_center/assets/tihulu-satellite.svg" "$icon_dir/tihulu-satellite.svg"
    cp "$APP_DIR/satellite_center/assets/tihulu-satellite.png" "$png_dir/tihulu-satellite.png"
    # Desktop: produce exactly one Satellite Center icon by default.
    # If installed system .deb is present, do not create a duplicate user icon.
    if dpkg -s tihulu-satellite-center 2>/dev/null | grep -q '^Status: install ok installed
    command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
    echo "Only the native Qt desktop launcher is installed by default."
    echo "To preview old duplicate shortcuts without changing files:"
    echo "  $APP_DIR/.venv-satellite/bin/python -m satellite_center cleanup-shortcuts"
    echo "To archive those old Local/PWA icons with a backup, append --apply."
    echo "Opt-in browser shortcut only: TIHULU_INSTALL_WEB_SHORTCUT=1 bash install.sh"
    echo "Optional RTL-SDR CLI tools for the local companion: sudo apt install rtl-sdr multimon-ng"
    ;;
  Darwin)
    mkdir -p "$HOME/Applications"
    cp "$BIN_DIR/tihulu-satellite" "$HOME/Applications/TIHULU Satellite Center.command"
    chmod 755 "$HOME/Applications/TIHULU Satellite Center.command"
    echo "Install SDR tools separately: brew install librtlsdr (Apple Silicon supported)."
    ;;
  *) echo "Use Windows install.ps1 on Windows." >&2; exit 1;;
esac
echo "Native Qt SDR program: $BIN_DIR/tihulu-satellite (no browser required)"
echo "Optional browser WebUSB: $WEB_LAUNCH (Chromium required for RF capture)"
echo "Optional legacy HTTP service (not started by the Qt app): python3 -m satellite_center serve"
echo "No USB driver, RF capture, remote listener or background daemon was silently activated."
; then
      echo "Native Qt .deb installed: using the existing System launcher; no duplicate Local icon."
    else
      cat > "$HOME/.local/share/applications/tihulu-satellite.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TIHULU Satellite Center
Comment=Real Qt Widgets program, no browser/localhost page required
Exec=$BIN_DIR/tihulu-satellite
Icon=tihulu-satellite
Terminal=false
StartupNotify=true
Categories=Education;Science;HamRadio;
EOF
    fi
    # Keep browser/PWA workflow available only if user OPTS IN.
    if [ "${TIHULU_INSTALL_WEB_SHORTCUT:-0}" = "1" ]; then
      cat > "$HOME/.local/share/applications/tihulu-satellite-web.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TIHULU Satellite Center (Browser WebUSB)
Comment=Opt-in Chromium WebUSB satellite planner
Exec=$WEB_LAUNCH
Icon=tihulu-satellite
Terminal=false
StartupNotify=true
StartupWMClass=tihulu-satellite-web
Categories=Education;Science;HamRadio;
Keywords=RTL-SDR;Satellite;ISS;Meteor;WebUSB;
EOF
    fi
    command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
    echo "Desktop launchers registered: TIHULU Satellite Center (native default) and optional Browser WebUSB."
    echo "Pin the TIHULU Satellite Center launcher to the COSMIC dock from the Applications menu."
    echo "If Chromium isn't installed, Firefox can show the planner, but cannot directly open WebUSB."
    echo "Optional RTL-SDR CLI tools for the local companion: sudo apt install rtl-sdr multimon-ng"
    ;;
  Darwin)
    mkdir -p "$HOME/Applications"
    cp "$BIN_DIR/tihulu-satellite" "$HOME/Applications/TIHULU Satellite Center.command"
    chmod 755 "$HOME/Applications/TIHULU Satellite Center.command"
    echo "Install SDR tools separately: brew install librtlsdr (Apple Silicon supported)."
    ;;
  *) echo "Use Windows install.ps1 on Windows." >&2; exit 1;;
esac
echo "Native Qt SDR program: $BIN_DIR/tihulu-satellite (no browser required)"
echo "Optional browser WebUSB: $WEB_LAUNCH (Chromium required for RF capture)"
echo "Optional legacy HTTP service (not started by the Qt app): python3 -m satellite_center serve"
echo "No USB driver, RF capture, remote listener or background daemon was silently activated."
