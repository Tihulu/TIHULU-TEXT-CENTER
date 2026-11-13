#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Standalone Media CI/provisioned-VM installer; no global APT/dpkg mutation.
set -Eeuo pipefail
if [[ "$(uname -s)" != Linux ]] || (( EUID == 0 )); then
  echo "MEDIA_STANDALONE_HOLD: non-root Linux desktop user required" >&2
  exit 2
fi
SOURCE_DIR="${TIHULU_MEDIA_SOURCE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
REVIEWED_SHA="${TIHULU_MEDIA_SOURCE_SHA:-}"
[[ "$REVIEWED_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "MEDIA_STANDALONE_HOLD: exact reviewed source SHA required" >&2; exit 2;
}
GUARD="$SOURCE_DIR/kaffeine_next/media_standalone_guard.py"
[[ -f "$GUARD" && ! -L "$GUARD" ]] || {
  echo "MEDIA_STANDALONE_HOLD: unavailable standalone guard" >&2; exit 2;
}
DRY=0; ROLLBACK=0; RECOVER=0; WITH_DAB=0; WITH_AI=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --rollback) ROLLBACK=1 ;;
    --recover) RECOVER=1 ;;
    --no-ai) WITH_AI=0 ;;
    --with-ai) WITH_AI=1 ;;
    --with-dab) WITH_DAB=1 ;;
    --with-analog) : ;; # no global RTL-SDR package mutation
    *) echo "Usage: install.sh [--dry-run|--rollback|--recover] [--no-ai|--with-ai] [--with-dab]" >&2; exit 2 ;;
  esac
done
(( DRY + ROLLBACK + RECOVER <= 1 )) || {
  echo "MEDIA_STANDALONE_HOLD: conflicting transaction modes" >&2; exit 2;
}
# A single non-root guard owns an inode-checked flock across source
# verification, full native build, activation, rollback or recovery. The child
# inherits the SAME held FD. Dry-run remains completely read-only.
if (( !DRY )) && [[ -z "${TIHULU_MEDIA_TRANSACTION_FD:-}" ]]; then
  exec /usr/bin/python3 "$GUARD" guarded-script --source "$SOURCE_DIR" \
    --sha "$REVIEWED_SHA" --script "$SOURCE_DIR/kaffeine_next/media_standalone_install.sh" -- "$@"
fi
if (( DRY )); then
  OPT=()
  if (( WITH_AI )); then OPT+=(--with-ai); fi
  if (( WITH_DAB )); then OPT+=(--with-dab); fi
  exec python3 "$GUARD" dry-run --source "$SOURCE_DIR" --sha "$REVIEWED_SHA" "${OPT[@]}"
fi
if (( ROLLBACK || RECOVER )); then
  python3 "$GUARD" rollback-plan --sha "$REVIEWED_SHA" >/dev/null
  exec python3 "$GUARD" rollback --sha "$REVIEWED_SHA"
fi
PLAN="$(python3 "$GUARD" preflight --source "$SOURCE_DIR" --sha "$REVIEWED_SHA")"
if printf '%s' "$PLAN" | python3 -c \
  'import json,sys; exit(0 if json.load(sys.stdin)["already_active"] else 1)'; then
  echo "Already installed and hash verified: $REVIEWED_SHA"
  exit 0
fi
# Prerequisites must be provisioned separately in a disposable VM.
# No sudo, APT, dpkg -i, shared Argos changes or auto-downloaded models.
for cmd in git cmake g++ make pkg-config python3 ffmpeg; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "MEDIA_STANDALONE_HOLD: missing prerequisite $cmd" >&2; exit 2;
  }
done
if [[ "${TIHULU_MEDIA_IMPORT_STOCK_KAFFEINE:-0}" == 1 ]]; then
  echo "MEDIA_STANDALONE_HOLD: silent stock/stable import forbidden" >&2; exit 2
fi
if (( WITH_AI )); then
  echo "AI remains opt-in via Model Market; no installer model/Argos writes."
fi
if (( WITH_DAB )); then
  echo "DAB opt-in retained; provision welle-cli separately (no APT writes)."
fi
TMP="$(mktemp -d)"
BUILDSRC="$TMP/upstream"
BUILD="$TMP/build"
ARTIFACT="$TMP/release"
cleanup() {
  # Only this unique temp tree is ours; never delete installed/user folders.
  rm -rf -- "$TMP"
}
trap cleanup EXIT
mkdir -p "$ARTIFACT/share" "$ARTIFACT/aux" "$ARTIFACT/setup"
UPSTREAM_SHA=e7ea15b86dafed3b20b151cbcb080578ab8e2d5c
git clone --depth 1 --no-tags --branch v2.0.19 \
  https://github.com/KDE/kaffeine.git "$BUILDSRC"
[[ "$(git -C "$BUILDSRC" rev-parse HEAD)" == "$UPSTREAM_SHA" ]] || {
  echo "MEDIA_STANDALONE_HOLD: upstream Git mismatch" >&2; exit 2;
}
python3 "$SOURCE_DIR/kaffeine_next/patch_upstream.py" "$BUILDSRC"
git -C "$BUILDSRC" diff --check
SQL_HEADER="$BUILDSRC/src/sqlinterface.h"
if grep -Fq 'std::prev(container.constEnd(), -1)' "$SQL_HEADER" ||
   ! grep -Fq 'std::prev(container.constEnd())' "$SQL_HEADER"; then
  echo "MEDIA_STANDALONE_HOLD: Kaffeine SQL iterator fix missing" >&2; exit 2;
fi
SYSTEM_ENV=(env -i "HOME=$HOME" "USER=$(id -un)" \
  "PATH=/usr/bin:/bin:/usr/sbin:/sbin" "LANG=C.UTF-8")
"${SYSTEM_ENV[@]}" /usr/bin/cmake -S "$BUILDSRC" -B "$BUILD" \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
  -DCMAKE_INSTALL_PREFIX="$ARTIFACT"
"${SYSTEM_ENV[@]}" /usr/bin/cmake --build "$BUILD" --parallel 2
"${SYSTEM_ENV[@]}" /usr/bin/cmake --install "$BUILD"
[[ -x "$ARTIFACT/bin/kaffeine" ]] || {
  echo "MEDIA_STANDALONE_HOLD: no compiled native player" >&2; exit 2;
}
ln -s kaffeine "$ARTIFACT/bin/tihulu-media-standalone"
cp -a "$SOURCE_DIR/tv_center" "$SOURCE_DIR/kaffeine_next" "$ARTIFACT/share/"
# The SHIPPED auxiliary is forced into no-APT standalone mode even when
# launched directly from a desktop/menu without any inherited environment.
# Keep the legacy source script untouched for historical CI compatibility.
cat > "$ARTIFACT/aux/install_welle.sh" <<'SAFE_WELLE'
#!/usr/bin/env bash
set -Eeuo pipefail
export TIHULU_MEDIA_STANDALONE=1
exec /bin/bash "$HOME/.local/opt/tihulu-media-standalone/current/share/kaffeine_next/install_welle.sh" "$@"
SAFE_WELLE
cp "$SOURCE_DIR/kaffeine_next/dvb_diagnostics.sh" "$ARTIFACT/aux/dvb_diagnostics.sh"
chmod 755 "$ARTIFACT/aux/"*.sh
cp "$SOURCE_DIR/kaffeine_next/assets/tihulu-media-center.svg" "$ARTIFACT/setup/icon"
cat > "$ARTIFACT/setup/launcher" <<'LAUNCH'
#!/bin/sh
export TIHULU_MEDIA_STANDALONE=1
if [ -n "${WAYLAND_DISPLAY:-}" ]; then export QT_QPA_PLATFORM=xcb; fi
if [ -z "${TIHULU_VLC_PROFILE:-}" ]; then
  if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -r /proc/driver/nvidia/version ]; then
    TIHULU_VLC_PROFILE=software
  else
    TIHULU_VLC_PROFILE=auto
  fi
fi
case "${1:-}" in
  --diagnose-tuner) shift; exec /bin/bash "$HOME/.local/opt/tihulu-media-standalone/current/aux/dvb_diagnostics.sh" "$@" ;;
  --software-video) TIHULU_VLC_PROFILE=software; shift ;;
  --auto-video) TIHULU_VLC_PROFILE=auto; shift ;;
  --diagnose-no-audio) TIHULU_VLC_PROFILE=software-no-audio; shift ;;
esac
export TIHULU_VLC_PROFILE
if [ "$#" -eq 0 ] && [ "${TIHULU_AUTOPLAY_LAST_CHANNEL:-0}" = 1 ]; then
  set -- --lastchannel
fi
exec /usr/bin/env -u LD_LIBRARY_PATH -u LD_PRELOAD -u QT_PLUGIN_PATH \
  -u QT_QPA_PLATFORM_PLUGIN_PATH -u QML2_IMPORT_PATH -u QML_IMPORT_PATH \
  "$HOME/.local/opt/tihulu-media-standalone/current/bin/tihulu-media-standalone" "$@"
LAUNCH
cat > "$ARTIFACT/setup/cli" <<'CLI'
#!/bin/sh
export TIHULU_MEDIA_STANDALONE=1
BASE="$HOME/.local/opt/tihulu-media-standalone/current"
export PYTHONPATH="$BASE/share${PYTHONPATH:+:$PYTHONPATH}"
if [ -n "${WAYLAND_DISPLAY:-}" ]; then export QT_QPA_PLATFORM=xcb; fi
PYTHON=/usr/bin/python3
AI_ENV="$HOME/.local/share/tihulu-media-standalone/ai-runtime"
if [ -f "$AI_ENV/.tihulu-owned-ai-runtime" ] && [ -x "$AI_ENV/bin/python3" ]; then
  PYTHON="$AI_ENV/bin/python3"
fi
exec "$PYTHON" -m tv_center "$@"
CLI
cat > "$ARTIFACT/setup/desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=TIHULU Media Center (Standalone)
GenericName=TV · DAB+ Radio · Offline AI
Comment=New Media with separate settings from frozen stable Media
Exec=$HOME/.local/bin/tihulu-media-standalone
TryExec=$HOME/.local/bin/tihulu-media-standalone
Icon=tihulu-media-standalone
StartupWMClass=tihulu-media-standalone
Terminal=false
Categories=AudioVideo;Video;TV;Audio;Player;
DESKTOP
chmod 755 "$ARTIFACT/setup/launcher" "$ARTIFACT/setup/cli"
chmod 600 "$ARTIFACT/setup/desktop" "$ARTIFACT/setup/icon"
# One owner-only ledger hashes and prevalidates every release file and shared
# destination BEFORE it starts writing. No global package transaction exists.
python3 "$GUARD" activate --source "$SOURCE_DIR" --sha "$REVIEWED_SHA" \
  --artifact "$ARTIFACT"
echo "Standalone: $HOME/.local/bin/tihulu-media-standalone"
echo "Model Market: $HOME/.local/bin/tihulu-media-standalone-cli ai-market"
echo "Stable Media settings, channels, recordings, models and packages preserved."
