#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DRY_RUN=0
INSTALL_PACKAGES=0
INSTALL_APP_PACKAGES=0
INSTALL_APPS=0
SET_SYSTEM_KEYMAP=0
WALLPAPER=""

usage() {
    cat <<'EOF'
Usage: ./install.sh [options]

  --dry-run                 Show planned changes without writing anything
  --packages                Install the curated Sparrow Shell core packages
  --apps                    Configure installed themed applications
  --full                    Install core + themed apps, then configure them
  --system-keymap           Set the system keymap to Slovenian
  --wallpaper PATH          Regenerate the live palette from this wallpaper
  -h, --help                Show this help

The default only installs dotfiles. It does not change packages, locale, or
application accounts. Existing files are backed up before replacement.
EOF
}

while (($#)); do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --packages) INSTALL_PACKAGES=1 ;;
        --apps) INSTALL_APPS=1 ;;
        --full) INSTALL_PACKAGES=1; INSTALL_APP_PACKAGES=1; INSTALL_APPS=1 ;;
        --system-keymap) SET_SYSTEM_KEYMAP=1 ;;
        --wallpaper) WALLPAPER=${2:?--wallpaper needs a path}; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

HOME_DIR=${HOME:?HOME is not set}
CURRENT_USER=${USER:-$(id -un)}
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$HOME_DIR/.local/state/sparrow-shell-backups/$STAMP"

run() {
    printf '+ '; printf '%q ' "$@"; printf '\n'
    ((DRY_RUN)) || "$@"
}

[[ -d "$ROOT/dotfiles" ]] || { echo "Missing dotfiles payload" >&2; exit 1; }
if ((INSTALL_PACKAGES)) && ! command -v pacman >/dev/null; then
    echo "Package installation is supported only on Arch Linux and CachyOS." >&2
    exit 1
fi
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
if ! command -v rsync >/dev/null && ((INSTALL_PACKAGES == 0)); then
    echo "rsync is required. Install it or rerun with --packages/--full." >&2
    exit 1
fi
run mkdir -p "$BACKUP"
run rsync -a --backup --backup-dir="$BACKUP" "$ROOT/dotfiles/" "$HOME_DIR/"
run install -Dm755 "$ROOT/scripts/sparrow-update" "$HOME_DIR/.local/bin/sparrow-update"
run install -Dm755 "$ROOT/dotfiles/.config/hypr/scripts/ricelin" "$HOME_DIR/.local/bin/sparrow-shell"

if ((INSTALL_PACKAGES)); then
    package_list=$(mktemp)
    repo_list=$(mktemp)
    aur_list=$(mktemp)
    sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "$ROOT/packages/core.txt" > "$package_list"
    if ((INSTALL_APP_PACKAGES)); then
        sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "$ROOT/packages/apps.txt" >> "$package_list"
    fi
    sort -u -o "$package_list" "$package_list"
    while IFS= read -r package; do
        if pacman -Si "$package" >/dev/null 2>&1; then
            printf '%s\n' "$package" >> "$repo_list"
        else
            printf '%s\n' "$package" >> "$aur_list"
        fi
    done < "$package_list"
    if ((DRY_RUN)); then
        echo "Would install $(wc -l < "$repo_list") repository and $(wc -l < "$aur_list") AUR packages."
    else
        if [[ -s "$repo_list" ]]; then
            mapfile -t repo_packages < "$repo_list"
            sudo pacman -S --needed --noconfirm -- "${repo_packages[@]}"
        fi
        helper=$(command -v yay || command -v paru || true)
        if [[ -z "$helper" && -s "$aur_list" ]]; then
            sudo pacman -S --needed --noconfirm base-devel git
            build_dir=$(mktemp -d)
            trap 'rm -rf "$build_dir"' EXIT
            git clone https://aur.archlinux.org/yay-bin.git "$build_dir/yay-bin"
            (cd "$build_dir/yay-bin" && makepkg -si --noconfirm)
            helper=$(command -v yay || command -v paru || true)
        fi
        if [[ -n "$helper" && -s "$aur_list" ]]; then
            mapfile -t aur_packages < "$aur_list"
            "$helper" -S --needed --noconfirm -- "${aur_packages[@]}"
        elif [[ -z "$helper" && -s "$aur_list" ]]; then
            echo "No AUR helper available; skipping AUR packages." >&2
        fi
    fi
    rm -f "$package_list" "$repo_list" "$aur_list"
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
        if [[ -d /opt/spotify/Apps && ! -w /opt/spotify/Apps ]] && command -v setfacl >/dev/null; then
            if ((DRY_RUN)); then
                echo "Would grant the current user write access to /opt/spotify for Spicetify."
            else
                sudo setfacl -R -m "u:${CURRENT_USER}:rwx" /opt/spotify
                sudo setfacl -R -d -m "u:${CURRENT_USER}:rwx" /opt/spotify
            fi
        fi
        run spicetify config prefs_path "$HOME_DIR/.config/spotify/prefs"
        run spicetify config custom_apps marketplace
        run spicetify apply
    fi
    if command -v pipx >/dev/null; then
        if ! command -v pywalfox >/dev/null; then
            run pipx install pywalfox
        fi
        pywalfox_bin=$(command -v pywalfox || true)
        [[ -n "$pywalfox_bin" ]] || pywalfox_bin="$HOME_DIR/.local/bin/pywalfox"
        if [[ -x "$pywalfox_bin" ]] || ((DRY_RUN)); then
            run "$pywalfox_bin" install
        fi
    else
        echo "pipx not found; install Pywalfox manually from docs/manual-steps.md." >&2
    fi
fi

if ((INSTALL_PACKAGES)); then
    rishot_dir="$HOME_DIR/.local/share/rishot"
    if ! command -v rishot >/dev/null; then
        if ((DRY_RUN)); then
            echo "Would install rishot from https://github.com/Gakuseei/rishot."
        else
            if [[ ! -d "$rishot_dir/.git" ]]; then
                git clone --depth 1 https://github.com/Gakuseei/rishot.git "$rishot_dir"
            fi
            mkdir -p "$HOME_DIR/.local/bin"
            ln -sfn "$rishot_dir/bin/rishot" "$HOME_DIR/.local/bin/rishot"
        fi
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
