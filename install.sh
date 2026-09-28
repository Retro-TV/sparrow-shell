#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ ${EUID} -eq 0 ]]; then
    printf '%s\n' 'Run Sparrow Installer as your normal user; it uses sudo only for approved package installation.' >&2
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
    if [[ ! -r /etc/os-release ]] || ! grep -Eiq '^(ID=(arch|cachyos)|ID_LIKE=.*arch)' /etc/os-release; then
        printf '%s\n' 'Python is missing. This bootstrap only installs it on Arch/CachyOS; install Python manually with your distribution package manager.' >&2
        exit 1
    fi
    if ! command -v pacman >/dev/null 2>&1 || ! command -v sudo >/dev/null 2>&1; then
        printf '%s\n' 'Python is missing. Install it manually with: sudo pacman -S --needed python' >&2
        exit 1
    fi
    if [[ ! -t 0 ]]; then
        printf '%s\n' 'Python is missing and this is not an interactive terminal. Install it manually with: sudo pacman -S --needed python' >&2
        exit 1
    fi
    printf '%s' 'Python is needed to run Sparrow Installer. Install it now with sudo pacman? [y/N] '
    read -r answer
    case "${answer,,}" in
        y|yes)
            printf '%s\n' 'Starting pacman transaction to install the Sparrow Installer runtime (python).'
            if sudo pacman -S --needed python; then
                printf '%s\n' 'Python bootstrap completed; starting Sparrow Installer.'
            else
                status=$?
                printf 'Python bootstrap failed or was interrupted (exit status %s). No Sparrow files were changed.\n' "$status" >&2
                exit "$status"
            fi
            ;;
        *) printf '%s\n' 'No changes made. Install Python with: sudo pacman -S --needed python' >&2; exit 1 ;;
    esac
fi
exec python3 "$repo_root/installer/sparrow_installer.py" "$@"
