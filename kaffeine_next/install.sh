#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# QA-05: legacy installer entrypoint MUST NOT perform any system/package writes.
set -Eeuo pipefail
SOURCE_DIR="${TIHULU_MEDIA_SOURCE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
EXPECTED_SHA="${TIHULU_MEDIA_SOURCE_SHA:-}"
if [[ ! "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "MEDIA_INSTALL_HOLD: exact reviewed SHA is required" >&2
  exit 2
fi
SAFE="$SOURCE_DIR/kaffeine_next/media_standalone_install.sh"
if [[ -f "$SAFE" && ! -L "$SAFE" ]]; then
  # Only the distinct development Media entrypoint is executable. Frozen
  # stable launchers, dpkg and user data are never modified here.
  exec /bin/bash "$SAFE" "$@"
fi
# Source-only QA-03 fake-Git fixtures intentionally do not contain the new
# installer; preserve their original read-only dry-run test and fail closed
# for every mutating/rollback path. NEVER run historical unsafe installation.
DRY=0; AI=0; DAB=0; ANALOG=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --with-ai) AI=1 ;;
    --with-dab) DAB=1 ;;
    --with-analog) ANALOG=1 ;;
    --no-ai) : ;;
    *) echo "MEDIA_INSTALL_HOLD: standalone installer absent; no writes permitted" >&2; exit 2 ;;
  esac
done
if (( DRY == 0 )); then
  echo "MEDIA_INSTALL_HOLD: standalone installer absent; no writes permitted" >&2
  exit 2
fi
GUARD="$SOURCE_DIR/kaffeine_next/media_install_guard.py"
OPTS=()
if (( AI )); then OPTS+=(--with-ai); fi
if (( DAB )); then OPTS+=(--with-dab); fi
if (( ANALOG )); then OPTS+=(--with-analog); fi
exec python3 "$GUARD" dry-run --source "$SOURCE_DIR" --sha "$EXPECTED_SHA" "${OPTS[@]}"
