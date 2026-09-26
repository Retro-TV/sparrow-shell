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
| `networkmanager` | Quickshell networking plus `nmcli` actions in Wi-Fi UI. NetworkManager daemon must be running for Wi-Fi controls. |
| `bluez`, `bluez-utils` | Quickshell Bluetooth and `bluetoothctl` pairing/trust/connect operations; Bluetooth service/adapter are system-dependent. |
| `curl` | Weather lookup, wallpaper search/download/preview, optional online wallpaper actions. |
| `xdg-utils` | Generic `xdg-open` integration where used. |
| `gtk3` | `gtk-launch` starts selected `.desktop` entries in Sparrow Launcher. Ordinary desktop-entry discovery is not a package manager. |
| `libnotify` | `notify-send` for Sparrow recorder/peripheral notifications. |
| `systemd` | User units, idle/power actions and graphical session target. |
| `dbus` and `upower` | User/session services consumed by Quickshell's notifications, tray, Bluetooth and UPower battery services; actual daemons/session bus must be available. |
| `xdg-desktop-portal` plus a compatible session backend | Portal-based recording directory/file selection and desktop integration. Select a backend suitable for the installed session; this host has GNOME/GTK portal backends. |

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
| `hyprlock` | Required for Sparrow's selected lock backend; Niri-independent session-lock client. The Sparrow wrapper fails clearly if it is absent. |
| `gpu-screen-recorder` | Required for Sparrow's Recorder capture/record operation. |
| `slurp` | Used for Niri's recorder region/window selection helper. |
| `python-gobject` | Used by the recording folder-selection helper (`gi.repository.Gio/GLib`). |
| `qt6-multimedia`, `qt6-multimedia-ffmpeg` | Needed for Sparrow's wallpaper video previews in the picker. |
| `wlsunset` | Optional Night Light backend; status UI remains adaptive when absent. |
| `cava` | Optional pill spectrum visualizer; Sparrow probes and stays usable when absent. |
| `brightnessctl` | Optional on systems with `/sys/class/backlight`; internal brightness UI is only exposed when hardware and tool are detected. |
| `ddcutil` | Optional external DDC/CI display brightness controls in Mixer. Not installed on the audited host. |
| `nvibrant` | Optional NVIDIA vibrance backend; Sparrow checks its executable and NVIDIA device before exposing it. Not installed on the audited host. |
| `kitty`, `thunar`, `firefox` | Current default Niri app bindings. These are replaceable user app choices, not intrinsic Sparrow runtime dependencies. |
| `bibata-cursor-theme-bin` (AUR) | Supplies the configured `Bibata-Modern-Ice` XCursor theme. The config sets theme and size but does not bundle cursor files. |

## Separate screenshot application

Rishot is upstream software, separately installed as `rishot-git` from AUR or
through its upstream standalone install route; it is not part of Sparrow's
source tree. Its documented required runtime dependencies are `quickshell`,
`qt6-declarative`, `qt6-svg`, `qt6-5compat`, `qt6-wayland`, and
`wl-clipboard`. On Niri, `grim` is the screenshot grabber. Optional: `imagemagick`
(multi-monitor stitch), `cliphist` (clipboard history), `curl` (upload),
`kdialog` (file/directory dialogs), and `libnotify` (notifications). `spectacle`
is a KDE/KWin capture path and is not required for Niri.

## Development/test only

- `qmllint`/Qt declarative tooling for QML checks (provided by Qt 6 tooling on
  the development host; not needed merely to run the installed shell).
- `niri validate` for static config checking; comes with Niri.
- Python standard-library `unittest` for the Niri config transaction tests.
- `git` for checkout/development.

## Not core / not included

- `ddcutil`, `nvibrant`, `wlsunset`, `cava`, `mpvpaper`, cursor assets and
  Rishot are optional or feature-specific as described above.
- Sparrow does not install packages, manage pacman/AUR, bundle a browser,
  terminal, file manager, personal wallpapers, monitor setup, generated theme
  files, personal Hyprlock configuration or Rishot source.
- A Wayland session portal backend is a session integration dependency, not a
  reason to hardcode this host's GNOME/GTK backend into the portable defaults.
