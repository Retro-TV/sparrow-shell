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
