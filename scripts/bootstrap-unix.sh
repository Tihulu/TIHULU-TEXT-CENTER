#!/usr/bin/env bash
# TIHULU TEXT CENTER — non-destructive bootstrap for Debian, Raspberry Pi OS and macOS.
set -euo pipefail
fail(){ printf 'TIHULU bootstrap: %s\n' "$*" >&2; exit 1; }
ref="${1:-main}"
preview_switch="${2:-}"
[[ "$#" -le 2 && ( -z "$preview_switch" || "$preview_switch" == "--switch" ) ]] ||
    fail "Usage: bash bootstrap-unix.sh [branch] [--switch]"
# --switch explicitly authorizes a clean worktree to change between preview
# branches; it never resets/force-pulls/deletes the previous branch or user data.
command -v git >/dev/null || fail "git is required"
command -v python3 >/dev/null || fail "Python 3.11+ is required"
python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)' ||
    fail "Python 3.11 or newer is required"
git check-ref-format --branch "$ref" >/dev/null 2>&1 ||
    fail "Invalid branch name"
root="$HOME/.local/opt"
dest="$root/tihulu-text-center"
mkdir -p "$root"
if [[ -e "$dest" ]]; then
    [[ -d "$dest/.git" ]] || fail "Refusing to overwrite unrelated directory $dest"
    remote="$(git -C "$dest" remote get-url origin)" || fail "Missing git origin"
    [[ "$remote" == "https://github.com/Tihulu/TIHULU-TEXT-CENTER.git" ]] ||
        fail "Unexpected git origin; refusing to update"
    [[ -z "$(git -C "$dest" status --porcelain)" ]] ||
        fail "Local changes detected; refusing to overwrite"
    active="$(git -C "$dest" symbolic-ref --short HEAD)" ||
        fail "Detached HEAD not eligible for automated update"
    git -C "$dest" fetch origin "$ref"
    if [[ "$active" != "$ref" ]]; then
        [[ "$preview_switch" == "--switch" ]] ||
            fail "Checkout is on $active, requested $ref; pass --switch to explicitly change preview branches"
        if git -C "$dest" show-ref --verify --quiet "refs/heads/$ref"; then
            git -C "$dest" switch "$ref" ||
                fail "Could not switch branch safely; previous checkout retained"
        else
            git -C "$dest" switch --create "$ref" FETCH_HEAD ||
                fail "Could not create requested branch safely; previous checkout retained"
        fi
    fi
    git -C "$dest" merge --ff-only FETCH_HEAD ||
        fail "Repository diverged: no merge/reset performed"
else
    git clone --single-branch --branch "$ref" \
        https://github.com/Tihulu/TIHULU-TEXT-CENTER.git "$dest"
fi
bash "$dest/install.sh"
printf 'Launch with: %s/.local/bin/tihulu-text-center desktop\n' "$HOME"
printf 'The source checkout, SQLite and recordings are never deleted by this bootstrap.\n'
