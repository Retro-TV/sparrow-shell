#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
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
for tool in bash diff python3 rg; do
    if command -v "$tool" >/dev/null 2>&1; then
        printf 'PASS  validator available: %s\n' "$tool"
    else
        printf 'FAIL  validator missing: %s\n' "$tool"
        fail=1
    fi
done
check 'wallcolor Python syntax' python3 -m py_compile "$ROOT/dotfiles/.config/hypr/scripts/wallcolors.py"
check 'wallcolor contrast policy' python3 "$ROOT/scripts/test-palette.py"
check 'terminal palette Python syntax' python3 -m py_compile "$ROOT/dotfiles/.local/bin/sparrow-terminal-palette.py"
check 'wallpaper shell syntax' bash -n "$ROOT/dotfiles/.config/hypr/scripts/wallpaper.sh"
check 'Sparrow updater shell syntax' bash -n "$ROOT/scripts/sparrow-update"
check 'Ricelin updater Python syntax' python3 -m py_compile "$ROOT/dotfiles/.config/hypr/scripts/ricelin-update.py"
check 'installer shell syntax' bash -n "$ROOT/install.sh"
if command -v jq >/dev/null && [[ -f "$ROOT/dotfiles/.config/vesktop/settings/settings.json" ]]; then
    check 'Vesktop settings JSON' jq empty "$ROOT/dotfiles/.config/vesktop/settings/settings.json"
fi
if command -v node >/dev/null; then
    check 'Quickshell JavaScript tests' node --test \
        "$ROOT/dotfiles/.config/quickshell/launcher/lib/fuzzy.test.mjs" \
        "$ROOT/dotfiles/.config/quickshell/pill/lib/monitors.test.mjs"
fi
for manifest in "$ROOT/packages/core.txt" "$ROOT/packages/apps.txt"; do
    check "$(basename "$manifest") sorted and unique" \
        bash -c 'diff -u "$1" <(sort -u "$1")' _ "$manifest"
done
if rg -n '/home/[^/$[:space:]]+|/Users/[^/$[:space:]]+' "$ROOT/dotfiles" --hidden \
    --glob '!**/*.pak' >/dev/null; then
    printf 'FAIL  portable home paths\n'
    fail=1
else
    printf 'PASS  portable home paths\n'
fi
if rg -n -i '(gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|BEGIN [A-Z ]*PRIVATE KEY|aws_secret_access_key)' \
    "$ROOT" --hidden --glob '!.git/**' --glob '!docs/assets/**' \
    --glob '!scripts/validate.sh' >/dev/null; then
    printf 'FAIL  credential pattern scan\n'
    fail=1
else
    printf 'PASS  credential pattern scan\n'
fi
if ((fail)); then exit 1; fi
echo 'Validation complete.'
