# Sparrow installation inventory

Audit date: 2026-09-28. This document records the current repository and live
CachyOS/Niri host before installer design. It is an implementation inventory,
not an installer specification that authorizes overwriting existing files.
Current source is authoritative for executable use; installed Arch package
pages and upstream project documentation are linked where they establish
package/source facts.

## Product being reproduced

Sparrow is a Niri 26.04 desktop with a Quickshell 0.3.1 shell and a separate
Quickshell idle instance. Niri owns windows, outputs, workspaces and input;
Sparrow owns its multi-output pill/surfaces, selected wallpaper and generated
theme state. The default configuration is a coordinated rice rather than a
general-purpose desktop environment: it does not include a greeter, browser
theme, package manager, clipboard manager, or a second compositor-control
framework.

### Intended visible stack

| Area | Actual current component / backend | Classification |
| --- | --- | --- |
| Session | Niri 26.04, systemd user manager, graphical-session target | Required foundation |
| Main shell | Quickshell main `shell.qml`; pill, surfaces and IPC | Required foundation |
| Background | Sparrow wallpaper unit, awww image/still layer; optional mpvpaper video per output | awww is default; mpvpaper optional |
| Idle | Separate `idle/shell.qml` instance; Niri idle/output controls and session lock | Required to deliver configured idle policy |
| Pill / surfaces | Workspaces, Launcher, Wallpaper, Mixer, Recorder, Settings and modal/morphed surfaces | Core Sparrow UI |
| Niri settings | Look, Display, Input, Keybinds through validated managed fragments | Core, with machine/user values generated outside portable defaults |
| Personalization | Matugen-derived shell roles, lock foreground, Niri border colors, Kitty, Sparrow GTK/icon assets | Core dynamic theme; outputs generated |
| Lock | Quickshell `WlSessionLock` + Quickshell PAM + adapted Qylock Last of Us | Primary lock; Qt Multimedia used for themed motion/background behavior |
| Applications | Kitty/Fish/Starship terminal; Thunar with Sparrow GTK theme; Firefox binding | Intended defaults, replaceable by user |
| Desktop integration | Sparrow Files `.desktop` directory handler; merge-only GTK FileChooser preference; GTK portal theme scope | Sparrow-owned integration; preserve existing defaults and all other portal routes |
| Network/devices | NetworkManager Wi-Fi, BlueZ Bluetooth, PipeWire audio, UPower/battery, MPRIS | Core surfaces, but dependent on services/devices |
| Optional controls | Video, Cava, Night Light, brightness, DDC, NVIDIA vibrance, recording, weather/search, Hyprlock fallback, screenshots | Explicitly optional/adaptive |

The fresh-install default flags are Dynamic palette + Auto palette style/mode,
Auto lock text, Night Light off and the built-in Sparrow Default wallpaper.
Flags are per-user: installation must provide defaults through the schema, not
copy the development host's `flags.json`.

## Rishot PATH correction and standalone boundary

The tracked Niri bind previously executed the host-specific
`"$HOME/.local/bin/rishot"` through `spawn-sh`. It now uses Niri's direct
`spawn "rishot"`, resolving the executable through the inherited session PATH.
The keybind catalog already described only the screenshot action/key and had
no path to change. Getting Started likewise has no Rishot command/path. The
dependency, portability, baseline and fresh-install docs now describe the
PATH contract rather than asserting a fixed installation path. The current
host's active `~/.config/niri` tree is separate from the tracked source; it was
not edited or reloaded in this task.

Rishot is an independent MIT-licensed Quickshell application by Gakuseei, not a
Sparrow component. Its current [upstream README](https://github.com/Gakuseei/rishot)
documents `rishot` as the command and its current installer installs runtime
files under `~/.local/share/rishot` and links `~/.local/bin/rishot`. The
installer's source says the `rishot-git` AUR package is its primary route;
because the README and AUR availability/maintenance need to remain current,
Installer v1 does not silently clone or run a privileged upstream script.
Recommended policy: list Rishot as an optional, separate app; offer its
upstream-supported AUR package only after explicit AUR consent, otherwise give
the user the upstream reviewed-install instructions. Verify that the resulting
launcher is on PATH before enabling its optional bind. Do not vendor it.

Rishot required runtime dependencies per upstream: `quickshell` (`qs`),
`wl-clipboard`, Qt 6 declarative, SVG, 5compat and Wayland modules; on Niri it
uses `grim` for capture. Optional features use ImageMagick (stitch/metadata),
cliphist, curl (upload), kdialog and libnotify. On Niri upstream documents
region/monitor capture and window-click only for floating windows. The current
host's launcher is a symlink at `~/.local/bin/rishot` to
`~/.local/share/rishot/bin/rishot`, not owned by pacman.

## External executable inventory

This is the source-traced set of external commands directly run by tracked
runtime QML/JS/Python/shell/KDL/systemd/desktop files. Shell builtins, paths
read directly from `/proc` and `/sys`, and commands used only in tests are
called out separately. Several base utilities are invoked by helper scripts;
Arch's `base`/`base-devel`-adjacent environment is not a substitute for
declaring those when a genuinely minimal install omits them.

| Command / executable | Callers and purpose | Arch/source recommendation | Absence behavior / class |
| --- | --- | --- | --- |
| `niri` | Niri binds; Sparrow Niri IPC/event stream/output queries; transaction helper/reload; recorder window list; power logout | Official `niri` in Extra ([package](https://archlinux.org/packages/extra/x86_64/niri/)) | Required; shell backend cannot operate without Niri |
| `qs` / `quickshell` | Main and idle shell services; IPC bindings; Rishot; Quickshell components | Official Extra `quickshell` ([package](https://archlinux.org/packages/extra/x86_64/quickshell/)); require compatible Qt QML/runtime modules | Required; no shell or lock |
| `python3` | Service migration, color generation, folder chooser, input info, window selection, config transaction | Official `python`; `python-pillow` for palette processing, `python-gobject` for portal chooser helper | Required for service migration/palette/Niri helper; chooser helper reports failure if GObject unavailable |
| Python `PIL` | `wallcolors.py` image sampling/metadata | Official `python-pillow` | Required for palette generation; background stays but palette update fails |
| `bash` | wallpaper, thumbnails/search, lock wrapper, several script callers; `bash` is explicit in units/QML | Official `bash` (also Niri package's optional `niri-session` dependency) | Required; helpers don't run |
| `sh` | QML shell probes/wrappers and script helpers | `/bin/sh` provider from base system (`bash` on current Arch) | Required for numerous integrations |
| `jq` | flags/state JSON reads/writes and wallpaper/theme tooling | Official `jq` | Required for reliable wallpaper and state helpers; error/fallback paths otherwise |
| `matugen` | `wallcolors.py` invokes Matugen for wallpaper palette generation | Official Extra `matugen` ([package](https://archlinux.org/packages/extra/x86_64/matugen/)); prefer official repo package over `matugen-bin` | Required for Dynamic palette; old palette/fallback colors remain if failed |
| `awww-daemon`, `awww` | wallpaper systemd service and wallpaper operations/query/stop | Official Extra `awww` ([package](https://archlinux.org/packages/extra/x86_64/awww/)) | Required default wallpaper daemon; restoration reports failure if absent |
| `mpvpaper` | video wallpaper playback | AUR package `mpvpaper` on Arch ([ArchWiki app index](https://wiki.archlinux.org/title/List_of_applications/Other)); confirm target repo/package before install | Optional; images/stills continue; saved video cannot restore as video |
| `ffmpeg`, `ffprobe` | video/GIF stills, wallpaper thumbnails, recording thumbnails and media dimensions | Official Extra `ffmpeg` | Feature-critical: static images remain, but animated still/palette and previews fail/are omitted |
| `nmcli` | Wi-Fi scan/connect/profile operations and hotspot UI | Official `networkmanager` provides CLI; enable NetworkManager only by user choice if another network manager owns networking | Wi-Fi feature requires NetworkManager service; failures are presented in that surface |
| `bluetoothctl` | Bluetooth pairing/trust/connect command path | Official `bluez-utils`; daemon is `bluez` | Feature-specific; unavailable adapter/daemon prevents Bluetooth operations |
| `wpctl` | Volume, mute, source and default sink controls | Official `wireplumber` supplies `wpctl`; install PipeWire + WirePlumber | Audio control needs a running PipeWire session; unavailable device/backend prevents use |
| `systemctl` | Sparrow power actions, idle service start, environment import, service lifecycle | Official `systemd` | Required for units/power/idle path; systemd user session is core |
| `wlsunset` | Quickshell-managed Night Light process | Official Extra package if present; optional | Optional; reports unavailable; off state starts none |
| `cava` | Quickshell audio visualizer process | Official Extra `cava` | Optional; availability probe keeps visualizer hidden/inactive |
| `brightnessctl` | Niri hardware brightness bindings and Mixer internal backlight | Official Extra `brightnessctl` | Optional; useful only with a backlight device; other Mixer remains |
| `ddcutil`, `timeout` | Mixer DDC detection/control; timeout bounds writes | Official `ddcutil` package if available; `timeout` from `coreutils` | Optional; no DDC row when absent; silent guard |
| `nvibrant` | NVIDIA vibrance control | Third-party/upstream package/source; identify compatible package only on NVIDIA targets | Optional; hidden unless command and NVIDIA modeset device exist |
| `gpu-screen-recorder` | Recorder capture/record; process polling/stop | Official Extra `gpu-screen-recorder` ([package](https://archlinux.org/packages/extra/x86_64/gpu-screen-recorder/)) | Optional feature; surface reports backend failures |
| `slurp` | Recorder region and window-point selection helper | Official Extra `slurp` | Optional within Recorder; direct display recording remains; picker reports unavailable |
| `grim` | Rishot Niri capture dependency | Official Extra `grim`; separate Rishot dependency | Optional Rishot path only |
| `rishot` | Niri `Super+Shift+S` screenshot bind, resolved through PATH | Separate upstream Rishot install; not Sparrow package/source | Optional; key action fails if user hasn't installed it |
| `kitty` | Niri terminal bind; generated colors reload via `pkill -USR1` | Official Extra `kitty` ([manual/package](https://man.archlinux.org/man/kitty.1.en)) | Default app; change bind if user does not install/choose Kitty |
| `fish` | Kitty login shell; user's Fish configuration | Official Extra `fish` | Default app dependency; Kitty shell launch fails or falls back depending Kitty handling |
| `starship` | Fish prompt initialization | Official Extra `starship` | Optional for base Fish; Sparrow directory prompt absent if not installed |
| `zoxide`, `fastfetch` | Optional Fish startup integration and `ff` abbreviation | Official Extra packages | User-invoked Fish conveniences; not Sparrow shell requirements |
| `thunar`, `env`, `gtk-launch` | Niri/default-files `.desktop` entry; launcher routes desktop entries via `gtk-launch` | `thunar` official Extra ([package](https://archlinux.org/packages/extra/x86_64/thunar/)); `gtk-launch` from GTK3/GLib stack; `env` base coreutils | Thunar is the configured default file manager; other desktop entries need their own installed apps |
| `pavucontrol` | Sparrow Launcher recognizes its desktop ID and starts this external advanced-volume UI with app-scoped `GTK_THEME=Sparrow` | Optional upstream app; GTK4/gtkmm4 is supplied by its package | Optional; the native Sparrow Mixer remains the primary control surface |
| `tumbler` | Thunar image/media thumbnails; not directly launched by Sparrow but required for stated file-manager experience | Official Extra `tumbler` ([package](https://archlinux.org/packages/extra/x86_64/tumbler/)) | Recommended default app integration; without it previews are missing |
| `gio` | Wallpaper deletion through Trash | GTK/GLib (`glib2`) runtime | Missing GUI trash integration makes that picker action fail |
| `xdg-open` | Open saved recordings/output directory | Official `xdg-utils` | Recording UI can open paths only if a handler exists |
| `wl-copy` | Launcher calculation result copy; Rishot clipboard path | Official `wl-clipboard` | Copy/Rishot clipboard feature unavailable |
| `notify-send` | Recorder feedback and battery notification | Official `libnotify` | Non-blocking feedback absent; core UI still runs |
| `curl` | Weather, wallpaper search/download/preview, Rishot optional upload | Official Extra `curl` | Weather/search fail gracefully; normal local wallpapers unaffected |
| `magick` | Wallpaper-search image identification; Rishot optional | Official `imagemagick` (command `magick`) | Optional downloaded-format check/conveniences; local wallpapers unaffected |
| `cp` | Pill copies dropped wallpaper images/videos into Sparrow's wallpaper library | `coreutils` | Required only for wallpaper file-drop import; picker and normal wallpaper selection remain separate |
| `firefox` | Niri default browser binding | Official Extra `firefox` | Replaceable default-app choice; not needed by Sparrow itself |
| `gtk-update-icon-cache` | Regenerated Sparrow icon theme index | GTK3 package | Optional integration refresh; generated SVGs still written |
| `nvidia-smi` | Optional NVIDIA GPU stats | `nvidia-utils` | GPU fields unavailable; CPU/memory/disk stats remain |
| `df`, `awk`, `grep`, `head`, `cat`, `ls`, `sleep`, `printf`, `find`, `sort`, `shuf`, `tail`, `tr`, `cut`, `date`, `md5sum`, `flock`, `setsid`, `kill`, `rm`, `mv`, `mkdir`, `dirname`, `basename`, `readlink`, `pgrep`, `pkill`, `timeout`, `env`, `stat`, `ip` | Basic helper scripting, CPU/system monitoring, wallpaper/cache process and file operations, Kitty signaling, recorder management, Wi-Fi details | Primarily official `coreutils`, `findutils`, `gawk`, `grep`, `procps-ng`, `util-linux`, `iproute2`; standard Arch base packages | Low-level runtime requirements of helper scripts; normally supplied by a minimal Arch base install but document/check explicitly |
| `python3` + `gi.repository.Gio` | Recorder directory picker via XDG FileChooser portal | `python`, `python-gobject`, `xdg-desktop-portal`, chosen backend | Portal picker error is surfaced; manual path selection is not silently substituted |
| `lxqt-policykit-agent` | `sparrow-polkit-agent.service`; graphical Polkit dialogs when no user agent is already running | Official Extra `lxqt-policykit` ([package](https://archlinux.org/packages/extra/x86_64/lxqt-policykit/)) | Unit skips if package binary is absent or a recognized agent is running; existing agent remains authoritative |

Commands such as `nvidia-smi`, DDC, vibrance, brightness, Night Light, weather
and recording are guarded or feature-specific. The table distinguishes shell
executable requirements from compositor/API integrations. QML also talks
directly over Quickshell services to PipeWire, UPower, Bluetooth, networking,
MPRIS, notifications, PAM, system tray and Wayland; those are libraries or
session services, not separate shell commands.

### Arch package map and current source recommendation

Prefer official Arch Extra packages for the base; this avoids an installer
silently adding an AUR helper or third-party repository. On CachyOS, package
availability/version policy can differ, so preflight the target's own package
database. “Optional” means the desktop must remain useful when omitted.

| Purpose | Recommended package/source | Install tier / notes |
| --- | --- | --- |
| Niri | `niri` — Arch Extra ([package](https://archlinux.org/packages/extra/x86_64/niri/)) | Required, target compositor |
| Quickshell | `quickshell` — Arch Extra ([package](https://archlinux.org/packages/extra/x86_64/quickshell/)) | Required; require a release compatible with Sparrow's used APIs and Qt modules |
| Matugen | `matugen` — Arch Extra ([package](https://archlinux.org/packages/extra/x86_64/matugen/)) | Required for palette generator; prefer this over a `-bin` variant |
| awww | `awww` — Arch Extra ([package](https://archlinux.org/packages/extra/x86_64/awww/)) | Required default background |
| Pillow | `python-pillow` — Arch Extra | Required for `wallcolors.py` |
| Inter | `inter-font` — Arch Extra ([package](https://archlinux.org/packages/extra/any/inter-font/)) | Default UI font |
| Outfit Black | Bundled `Outfit-Black.ttf` + OFL notice | Used by lockscreen; don't fetch separately or omit its license |
| JetBrains Mono Nerd Font | `ttf-jetbrains-mono-nerd` — Arch Extra ([package](https://archlinux.org/packages/extra/any/ttf-jetbrains-mono-nerd/)) | Default Kitty/Fish/Starship typography |
| Bibata Modern Ice | Upstream Bibata project; currently AUR package `bibata-cursor-theme` per [upstream install docs](https://github.com/ful1e5/Bibata_Cursor) | Recommended default; AUR requires explicit consent; never overwrite user's chosen cursor |
| GTK base theme | `adw-gtk-theme` — Arch Extra ([package](https://archlinux.org/packages/extra/any/adw-gtk-theme/)) | Required only for generated Sparrow GTK theme source; GTK3 is also required for Thunar |
| Kitty | `kitty` — Arch Extra | Default terminal |
| Fish | `fish` — Arch Extra | Kitty shell default |
| Starship | `starship` — Arch Extra | Default Fish prompt |
| Thunar | `thunar` — Arch Extra ([package](https://archlinux.org/packages/extra/x86_64/thunar/)) | Default file manager |
| Thumbnails | `tumbler` — Arch Extra ([package](https://archlinux.org/packages/extra/x86_64/tumbler/)) | Recommended part of default Thunar integration |
| Portals | `xdg-desktop-portal` + a backend such as `xdg-desktop-portal-gtk` ([portal package](https://archlinux.org/packages/extra/x86_64/xdg-desktop-portal/)) | Required for portal chooser and recording folder chooser; choose compatible backend, don't force GTK globally |
| Polkit agent | Existing user agent, otherwise recommended `lxqt-policykit` (Arch Extra) | Desktop infrastructure; Sparrow unit is conditional and Niri-session-scoped; preserve other agents |
| video wallpapers | `mpvpaper` AUR | Optional video wallpaper enhancement |
| recording | `gpu-screen-recorder`, `slurp` | Optional GPU-dependent recorder; direct output capture and picker capabilities vary |
| screenshot | Rishot upstream, `grim`, `wl-clipboard` | Optional separate application; do not bundle or silently run external installer |
| Night Light / audio viz | `wlsunset`, `cava` — prefer official Extra where available | Optional features |
| hardware | `brightnessctl`, `ddcutil` — official Arch packages; compatible `nvibrant` source/package varies | Optional and device-specific; never force onto host |
| network, audio, battery | `networkmanager`, `bluez`, `bluez-utils`, `pipewire`, `wireplumber`, `upower`, `pipewire-pulse` as appropriate | Core surfaces rely on compatible user/system services; enabling can conflict with a host setup |
| media & portal modules | Quickshell runtime modules, Qt Multimedia QML module, GTK3/4; check imports against installed package | Required modules should be preflighted, not guessed by package names across releases |
| XWayland | `xwayland-satellite` (which depends on Xwayland) | Optional compatibility for X11-only apps, not needed for Wayland-native Sparrow |
| Hyprlock fallback | `hyprlock` — Arch Extra | Optional only if retaining the simple fallback; not needed for primary lock |
| icons | Tracked Sparrow icon subset and license notice; no need to install all Papirus theme | Sparrow's theme assets are tracked, while generated folder/doc artwork is runtime output |

Arch's package pages currently show `quickshell`, `niri`, `matugen`, `awww`,
`python-pillow`, `inter-font`, `ttf-jetbrains-mono-nerd`, `adw-gtk-theme`,
`kitty`, `fish`, `starship`, `thunar`, `tumbler`, `xdg-desktop-portal`, and
`gpu-screen-recorder` in official repositories. The Bibata source recommends
an AUR package. Rishot's upstream install script says its primary package is
`rishot-git`; the project's README currently documents its own standalone
installer rather than a package command. Verify AUR status at implementation
time. Never assume `matugen-bin` is the Arch default.

## Repository files to deploy

Repository source is not a template for machine-generated state. Preserve and
merge existing user config rather than copying whole directories over them.

| Tracked repository path(s) | Future destination | Ownership class | Deployment policy |
| --- | --- | --- | --- |
| `quickshell/sparrow/**` (including `shell.qml`, QML, `Singletons/`, `lib/`, `scripts/`, `idle/shell.qml`, `qmldir`, lockscreen assets, wallpaper default) | `~/.config/quickshell/sparrow` | Sparrow-owned source | One managed runtime tree; stable canonical path. Development may symlink to checkout; released install must not depend on checkout |
| `niri/config.kdl` | `~/.config/niri/config.kdl` | Sparrow template + user-owned active root | Merge includes into existing config; never overwrite a user's root config wholesale |
| `niri/sparrow/appearance.kdl`, `binds.kdl`, `input.kdl`, `window-rules.kdl` | `~/.config/niri/sparrow/` | Sparrow-owned static defaults | Back up conflicts; generated/user subfragments are separate |
| `quickshell/sparrow/systemd/sparrow-shell.service`, `sparrow-idle.service`, `sparrow-wallpaper.service`, `sparrow-polkit-agent.service` | `~/.config/systemd/user/` | Sparrow-owned unit templates | Copy files on install, not links into source checkout; enable the Polkit unit only if no existing agent/autostart owns that role |
| `quickshell/sparrow/systemd/xdg-desktop-portal-gtk.service.d/10-sparrow-theme.conf` | `$XDG_CONFIG_HOME/systemd/user/xdg-desktop-portal-gtk.service.d/` | Sparrow-owned integration override | Conflict/backup required; scoped GTK theme affects portal only |
| `xdg-desktop-portal/niri-portals.conf.fragment` | Merge into `$XDG_CONFIG_HOME/xdg-desktop-portal/niri-portals.conf` | Sparrow-owned one-key merge fragment, not a complete portal config | Add/merge only `org.freedesktop.impl.portal.FileChooser=gtk;`; preserve all other user backend routes |
| `kitty/kitty.conf` | `~/.config/kitty/kitty.conf` | Sparrow default with generated include | Merge/back up pre-existing Kitty config; runtime colors go beside it |
| `fish/config.fish` | `~/.config/fish/config.fish` | Sparrow recommendation + user shell config | Merge or install opt-in; Fish config is user-owned and should not be wholesale replaced |
| `starship/starship.toml` | `~/.config/starship.toml` | Sparrow default + user-customizable prompt | Backup/merge; prompt config may be user's own |
| `environment.d/90-cursor.conf` | `~/.config/environment.d/90-cursor.conf` | Recommended Sparrow environment defaults | Only offer if user accepts Bibata defaults; preserve existing cursor env |
| `gtk/Sparrow/**` | `$XDG_DATA_HOME/themes/Sparrow/` | Sparrow static theme scaffold | Install tracked CSS/theme metadata; generated colors are separate |
| `icons/Sparrow/**`, `icons/NOTICE.md`, `icons/PAPIRUS-LICENSE.txt` | `$XDG_DATA_HOME/icons/Sparrow/` and license records | Sparrow theme files plus third-party subset | Deploy exact subset with GPL notice; generated palette recolors selected icons |
| `applications/sparrow-files.desktop` | `$XDG_DATA_HOME/applications/sparrow-files.desktop` | Sparrow-owned desktop handler | Install optionally; MIME default change requires explicit user approval |
| `hyprlock/hyprlock.conf` | `~/.config/sparrow/hyprlock.conf` (fallback only) | Optional Sparrow baseline; active config user-owned | Offer only if fallback retained and destination absent; never replace personal Hyprlock config |
| `quickshell/sparrow/wallpapers/default.png` | remains inside Sparrow runtime tree | Sparrow-owned redistributable default asset | Install as read-only fallback; never copy over the user's wallpaper library |
| `docs/**`, `LICENSES/**`, root `LICENSE`, `THIRD_PARTY.md` | repo/docs | Project/legal metadata and component notices | Repository distribution; retain root and asset-adjacent notices with redistributed source/assets |

Do not deploy active `~/.config/niri/sparrow/{display-outputs,display-binds,
generated-colors,user-appearance,user-binds,user-input}.kdl`, current state,
portal choices, user-selected app defaults or user shell preferences from this
host. `~/.config/quickshell/sparrow` currently is a development symlink; the
three live service links also point to the checkout and are not a released
installation model.

## Runtime-generated and user-specific files

Current code uses `$XDG_STATE_HOME` (default `~/.local/state`),
`$XDG_CACHE_HOME` (default `~/.cache`), `$XDG_CONFIG_HOME` (default
`~/.config`) and `$XDG_DATA_HOME` (default `~/.local/share`). These must not be
seeded with development-host contents.

| Runtime file/group | Current location | Creator/use | Install policy |
| --- | --- | --- | --- |
| Flags/settings | `$XDG_STATE_HOME/sparrow-shell/flags.json` | Quickshell JsonAdapter | Runtime creates; preserve existing values |
| Onboarding | `$XDG_STATE_HOME/sparrow-shell/onboarding.json` | migration/Flags | Runtime creates; don't replay onboarding on existing state |
| migration backups | `$XDG_STATE_HOME/sparrow-shell/backups/` | `migrate-state.py` | User recovery material, never replace |
| wallpaper choice/map/shuffle | `$XDG_STATE_HOME/sparrow-shell/{wallpaper,wallpaper-map,wallpaper-bag,...}` | wallpaper scripts | Per-user/output state; never seed |
| video still and mpvpaper bookkeeping/logs | `$XDG_STATE_HOME/sparrow-shell/{wallpaper-still.png,mpvpaper-*.pid,mpvpaper-*.log}` | wallpaper scripts | Runtime/cache/process state |
| migration/config transaction journals/backup | `$XDG_STATE_HOME/sparrow-shell/niri-config-transactions/`, `backups/` | Niri transaction helper | Runtime recovery state, never copy |
| display/config overrides | `~/.config/niri/sparrow/{display-outputs,display-binds,user-appearance,user-binds,user-input}.kdl` | Display, Look, Keybinds, Input | User-owned outputs/preferences; preserve and validate |
| generated Matugen palette | `$XDG_CACHE_HOME/sparrow-shell/palette.json` | `wallcolors.py` | Generated, contains current wallpaper-derived palette/luminance |
| generated Niri colors | `~/.config/niri/sparrow/generated-colors.kdl` | Matugen + transaction helper | Generated; do not include a machine's current values as portable default |
| Kitty palette | `~/.config/kitty/sparrow-colors.conf` | `wallcolors.py` | Generated; optional include is quiet before first generation |
| GTK theme CSS | `$XDG_DATA_HOME/themes/Sparrow/gtk-3.0/gtk.css` | palette generator based on installed adw-gtk-theme | Generated; not a copy of current palette |
| Sparrow icon colors/cache | `$XDG_DATA_HOME/icons/Sparrow` generated SVGs / icon cache | palette generator | Static licensed icon subset + generated colors; cache refresh optional |
| weather location/cache | `$XDG_STATE_HOME/sparrow-shell/weather-loc.json` and cache roots | Weather singleton | User/derived location state; no install seed; external requests optional |
| event/notification history | `$XDG_STATE_HOME/sparrow-shell/events.json` and related state | Events/Notifs | Runtime state; empty on new install |
| Launcher usage | `$XDG_STATE_HOME/sparrow-shell/launcher-usage.json` | Launcher | Runtime-created ranking data |
| vibrance value | `$XDG_STATE_HOME/sparrow-shell/nvibrant-value` | Devices | Device-specific setting; don't restore across machines |
| wallpaper/recording thumbnails and video preview cache | `$XDG_CACHE_HOME/sparrow-shell/...`; preview downloads also use `/tmp` | helper scripts/Wallpaper/Recorder | Disposable; do not package or clear as install step |
| recordings/screenshots | Flags-configured recordings default under `~/Videos/Recordings`; screenshots per Niri screenshot path / Rishot | User output | Never overwrite or include |
| awww cache/socket | `$XDG_CACHE_HOME/awww`, `$XDG_RUNTIME_DIR` | awww | External daemon runtime/cache |
| Rishot settings/lock/source | `~/.local/share/rishot`, `~/.local/bin/rishot`; runtime lock in `$XDG_RUNTIME_DIR` or cache fallback | Independent Rishot install | Separate app-owned files |

Machine-specific values include output names/resolution/scale/position, display
number labels, keyboard and input device choices, hardware probes, audio
devices, personal wallpaper directory/map, generated palette, accounts, saved
flags, recordings, portal backend selection and existing service manager
configuration.

## System integration actions

| Action | Classification | Safe installer boundary |
| --- | --- | --- |
| Establish canonical Quickshell runtime root and stage shell code | Must | Refuse unrelated target; back up/copy policy explicit |
| Merge Sparrow Niri include graph into user's existing root config | Must for Niri integration | Show staged diff; back up; run `niri validate` before reload; never replace root wholesale |
| Install/validate Sparrow user units and run `systemctl --user daemon-reload` | Must for managed startup | Enable only after paths/session dependencies are staged; enable the Polkit unit only if no existing agent/autostart exists; no duplicate manual QS/agent launch |
| `graphical-session.target` / environment availability for Niri | Must | Check session manager integration; do not start shell from Kitty or duplicate compositor autostart |
| Install `xdg-desktop-portal` and choose compatible backend | Must for folder chooser/recording portal integration; screen casting is a separate optional portal capability | Merge the one-key FileChooser fragment; preserve existing routes; keep GTK theme environment scoped to GTK portal service |
| GTK portal per-service override | Recommended for Sparrow-themed chooser | Back up conflicts; no global GTK_THEME |
| Polkit agent | Use an existing user agent, or offer `lxqt-policykit` when none is found | Never remove/disable an existing agent; skip Sparrow unit if an agent/autostart already owns the role |
| `inode/directory` default to Sparrow Files | Optional | Must ask; current default is a user preference and may conflict with another file manager |
| GSettings icon/cursor/theme defaults | Recommended | Must ask/preserve non-default current values; don't globally force `GTK_THEME=Sparrow` |
| Cursor environment/Niri cursor settings | Recommended portable defaults | Preserve existing XCURSOR and cursor selection unless user opts in |
| Font and icon cache refresh | Recommended when deploying fonts/icons | Use installed package fonts or tracked assets; refresh caches without changing preferences |
| NetworkManager / Bluetooth services | Optional system services | Must ask before enabling; avoid conflict with a user's existing network stack or Bluetooth policy |
| PipeWire/WirePlumber, UPower, PAM | Required compatible platform services/features | Preflight status; avoid replacing service configs; lock uses Quickshell PAM integration and must be validated without writing custom system PAM policy blindly |
| Display manager / greeter | User decision, not in repository | Do not install/select a DM or replace login behavior implicitly |
| User wallpaper, existing palette/state, recording paths, monitor layout | Never automatic | Preserve; ask only if a future guided setting needs a choice |

## Clean Arch to Sparrow: dependency-ordered sequence

1. Read-only preflight: identify Arch/CachyOS, Niri version/session, user
   manager/graphical-session target, XDG roots, existing config/service files,
   package manager/AUR availability and selected default apps. Print a plan.
2. Decide baseline package additions. Request consent before any pacman/AUR
   writes; do not use a helper or third-party repo silently. Keep optional
   package list separate.
3. Stage timestamped backups and prepared files in an install transaction.
   Refuse collisions that cannot be safely merged.
4. Install/copy the Quickshell runtime to canonical
   `~/.config/quickshell/sparrow`; ensure all tracked scripts/assets/licenses
   are present before enabling units.
5. Deploy Sparrow static Niri fragments. Merge only include statements into
   existing `~/.config/niri/config.kdl`; keep generated colors/output/user
   files absent until runtime creates them. Validate staged config.
6. Install default-app configs and desktop entry only with explicit conflict
   policy. Preserve app config and MIME defaults; install packages only when
   chosen.
7. Install GTK theme/icon scaffold and chosen fonts/cursor. Scope theme to the
   portal and Thunar launch; preserve global app theming and GSettings.
8. Merge the portal fragment into the existing Niri portal config without
   replacing other routes. Install unit files and the GTK portal drop-in;
   validate units. Enable Sparrow's Polkit unit only if the user has no
   existing agent/autostart. Only after runtime/config validation, daemon-reload
   and enable units against the Niri graphical session. Do not start duplicate
   Quickshell or Polkit agents.
9. Initialize XDG runtime roots through Sparrow's idempotent migration. Do not
   create fabricated Flags, wallpaper maps, palettes or host display config.
10. At first Niri session, wallpaper service restores saved wallpaper or the
    bundled default and generates the first palette; only then does the shell
    service start. Generated Niri colors require the Niri include graph.
11. Verify service/process multiplicity, `niri validate`, generated output
    ownership, app handlers, portal chooser and first-run Getting Started.
    Reload Niri only after successful staged validation and user approval.
12. Report remaining optional backends and manual actions; provide rollback
    path. A clean graphical VM/login remains the release acceptance test.

## One default profile and optional capabilities

Do not create dozens of feature toggles. The proposed single Sparrow Default is
Niri + Quickshell + idle/wallpaper services, image wallpaper/Matugen,
Dynamic/Auto palette, Sparrow default image, Pill/Launcher/Settings, Niri
Look/Display/Input/Keybind surfaces, system tray/media/audio/network/device
surfaces, Qylock-derived Quickshell lock/PAM, Kitty/Fish/Starship, Thunar with
Tumbler and scoped Sparrow GTK, Inter, JetBrains Mono Nerd Font, Bibata Modern
Ice, Sparrow's licensed icon subset, and portal chooser integration. User may
decline or substitute default applications; those are not hard dependencies of
the shell binary.

Keep adaptive extras as a compact optional list: video wallpapers, Cava, Night
Light, internal brightness, DDC, NVIDIA vibrance, GPU Screen Recorder,
Rishot/grim, weather/search network endpoints, Hyprlock fallback and
XWayland compatibility. These controls already gate or report missing
capabilities; do not install a package simply because an optional UI is
present.

## Licensing and redistribution

| Material | Current evidence | Release obligation / action |
| --- | --- | --- |
| Sparrow combined program and Ricelin-derived shell lineage | Root `LICENSE` is GPL-3.0-only; `LICENSES/Ricelin-MIT.txt` retains the original MIT notice | Keep the MIT notice for inherited portions; the integrated GPL Qylock adaptation makes a uniform MIT project license inaccurate |
| Qylock Last of Us lockscreen | `Lockscreen/COPYING.GPL-3.0` + `THIRD_PARTY.md`; adapted theme is GPL-3.0 | Preserve license and attribution with source; distribute corresponding source/license for derivative adaptation |
| Outfit Black font | `Lockscreen/font/OFL.txt` | Preserve OFL and copyright next to font; font is bundled |
| Papirus-derived fixed icons | `icons/PAPIRUS-LICENSE.txt`, `icons/NOTICE.md`, GPL-3 | Preserve attribution/license; distribute modified/recolored source SVGs as applicable |
| Sparrow Default wallpaper | `wallpapers/README.md`; original SpaceEngine Pro screenshot created by author; permission is for bundling as Sparrow's default | Keep author copyright and scoped redistribution permission; do not call it upstream art or assign an invented license |
| Rishot | Separate upstream MIT project | Do not copy source/assets into Sparrow; link to upstream and retain separate license if installer offers it |
| Arch packages/fonts/theme assets | Installed package projects keep their own licenses | Install packages through package managers rather than repackaging package files |

`LICENSE`, `THIRD_PARTY.md`, and component notices now state the project license
and the separately licensed material. Recheck this map if files/assets are
added or if the lock/icon/font components change.

## Greeter and login boundary

Sparrow currently ships no display manager, greeter theme, or first-boot
session selector. A clean Arch machine without a DM normally reaches a TTY;
the user can launch `niri-session` from a getty. Arch Niri packages register a
desktop entry that compatible display managers can select and invoke
`niri-session`. Sparrow assumes an already-running Niri graphical session,
systemd user manager, `graphical-session.target`, Wayland/Niri environment,
and PAM access for its primary lock. It does not assume a particular DM. The
absence of a greeter is not a technical blocker to installing the rice, but a
“complete appliance-like install” must either document existing DM selection
or ask the user whether they want a login manager. No greeter design should be
invented by the installer.

## Ricelin lineage and visible identity

| Dimension | Assessment |
| --- | --- |
| Shared technical lineage | QML helpers, shell/module structure and parts of the shell interaction evolved from Ricelin; MIT provenance is tracked. Rishot is now separate upstream software. |
| Most recognizably inherited interaction | Single capsule/pill morphing across compact/rest and feature surfaces; one launcher/pill-driven workflow. |
| Adapted rather than copied as compositor model | Niri workspace/window/output event backend, settings transactions, layout, inputs and keybindings are Niri-native; old Hyprland special workspaces were removed. |
| Distinct Sparrow systems | Wallpaper-to-Matugen palette pipeline and generated Niri/Kitty/GTK/icon outputs; Niri Display/Look/Input/Keybind settings; Sparrow default wallpaper, file handler, Settings/onboarding. |
| Distinct/current lock | Qylock Last of Us layout, not Ricelin lock UI; PAM secure session lock and wallpaper/palette adaptation are Sparrow integration. |
| Theming residue | GTK theme is generated from installed adw-gtk-theme and scoped; app settings are deliberately limited, and Thunar running instances need reopen after color change. |

This is descriptive only; no redesign decision is implied.

## Basic desktop gap scan and installer acceptance

No clearly missing basic desktop facility was found in current source for the
declared scope: windows/workspaces/compositor are Niri; applications come
through desktop entries; audio/network/Bluetooth/device, battery, notifications,
tray, media and lock/idle are represented; portal-based directory selection,
wallpaper, screenshots and recording exist. The key caveat is availability:
service daemons and hardware vary and some are intentionally optional.

The login manager/greeter remains intentionally outside Sparrow. Installer v1
now implements the XDG runtime copy, Niri staged validation/include merge,
FileChooser-only portal merge, package consent tiers, conflict backups,
ownership manifest, service enablement policy, and restore command. Its exact
automatic package lists are in `installer/package-sets.json`; AUR tools remain
manual. Remaining acceptance is a disposable Arch/CachyOS graphical user or
VM run, especially session startup, PAM lock, portal chooser and multi-output
wallpaper restore. No live-session test is substituted for that check.
