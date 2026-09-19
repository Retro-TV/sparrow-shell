#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DRY_RUN=0
INSTALL_PACKAGES=0
INSTALL_APPS=0
SET_SYSTEM_KEYMAP=0
WALLPAPER=""

usage() {
    cat <<'EOF'
Usage: ./install.sh [options]

  --dry-run                 Show planned changes without writing anything
  --packages                Install recorded official/AUR packages
  --apps                    Set recorded defaults and Spicetify Marketplace
  --system-keymap           Set the system keymap to Slovenian
  --wallpaper PATH          Regenerate the live palette from this wallpaper
  -h, --help                Show this help

The default only installs dotfiles. It does not change packages, locale,
monitor layout, or application accounts.
EOF
}

while (($#)); do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --packages) INSTALL_PACKAGES=1 ;;
        --apps) INSTALL_APPS=1 ;;
        --system-keymap) SET_SYSTEM_KEYMAP=1 ;;
        --wallpaper) WALLPAPER=${2:?--wallpaper needs a path}; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

HOME_DIR=${HOME:?HOME is not set}
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$HOME_DIR/.local/state/sparrow-shell-backups/$STAMP"

run() {
    printf '+ '; printf '%q ' "$@"; printf '\n'
    ((DRY_RUN)) || "$@"
}

[[ -d "$ROOT/dotfiles" ]] || { echo "Missing dotfiles payload" >&2; exit 1; }
if ((DRY_RUN)); then
    echo "Dry run: no files, packages, services, or system settings will change."
else
    mkdir -p "$BACKUP"
fi
if ((INSTALL_PACKAGES)) && ! command -v rsync >/dev/null; then
    if ((DRY_RUN)); then
        echo "Would bootstrap rsync before copying dotfiles."
    else
        sudo pacman -S --needed --noconfirm rsync
    fi
fi
run mkdir -p "$BACKUP"
run rsync -a --backup --backup-dir="$BACKUP" "$ROOT/dotfiles/" "$HOME_DIR/"
run install -Dm755 "$ROOT/scripts/sparrow-update" "$HOME_DIR/.local/bin/sparrow-update"

if ((INSTALL_PACKAGES)); then
    command -v pacman >/dev/null || { echo "pacman is required" >&2; exit 1; }
    native=$(mktemp)
    grep -vxFf "$ROOT/packages/aur.txt" "$ROOT/packages/pacman-explicit.txt" > "$native" || true
    if ((DRY_RUN)); then
        echo "Would install official packages and AUR packages from packages/."
    else
        sudo pacman -S --needed -- < "$native"
        helper=$(command -v yay || command -v paru || true)
        if [[ -z "$helper" && -s "$ROOT/packages/aur.txt" && $DRY_RUN -eq 0 ]]; then
            sudo pacman -S --needed --noconfirm base-devel git
            build_dir=$(mktemp -d)
            trap 'rm -rf "$build_dir"' EXIT
            git clone https://aur.archlinux.org/yay-bin.git "$build_dir/yay-bin"
            (cd "$build_dir/yay-bin" && makepkg -si --noconfirm)
            helper=$(command -v yay || command -v paru || true)
        fi
        if [[ -n "$helper" && -s "$ROOT/packages/aur.txt" ]]; then
            "$helper" -S --needed -- < "$ROOT/packages/aur.txt"
        elif [[ -z "$helper" && -s "$ROOT/packages/aur.txt" ]]; then
            echo "No AUR helper available; skipping AUR packages." >&2
        fi
    fi
    rm -f "$native"
fi

if ((SET_SYSTEM_KEYMAP)); then
    if ((DRY_RUN)); then
        echo "Would set X11 keymap to si/pc105 and console keymap to slovene."
    else
        sudo localectl set-x11-keymap si pc105
        sudo localectl set-keymap slovene
    fi
fi

if ((INSTALL_APPS)); then
    if command -v xdg-mime >/dev/null; then
        while IFS=$'\t' read -r mime desktop; do
            [[ -n "$mime" && -n "$desktop" ]] || continue
            run xdg-mime default "$desktop" "$mime"
        done < "$ROOT/system/default-apps.tsv"
    fi
    if command -v spicetify >/dev/null; then
        run spicetify config custom_apps marketplace
        run spicetify apply
    fi
    if command -v pipx >/dev/null; then
        if ! command -v pywalfox >/dev/null; then
            run pipx install pywalfox
        fi
        if command -v pywalfox >/dev/null; then
            run pywalfox install
        fi
    else
        echo "pipx not found; install Pywalfox manually from docs/manual-steps.md." >&2
    fi
fi

if [[ -n "$WALLPAPER" ]]; then
    [[ -f "$WALLPAPER" ]] || { echo "Wallpaper not found: $WALLPAPER" >&2; exit 1; }
    run python3 "$HOME_DIR/.config/hypr/scripts/wallcolors.py" "$WALLPAPER"
fi

if ((DRY_RUN == 0)); then
    systemctl --user daemon-reload 2>/dev/null || true
    echo "Installed. Backup: $BACKUP"
fi
