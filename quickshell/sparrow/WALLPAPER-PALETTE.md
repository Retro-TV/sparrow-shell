# Sparrow wallpaper palette contract

The canonical generated palette is JSON at
`$XDG_CACHE_HOME/sparrow-shell/palette.json` (or
`~/.cache/sparrow-shell/palette.json`). `scripts/wallcolors.py` writes it
atomically after a successful Matugen run. Dynamic mode is always dark: source
wallpaper luminance never selects a light scheme. Matugen supplies image color
candidates using Material Color Utilities' Celebi quantizer and Score ranking.
Sparrow measures those candidates' actual image coverage in OKLab, discounts
neutral/extreme-lightness pixels, and rejects tiny accents, so a small colored
object cannot outweigh a mostly neutral image. Dark Sparrow surfaces are
generated from the selected image seed's Material tonal palette, rather than
the stock near-black surface roles.

Appearance offers image-derived choices: **Tonal** uses the strongest useful
wallpaper color with Matugen's restrained `scheme-tonal-spot` treatment;
**Vibrant** uses a high-chroma, adequately represented wallpaper color with
Matugen's source-faithful `scheme-content` treatment and a stronger accent/surface
ramp; **Alternate** uses a second significant color only when it is perceptually
distinct from the dominant color. Alternate is disabled when no real second hue
exists; it is never replaced by an invented harmony color. Grayscale or nearly
neutral images expose only Tonal. The choice is saved in Sparrow's user flags
and applies to subsequent wallpaper changes. Matugen never rotates the seed to
an unrelated harmony hue. Its native `scheme-monochrome` is used when the image
has too little significant chroma. The generated JSON records the effective
style and which choices are available; Appearance follows a safe fallback if a
new wallpaper lacks the previously selected Alternate.

Legacy values (`scheme-tonal-spot`, `scheme-neutral`, and `scheme-fidelity` →
Tonal; `scheme-expressive` and `scheme-vibrant` → Vibrant;
`scheme-fruit-salad` → Alternate, with equivalent short names such as
`expressive`, `fruit`, and `fidelity`) are accepted and normalized when
Appearance loads. The generation script also accepts them for wallpaper
changes before Appearance has been opened.
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
GTK theme unchanged. GTK3 loads theme CSS into the application when its theme
provider is initialized; changing the generated CSS file does not refresh
already-open Thunar windows. Thunar serves its windows from one running app
instance, so all of its windows use that instance's loaded palette. Applying a
new palette to an existing instance requires an app-supported theme reload;
Thunar does not expose one for re-reading these generated theme files. For now,
the new palette appears the next time Thunar is fully closed and launched
again. Sparrow deliberately does not close user windows to force a refresh.

Thunar's “Always” thumbnail preference also requires the D-Bus thumbnail
service `tumbler`; Sparrow lists it as a required dependency for image previews.

It also updates Sparrow's lightweight icon-theme overlay under
`$XDG_DATA_HOME/icons/Sparrow/`, which inherits Adwaita for all other icons
and regenerates folder and file-manager glyphs from the same primary palette
color. The desktop icon-theme preference selects this overlay so folders
follow the wallpaper palette in GTK applications.

The Quickshell session lock reads the same palette and wallpaper luminance
metadata directly. It does not require a separate lock-specific color include
or cached wallpaper symlink.
