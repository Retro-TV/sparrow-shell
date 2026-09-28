# Sparrow source of truth (known-good SSD, September 2026)

`SOURCE-OF-TRUTH.json` is the machine-readable file/output contract. A means
portable tracked bytes, B is derived output, C is machine discovery, and D is
mutable user/runtime state. The live SSD is evidence, not an installation
input. Do not deploy its generated palette, monitor names, saved choices, or
personal wallpaper library.

## Deliberate live-to-Git differences

| Item | Portable representation and reason |
| --- | --- |
| Niri root config | Live requires generated colors and contains a Bibata cursor block plus a commented host output. Git makes colors optional until bootstrap, places the same cursor block in conditional `sparrow/cursor.kdl`, and omits the host output comment. |
| Niri appearance | Live's mutable `user-appearance.kdl` holds the balanced top strut, corner radius/clipping and slowdown. Git promotes these intended defaults into static `appearance.kdl`; fresh users should not need that saved override. Other live appearance directives match. |
| Niri binds | Live invokes Rishot through `$HOME/.local/bin/rishot`; Git invokes `rishot` through `PATH` for portability. Other binds match. |
| Niri input | Live's `input.kdl` and Git's bridge are byte-identical; live `user-input.kdl` supplies focus-follows-mouse alongside user-specific Num Lock/touchpad choices. The tracked `niri/defaults/user-input.kdl` holds focus-follows-mouse, tap-to-click, and Niri's existing 25/600 keyboard repeat defaults. Do **not** copy live device preferences. |
| Niri generated colors | Live colors reflect the current bundled default wallpaper. Git contains the wallpaper, Matugen generator, and transaction helper, not a frozen palette. |
| Displays and user binds | Live `display-outputs.kdl`, `display-binds.kdl`, `user-binds.kdl` are machine/user state; Git ships only the static fragments and the generators. |
| Niri cursor | Live has Bibata inline. Git has the same block in a conditional fragment; the installer offers the pinned upstream v2.0.6 asset and installs it per-user before deploying that selection. |
| Portal profile | Live has `Secret=gnome-keyring` without that backend installed. Git omits only that stale route; GTK FileChooser and Niri screencast/screenshot routes remain. |
| GTK theme | Live GTK3/4 CSS is generated and current. The 106-byte Git stub was not a theme and has been removed. Git retains theme metadata and the generator; `adw-gtk-theme` supplies upstream GTK3/GTK4 CSS. Live `gtk-contained-dark.css` and `sparrow-colors.css` are stale historical files, not inputs to the active generator. |
| Live service links | Their contents match tracked systemd units; live links point into the development checkout. Units themselves use `%h/.config/quickshell/sparrow`, not the checkout path. The installer deploys the runtime tree directly at that stable path. |

The audited static Kitty, Fish, Starship, window-rule, GTK-settings, desktop,
systemd and Quickshell files match their live counterparts. The existing
`installer/test_installer.py` includes a file-level live source-map comparison;
the Quickshell tree matched through its development symlink. No canonical
Sparrow runtime source needs `/home/vrabko/Projects/sparrow-shell`.

### Niri 26.04 input limitation

`focus-follows-mouse` is an optional config node, not a boolean flag. Niri
26.04 rejects `focus-follows-mouse false`. The merge of a later `input` block
cannot clear an earlier enabled node. Therefore placing focus-follows-mouse in
immutable `input.kdl` would make Sparrow's existing Input off toggle lie. The
portable tracked seed is the only honest source for the initial preference;
the user fragment remains its sole runtime owner. Installer copies that seed
to `$XDG_CONFIG_HOME/niri/sparrow/user-input.kdl` only when absent, before
Niri starts, and never overwrites it on updates. Uninstall removes the seed
only while it still matches the installer-created bytes; an edited file stays
user-owned.

## Cursor provenance and selection

The SSD's `Bibata-Modern-Ice/index.theme` identifies v2.0.6. Installer offers
the official [upstream v2.0.6 release archive](https://github.com/ful1e5/Bibata_Cursor/releases/download/v2.0.6/Bibata-Modern-Ice.tar.xz),
checks it against the SHA-256 recorded in `SOURCE-OF-TRUTH.json`, and
installs it under `$XDG_DATA_HOME/icons/Bibata-Modern-Ice`. No AUR helper or
system-wide privilege is needed. Declining the asset offer stops deployment
before Sparrow files are written, so a blank user does not silently receive a
different cursor. Existing explicit cursor choices are preserved. The
[upstream project](https://github.com/ful1e5/Bibata_Cursor) is GPL-3.0; the
installer tracks the downloaded directory for safe update/restore.

The tracked Niri cursor fragment, `environment.d/90-cursor.conf`, and unset
GSettings `org.gnome.desktop.interface` cursor-theme/cursor-size defaults all
select `Bibata-Modern-Ice` at size 24, only when the asset is present and the
user has no explicit different cursor choice. Installer records the GSettings
values it sets and restores them only while unchanged. A later explicit cursor
choice relinquishes Sparrow ownership; updates also remove/restore only
unchanged Sparrow cursor fragments.

## Palette and GTK bootstrap

The initial source is tracked `quickshell/sparrow/wallpapers/default.png`.
Fresh Flags choose Dynamic + Auto style + Auto appearance. `wallcolors.py`
uses installed Matugen and Pillow to derive Material roles and wallpaper
luminance. The constrained Niri transaction stages and validates
`generated-colors.kdl` before the active compositor reload. The same roles
write `palette.json`, Kitty ANSI/foreground/background, system-adw-gtk3-based
GTK3/GTK4 Sparrow CSS, and colored folder/text icons. The GTK3 source is
`/usr/share/themes/adw-gtk3/gtk-3.0/gtk.css` or `gtk-dark.css`; GTK4 reads that
package's `gtk-4.0` CSS/tweaks/assets. Missing or incompatible GTK source is
now a hard palette-generation error, detected before generated Niri/palette
state is committed. GTK CSS/Kitty/icon writes also fail visibly; only
notifying running Kitty and refreshing the icon cache are optional side
effects. `adw-gtk-theme` is therefore required for the intended desktop, not
an optional appearance bonus.
Before Flags exists, `wallpaper.sh` now chooses the same Auto appearance
default. A failed initial palette is reported as a failed wallpaper bootstrap
instead of being swallowed; later wallpaper changes also report a failed
palette update even if their image surface has already changed.

An isolated test copied tracked Niri/Kitty/GTK/icon inputs to a blank temporary
HOME/XDG tree, seeded only the tracked input default, and ran the real Matugen
and palette generator. Fake `niri`/`pkill` commands prevented any live reload
or Kitty signal; an isolated `wallpaper.sh recolor` run confirmed the pre-Flags
Auto default without starting awww. The installed Niri validator accepted the
generated config. The test found palette JSON, Niri colors, Kitty colors, full GTK3/GTK4
CSS and icons. A separate read-only comparison recomputed the roles directly
from `default.png`: dark mode, `source_color #bab1a5`, background `#151311`,
primary `#d5c4aa`, all matching the SSD's current palette. Re-rendered GTK3
(303882 bytes), GTK4 (431874 bytes), GTK4 tweaks (2302 bytes), Niri colors,
Kitty colors, folder SVG and text SVG matched live output byte-for-byte. No
live generated file was an input to the isolated bootstrap.

## Packages and nonportable state

The installer requires and verifies the intended font families: `Inter Black` in `Theme.qml` (`inter-font`),
`JetBrains Mono Nerd Font` in Kitty (`ttf-jetbrains-mono-nerd`), Adwaita Sans
for GTK/libadwaita (`adwaita-fonts`), and the bundled Outfit Black font for the
Qylock-derived lockscreen. The audited host resolves each installed family.
`adw-gtk-theme`, `adwaita-fonts`, the default desktop applications, Niri 26.04,
Quickshell, Matugen, Python/Pillow, awww, and the declared GTK/Qt runtime
dependencies are in the required package set. Optional features remain
separate; see `docs/DEPENDENCIES.md` for the current package groups.

The live laptop exposes one internal backlight. The Mixer loads that control
only with `Backlight.present` and `brightnessctlAvailable`, and separately
repeats one external slider per `Devices.ddcMonitors`. `ddcutil` is absent on
the SSD, so exactly one Mixer brightness control appears. Another machine can
legitimately show additional DDC controls; that is hardware discovery, not a
second internal brightness implementation.
