# Sparrow color pipeline

Sparrow consumes Matugen's Material 3 semantic palette rather than constructing
its own hue ramps. Wallpaper selection and video playback remain in
`scripts/wallpaper.sh`; a video contributes one extracted still frame and is not
continuously sampled.

## User choices

`Flags.paletteMode` chooses **Static** or **Dynamic**. Static uses Sparrow's
fixed flame seed with Matugen Tonal Spot in dark mode, so a wallpaper change
does not change the theme. Dynamic generates from Matugen's first ranked image
source color (`--source-color-index 0`), falling back to the same fixed seed if
the image has no useful source color.

Dynamic users choose a palette style independently from appearance mode. These
choices use Matugen's native generators, not Sparrow-authored color science:

| Appearance label | Matugen type | Intent |
| --- | --- | --- |
| Auto | `scheme-smart` | Matugen chooses Monochrome below colorfulness 6, Neutral from 6–20, Tonal Spot from 20–70, and Vibrant at 70 or above. |
| Tonal | `scheme-tonal-spot` | Restrained, balanced wallpaper color. |
| Source | `scheme-content` | Follows the selected source color more closely. The source is Matugen's highest-ranked image color (`--source-color-index 0`), not necessarily the most frequent pixel. |
| Mono | `scheme-monochrome` | Deliberately neutral. |

Sparrow keeps the visible set intentionally small. With installed Matugen 4.2.0
and a solid `#d52331` source, Expressive generated a blue primary (`#a8c8ff`)
and Fruit Salad a magenta primary (`#fbacf8`); these schemes can therefore
depart from a red wallpaper's dominant color. Tonal Spot, Content, and Fidelity
all produced red-family primaries in this check, so a separate Fidelity control
would add little to the compact UI for this tested case. Older stored style
names migrate deterministically: Tonal/Fidelity/Neutral to Tonal; Vibrant to
Source; Alternate/Expressive/Fruit to Auto.

Appearance mode is separate: **Auto**, **Dark**, or **Light**. Auto passes
Matugen `--mode smart`; Sparrow does not run a second mode-selection heuristic.
Matugen currently downsamples the image, evaluates its HCT tone, and selects
Light above tone 60, otherwise Dark. Explicit modes use Matugen's corresponding
light or dark semantic roles. Old saved dynamic palettes migrate to Dark to
preserve the former behavior; new Flags default to Dynamic + Auto + Auto.

Matugen's `scheme-smart` thresholds and mode detection are implemented in its
[`smart_scheme.rs`](https://github.com/InioX/matugen/blob/main/src/smart_scheme.rs);
image source ranking and source-color selection are in
[`color.rs`](https://github.com/InioX/matugen/blob/main/src/color/color.rs).
Sparrow uses this native behavior rather than copying another rice's heuristic.
end-4's current image script computes a colorfulness metric but maps values below
40 to Neutral and otherwise Tonal Spot
([`scheme_for_image.py`](https://github.com/end-4/dots-hyprland/blob/main/dots/.config/quickshell/ii/scripts/colors/scheme_for_image.py));
its separate Material generator optionally switches low-chroma inputs to
Neutral and has extra terminal harmonization controls. Caelestia's CLI doesn't
use Matugen for this path: it scores wallpaper colors with MaterialYouColor,
then applies its own thresholds—Neutral below 10, Content below 20, and Tonal
Spot otherwise ([wallpaper source](https://github.com/caelestia-dots/cli/blob/main/src/caelestia/utils/wallpaper.py),
[variant source](https://github.com/caelestia-dots/cli/blob/main/src/caelestia/utils/colourfulness.py)).

## One palette, several renderers

The selected wallpaper/still, source, style, and mode produce one
`$XDG_CACHE_HOME/sparrow-shell/palette.json`. Its Material role values are read
directly from one Matugen result. Wallpaper luminance remains a separate small
sample solely for the Last of Us lockscreen's Auto foreground choice; it does
not affect shell palette selection.

The same semantic palette feeds:

- Quickshell through the watching `Dyn` singleton and `Theme` role aliases.
- Niri active/inactive borders through the validated
  `generated-colors.kdl` transaction.
- Kitty through its generated include, ANSI slots, and reload signal.
- Sparrow's app-scoped GTK3 and GTK4/adw-gtk3 CSS plus generated folder/file
  icon assets. The launcher opts only `org.pulseaudio.pavucontrol` into the
  GTK4 theme; global GTK settings remain unchanged.
- The Quickshell lock through its existing `Dyn` roles and independent wallpaper
  luminance recommendation.

Renderer-specific work is limited to mapping semantic roles to the application's
color names/slots (for example GTK named colors and Kitty ANSI). Sparrow no
longer chooses alternate image hues, rotates seeds, invents surface ramps, or
darkens/lightens Matugen colors afterward. Legacy presentation aliases such as
`cream` map directly to Matugen text roles.

Generated files are outputs, never inputs. Niri's transaction is validated
before the JSON palette and other consumers are replaced. Writes are atomic;
if Niri validation fails, the previous palette remains. A running Thunar process
does not reread its GTK3 theme CSS live; fully closing and reopening Thunar is
still needed to see a new palette.

## GTK portal file chooser boundary

The active Niri portal configuration selects `xdg-desktop-portal-gtk` for
FileChooser. A tracked systemd user drop-in scopes `GTK_THEME=Sparrow` only to
that backend; it does not change global GTK settings or unrelated applications.
The chooser reads Sparrow's generated GTK3 stylesheet. pavucontrol is GTK4, so
its launcher entry receives `GTK_THEME=Sparrow` and uses a generated GTK4
adw-gtk3-derived stylesheet built from the same Matugen roles. Its CSS and
selection accent therefore update on the next launch; a running instance must
be closed and reopened to pick up a changed palette. The active development
drop-in is linked to
`systemd/xdg-desktop-portal-gtk.service.d/10-sparrow-theme.conf`; a future
installer should place that tracked file at the standard user-service drop-in
path.

The reproducible GTK3/GTK4 base is the Arch `adw-gtk-theme` package (adw-gtk3,
LGPL-2.1-only), already listed in `docs/DEPENDENCIES.md`. Generation prefers
the package's `/usr/share/themes/adw-gtk3` files. `$XDG_DATA_HOME/themes/adw-gtk3`
is a development fallback only; a clean install must install the declared
package rather than depend on this machine's local copy.

## Tests

`scripts/test_wallcolors.py` checks Matugen output for the representative
wallpaper matrix (black/red, blue/green/white, warm, purple/pink, neutral, bright,
dark, multicolor), all four curated styles, and Auto/Dark/Light modes. It checks
semantic-role contrast, genuinely distinct light/dark outputs, source-color
relationships, migration idempotence, GTK source priority, and isolated
consumer fan-out rather than freezing arbitrary hex values.
