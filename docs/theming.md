# Dynamic theming

Sparrow Shell uses one wallpaper-derived palette for the desktop and themed
applications. The palette generator favors coherent surfaces and readable text
over copying the most saturated pixel in the wallpaper.

## Flow

```text
wallpaper
  -> wallpaper.sh
  -> wallcolors.py + Matugen
  -> shared palette
  -> Quickshell, Hyprland, GTK, terminals, Firefox, Vesktop and Fastfetch
```

The generated cache lives under `~/.cache/ricelin/`. The internal name is kept
for compatibility with the Ricelin-based Quickshell modules.

## Applications

- **Quickshell:** watches the generated color JSON and updates immediately.
- **Hyprland:** reloads generated border and decoration colors.
- **GTK/Thunar:** receives matching GTK3/GTK4 settings and CSS.
- **Kitty/Ghostty:** loads generated terminal color fragments, including the
  extended ANSI slots used by the Starship rounded prompt.
- **Firefox:** reads the exported Pywal palette through Pywalfox.
- **Vesktop:** receives generated QuickCSS while staying opaque for compositor
  stability. Its built-in QuickCSS watcher applies later wallpaper changes
  live; the installer relaunches an existing process once so newly installed
  settings are loaded.
- **Fastfetch:** regenerates its accent and lantern colors.
- **Spotify:** remains on the selected Marketplace/Spicetify theme; it is not
  force-refreshed on every wallpaper change.

## Wallpaper folders

The first existing collection with two or more supported files is selected:

1. `~/Pictures/Wallpapers`
2. `~/Pictures/wallpapers`
3. `~/Wallpapers`
4. `~/wallpapers`

Images, GIFs and common video formats are supported. The folder can also be
changed from the Quickshell settings surface.

## Rebuild a palette manually

```sh
./install.sh --wallpaper /absolute/path/to/wallpaper.jpg
```

Or use `Super+C` for the wallpaper picker and `Super+B` for a shuffled wallpaper.

## Why some internal files still say Ricelin

The Quickshell modules, cache paths, managed markers and compatibility CLI began
in Ricelin. Sparrow Shell deliberately preserves those internal interfaces to
stay compatible with the upstream base while presenting Sparrow Shell as the
complete distribution and update layer.
