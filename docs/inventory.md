# Sparrow Shell system inventory

This repository captures the intentional personal layer discovered on the
source CachyOS machine. It does not capture accounts, browser profiles,
Discord/Spotify data, tokens, caches, or the wallpaper collection.

## Platform

- CachyOS Linux
- Hyprland 0.56.2 on Wayland
- Quickshell Sparrow Shell layer and pill
- Slovenian keyboard layout (`si` / `slovene`)
- Flat mouse acceleration profile, 40 repeat rate, 400 ms repeat delay
- Bibata-Modern-Ice cursor, size 24

## Main custom layer

- Hyprland Lua modules, window rules, animations, monitor template, startup,
  lock, screenshot, launcher, wallpaper, recording, and watchdog scripts
- Quickshell launcher, lock screen, pill surfaces, settings, media, display,
  workspace, wallpaper, Bluetooth, Wi-Fi, audio, recorder, and keybind UI
- Dynamic Matugen `scheme-fidelity` palette generation
- GTK3/GTK4, terminal, Fastfetch, Firefox/Pywalfox, and Vesktop palette fan-out
- Opaque Vesktop rendering retained for workspace-move stability
- Ghostty and Kitty configs; Fish prompt and greeting; JetBrains Mono Nerd Font
- Papirus icons and Bibata cursor

## Key behavior

The main custom bindings are in `dotfiles/.config/hypr/modules/binds.lua`.
Notable bindings include Super+Return/ T for Kitty, Super+F for Firefox,
Super+E for Thunar, workspace navigation and movement on Super+number,
Super+Space launcher, Super+V clipboard, Super+B wallpaper rotation,
Super+C wallpaper picker, Super+D recording, Super+L lock, and the media,
brightness, and volume keys.

## Defaults and packages

- Default browser: Brave
- Directory handler: Thunar
- Audio: mpv
- Video: Stremio
- PNG/PDF: Brave
- Official and AUR package snapshots are in `packages/`.

## Deliberately not included

- Firefox/Brave profiles and extensions with account state
- Discord, Vesktop session data, Spotify account data, ChatGPT data
- GitHub credentials and SSH keys
- Wallpaper files and current wallpaper state
- Monitor configuration is included as a reference but should be reviewed on
  a different machine before use.
