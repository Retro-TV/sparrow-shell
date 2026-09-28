#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Sparrow restore requires python3.' >&2
    exit 1
fi
exec python3 "$repo_root/installer/sparrow_installer.py" --uninstall "$@"
