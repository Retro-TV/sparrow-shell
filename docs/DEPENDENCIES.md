# Sparrow runtime dependencies (Arch/CachyOS)

This inventory is based on active QML, scripts, systemd units and the current
Niri binds. `installer/package-sets.json` is the exact package set used by
Installer v1. The complete approved desktop package profile is installed in
one default transaction and validated before deployment; only the Hyprlock
fallback remains optional. Sparrow never invokes an AUR helper.
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
| `gtk-launch` + Sparrow `sparrow-launch-app` | Niri's Browser/Terminal/File manager role shortcuts resolve a desktop ID and launch the desktop entry (so Sparrow Files retains its app-scoped GTK theme). |
| Arch/CachyOS base session | `systemctl`, `systemd-analyze`, `env`, `gio`, and `udevadm` come from the existing systemd/glib/base installation; the installer checks the commands needed for session and config validation. |
| `systemd` and `dbus` | User services, graphical-session target, session bus and Quickshell desktop-service integration. |
| `pam` | System PAM stack used by Quickshell's primary secure session lock. |
| `polkit` plus one graphical authentication agent | The daemon alone cannot display authorization prompts. Sparrow recommends `lxqt-policykit` only when the user has no existing agent; preserve an existing agent rather than starting a second. |
| `greetd`, `greetd-tuigreet` | Sparrow's tested terminal login flow. Packages are installed with the default profile; on a clean system with no competing display manager, enablement prepares tty2 recovery and takes effect next boot. |
| `xwayland-satellite` | Default compatibility backend for legacy/X11 applications such as Steam under Niri. Modern Niri manages it automatically; Sparrow adds no custom startup or environment configuration. |

Quickshell's Arch package depends on Qt 6 base/declarative/SVG/Wayland
components. Sparrow's video preview additionally uses `qt6-multimedia` and
`qt6-multimedia-ffmpeg`.

## Feature packages

| Package/tool | Classification and caller |
| --- | --- |
| `awww` | Required for image wallpapers, the persistent still/backdrop layer, and transition control; `awww-daemon` is launched by `sparrow-wallpaper.service`. |
| `matugen` | Required for wallpaper-derived palette generation. This host currently has the AUR `matugen-bin`; Arch Extra provides `matugen`, which is the preferred portable package name. |
| `python-pillow` | Required by `scripts/wallcolors.py` for palette image processing. |
| `mpvpaper` | Required for Sparrow's first-class animated/video wallpapers (GIF, MP4, WebM, MKV, MOV); it renders motion per output while awww supplies the still/backdrop layer. Installer installs the CachyOS repository package and refuses file deployment if the backend is neither installed nor available. On Arch, install `mpvpaper` from the AUR using a reviewed `PKGBUILD`, then rerun the installer; Sparrow does not bootstrap an AUR helper or execute remote install scripts. |
| `ffmpeg` | Recommended default bundle: Wallpaper-picker thumbnails, wallpaper dimensions/stills, and recording thumbnails use it. Images and the shell still work without it, but those previews/helpers are degraded. |
| `imagemagick` | Default-profile wallpaper-search image format identification and Rishot multi-monitor stitching/metadata handling. |
| `hyprlock` | Optional fallback only. The primary lock is Sparrow's Quickshell `WlSessionLock` + PAM flow; `sparrow-lock` invokes Hyprlock only when Sparrow lock IPC is unavailable. |
| `gpu-screen-recorder` | Installed by the default profile for Sparrow's Recorder capture/record operation. |
| `slurp` | Installed by the default profile for Niri's recorder region/window selection helper. |
| `python-gobject` | Required; used by Sparrow's recording-folder FileChooser integration and Gio-backed first-user defaults. |
| `xdg-desktop-portal`, `xdg-desktop-portal-gtk` | Required for the tracked FileChooser route; GTK theme remains scoped to the GTK portal service. |
| `xdg-desktop-portal-gnome` | Required for the tracked Niri ScreenCast route in the canonical Sparrow portal profile ([Niri screencasting](https://github.com/niri-wm/niri/wiki/Screencasting)). Existing user portal config is backed up before replacement. |
| `lxqt-policykit` (conditional required agent) | Provides `/usr/bin/lxqt-policykit-agent`; added to required packages only when no running/autostart/user-unit graphical Polkit agent is detected. Existing agents are preserved and Sparrow's own unit is omitted. |
| `xdg-utils` | `xdg-open` integration used by Recorder for recordings and folders; `xdg-settings` synchronizes a Browser choice with the desktop's default browser. |
| `qt6-multimedia`, `qt6-multimedia-ffmpeg` | Needed for Sparrow's wallpaper video previews in the picker. |
| `wlsunset` | Default-profile Night Light backend; Sparrow starts it only when the user enables Night Light. |
| `inter-font` | Required; supplies Sparrow's core UI family `Inter Black`. |
| `ttf-jetbrains-mono-nerd` | Required; supplies Kitty's configured `JetBrains Mono Nerd Font` family. |
| `adwaita-fonts` | Required; supplies the GTK/libadwaita `Adwaita Sans` default. |
| `cava` | Default-profile pill spectrum visualizer; still activated only when the UI needs it. |
| `networkmanager` | Default-profile Wi-Fi backend (`nmcli`); availability still depends on the host daemon and adapter. |
| `bluez`, `bluez-utils` | Default-profile Bluetooth integration; availability still depends on the daemon and adapter. |
| `upower` | Default-profile battery/peripheral status integration when supported hardware is present. |
| `curl` | Default profile: weather and online wallpaper search/download/preview. The local wallpaper flow does not depend on network access. |
| `wl-clipboard` | Default-profile requirement; Launcher copies calculator results and Rishot uses it for clipboard integration. |
| `libnotify` | `notify-send` notices from Recorder and low-battery peripheral handling; Sparrow's internal notification UI does not use it. |
| `brightnessctl` | Default-profile utility; internal brightness control appears only when a sysfs backlight is detected. |
| `ddcutil` | Default-profile utility; external brightness controls appear only for displays with a readable DDC/CI VCP 10 brightness value. Its package supplies the userspace tool and udev access rules; the kernel's I²C support and monitor capability remain hardware/system dependent. `coreutils` supplies the `timeout` wrapper used for writes. |
| `nvibrant` | Optional NVIDIA vibrance backend; Sparrow checks its executable and NVIDIA device before exposing it. Not installed on the audited host. |
| `tumbler` | Optional system D-Bus thumbnail service for Thunar image previews. |
| `adw-gtk-theme` | Required source for Sparrow's generated GTK3/GTK4 CSS (Thunar, scoped pavucontrol, and GTK portal); palette generation fails clearly if the base is missing or incompatible. |
| Bibata Modern Ice v2.0.6 | Not a pacman/AUR dependency: Installer explicitly offers the official pinned upstream archive, verifies its SHA-256, and installs per-user under `$XDG_DATA_HOME/icons/Bibata-Modern-Ice`. Declining stops a fresh canonical install before Sparrow files are deployed. When installed and no explicit different cursor choice exists, Niri, `environment.d`, and unset GSettings keys select it at size 24. |

The pinned [Bibata v2.0.6 release archive](https://github.com/ful1e5/Bibata_Cursor/releases/download/v2.0.6/Bibata-Modern-Ice.tar.xz)
is checked against the digest in `SOURCE-OF-TRUTH.json`; the installer
keeps a backup and records ownership of the per-user cursor directory so update
and uninstall can preserve later user changes. The upstream project is
[GPL-3.0 licensed](https://github.com/ful1e5/Bibata_Cursor/blob/main/LICENSE).
Inter and JetBrains Mono Nerd Font are installed on the audited host. Sparrow
has no decorative CJK glyph mode or Zen Kaku font dependency.

The lockscreen's `Outfit-Black.ttf` is bundled under
`quickshell/sparrow/Lockscreen/font/` with its OFL-1.1 notice; it does not need
a system package. Sparrow's icons are SVG/custom QML paths, not a Material,
Font Awesome, or Nerd Font icon-font dependency.
The portable source/output contract and the remaining installer-policy gaps
are recorded in `SOURCE-OF-TRUTH.json` and `docs/SOURCE-OF-TRUTH.md`.

## Screenshot integration

Rishot remains an independent MIT-licensed upstream application, but is now
installed by Sparrow from an immutable official GitHub source archive pinned
to commit `a87427a9083981315a080133636c38d8ca565d0e` and its SHA-256 in
`SOURCE-OF-TRUTH.json`. Sparrow never runs the upstream mutable installer or
builds an AUR package. Its files are managed at `$XDG_DATA_HOME/rishot`, with a
PATH launcher at `$HOME/.local/bin/rishot`; Rishot user config/state is not
owned. Reruns skip unchanged pinned files; uninstall restores/removes only
unchanged Sparrow-managed files. Required runtime dependencies are `quickshell`,
`qt6-declarative`, `qt6-svg`, `qt6-5compat`, `qt6-wayland`, and `wl-clipboard`.
On Niri, `grim` is the screenshot grabber. Optional: `imagemagick`
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

## Replaceable/recommended application extras

| Package/tool | Why it is in the reference desktop profile |
| --- | --- |
| `pavucontrol` | Installed by default as the advanced audio-control app. If launched from Sparrow Launcher, only this GTK4 application receives `GTK_THEME=Sparrow`; Sparrow's native Mixer remains primary. |
| `firefox` | Ordinary default browser binding only; Sparrow does not ship or apply a Firefox theme. |
| `curl`, `wl-clipboard`, `ffmpeg` | Recommended support tools for Weather/wallpaper search, Launcher copy, and wallpaper/recording previews. |

`kitty`, `fish`, `starship`, `thunar`, `inter-font`, and
`ttf-jetbrains-mono-nerd` are required packages because their bindings,
configuration, and typography are part of the captured default desktop.
`tumbler` is installed by default for Thunar image thumbnails; `adw-gtk-theme` supplies the required
base used to generate Sparrow's Thunar appearance.

The only browser-related runtime work is optional wallpaper search/download.

## Not core / not included

- `nvibrant` and the Hyprlock fallback are optional. Rishot is installed by
  default from its pinned upstream archive. Bibata is a pinned upstream
  per-user install (not an AUR package); it is applied automatically only when
  there is no explicit different cursor choice.
- `gvfs` is recommended for Thunar's removable-volume and remote-location
  integration; it is not required for opening local folders or basic file
  operations. `zoxide` is optional for the reference Fish shell.
- Sparrow installs only the declared official-package groups after consent;
  it does not manage arbitrary pacman/AUR packages or bundle a browser,
  personal wallpapers, monitor setup, generated theme files or personal
  Hyprlock configuration. Rishot upstream source is fetched at install time
  from the pinned commit and is not vendored in Git.
- The tracked portal profile and GTK/GNOME backends are part of the required
  Sparrow configuration path. FileChooser routes to GTK and Niri ScreenCast
  routes to GNOME; the GTK theme override remains scoped to the portal service.

## Installer v1 package policy

Installer v1 installs the complete Sparrow default profile described in
`installer/package-sets.json`; optionality is reserved for true fallback or
hardware-specific capabilities. It uses pacman only after consent, never
bootstraps an AUR helper, and never removes packages during restore.
Systemd, D-Bus, PAM, the Polkit daemon, and a graphical session are platform
prerequisites rather than installer-owned system services; Sparrow does not
rewrite their system configuration.
