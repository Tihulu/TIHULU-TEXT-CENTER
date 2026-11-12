#!/usr/bin/env bash
# TIHULU Media Center compatibility installer entrypoint.
# This file no longer fetches/installs Text Center or a floating old feature.
# SPDX-License-Identifier: GPL-2.0-or-later
set -Eeuo pipefail

script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$script_root/kaffeine_next/install.sh" ]]; then
  echo "A complete reviewed Media source checkout is required." >&2
  exit 1
fi
if [[ -z "${TIHULU_MEDIA_SOURCE_SHA:-}" ]]; then
  echo "Set TIHULU_MEDIA_SOURCE_SHA to the exact audited Media source commit." >&2
  exit 1
fi
case "${1:-}" in
  ""|--local|--tv-only|--no-ai)
    exec /bin/bash "$script_root/kaffeine_next/install.sh" --no-ai ;;
  --with-ai)
    exec /bin/bash "$script_root/kaffeine_next/install.sh" --with-ai ;;
  --with-dab|--with-analog)
    exec /bin/bash "$script_root/kaffeine_next/install.sh" --no-ai "$1" ;;
  *)
    echo "Usage: bash tv_center/install.sh [--local|--tv-only|--no-ai|--with-ai|--with-dab|--with-analog]" >&2
    exit 2 ;;
esac
