#!/usr/bin/env bash
# TIHULU Satellite Center: native Qt Debian/Ubuntu/Pop!_OS one-command install.
# This does not install the separate web/PWA launcher, start any SDR capture,
# activate a background daemon, or modify unrelated TIHULU applications.
set -euo pipefail

fail() { printf 'TIHULU install: %s\n' "$*" >&2; exit 1; }
case "$(uname -s)" in Linux) ;; *) fail "This .deb installer requires Linux. Use install.sh on macOS." ;; esac
[[ -r /etc/os-release ]] || fail "Cannot identify Linux distribution."
# shellcheck source=/dev/null
. /etc/os-release
case " ${ID:-} ${ID_LIKE:-} " in
  *debian*|*ubuntu*|*pop*) ;;
  *) fail "This installer targets Debian, Ubuntu and Pop!_OS; found ${ID:-unknown}." ;;
esac
for program in curl tar dpkg-deb apt; do
  command -v "$program" >/dev/null 2>&1 || fail "Missing $program. Install it first."
done
if [[ "${EUID}" -ne 0 ]] && ! command -v sudo >/dev/null 2>&1; then
  fail "sudo is needed only for installing the built Debian package."
fi
REF="${TIHULU_REF:-feature/satellite-auto-discovery-integrated-2026-11-06}"
# Normal use is deliberately fixed to the reviewed preview branch.
# Override only when testing an explicitly selected public branch/tag/commit.
[[ "$REF" =~ ^[A-Za-z0-9._/-]+$ && "$REF" != /* && "$REF" != *..* ]] ||
  fail "Unsafe GitHub ref: $REF"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/tihulu-satellite-install.XXXXXXXX")"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/source"
printf 'Downloading the native Qt source from GitHub (%s) ...\n' "$REF"
curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error \
  --retry 3 --connect-timeout 20 \
  "https://codeload.github.com/Tihulu/TIHULU-TEXT-CENTER/tar.gz/$REF" \
  --output "$WORK/source.tar.gz"
tar --extract --gzip --file "$WORK/source.tar.gz" \
  --directory "$WORK/source" --strip-components=1
[[ -f "$WORK/source/satellite_center/packaging/debian/build.sh" ]] ||
  fail "The downloaded GitHub source has no native Debian packager."
printf 'Building the independent .deb package (no Python pip required) ...\n'
(cd "$WORK/source" && bash satellite_center/packaging/debian/build.sh)
package="$(find "$WORK/source/dist" -maxdepth 1 -type f \
  -name 'tihulu-satellite-center_*.deb' -print -quit)"
[[ -n "$package" && -f "$package" ]] || fail "Package build produced no .deb."
[[ "$(dpkg-deb --field "$package" Package)" == 'tihulu-satellite-center' ]] ||
  fail "Package name mismatch."
version="$(dpkg-deb --field "$package" Version)"
[[ "$version" == '0.3.0~preview10' ]] ||
  fail "Expected verified preview9 package, got $version."
printf 'Package: %s\nSHA256: ' "$version"
sha256sum "$package"
if [[ "${TIHULU_BUILD_ONLY:-0}" == 1 ]]; then
  [[ -n "${TIHULU_OUTPUT_DIR:-}" ]] ||
    fail "Build-only mode requires TIHULU_OUTPUT_DIR."
  mkdir -p "$TIHULU_OUTPUT_DIR"
  cp "$package" "$TIHULU_OUTPUT_DIR/"
  echo "Build-only verified package saved in: $TIHULU_OUTPUT_DIR"
  exit 0
fi
# apt may read the package as the _apt user; make temporary source and parent
# traversable without exposing private files (source is a public GitHub archive).
chmod 755 "$WORK" "$WORK/source" "$WORK/source/dist"
chmod 644 "$package"
printf 'Installing/refreshing native system application via apt ...\n'
if [[ "${EUID}" -eq 0 ]]; then
  apt install --reinstall -y "$package"
else
  sudo apt install --reinstall -y "$package"
fi
printf '\nTIHULU Satellite Center %s is installed.\n' "$version"
printf 'Open it from Applications or run: tihulu-satellite-center\n'
printf 'Check dependencies without USB capture: tihulu-satellite-center doctor\n'
printf 'No browser/WebUSB app, automatic SDR acquisition or background service was enabled.\n'
