#!/usr/bin/env bash
# User-local install: Debian/Ubuntu/Pop!_OS, Raspberry Pi OS, macOS arm64/x86_64.
set -euo pipefail
REPO="https://github.com/Tihulu/TIHULU-TEXT-CENTER.git"
CHANNEL="${TIHULU_CHANNEL:-feature/satellite-center-standalone-2026-11-06}"
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
"$APP_DIR/.venv-satellite/bin/python" -m pip install --disable-pip-version-check 'skyfield>=1.49,<2'
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/tihulu-satellite" <<EOF
#!/bin/sh
cd "$APP_DIR"
exec "$APP_DIR/.venv-satellite/bin/python" -m satellite_center serve --port 8791 --open-browser
EOF
chmod 755 "$BIN_DIR/tihulu-satellite"

# Standalone WebUSB window is the primary desktop shortcut; no local backend
# is launched by it. Kept separate from the optional local companion command.
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
    cat > "$HOME/.local/share/applications/tihulu-satellite-web.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TIHULU Satellite Center
Comment=WebUSB satellite receiver in a standalone Chromium window
Exec=$WEB_LAUNCH
Icon=tihulu-satellite
Terminal=false
StartupNotify=true
StartupWMClass=tihulu-satellite-web
Categories=Education;Science;HamRadio;
Keywords=RTL-SDR;Satellite;ISS;Meteor;WebUSB;
EOF
    cat > "$HOME/.local/share/applications/tihulu-satellite.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TIHULU Satellite Center (Local Companion)
Comment=Optional localhost radio decoding and scheduled satellite captures
Exec=$BIN_DIR/tihulu-satellite
Icon=tihulu-satellite
Terminal=false
StartupNotify=true
Categories=Education;Science;HamRadio;
EOF
    command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
    echo "App icons registered: TIHULU Satellite Center (browser) and Local Companion."
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
echo "WebUSB browser application: $WEB_LAUNCH (no local SDR service)"
echo "Optional local decoder companion: $BIN_DIR/tihulu-satellite"
echo "Local dashboard: http://127.0.0.1:8791/"
echo "No USB driver, RF capture, remote listener or background daemon was silently activated."
