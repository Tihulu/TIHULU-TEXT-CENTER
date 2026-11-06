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
case "$(uname -s)" in
  Linux)
    mkdir -p "$HOME/.local/share/applications"
    cat > "$HOME/.local/share/applications/tihulu-satellite.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TIHULU Satellite Center
Comment=Receive-only satellite dashboard and scheduled captures
Exec=$BIN_DIR/tihulu-satellite
Terminal=false
Categories=Education;Science;
EOF
    echo "Optional SDR tools: sudo apt install rtl-sdr multimon-ng"
    ;;
  Darwin)
    mkdir -p "$HOME/Applications"
    cp "$BIN_DIR/tihulu-satellite" "$HOME/Applications/TIHULU Satellite Center.command"
    chmod 755 "$HOME/Applications/TIHULU Satellite Center.command"
    echo "Install SDR tools separately: brew install librtlsdr (Apple Silicon supported)."
    ;;
  *) echo "Use Windows install.ps1 on Windows." >&2; exit 1;;
esac
echo "Installed. Start: $BIN_DIR/tihulu-satellite"
echo "Local dashboard: http://127.0.0.1:8791/"
echo "No USB driver, RF capture, remote listener or background daemon was silently activated."
