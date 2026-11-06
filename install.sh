#!/usr/bin/env bash
# TIHULU TEXT CENTER — safe local install/update, no sudo or RF tuning.
set -euo pipefail

fail() { printf 'TIHULU install: %s\n' "$*" >&2; exit 1; }
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
mode="${1:-install}"
[[ "$#" -le 1 && ( "$mode" == install || "$mode" == --update || "$mode" == --check ) ]] ||
    fail "Usage: bash install.sh [--update|--check]"

command -v python3 >/dev/null || fail "Python 3.11+ is required"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' ||
    fail "Python 3.11+ is required (the active python3 is older)"
command -v git >/dev/null || fail "git is required"

if [[ "$mode" == --update ]]; then
    [[ -d "$repo/.git" || -f "$repo/.git" ]] || fail "Not a Git checkout; cannot safely update"
    [[ -z "$(git -C "$repo" status --porcelain)" ]] ||
        fail "Uncommitted or untracked files exist; preserve your work and update manually"
    branch="$(git -C "$repo" symbolic-ref --short HEAD 2>/dev/null)" ||
        fail "Detached HEAD; select the intended branch before updating"
    git -C "$repo" fetch origin "$branch" ||
        fail "Could not fetch origin/$branch; no files were overwritten"
    git -C "$repo" merge --ff-only FETCH_HEAD ||
        fail "Your branch diverged; update stopped without reset, merge, or force-push"
fi

if [[ "$mode" != --check ]]; then
    bin="$HOME/.local/bin"
    mkdir -p "$bin"
    for name in tihulu-text-center tihulu-text-center-update; do
        file="$bin/$name"
        if [[ -e "$file" ]] && ! grep -Fq "TIHULU TEXT CENTER launcher managed by install.sh" "$file"; then
            fail "Refusing to overwrite unrelated file: $file"
        fi
    done
    {
        printf '#!/usr/bin/env bash\n'
        printf '# TIHULU TEXT CENTER launcher managed by install.sh\n'
        printf 'set -euo pipefail\ncd %q\n' "$repo"
        printf 'exec python3 -m textcenter "$@"\n'
    } > "$bin/tihulu-text-center"
    {
        printf '#!/usr/bin/env bash\n'
        printf '# TIHULU TEXT CENTER launcher managed by install.sh\n'
        printf 'set -euo pipefail\nexec bash %q --update\n' "$repo/install.sh"
    } > "$bin/tihulu-text-center-update"
    chmod 755 "$bin/tihulu-text-center" "$bin/tihulu-text-center-update"
    case "$(uname -s)" in
      Linux)
        xdg="$HOME/.local/share"
        entry="$xdg/applications/tihulu-text-center.desktop"
        mkdir -p "$(dirname "$entry")"
        if [[ -e "$entry" ]] && ! grep -Fq "X-Tihulu-Managed=true" "$entry"; then
            fail "Unrelated desktop entry exists at $entry; not overwriting"
        fi
        {
            printf '%s\n' '[Desktop Entry]' 'Type=Application' 'Name=TIHULU Text Center'
            printf '%s\n' 'Comment=Offline-first SDR radio, TV and text center'
            printf 'Exec="%s/tihulu-text-center" desktop\n' "$bin"
            printf 'Icon=%s/web/favicon.svg\n' "$repo"
            printf '%s\n' 'Terminal=false' 'Categories=AudioVideo;Network;Utility;'
            printf '%s\n' 'StartupNotify=true' 'X-Tihulu-Managed=true'
        } > "$entry"
        chmod 644 "$entry"
        ;;
      Darwin)
        app="$HOME/Applications/Tihulu Text Center.app"
        script="$app/Contents/MacOS/TihuluTextCenter"
        mkdir -p "$app/Contents/MacOS"
        if [[ -e "$script" ]] && ! grep -Fq 'TIHULU Text Center managed app' "$script"; then
            fail "An unrelated macOS app launcher already exists: $script"
        fi
        {
            printf '%s\n' '#!/usr/bin/env bash' '# TIHULU Text Center managed app'
            printf 'cd %q\n' "$repo"
            printf '%s\n' 'exec python3 -m textcenter desktop'
        } > "$script"
        chmod 755 "$script"
        cat > "$app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>TIHULU Text Center</string>
  <key>CFBundleExecutable</key><string>TihuluTextCenter</string>
  <key>CFBundleIdentifier</key><string>dev.tihulu.textcenter</string>
  <key>CFBundlePackageType</key><string>APPL</string>
</dict></plist>
PLIST
        ;;
    esac
fi

(
    cd "$repo"
    python3 -m compileall -q textcenter
) || fail "Python source compilation failed; inspect the checkout"

printf '\nTIHULU TEXT CENTER %s ready at: %s\n' "$mode" "$repo"
printf 'Commands (if ~/.local/bin is in PATH):\n'
printf '  tihulu-text-center serve --port 8787\n'
printf '  tihulu-text-center doctor\n'
printf '  tihulu-text-center-update\n'
printf 'Or use: %s/tihulu-text-center serve\n' "$HOME/.local/bin"
printf '\nOptional receiver/decoder dependencies (not installed automatically):\n'
for exe in rtl_fm rtl_power redsea ffmpeg welle-cli; do
    if command -v "$exe" >/dev/null 2>&1; then
        printf '  %-12s installed\n' "$exe"
    else
        printf '  %-12s MISSING (dependent features remain disabled)\n' "$exe"
    fi
done
printf 'No RF scan, model download, background service, sudo action or Internet polling was started.\n'
printf 'User archives remain under ~/.local/share/tihulu-text-center/.\n'
