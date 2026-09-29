# Sparrow licensing and third-party notices

## Project license

Unless a path is identified as separately licensed below, Sparrow's combined
shell and configuration source is offered under **GNU GPL version 3.0 only**;
the full terms are in [`LICENSE`](LICENSE). The integrated Quickshell lock
contains an adaptation of Qylock's GPL-3.0 Last of Us theme, so calling the
repository uniformly MIT would be inaccurate. This is a project-level license
statement, not legal advice.

Sparrow-authored material is copyright (C) 2026 Gakusei unless a file or
component notice identifies another holder.

The Sparrow codebase began from the Ricelin repository and retains modified
and adapted portions. `LICENSES/Ricelin-MIT.txt` preserves its MIT notice; the
MIT terms permit inclusion in the GPL-3.0 combined program. Sparrow's changes
and Niri integration are identified as Sparrow work, while the original notice
is retained.

## Redistributed third-party material

| Material and paths | Source and license | Changes / notice carried here |
|---|---|---|
| Ricelin-derived shell source across active `quickshell/sparrow/` files | [Gakusei/Ricelin](https://github.com/Gakusei/Ricelin), MIT | Sparrow began by importing the Ricelin shell tree and has since removed, rewritten, and adapted components for Niri. The MIT notice is retained in `LICENSES/Ricelin-MIT.txt`; the combined program is GPL-3.0-only. |
| `quickshell/sparrow/Lockscreen/LastOfUs.qml` | [Darkkal44/qylock — Last of Us theme](https://github.com/Darkkal44/qylock/tree/main/themes/last-of-us), GPL-3.0 | Adapted into Sparrow's Quickshell `WlSessionLock`/PAM flow and Sparrow wallpaper/palette interfaces. Attribution is in the QML header and `Lockscreen/THIRD_PARTY.md`; the full license remains at `Lockscreen/COPYING.GPL-3.0`. Corresponding adapted QML source is included. |
| Fixed SVG subset under `icons/Sparrow/16x16/` | [Papirus-Dark](https://github.com/PapirusDevelopmentTeam/papirus-icon-theme), GPL-3.0, release `20260801`, commit [`5f8b701d7521e27b4859d7e4f9b0da4c423c036c`](https://github.com/PapirusDevelopmentTeam/papirus-icon-theme/tree/5f8b701d7521e27b4859d7e4f9b0da4c423c036c) | Redistributed as a small fixed sidebar/device subset and compatibility aliases. Exact scope and alias mapping are in `icons/NOTICE.md`; full license is `icons/PAPIRUS-LICENSE.txt`. |
| `quickshell/sparrow/Lockscreen/font/Outfit-Black.ttf` | [Outfit Fonts](https://github.com/Outfitio/Outfit-Fonts), SIL Open Font License 1.1 | Unmodified bundled font; copyright and full OFL notice are in `Lockscreen/font/OFL.txt`. The font remains separately licensed and is not relicensed under the project license. |

## Sparrow-created material and generated output

- `quickshell/sparrow/wallpapers/default.png` is the Sparrow author's own
  screenshot captured in SpaceEngine Pro. The author retains its copyright and
  permits its redistribution bundled as Sparrow's default wallpaper. It is not
  an upstream SpaceEngine image, and this statement does not grant a separate
  standalone wallpaper license. See `quickshell/sparrow/wallpapers/README.md`.
- Sparrow's GTK base stylesheet is read from the locally installed
  `adw-gtk-theme` (`adw-gtk3`, LGPL-2.1-only) package and recolored into generated
  per-user files. The upstream stylesheet is not vendored in this repository;
  generated output carries a source/license header. The package is a runtime
  dependency, not a redistributed Sparrow component.
- Wallpaper palettes, generated GTK theme/icon output, Kitty colors, and Niri
  generated color fragments are local generated state, not committed assets.
- Kitty, Fish, Starship, Niri, Hyprlock, and desktop-entry defaults in this
  repository are Sparrow-authored configuration or integration examples. No
  external config repository is bundled for those files.

## Runtime dependencies, not redistributed

Niri, Quickshell, Matugen, awww, mpvpaper, GTK/adw-gtk3, Kitty, Fish, Starship,
Thunar, LXQt PolicyKit, Rishot, and other invoked package/application projects
are installed by the user or distribution. Their licenses remain with their
upstream packages. Sparrow's installer downloads the official pinned Rishot
source archive at install time and installs its MIT notice alongside the
managed files; Rishot source is not vendored in this repository.

## License-file placement

The full GPL-3.0 text appears in the root `LICENSE` and is also retained beside
the Qylock adaptation and Papirus subset so those component directories remain
self-describing. These identical license-text copies are intentional; do not
remove or rewrite the component copies when packaging them independently.
