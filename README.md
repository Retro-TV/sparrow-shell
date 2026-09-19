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
