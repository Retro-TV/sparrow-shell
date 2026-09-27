# Sparrow runtime dependencies (Arch/CachyOS)

This inventory is based on active QML, scripts, systemd units and the current
Niri binds. It is a future-installer input, not a package-install command.
Arch package names are shown in backticks; names marked AUR are not official
repository packages. Core means needed for the corresponding Sparrow session
or surface, not that every feature-specific binary must be installed for the
shell to start.

## Session/core

| Package/tool | Why Sparrow uses it |
| --- | --- |
| `niri` | Niri 26.04 compositor, `niri msg` event stream/output/config transaction API, native rules and actions. |
| `quickshell` | `qs` runtime and the QtQuick/Quickshell services used by the shell; current version is 0.3.1. |
| `python` | State migration, Niri transaction/display/input/recording helpers, wallpaper palette helper. |
| `bash` | Sparrow shell scripts and a number of shell-backed QML processes. |
| `jq` | JSON parsing in wallpaper initialization/search and helper scripts. |
| `findutils`, `coreutils`, `grep`, `gawk`, `sed`, `procps-ng`, `util-linux` | Base commands used by scripts (`find`, `timeout`, `pgrep`, `flock`, `shuf`, text processing, filesystem utilities). |
| `pipewire`, `wireplumber` | Quickshell PipeWire service, mixer/OSD, Cava source, recording audio; `wpctl` comes from WirePlumber and `pw-dump` from PipeWire. |
| `gtk3` | `gtk-launch` starts selected `.desktop` entries in Sparrow Launcher. Ordinary desktop-entry discovery is not a package manager. |
| `systemd` and `dbus` | User services, graphical-session target, session bus and Quickshell desktop-service integration. |
| `pam` | System PAM stack used by Quickshell's primary secure session lock. |

Quickshell's Arch package depends on Qt 6 base/declarative/SVG/Wayland
components. Sparrow's video preview additionally uses `qt6-multimedia` and
`qt6-multimedia-ffmpeg`.

## Feature packages

| Package/tool | Classification and caller |
| --- | --- |
| `awww` | Required for the image/GIF-still wallpaper backend and transition control; `awww-daemon` is launched by `sparrow-wallpaper.service`. |
| `matugen` | Required for wallpaper-derived palette generation. This host currently has the AUR `matugen-bin`; Arch Extra provides `matugen`, which is the preferred portable package name. |
| `python-pillow` | Required by `scripts/wallcolors.py` for palette image processing. |
| `mpvpaper` | Optional; enables video wallpaper playback while awww still supplies the still frame/backdrop. |
| `ffmpeg` | Required by wallpaper thumbnail/still generation and recording thumbnail work; used for video wallpaper extraction and supported preview formats. |
| `imagemagick` | Optional wallpaper-search image format identification and Rishot multi-monitor stitching/metadata handling. |
| `hyprlock` | Optional fallback only. The primary lock is Sparrow's Quickshell `WlSessionLock` + PAM flow; `sparrow-lock` invokes Hyprlock only when Sparrow lock IPC is unavailable. |
| `gpu-screen-recorder` | Required for Sparrow's Recorder capture/record operation. |
| `slurp` | Used for Niri's recorder region/window selection helper. |
| `python-gobject` | Used by the recording folder-selection helper (`gi.repository.Gio/GLib`). |
| `xdg-desktop-portal`, `xdg-desktop-portal-gtk`, compatible session backend | Recording folder selection calls the FileChooser portal. The GTK backend receives Sparrow's generated GTK theme only through its scoped service environment. |
| `xdg-utils` | `xdg-open` integration used by Recorder for recordings and folders. |
| `qt6-multimedia`, `qt6-multimedia-ffmpeg` | Needed for Sparrow's wallpaper video previews in the picker. |
| `wlsunset` | Optional Night Light backend; status UI remains adaptive when absent. |
| `inter-font` | Required for the Sparrow core UI default family `Inter`; the package includes its Black/ExtraBold weights, so no separate Inter Black package is needed. |
| `cava` | Optional pill spectrum visualizer; Sparrow probes and stays usable when absent. |
| `networkmanager` | Wi-Fi surface uses `nmcli`; useful only with NetworkManager and a Wi-Fi adapter. |
| `bluez`, `bluez-utils` | Bluetooth surface uses Quickshell BlueZ integration and `bluetoothctl`; requires the daemon and adapter. |
| `upower` | Battery/peripheral status integration, when supported hardware is present. |
| `curl` | Weather lookup and optional online wallpaper search/download/preview. |
| `libnotify` | `notify-send` notices from Recorder and low-battery peripheral handling; Sparrow's internal notification UI does not use it. |
| `brightnessctl` | Optional on systems with `/sys/class/backlight`; internal brightness UI is only exposed when hardware and tool are detected. |
| `ddcutil` | Optional external DDC/CI display brightness controls in Mixer. Not installed on the audited host. |
| `nvibrant` | Optional NVIDIA vibrance backend; Sparrow checks its executable and NVIDIA device before exposing it. Not installed on the audited host. |
| `tumbler` | Optional system D-Bus thumbnail service for Thunar image previews. |
| `adw-gtk-theme` | Provides the system-installed `adw-gtk3` base used by Sparrow's generated, wallpaper-colored Thunar GTK3 theme. |
| `bibata-cursor-theme-bin` (AUR) | Recommended default cursor asset; Niri and `environment.d/90-cursor.conf` select Bibata Modern Ice at size 24. The theme itself is not bundled. |

The current live Bibata files identify themselves as version 2.0.6 and are an
unowned copy under `~/.local/share/icons/Bibata-Modern-Ice`. The AUR package
currently offers the same named theme variant from upstream v2.0.7; fresh
installations should use that package rather than copy this host's local files.
Inter and JetBrains Mono Nerd Font are installed on the audited host. Sparrow
has no decorative CJK glyph mode or Zen Kaku font dependency.

The lockscreen's `Outfit-Black.ttf` is bundled under
`quickshell/sparrow/Lockscreen/font/` with its OFL-1.1 notice; it does not need
a system package. Sparrow's icons are SVG/custom QML paths, not a Material,
Font Awesome, or Nerd Font icon-font dependency.

## Separate screenshot application

Rishot is upstream software, separately installed as `rishot-git` from AUR or
through its upstream standalone install route; it is not part of Sparrow's
source tree. Its documented required runtime dependencies are `quickshell`,
`qt6-declarative`, `qt6-svg`, `qt6-5compat`, `qt6-wayland`, and
`wl-clipboard` (Rishot's own screenshot workflow; Sparrow does not provide a
Quickshell clipboard feature). On Niri, `grim` is the screenshot grabber. Optional: `imagemagick`
(multi-monitor stitch), `cliphist` (clipboard history), `curl` (upload),
`kdialog` (file/directory dialogs), and `libnotify` (notifications). `spectacle`
is a KDE/KWin capture path and is not required for Niri.

## Development/test only

- `qmllint`/Qt declarative tooling for QML checks (provided by Qt 6 tooling on
  the development host; not needed merely to run the installed shell).
- `niri validate` for static config checking; comes with Niri.
- Python standard-library `unittest` for the Niri config transaction tests.
- `nodejs` for `quickshell/sparrow/lib/monitors.test.mjs`.
- `git` for checkout/development.

## Bundled assets (not packages)

- Outfit Black (`quickshell/sparrow/Lockscreen/font/Outfit-Black.ttf`) and its
  OFL-1.1 notice are bundled for the Quickshell lockscreen only.
- Sparrow QML, its custom SVG/QML icons, the portable Niri fragments, Kitty/Fish/
  Starship and Thunar defaults, Matugen templates, and the redistributable
  Sparrow default wallpaper are repository assets. Their corresponding runtime
  applications/tools remain package or external-application dependencies.
- Papirus-derived Sparrow SVG icons are included with their license notices.

## Default desktop apps (replaceable choices)

| Package/tool | Why it is in the reference desktop profile |
| --- | --- |
| `kitty`, `fish`, `starship` | Shipped terminal and shell defaults; not required to run Quickshell. `zoxide` and `fastfetch` are optional Fish conveniences. |
| `ttf-jetbrains-mono-nerd` | Provides the selected Kitty face and Starship's Nerd Font symbols. |
| `thunar` | Current default file manager, not a Sparrow runtime requirement. `tumbler` adds image thumbnails; `adw-gtk-theme` supplies the system GTK3 theme base used for Sparrow's generated Thunar theme. |
| `firefox` | Ordinary default browser binding only; Sparrow does not ship or apply a Firefox theme. |

The only browser-related runtime work is optional wallpaper search/download.

## Not core / not included

- `ddcutil`, `nvibrant`, `wlsunset`, `cava`, and `mpvpaper` are optional;
  Rishot is separately installed as described above. The cursor package is a
  recommended default, but users may select a different installed cursor.
- `gvfs` is recommended for Thunar's removable-volume and remote-location
  integration; it is not required for opening local folders or basic file
  operations. `zoxide` is optional for the reference Fish shell.
- Sparrow does not install packages, manage pacman/AUR, bundle a browser,
  terminal, file manager, personal wallpapers, monitor setup, generated theme
  files, personal Hyprlock configuration or Rishot source.
- A Wayland session portal backend is a session integration dependency, not a
  reason to hardcode this host's GNOME/GTK backend into the portable defaults.
