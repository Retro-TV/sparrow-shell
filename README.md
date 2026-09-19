# Ricelin dotfiles

Reproducible personal layer for a CachyOS + Hyprland + Quickshell Ricelin
desktop. This is a configuration repository, not a backup of personal data.

## What it contains

- Hyprland Lua configuration, keybinds, input settings, startup, window rules,
  wallpaper rotation, screenshots, locking, recording, and helper scripts
- Quickshell Ricelin launcher, pill, lock screen, settings, media, workspace,
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
git clone https://github.com/Retro-TV/ricelin-dotfiles.git "$HOME/Ricelin/ricelin-dotfiles"
cd "$HOME/Ricelin/ricelin-dotfiles"
./install.sh --packages --apps --system-keymap
```

The package mode bootstraps an AUR helper when needed, installs the recorded
Hyprland/Ricelin dependencies, and then applies the tracked configuration.
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

## Save future changes

After changing a supported part of the rice, run:

```sh
rice-update
```

It snapshots the allowlisted configuration and system facts, scans for obvious
credential material, commits the diff, and pushes it to GitHub. Use
`rice-update --dry-run` to inspect the next commit or `rice-update --no-push`
to commit locally only. New package installs, default-app changes, keybind
edits, theme edits, and wallpaper-palette changes are included automatically.

The command is intentionally allowlisted: it does not inspect or copy browser
profiles, app sessions, cookies, tokens, SSH keys, arbitrary home files, or
wallpaper files. If you add a new kind of rice component, add its path to
`scripts/rice-update` once; after that it is automatic.

The installer never copies browser profiles, app accounts, tokens, wallpaper
files, or GitHub credentials. It also does not blindly install the current
monitor geometry; review `dotfiles/.config/hypr/modules/monitors.lua` first on
another machine.

## GitHub publishing

This directory is ready to become a private or public GitHub repository. Before
publishing, review the diff and run:

```sh
git init
git add .
git diff --cached --stat
git commit -m 'Initial Ricelin desktop configuration'
gh repo create ricelin-dotfiles --private --source=. --remote=origin --push
```

Use `--public` instead of `--private` only after reviewing the files again.
