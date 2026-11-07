#!/usr/bin/env bash
# Pure-Python native Debian application, not a browser-only WebUSB shortcut.
# Builds a native apt-installable .deb without network, root or pip.
set -euo pipefail
cd "$(dirname "$0")/../../.."
if ! command -v dpkg-deb >/dev/null; then echo "dpkg-deb is required" >&2; exit 1; fi
VERSION="${TIHULU_DEB_VERSION:-0.3.0~preview10}"
case "$VERSION" in *[!a-zA-Z0-9.+:~-]*|"") echo "Invalid Debian package version" >&2; exit 1;; esac
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
PKG="$ROOT/tihulu-satellite-center"
DEST="$PKG/usr/share/tihulu-satellite-center"
mkdir -p "$PKG/DEBIAN" "$DEST/satellite_center" "$PKG/usr/bin" \
 "$PKG/usr/share/applications" \
 "$PKG/usr/share/icons/hicolor/scalable/apps" \
 "$PKG/usr/share/icons/hicolor/512x512/apps" \
 "$PKG/usr/share/doc/tihulu-satellite-center"
cp satellite_center/*.py "$DEST/satellite_center/"
install -m 644 satellite_center/native_desktop_bridge.js "$DEST/satellite_center/native_desktop_bridge.js"
install -m 644 satellite_center/index.html "$DEST/satellite_center/index.html"
cp -R satellite_center/browser "$DEST/satellite_center/browser"
cp -R satellite_center/assets "$DEST/satellite_center/assets"
cp satellite_center/README.md "$PKG/usr/share/doc/tihulu-satellite-center/README.md"
cat > "$PKG/DEBIAN/control" <<EOF
Package: tihulu-satellite-center
Version: $VERSION
Section: hamradio
Priority: optional
Architecture: all
Maintainer: TIHULU Project <noreply@github.com>
Depends: python3 (>= 3.11), python3-pyqt5, python3-pyqt5.qtwebengine, python3-numpy, python3-skyfield, rtl-sdr, xdg-utils
Recommends: multimon-ng, qtwayland5, python3-pyqt5.qtmultimedia
Description: TIHULU Satellite Center real native Qt desktop for Debian
 Independent Qt Widgets SDR desktop (no browser or embedded WebView),
 receive-only rtl_sdr USB, pass schedules, long on-disk raw IQ recording,
 local spectral FFT, saved images/audio and provenance ZIP exports.
 HTTP companion is explicitly opt-in and not launched by the GUI.
EOF
cat > "$PKG/usr/bin/tihulu-satellite-center" <<'EOF'
#!/bin/sh
set -eu
export PYTHONPATH="/usr/share/tihulu-satellite-center${PYTHONPATH:+:$PYTHONPATH}"
# Prefer native Wayland in COSMIC/Pop!_OS, XWayland fallback as needed.
if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -z "${QT_QPA_PLATFORM:-}" ]; then
 export QT_QPA_PLATFORM="wayland;xcb"
fi
if [ "$#" -eq 0 ]; then
 set -- desktop
fi
exec /usr/bin/python3 -m satellite_center "$@"
EOF
chmod 755 "$PKG/usr/bin/tihulu-satellite-center"
cat > "$PKG/usr/share/applications/tihulu-satellite-center.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=TIHULU Satellite Center
GenericName=Satellite SDR Receiver
Comment=Native Qt Widgets SDR recording, planning and analysis
Exec=tihulu-satellite-center desktop
Icon=tihulu-satellite
Terminal=false
StartupNotify=true
Categories=Science;Education;HamRadio;
Keywords=RTL-SDR;SSTV;Meteor;Satellite;Debian;Radio;
EOF
install -m 644 satellite_center/assets/tihulu-satellite.svg \
 "$PKG/usr/share/icons/hicolor/scalable/apps/tihulu-satellite.svg"
install -m 644 satellite_center/assets/tihulu-satellite.png \
 "$PKG/usr/share/icons/hicolor/512x512/apps/tihulu-satellite.png"
mkdir -p dist
dpkg-deb --root-owner-group --build "$PKG" "dist/tihulu-satellite-center_${VERSION}_all.deb"
echo "Created Debian native package: dist/tihulu-satellite-center_${VERSION}_all.deb"
