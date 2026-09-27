# Sparrow wallpaper palette contract

The canonical generated palette is JSON at
`$XDG_CACHE_HOME/sparrow-shell/palette.json` (or
`~/.cache/sparrow-shell/palette.json`). `scripts/wallcolors.py` writes it
atomically after a successful Matugen run. Dynamic mode is always dark: source
wallpaper luminance never selects a light scheme. Matugen's wallpaper-seeded
Material tonal palette supplies the chromatic dark surface ramp, while its
dark semantic scheme supplies readable foregrounds and accent roles.
The separate explicit manual `--hue ... light` path remains light when chosen;
it is not used by wallpaper-driven dynamic mode.
Quickshell's `Dyn` singleton watches
the file and updates live; no shell restart is needed. `Theme` maps its shared
Ricelin-derived surface, text, outline, and accent tokens from `Dyn` whenever
the palette mode is `dynamic`.

Adapters can read the file directly. Main semantic fields are `background`,
`surface`, `surface_container_lowest`,
`surface_container_low`, `surface_container`, `surface_container_high`,
`surface_container_highest`, `surface_bright`, `on_surface`, `on_background`,
`on_surface_variant`, `cream`, `bright`, `subtle`, `dim`, `faint`, `primary`,
`on_primary`, `primary_container`, `on_primary_container`, `secondary`,
`on_secondary`, `secondary_container`, `on_secondary_container`, `tertiary`,
`on_tertiary`, `tertiary_container`, `on_tertiary_container`, `error`,
`on_error`, `outline`, and `outline_variant`. For conventional adapter names,
map background to `background`, secondary background to `surface_container`,
foreground to `on_surface` (or `bright`/`cream`), muted foreground to
`on_surface_variant` (or `subtle`), accent to `primary`, and border to
`outline`. Secondary, tertiary, and error roles use Matugen's dark semantic
palette. Colors are CSS-style
`#RRGGBB` strings. The generated Niri
fragment consumes `primary` and `outline_variant` for active and inactive
window borders; it does not replace hand-maintained geometry, shadows, or other
appearance settings.

The same successful Matugen result also feeds Kitty. `palette.json` contains a
`terminal` object with its background/foreground, cursor and selection colors,
tab colors, ANSI 0–15 palette, and extended xterm slots used by the copied
Starship prompt. ANSI text colors use Matugen's primary, secondary, tertiary,
and error roles, so Fish syntax colors follow the wallpaper instead of fixed
hues. Neutral, cursor, selection, tab, and prompt-pill roles also come directly
from Sparrow's Matugen surfaces and accents. This prevents Starship's
235/240/243–255 style references from falling back to Kitty's default
grayscale. No second wallpaper sample or Matugen invocation is used.

`wallcolors.py` writes the Kitty include atomically to
`$XDG_CONFIG_HOME/kitty/sparrow-colors.conf` (default
`~/.config/kitty/sparrow-colors.conf`). The portable static defaults are in
`kitty/kitty.conf`; when installed as `$XDG_CONFIG_HOME/kitty/kitty.conf`, its
`globinclude` consumes the generated sibling file. Kitty's config watcher
tracks the primary config paths, not the file expanded through `globinclude`,
so after the generated colors actually change Sparrow sends Kitty's documented
`SIGUSR1` config-reload signal to existing Kitty instances. This is silent if
Kitty is not running and does not restart it. Kitty is an optional app:
failure to write its color include is reported as a warning but does not fail
Sparrow's wallpaper or palette update.

The same palette also produces generated color definitions for Sparrow's
app-scoped GTK3 theme at
`$XDG_DATA_HOME/themes/Sparrow/gtk-3.0/sparrow-colors.css`. The Sparrow Files
launcher sets `GTK_THEME=Sparrow` only for Thunar, leaving the user's global
GTK theme unchanged. GTK3 loads theme CSS at process startup, so an already-
running Thunar may need to be reopened to show colors from a newly selected
wallpaper.

It also updates Sparrow's lightweight icon-theme overlay under
`$XDG_DATA_HOME/icons/Sparrow/`, which inherits Adwaita for all other icons
and regenerates folder and file-manager glyphs from the same primary palette
color. The desktop icon-theme preference selects this overlay so folders
follow the wallpaper palette in GTK applications.
