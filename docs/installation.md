# Installation and first boot

Sparrow Shell targets Arch Linux and CachyOS on Wayland. Start with a working
base system, network access, a regular user with `sudo`, and the correct GPU
driver for the machine.

## Recommended installation

```sh
sudo pacman -S --needed git
git clone https://github.com/Retro-TV/sparrow-shell.git \
  "${XDG_DATA_HOME:-$HOME/.local/share}/sparrow-shell"
cd "${XDG_DATA_HOME:-$HOME/.local/share}/sparrow-shell"
./scripts/validate.sh
./install.sh --dry-run --full
./install.sh --full
```

`--full` installs the curated core and themed application manifests, copies the
dotfiles, installs rishot from its official repository, configures Spicetify and
the Pywalfox native helper, and installs the Sparrow commands. Packages missing
from the current pacman repositories are routed through `yay` or `paru`; the
installer bootstraps `yay-bin` when needed.

The installer never installs the maintainer's complete package snapshot. That
snapshot is retained only as reference under `packages/pacman-explicit.txt`.

## Existing configurations and backups

Files replaced by the installer are copied to a timestamped directory:

```text
~/.local/state/sparrow-shell-backups/YYYYMMDD-HHMMSS/
```

Review the dry run and keep the newest backup until the desktop has been tested.
Account data and application profiles are not copied into the repository or
replaced by the installer.

## First boot checklist

1. Put at least two images or videos in `~/Pictures/Wallpapers`.
2. Start Hyprland from a TTY with `Hyprland`, or select it in the display manager.
3. Press `Super+C` and select a wallpaper to generate the first live palette.
4. Open Firefox, enable the Pywalfox extension, and fetch the native colors once.
5. Sign in to Vesktop and Spotify normally; account state is intentionally absent.
6. Run `sparrow-shell status` and confirm the pill and lock watchdogs are running.

## Monitors

The shipped `modules/monitors.lua` uses a portable preferred-mode, automatic
layout. Inspect outputs with:

```sh
hyprctl monitors all
```

Then adapt `~/.config/hypr/modules/monitors.lua`. A two-monitor example is kept
beside it as `monitors.lua.example`.

## Keyboard layout

The public install does not force the maintainer's Slovenian keyboard layout.
Opt in explicitly with:

```sh
./install.sh --system-keymap
```

For another layout, edit `~/.config/hypr/modules/input.lua` and set the system
layout with `localectl`.

## Updating

```sh
sparrow-update --dry-run
sparrow-update
```

Local edits inside the checkout stop the update before anything is overwritten.
Commit, stash, or move those edits before updating. The installer creates a new
backup each time it reapplies the tracked configuration.
