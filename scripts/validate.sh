#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
fail=0
check() {
    local label=$1; shift
    if "$@" >/dev/null 2>&1; then
        printf 'PASS  %s\n' "$label"
    else
        printf 'FAIL  %s\n' "$label"
        fail=1
    fi
}
check 'wallcolor Python syntax' python3 -m py_compile "$ROOT/dotfiles/.config/hypr/scripts/wallcolors.py"
check 'wallpaper shell syntax' bash -n "$ROOT/dotfiles/.config/hypr/scripts/wallpaper.sh"
check 'Sparrow updater shell syntax' bash -n "$ROOT/scripts/sparrow-update"
check 'Ricelin updater Python syntax' python3 -m py_compile "$ROOT/dotfiles/.config/hypr/scripts/ricelin-update.py"
if command -v jq >/dev/null && [[ -f "$ROOT/dotfiles/.config/vesktop/settings/settings.json" ]]; then
    check 'Vesktop settings JSON' jq empty "$ROOT/dotfiles/.config/vesktop/settings/settings.json"
fi
if ((fail)); then exit 1; fi
echo 'Validation complete.'
