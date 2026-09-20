#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DRY_RUN=0
INSTALL_PACKAGES=0
INSTALL_APP_PACKAGES=0
INSTALL_APPS=0
SET_SYSTEM_KEYMAP=0
WALLPAPER=""
INTERACTIVE=0
ARG_COUNT=$#
OPTIONAL_FAILURES=0

usage() {
    cat <<'EOF'
Usage: ./install.sh [options]

  --dry-run                 Show planned changes without writing anything
  --settings                Apply settings only; useful for non-interactive updates
  --packages                Install the curated Sparrow Shell core packages
  --apps                    Configure installed themed applications
  --full                    Install core + themed apps, then configure them
  --system-keymap           Set the system keymap to Slovenian
  --wallpaper PATH          Regenerate the live palette from this wallpaper
  --interactive             Use the guided installer menu
  -h, --help                Show this help

Running without options opens the guided installer. Existing files are backed
up before replacement. Explicit flags remain available for scripts and CI.
EOF
}

while (($#)); do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --settings) ;;
        --packages) INSTALL_PACKAGES=1 ;;
        --apps) INSTALL_APPS=1 ;;
        --full) INSTALL_PACKAGES=1; INSTALL_APP_PACKAGES=1; INSTALL_APPS=1 ;;
        --system-keymap) SET_SYSTEM_KEYMAP=1 ;;
        --wallpaper) WALLPAPER=${2:?--wallpaper needs a path}; shift ;;
        --interactive) INTERACTIVE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

choose_install_mode() {
    local choice
    echo "Sparrow Shell guided installer"
    echo "Choose what this machine should receive:"
    if command -v gum >/dev/null 2>&1; then
        choice=$(gum choose \
            "Settings only (existing apps)" \
            "Settings + theme installed apps" \
            "Full install (packages + apps)" \
            "Full install + Slovenian keymap")
    else
        printf '%s\n' \
            '1) Settings only (existing apps)' \
            '2) Settings + theme installed apps' \
            '3) Full install (packages + apps)' \
            '4) Full install + Slovenian keymap'
        read -r -p 'Choose [1-4]: ' choice
    fi
    case "$choice" in
        1|"Settings only (existing apps)") ;;
        2|"Settings + theme installed apps") INSTALL_APPS=1 ;;
        3|"Full install (packages + apps)") INSTALL_PACKAGES=1; INSTALL_APP_PACKAGES=1; INSTALL_APPS=1 ;;
        4|"Full install + Slovenian keymap") INSTALL_PACKAGES=1; INSTALL_APP_PACKAGES=1; INSTALL_APPS=1; SET_SYSTEM_KEYMAP=1 ;;
        *) echo "Invalid selection; nothing was changed." >&2; exit 2 ;;
    esac
    if command -v gum >/dev/null 2>&1; then
        gum confirm "Run a dry run first?" && DRY_RUN=1 || true
    else
        read -r -p 'Run a dry run first? [Y/n] ' choice
        [[ "$choice" =~ ^([Nn][Oo]?|[Nn])$ ]] || DRY_RUN=1
    fi
}

pause_point() {
    ((INTERACTIVE && !DRY_RUN)) || return 0
    if command -v gum >/dev/null 2>&1; then
        gum confirm "$1" || { echo "Stopped at your request. No rollback was needed."; exit 0; }
    else
        read -r -p "$1 Press Enter to continue, or Ctrl-C to stop. " _
    fi
}

if ((ARG_COUNT == 0)); then
    INTERACTIVE=1
    choose_install_mode
fi

HOME_DIR=${HOME:?HOME is not set}
CURRENT_USER=${USER:-$(id -un)}
BIN_DIR="$HOME_DIR/.local/bin"
SYSTEM_BIN_DIR="/usr/local/bin"
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$HOME_DIR/.local/state/sparrow-shell-backups/$STAMP"

run() {
    printf '+ '; printf '%q ' "$@"; printf '\n'
    ((DRY_RUN)) || "$@"
}

run_optional() {
    printf '+ '; printf '%q ' "$@"; printf '\n'
    ((DRY_RUN)) && return 0
    if ! "$@"; then
        echo "Optional integration failed: $*" >&2
        OPTIONAL_FAILURES=$((OPTIONAL_FAILURES + 1))
    fi
    return 0
}

install_keyboard_backend() {
    # The tablet keyboard is core infrastructure, not an optional app. Install
    # its one package independently so an unrelated package/AUR failure cannot
    # leave the visible keyboard without an input daemon.
    ydotool_socket="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/.ydotool_socket"
    if systemctl is-active --quiet sparrow-ydotool.service 2>/dev/null \
        && [[ -S "$ydotool_socket" ]] \
        && "$BIN_DIR/sparrow-ydotool-key" 0:1 0:0 >/dev/null 2>&1; then
        echo "Keyboard backend: ready"
        return 0
    fi

    # A routine settings update must never stop on a sudo prompt. Full/new
    # installs still configure the system service; settings-only updates leave
    # an unavailable backend alone and report how to repair it later.
    if ((INSTALL_PACKAGES == 0 && INSTALL_APPS == 0 && DRY_RUN == 0)) \
        && ! sudo -n true 2>/dev/null; then
        echo "Keyboard backend was not changed (it needs an interactive sudo session)."
        echo "Run the guided/full installer later if this machine needs tablet input."
        return 0
    fi

    if ! command -v ydotool >/dev/null 2>&1; then
        if ((INSTALL_PACKAGES)); then
            run sudo pacman -S --needed --noconfirm ydotool
        else
            echo "ydotool is missing; cannot configure Sparrow's keyboard backend." >&2
            echo "Rerun with --packages or --full." >&2
            return 1
        fi
    fi

    if ((DRY_RUN == 0)) && ! command -v ydotool >/dev/null 2>&1; then
        echo "ydotool installation completed without providing its executable." >&2
        return 1
    fi

    uid=$(id -u "$CURRENT_USER")
    gid=$(id -g "$CURRENT_USER")
    service_tmp=$(mktemp)
    sed -e "s/__UID__/$uid/g" -e "s/__GID__/$gid/g" \
        "$ROOT/system/sparrow-ydotool.service.in" > "$service_tmp"
    run sudo install -Dm644 "$service_tmp" /etc/systemd/system/sparrow-ydotool.service
    rm -f "$service_tmp"

    if ((DRY_RUN)); then
        echo "Would enable Sparrow's private keyboard daemon and verify its socket."
        return 0
    fi

    systemctl --user disable --now ydotool.service >/dev/null 2>&1 || true
    rm -f "$ydotool_socket"
    sudo systemctl daemon-reload
    sudo systemctl enable --now sparrow-ydotool.service
    for _ in {1..20}; do
        sudo systemctl is-active --quiet sparrow-ydotool.service \
            && [[ -S "$ydotool_socket" ]] && break
        sleep 0.1
    done
    if ! sudo systemctl is-active --quiet sparrow-ydotool.service \
        || [[ ! -S "$ydotool_socket" ]] \
        || ! "$BIN_DIR/sparrow-ydotool-key" 0:1 0:0 >/dev/null 2>&1; then
        echo "Keyboard backend failed its input test." >&2
        sudo systemctl status sparrow-ydotool.service --no-pager -l >&2 || true
        return 1
    fi
    echo "Keyboard backend: ready"
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
run rsync -a --backup --backup-dir="$BACKUP" \
    --exclude='.config/systemd/user/default.target.wants/' \
    --exclude='.config/systemd/user/graphical-session.target.wants/' \
    "$ROOT/dotfiles/" "$HOME_DIR/"
run install -Dm755 "$ROOT/scripts/sparrow-update" "$BIN_DIR/sparrow-update"
run install -Dm755 "$ROOT/dotfiles/.config/hypr/scripts/ricelin" "$BIN_DIR/sparrow-shell"
run install -Dm755 "$ROOT/dotfiles/.config/hypr/scripts/ricelin" "$BIN_DIR/sparrow"
run install -Dm755 "$ROOT/dotfiles/.local/bin/sparrow-ydotool-key" "$BIN_DIR/sparrow-ydotool-key"

# Also install the public commands in the normal system command path.  The
# per-user copies remain useful as a fallback, while /usr/local/bin makes the
# commands available immediately from Fish, Bash, Zsh and a newly opened TTY.
if ((DRY_RUN)); then
    echo "Would refresh optional system-wide command shims when sudo is available."
elif sudo -n true 2>/dev/null; then
    run sudo -n install -Dm755 "$ROOT/scripts/sparrow-update" "$SYSTEM_BIN_DIR/sparrow-update"
    run sudo -n install -Dm755 "$ROOT/dotfiles/.config/hypr/scripts/ricelin" "$SYSTEM_BIN_DIR/sparrow-shell"
    run sudo -n install -Dm755 "$ROOT/dotfiles/.config/hypr/scripts/ricelin" "$SYSTEM_BIN_DIR/sparrow"
    run sudo -n install -Dm755 "$ROOT/dotfiles/.local/bin/sparrow-ydotool-key" "$SYSTEM_BIN_DIR/sparrow-ydotool-key"
else
    echo "System-wide command shims were not refreshed (sudo is not cached)."
    echo "The current per-user commands are installed in $BIN_DIR."
fi

# Sparrow's default shell is Fish. A universal Fish path updates running Fish
# sessions as well as future ones; .profile covers POSIX login shells.
if command -v fish >/dev/null 2>&1; then
    # fish_add_path intentionally returns non-zero when the directory is
    # already registered. That is a healthy idempotent update, not an install
    # failure, so force the small Fish snippet to finish successfully.
    run fish -c "fish_add_path -U '$BIN_DIR'; true"
fi
if ((DRY_RUN)); then
    echo "Would ensure $BIN_DIR is exported from $HOME_DIR/.profile."
else
    touch "$HOME_DIR/.profile"
    if ! grep -Fq 'Sparrow Shell commands' "$HOME_DIR/.profile"; then
        printf '\n# Sparrow Shell commands\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME_DIR/.profile"
    fi
fi
pause_point "Base files and the backup are ready. Continue with package and app setup?"

# Complete and verify the mandatory input path before the broad package and
# optional application phases. This is deliberately early: a later Spotify,
# Firefox or AUR problem must not produce a half-installed core desktop.
install_keyboard_backend

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
            run_optional xdg-mime default "$desktop" "$mime"
        done < "$ROOT/system/default-apps.tsv"
    fi
    if command -v spicetify >/dev/null; then
        # Spicetify refuses to operate reliably when the prefs file or path is
        # missing. Create the target first, then set the path explicitly.
        run mkdir -p "$HOME_DIR/.config/spotify"
        run touch "$HOME_DIR/.config/spotify/prefs"
        run_optional spicetify config prefs_path "$HOME_DIR/.config/spotify/prefs"
        pause_point "Close Spotify completely, then continue with the Spicetify backup/apply step."
        if [[ -d /opt/spotify/Apps && ! -w /opt/spotify/Apps ]] && command -v setfacl >/dev/null; then
            if ((DRY_RUN)); then
                echo "Would grant the current user write access to /opt/spotify for Spicetify."
            else
                run_optional sudo setfacl -R -m "u:${CURRENT_USER}:rwx" /opt/spotify
                run_optional sudo setfacl -R -d -m "u:${CURRENT_USER}:rwx" /opt/spotify
            fi
        fi
        run_optional spicetify backup apply
        run_optional spicetify config custom_apps marketplace
        run_optional spicetify apply
    fi
    if command -v pipx >/dev/null; then
        if ! command -v pywalfox >/dev/null; then
            run_optional pipx install pywalfox
        fi
        pywalfox_bin=$(command -v pywalfox || true)
        [[ -n "$pywalfox_bin" ]] || pywalfox_bin="$HOME_DIR/.local/bin/pywalfox"
        if [[ -x "$pywalfox_bin" ]] || ((DRY_RUN)); then
            run_optional "$pywalfox_bin" install
            pause_point "Install and enable the Pywalfox Firefox extension, then use Fetch colors once."
            echo "Firefox step: install and enable the Pywalfox extension in Firefox, then use its Fetch colors action once."
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

# A Ricelin installation normally already records the active wallpaper. Use it
# to render the app palette immediately after copying the files, so a new
# machine does not boot with stale tracked GTK/terminal/Firefox colors.
if [[ -z "$WALLPAPER" ]]; then
    wallpaper_state="$HOME_DIR/.local/state/ricelin-wallpaper"
    if [[ -r "$wallpaper_state" ]]; then
        candidate=$(head -n1 "$wallpaper_state")
        [[ -f "$candidate" ]] && WALLPAPER=$candidate
    fi
fi
if [[ -n "$WALLPAPER" ]]; then
    [[ -f "$WALLPAPER" ]] || { echo "Wallpaper not found: $WALLPAPER" >&2; exit 1; }
    run python3 "$HOME_DIR/.config/hypr/scripts/wallcolors.py" "$WALLPAPER"
else
    # A fresh machine has no wallpaper state yet, but Kitty and Starship still
    # require the generated extended palette. Seed a neutral dark palette so
    # the first terminal never falls back to defaults or loses prompt fills.
    run python3 "$HOME_DIR/.config/hypr/scripts/wallcolors.py" --hue 260 dark 0.18
fi

if ((DRY_RUN == 0)); then
    for generated in \
        "$HOME_DIR/.cache/ricelin/colors.json" \
        "$HOME_DIR/.cache/ricelin/kitty-colors.conf" \
        "$HOME_DIR/.cache/ricelin/ghostty-colors"; do
        [[ -s "$generated" ]] || { echo "Generated theme file is missing: $generated" >&2; exit 1; }
    done

    systemctl --user daemon-reload 2>/dev/null || true
    if command -v hyprctl >/dev/null 2>&1 && hyprctl monitors >/dev/null 2>&1; then
        hyprctl reload >/dev/null 2>&1 || true
        "$BIN_DIR/sparrow-shell" restart all >/dev/null 2>&1 || true
    fi
    # Vesktop watches quickCss.css live after startup, but an already-running
    # process does not adopt a newly installed useQuickCss setting from the
    # externally replaced settings.json. Relaunch it once during an update so
    # the watcher and generated wallpaper CSS are both active.
    if command -v vesktop >/dev/null 2>&1 && pgrep -x vesktop >/dev/null 2>&1; then
        pkill -TERM -x vesktop >/dev/null 2>&1 || true
        for _ in {1..30}; do
            pgrep -x vesktop >/dev/null 2>&1 || break
            sleep 0.1
        done
        setsid -f vesktop >/dev/null 2>&1
        echo "Vesktop: relaunched with dynamic QuickCSS"
    fi
    version_state="$HOME_DIR/.local/state/sparrow-shell/version"
    mkdir -p "$(dirname "$version_state")"
    git -C "$ROOT" rev-parse HEAD > "$version_state" 2>/dev/null || printf 'unknown\n' > "$version_state"
    "$BIN_DIR/sparrow" doctor
    echo "Installed. Backup: $BACKUP"
    echo "Commands: sparrow, sparrow-shell, sparrow-update"
    echo "Keyboard: Super+K, 'sparrow keyboard', or tap the keyboard icon in the expanded pill"
    if ((OPTIONAL_FAILURES > 0)); then
        echo "Core installation is healthy, but $OPTIONAL_FAILURES optional app step(s) need attention." >&2
        exit 3
    fi
fi
