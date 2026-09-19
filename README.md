# Sparrow Shell

Reproducible desktop rice for CachyOS + Hyprland + Quickshell. Sparrow Shell
is the maintained configuration layer around the Ricelin shell components; it
is a configuration repository, not a backup of personal data.

## What it contains

- Hyprland Lua configuration, keybinds, input settings, startup, window rules,
  wallpaper rotation, screenshots, locking, recording, and helper scripts
- Quickshell launcher, pill, lock screen, settings, media, workspace,
  wallpaper, network, Bluetooth, audio, and recorder surfaces
- Matugen wallpaper palette generation and the GTK, terminal, Fastfetch,
  Firefox/Pywalfox, and Vesktop integrations
- Fish, Ghostty, Kitty, Fastfetch, GTK, Thunar, Vesktop, Spicetify Marketplace,
  and selected Spicetify theme files
- Package snapshots, default applications, locale/keymap facts, and enabled
  user-service facts under `packages/` and `system/`

## Quick start

Review first:

```sh
./scripts/validate.sh
./install.sh --dry-run
```

Install the configuration with a timestamped backup:

```sh
./install.sh
```

For the simplest repeatable setup on an empty Arch-based terminal:

```sh
sudo pacman -S --needed git
git clone https://github.com/Retro-TV/sparrow-shell.git "$HOME/Sparrow/sparrow-shell"
cd "$HOME/Sparrow/sparrow-shell"
./install.sh --packages --apps --system-keymap
```

The package mode bootstraps an AUR helper when needed, installs the recorded
Hyprland/Sparrow Shell dependencies, and then applies the tracked configuration.
Review the monitor file before using it on different hardware.

Install packages too, when the target is an Arch/CachyOS machine:

```sh
./install.sh --packages
```

Apply the recorded defaults, Spicetify Marketplace integration, and Pywalfox
native helper:

```sh
./install.sh --apps
```

Set the Slovenian system keymap explicitly:

```sh
./install.sh --system-keymap
```

Regenerate the live palette after choosing a wallpaper:

```sh
./install.sh --wallpaper /path/to/wallpaper.jpg
```

## Update an installed Sparrow Shell

On any machine using the public rice, update from GitHub with:

```sh
sparrow-update
```

This pulls fast-forward-only changes from the official repository, applies the
tracked configuration, and reconciles the package and app integrations. It
does not commit or push anything. Use `sparrow-update --dry-run` to preview an
update, `--no-packages` or `--no-apps` to skip parts, and
`--upgrade-system` to opt into a full `yay`/`paru` system upgrade.

The maintainer command `rice-update` is deliberately private and is not part
of this repository. It snapshots the allowlisted configuration and system
facts, scans for obvious secrets, commits the diff, and pushes it to GitHub.
That separation means installing Sparrow Shell cannot grant a stranger a way
to publish changes to the repository.

The snapshot policy is intentionally allowlisted: it does not inspect or copy
browser profiles, app sessions, cookies, tokens, SSH keys, arbitrary home
files, or wallpaper files. When the maintainer adds a new kind of rice
component, its path is added to the private snapshot policy before it becomes
public.

The installer never copies browser profiles, app accounts, tokens, wallpaper
files, or GitHub credentials. It also does not blindly install the current
monitor geometry; review `dotfiles/.config/hypr/modules/monitors.lua` first on
another machine.

## Repository maintenance

The public repository is:

```text
https://github.com/Retro-TV/sparrow-shell
```

Only the maintainer should publish changes. Review the allowlisted diff and
run the private `rice-update` command from the maintainer machine. Never add
credentials, browser profiles, account data, wallpaper collections, or the
private publisher command to this repository.
