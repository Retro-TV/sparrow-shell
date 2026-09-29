# Sparrow installation inventory

Audit date: 2026-09-29. This document records the current repository and live
CachyOS/Niri reference implementation and its completed default installer
profile. It is an implementation inventory; it does not authorize overwriting
existing user files or changing machine-specific settings.
Current source is authoritative for executable use; installed Arch package
pages and upstream project documentation are linked where they establish
package/source facts.

## Product being reproduced

Sparrow is a Niri 26.04 desktop with a Quickshell 0.3.1 shell and a separate
Quickshell idle instance. Niri owns windows, outputs, workspaces and input;
Sparrow owns its multi-output pill/surfaces, selected wallpaper and generated
theme state. The coordinated default includes Sparrow's tested greetd/tuigreet
login, screenshot integration and core feature dependencies; it is not a
general-purpose desktop environment or package manager.

### Intended visible stack

| Area | Actual current component / backend | Classification |
| --- | --- | --- |
| Session | Niri 26.04, systemd user manager, graphical-session target | Required foundation |
| Main shell | Quickshell main `shell.qml`; pill, surfaces and IPC | Required foundation |
| Background | Sparrow wallpaper unit, awww image/still layer and required mpvpaper motion layer per output | Static and animated wallpapers are both first-class |
| Idle | Separate `idle/shell.qml` instance; Niri idle/output controls and session lock | Required to deliver configured idle policy |
| Pill / surfaces | Workspaces, Launcher, Wallpaper, Mixer, Recorder, Settings and modal/morphed surfaces | Core Sparrow UI |
| Niri settings | Look, Display, Input, Keybinds through validated managed fragments | Core, with machine/user values generated outside portable defaults |
| Personalization | Matugen-derived shell roles, lock foreground, Niri border colors, Kitty, Sparrow GTK/icon assets | Core dynamic theme; outputs generated |
| Lock | Quickshell `WlSessionLock` + Quickshell PAM + adapted Qylock Last of Us | Primary lock; Qt Multimedia used for themed motion/background behavior |
| Applications | Kitty/Fish/Starship terminal; Thunar with Sparrow GTK theme; Firefox binding | Intended defaults, replaceable by user |
| Desktop integration | Sparrow Files `.desktop` directory handler; GTK FileChooser and Niri ScreenCast portal routing; GTK portal theme scope | Add targeted routes only; preserve explicitly selected routes |
| Network/devices | NetworkManager Wi-Fi, BlueZ Bluetooth, PipeWire audio, UPower/battery, MPRIS | Core surfaces, but dependent on services/devices |
| Adaptive controls | Video, Cava, Night Light, brightness, DDC, NVIDIA vibrance, recording, image-format helper, Hyprlock fallback, screenshots | Tools install by default; UI remains adaptive to device/service support and Hyprlock remains optional |

The fresh-install default flags are Dynamic palette + Auto palette style/mode,
Auto lock text, Night Light off and the built-in Sparrow Default wallpaper.
Flags are per-user: installation must provide defaults through the schema, not
copy the development host's `flags.json`.

## Rishot deployment boundary

The portable Niri bind invokes `rishot` through `PATH`. The installer now
deploys the official Rishot source archive pinned by commit and SHA-256 in
`SOURCE-OF-TRUTH.json`, without running the upstream installer or building an
AUR package. Runtime files go to `$XDG_DATA_HOME/rishot`; the launcher is
managed at `$HOME/.local/bin/rishot`. Existing valid PATH installations are
preserved, reruns skip unchanged managed content, and user config/state is not
copied or owned. Uninstall restores/removes only unchanged Sparrow-managed
files. Its MIT notice is installed with the application. Rishot user settings
and screenshot outputs remain user-owned.

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
| `mpvpaper` | animated wallpaper playback | CachyOS repository package; on Arch, upstream's AUR package is a reviewed pre-install prerequisite | Required feature backend; installer installs from configured CachyOS repos or stops before deployment with an Arch prerequisite message |
| `ffmpeg`, `ffprobe` | video/GIF stills, wallpaper thumbnails, recording thumbnails and media dimensions | Official Extra `ffmpeg` | Installed by default; previews/stills use it when available |
| `nmcli` | Wi-Fi scan/connect/profile operations and hotspot UI | Official `networkmanager` provides CLI | Installed by default; service ownership/state is not changed, and availability follows host service/adapter |
| `bluetoothctl` | Bluetooth pairing/trust/connect command path | Official `bluez-utils`; daemon is `bluez` | Packages installed by default; service state and adapter availability remain host-specific |
| `wpctl` | Volume, mute, source and default sink controls | Official `wireplumber` supplies `wpctl`; install PipeWire + WirePlumber | Audio control needs a running PipeWire session; unavailable device/backend prevents use |
| `systemctl` | Sparrow power actions, idle service start, environment import, service lifecycle | Official `systemd` | Required for units/power/idle path; systemd user session is core |
| `wlsunset` | Quickshell-managed Night Light process | Official Extra package | Installed by default; the backend starts only when the user enables Night Light |
| `cava` | Quickshell audio visualizer process | Official Extra `cava` | Installed by default; visualizer starts only when needed |
| `brightnessctl` | Guarded Niri hardware-brightness binds and Mixer internal backlight | Official Extra `brightnessctl` | Installed by default; Mixer control still requires detected backlight hardware |
| `ddcutil`, `timeout` | Mixer DDC detection/control; timeout bounds writes | Official `ddcutil`; `coreutils` is already required | Installed by default; a slider appears only after VCP 10 is successfully read; EDID model identifies the display |
| `xwayland-satellite` | Niri-managed XWayland compatibility for legacy/X11 applications such as Steam | Official Arch Extra package; depends on `xorg-xwayland` | Installed in the complete default profile; modern Niri manages startup automatically, with no Sparrow service or command |
| `nvibrant` | NVIDIA vibrance control | Third-party/upstream package/source; identify compatible package only on NVIDIA targets | Optional; hidden unless command and NVIDIA modeset device exist |
| `gpu-screen-recorder` | Recorder capture/record; process polling/stop | Official Extra `gpu-screen-recorder` ([package](https://archlinux.org/packages/extra/x86_64/gpu-screen-recorder/)) | Installed by default; capture remains device/session-dependent |
| `slurp` | Recorder region and window-point selection helper | Official Extra `slurp` | Installed by default for Niri selection modes |
| `grim` | Rishot Niri capture dependency | Official Extra `grim` | Installed by default |
| `rishot` on `PATH` | Niri `Super+Shift+S` screenshot bind | Pinned upstream source archive, checksum verified by installer | Default installation; preserves valid existing Rishot and user config |
| `kitty` | Niri terminal bind; generated colors reload via `pkill -USR1` | Official Extra `kitty` ([manual/package](https://man.archlinux.org/man/kitty.1.en)) | Default app; change bind if user does not install/choose Kitty |
| `fish` | Kitty login shell; user's Fish configuration | Official Extra `fish` | Default app dependency; Kitty shell launch fails or falls back depending Kitty handling |
| `starship` | Fish prompt initialization | Official Extra `starship` | Required default Fish prompt |
| `greetd`, `greetd-tuigreet` | Sparrow's tested tty1 login flow using `niri-session` | Official Arch/CachyOS packages | Packages installed by default; on a clean machine with no competing display manager, installer prepares tty2 recovery and enables greetd for next boot. A competing manager remains a user-confirmed conflict. |
| `zoxide`, `fastfetch` | Optional Fish startup integration and `ff` abbreviation | Official Extra packages | User-invoked Fish conveniences; not Sparrow shell requirements |
| `thunar`, `env`, `gtk-launch` | Niri/default-files `.desktop` entry; launcher routes desktop entries via `gtk-launch` | `thunar` official Extra ([package](https://archlinux.org/packages/extra/x86_64/thunar/)); `gtk-launch` from GTK3/GLib stack; `env` base coreutils | Thunar is the configured default file manager; other desktop entries need their own installed apps |
| `pavucontrol` | Sparrow Launcher recognizes its desktop ID and starts this external advanced-volume UI with app-scoped `GTK_THEME=Sparrow` | Complete default package profile; GTK4/gtkmm4 supplied by its package | Installed by default; the native Sparrow Mixer remains the primary control surface |
| `tumbler` | Thunar image/media thumbnails; not directly launched by Sparrow but required for stated file-manager experience | Official Extra `tumbler` ([package](https://archlinux.org/packages/extra/x86_64/tumbler/)) | Installed by default; without it previews are missing |
| `gio` | Wallpaper deletion through Trash | GTK/GLib (`glib2`) runtime | Missing GUI trash integration makes that picker action fail |
| `xdg-open` | Open saved recordings/output directory | Official `xdg-utils` | Recording UI can open paths only if a handler exists |
| `wl-copy` | Launcher calculation result copy; Rishot clipboard path | Official `wl-clipboard` | Required default; copy/Rishot clipboard integration unavailable without it |
| `notify-send` | Recorder feedback and battery notification | Official `libnotify` | Installed by default; missing notices do not block the UI |
| `curl` | Weather, wallpaper search/download/preview, Rishot optional upload | Official Extra `curl` | Installed by default; weather/search still require network access |
| `magick` | Wallpaper-search image identification; Rishot optional | Official `imagemagick` (command `magick`) | Installed by default; used for optional image handling/stitching |
| `cp` | Pill copies dropped wallpaper images/videos into Sparrow's wallpaper library | `coreutils` | Required only for wallpaper file-drop import; picker and normal wallpaper selection remain separate |
| `firefox` | Niri default browser binding | Official Extra `firefox` | Installed as the canonical replaceable default browser |
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
| Bibata Modern Ice | Official pinned [v2.0.6 upstream archive](https://github.com/ful1e5/Bibata_Cursor/releases/download/v2.0.6/Bibata-Modern-Ice.tar.xz) | Installed per-user after SHA-256 verification when the user has no explicit different cursor selection; no AUR helper |
| GTK base theme | `adw-gtk-theme` — Arch Extra ([package](https://archlinux.org/packages/extra/any/adw-gtk-theme/)) | Required for generated Sparrow GTK theme source |
| Kitty | `kitty` — Arch Extra | Required canonical terminal default |
| Fish | `fish` — Arch Extra | Required Kitty shell default |
| Starship | `starship` — Arch Extra | Required Fish prompt |
| Thunar | `thunar` — Arch Extra ([package](https://archlinux.org/packages/extra/x86_64/thunar/)) | Required canonical file manager |
| Thumbnails | `tumbler` — Arch Extra ([package](https://archlinux.org/packages/extra/x86_64/tumbler/)) | Installed by default for the intended Thunar experience |
| Portals | `xdg-desktop-portal`, `xdg-desktop-portal-gtk`, and `xdg-desktop-portal-gnome` ([Arch package](https://archlinux.org/packages/extra/x86_64/xdg-desktop-portal-gnome/)) | Required by the tracked GTK FileChooser + Niri ScreenCast profile |
| Polkit agent | Existing user agent, otherwise `lxqt-policykit` (Arch Extra) | Added to required transaction only when no existing agent is detected; preserve other agents |
| video wallpapers | `mpvpaper` | Required runtime; CachyOS repository package, or Arch AUR package installed by the user before rerunning Installer |
| recording | `gpu-screen-recorder`, `slurp` | Installed by default; capture availability still depends on device/capabilities |
| screenshot | Pinned Rishot upstream source, `grim`, `wl-clipboard` | Installed by default; preserves valid external Rishot and user config |
| Night Light / audio viz | `wlsunset`, `cava` — prefer official Extra where available | Installed by default; user state remains off until enabled |
| hardware | `brightnessctl`, `ddcutil` — compatible `nvibrant` source/package varies | Utilities installed by default; controls remain device/driver adaptive |
| network, audio, battery | `networkmanager`, `bluez`, `bluez-utils`, `pipewire`, `wireplumber`, `upower`, `pipewire-pulse` as appropriate | Core surfaces rely on compatible user/system services; enabling can conflict with a host setup |
| media & portal modules | Quickshell runtime modules, Qt Multimedia QML module, GTK3/4; check imports against installed package | Required modules should be preflighted, not guessed by package names across releases |
| XWayland | `xwayland-satellite` (which depends on Xwayland) | Installed by default for legacy/X11 application compatibility |
| Hyprlock fallback | `hyprlock` — Arch Extra | Optional only if retaining the simple fallback; not needed for primary lock |
| icons | Tracked Sparrow icon subset and license notice; no need to install all Papirus theme | Sparrow's theme assets are tracked, while generated folder/doc artwork is runtime output |

Arch's package pages currently show `quickshell`, `niri`, `matugen`, `awww`,
`python-pillow`, `inter-font`, `ttf-jetbrains-mono-nerd`, `adw-gtk-theme`,
`kitty`, `fish`, `starship`, `thunar`, `tumbler`, `xdg-desktop-portal`, and
`gpu-screen-recorder` in official repositories. The Bibata source recommends
an AUR package. Rishot is fetched only from the immutable pinned commit and
verified against the tracked SHA-256; the mutable upstream installer is not
run. Never assume `matugen-bin` is the Arch default.

## Repository files to deploy

The live reference files are the source of truth for Sparrow-owned defaults.
The installer copies tracked files to known destinations; generated and
machine-specific state stays out of the repository. Existing conflicts require
consent and are backed up, rather than reconstructed by installer code.

| Tracked repository path(s) | Future destination | Ownership class | Deployment policy |
| --- | --- | --- | --- |
| `quickshell/sparrow/**` (including `shell.qml`, QML, `Singletons/`, `lib/`, `scripts/`, `idle/shell.qml`, `qmldir`, lockscreen assets, wallpaper default) | `~/.config/quickshell/sparrow` | Sparrow-owned source | Exact managed tree copy to canonical runtime path; never a checkout symlink |
| `niri/config.kdl` and tracked `niri/sparrow/*.kdl` | `~/.config/niri/` | Captured Sparrow root and working fragment defaults | Deploy repository files directly; an existing conflicting root/file requires explicit consent and a recoverable backup |
| `quickshell/sparrow/systemd/sparrow-shell.service`, `sparrow-idle.service`, `sparrow-wallpaper.service`, `sparrow-polkit-agent.service` | `~/.config/systemd/user/` | Sparrow-owned unit templates | Copy files on install, not links into source checkout; enable the Polkit unit only if no existing agent/autostart owns that role |
| `quickshell/sparrow/systemd/xdg-desktop-portal-gtk.service.d/10-sparrow-theme.conf` | `$XDG_CONFIG_HOME/systemd/user/xdg-desktop-portal-gtk.service.d/` | Sparrow-owned integration override | Conflict/backup required; scoped GTK theme affects portal only |
| `xdg-desktop-portal/niri-portals.conf` | `$XDG_CONFIG_HOME/xdg-desktop-portal/niri-portals.conf` | Captured working portal profile | Copy exact file with the recommended profile; existing destination requires consent and backup; declining profile leaves portal routing untouched |
| `kitty/kitty.conf` | `~/.config/kitty/kitty.conf` | Captured Sparrow default with generated palette include | Copy exact tracked file; ask and back up if a different file already exists |
| `fish/config.fish` | `~/.config/fish/config.fish` | Captured Sparrow shell setup | Copy exact tracked file; ask and back up if a different file already exists |
| `starship/starship.toml` | `~/.config/starship.toml` | Captured Sparrow prompt | Copy exact tracked file; ask and back up if a different file already exists |
| `environment.d/90-cursor.conf` | `~/.config/environment.d/90-cursor.conf` | Conditional Sparrow environment default | Install after pinned Bibata is present and only when the user has no explicit different cursor choice |
| `gtk/Sparrow/**` | `$XDG_DATA_HOME/themes/Sparrow/` | Sparrow static theme scaffold | Install tracked CSS/theme metadata; generated colors are separate |
| `icons/Sparrow/**`, `icons/NOTICE.md`, `icons/PAPIRUS-LICENSE.txt` | `$XDG_DATA_HOME/icons/Sparrow/` and license records | Sparrow theme files plus third-party subset | Deploy exact subset with GPL notice; generated palette recolors selected icons |
| `applications/sparrow-files.desktop` | `$XDG_DATA_HOME/applications/sparrow-files.desktop` | Sparrow-owned desktop handler | Install optionally; MIME default change requires explicit user approval |
| `hyprlock/hyprlock.conf` | `~/.config/sparrow/hyprlock.conf` (fallback only) | Optional Sparrow baseline; active config user-owned | Offer only if fallback retained and destination absent; never replace personal Hyprlock config |
| `quickshell/sparrow/wallpapers/default.png` | remains inside Sparrow runtime tree | Sparrow-owned redistributable default asset | Install as read-only fallback; never copy over the user's wallpaper library |
| `docs/**`, `LICENSES/**`, root `LICENSE`, `THIRD_PARTY.md` | repo/docs | Project/legal metadata and component notices | Repository distribution; retain root and asset-adjacent notices with redistributed source/assets |

Do not copy SSD values for `~/.config/niri/sparrow/{display-outputs,display-binds,
generated-colors,user-binds,user-input}.kdl`; seed the tracked `user-input.kdl`
default only on a fresh home. Do not copy current state, selected wallpaper,
user-selected app defaults or shell preferences from this host. The complete
portal profile is an intentional captured default.
`~/.config/quickshell/sparrow` is a development symlink on this SSD; the
installer deploys a real managed copy there. Live service symlinks on this SSD
are not copied; tracked unit files target the canonical runtime location.

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
| display/config overrides | `~/.config/niri/sparrow/{display-outputs,display-binds,user-binds,user-input}.kdl` | Display, Keybinds, Input | Machine/user preferences; preserve and validate |
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
| Rishot settings/source/lock | `$XDG_DATA_HOME/rishot`, `$HOME/.local/bin/rishot`; runtime lock in `$XDG_RUNTIME_DIR` or cache fallback | Pinned upstream integration; user config/state is unowned | Uninstall restores/removes only unchanged Sparrow-managed app files |

Machine-specific values include output names/resolution/scale/position, display
number labels, keyboard and input device choices, hardware probes, audio
devices, personal wallpaper directory/map, generated palette, accounts, saved
flags, recordings, portal backend selection and existing service manager
configuration.

## System integration actions

| Action | Classification | Safe installer boundary |
| --- | --- | --- |
| Establish canonical Quickshell runtime root and stage shell code | Must | Refuse unrelated target; back up/copy policy explicit |
| Deploy captured Niri root and Sparrow fragments | Must for Niri integration | Stage and validate repository files; ask before replacing an existing root and back it up |
| Install/validate Sparrow user units and run `systemctl --user daemon-reload` | Must for managed startup | Enable only after paths/session dependencies are staged; enable the Polkit unit only if no existing agent/autostart exists; no duplicate manual QS/agent launch |
| `graphical-session.target` / environment availability for Niri | Must | Check session manager integration; do not start shell from Kitty or duplicate compositor autostart |
| Install portal backends/config | Required captured chooser and Niri screen-sharing path | Install required backend packages and copy the tracked portal config with conflict consent/backup; keep GTK_THEME scoped to GTK portal service |
| GTK portal per-service override | Recommended for Sparrow-themed chooser | Back up conflicts; no global GTK_THEME |
| Polkit agent | Use an existing user agent, or offer `lxqt-policykit` when none is found | Never remove/disable an existing agent; skip Sparrow unit if an agent/autostart already owns the role |
| `inode/directory` default to Sparrow Files | Optional | Must ask; current default is a user preference and may conflict with another file manager |
| GSettings icon-theme default | Recommended Sparrow icon choice | Set `Sparrow` only when no user value exists; preserve explicit choices and restore only an unchanged installer-owned value. Does not change global GTK colors or set `GTK_THEME` |
| Cursor archive/environment/Niri cursor settings | Required canonical cursor for a fresh account | Offer the pinned upstream archive, verify SHA-256, install per-user, and select size 24 in Niri/environment/GSettings when no explicit different user choice exists |
| Font and icon cache refresh | Recommended when deploying fonts/icons | Use installed package fonts or tracked assets; refresh caches without changing preferences |
| NetworkManager / Bluetooth services | Optional system services | Must ask before enabling; avoid conflict with a user's existing network stack or Bluetooth policy |
| PipeWire/WirePlumber, UPower, PAM | Required compatible platform services/features | Preflight status; avoid replacing service configs; lock uses Quickshell PAM integration and must be validated without writing custom system PAM policy blindly |
| Display manager / greeter | User decision, not in repository | Do not install/select a DM or replace login behavior implicitly |
| User wallpaper, existing palette/state, recording paths, monitor layout | Never automatic | Preserve; ask only if a future guided setting needs a choice |

## Clean Arch to Sparrow: dependency-ordered sequence

1. Read-only preflight: identify Arch/CachyOS, Niri version/session, user
   manager/graphical-session target, XDG roots, existing config/service files,
   package manager/AUR availability and selected default apps. Print a plan.
2. Build a human-readable package/file plan and classify required, default,
   optional, and manual dependencies. Request explicit pacman consent; never
   bootstrap an AUR helper.
3. Install approved required/default packages, then verify required commands
   and Python modules. Packages intentionally remain installed if a later
   config step fails.
4. Stage and validate the Niri include graph and only the unit files whose
   executables are now installed. A clean host must not be unit-validated
   against binaries the transaction has not installed yet.
5. Stage timestamped backups and prepared files in an install transaction.
   Refuse collisions that cannot be safely merged.
6. Install/copy the Quickshell runtime to canonical
   `~/.config/quickshell/sparrow`; ensure all tracked scripts/assets/licenses
   are present before enabling units.
7. Deploy the repository's captured Niri root and Sparrow fragments. Ask
   before replacing a conflicting root, create a restorable backup, and
   validate the staged repository graph before changing live files. Keep
   machine output, generated colors, and user input/bind fragments outside the
   portable defaults.
8. Install default-app configs and desktop entry only with explicit conflict
   policy. Preserve app config and MIME defaults; install packages only when
   chosen.
9. Install GTK theme/icon scaffold and required fonts. Scope theme to the
   portal and Thunar launch; preserve global app theming. Offer the pinned
   Bibata archive when needed; a fresh account does not silently fall back to
   another cursor.
10. Copy the tracked portal file with conflict consent and backup. Install validated
    units and the GTK portal drop-in. Include Sparrow's Polkit unit only if the
   accepted agent package is installed and no existing agent/autostart owns it.
   Only after successful validation, daemon-reload and enable units against
   the Niri graphical session. Do not start duplicate Quickshell or Polkit
   agents.
11. Initialize XDG runtime roots through Sparrow's idempotent migration. Do not
   create fabricated Flags, wallpaper maps, palettes or host display config.
12. At first Niri session, wallpaper service restores saved wallpaper or the
    bundled default and generates the first palette; only then does the shell
    service start. Generated Niri colors require the Niri include graph.
13. Verify service/process multiplicity, `niri validate`, generated output
    ownership, app handlers, portal chooser and first-run Getting Started.
    Reload Niri only after successful staged validation and user approval.
14. Report remaining optional backends and manual actions; provide rollback
    path. A clean graphical VM/login remains the release acceptance test.

## One default profile and optional capabilities

Do not create dozens of feature toggles. The single Sparrow default install is
Niri + Quickshell + idle/wallpaper services, image wallpaper/Matugen,
Dynamic/Auto palette, Sparrow default image, Pill/Launcher/Settings, Niri
Look/Display/Input/Keybind surfaces, system tray/media/audio/network/device
surfaces, Qylock-derived Quickshell lock/PAM, Kitty/Fish/Starship, Thunar with
Tumbler and scoped Sparrow GTK, Inter, JetBrains Mono Nerd Font, Bibata Modern
Ice v2.0.6, Sparrow's licensed icon subset, XWayland compatibility through
`xwayland-satellite`, curl/wl-clipboard/FFmpeg support tools, and GTK
FileChooser/Niri ScreenCast portal integration.
Rishot is installed from the pinned upstream source by default. An existing
explicit cursor choice is preserved. Optional app extras may be declined without
removing the required terminal, file-manager, and GTK defaults.

Keep adaptive extras as a compact optional list: Hyprlock fallback. Hardware-
specific controls still gate on detected capabilities; their default-installed
utilities do not imply that a device-specific control is available.

## Licensing and redistribution

| Material | Current evidence | Release obligation / action |
| --- | --- | --- |
| Sparrow combined program and Ricelin-derived shell lineage | Root `LICENSE` is GPL-3.0-only; `LICENSES/Ricelin-MIT.txt` retains the original MIT notice | Keep the MIT notice for inherited portions; the integrated GPL Qylock adaptation makes a uniform MIT project license inaccurate |
| Qylock Last of Us lockscreen | `Lockscreen/COPYING.GPL-3.0` + `THIRD_PARTY.md`; adapted theme is GPL-3.0 | Preserve license and attribution with source; distribute corresponding source/license for derivative adaptation |
| Outfit Black font | `Lockscreen/font/OFL.txt` | Preserve OFL and copyright next to font; font is bundled |
| Papirus-derived fixed icons | `icons/PAPIRUS-LICENSE.txt`, `icons/NOTICE.md`, GPL-3 | Preserve attribution/license; distribute modified/recolored source SVGs as applicable |
| Sparrow Default wallpaper | `wallpapers/README.md`; original SpaceEngine Pro screenshot created by author; permission is for bundling as Sparrow's default | Keep author copyright and scoped redistribution permission; do not call it upstream art or assign an invented license |
| Rishot | Separate upstream MIT project | Installer checksum-verifies immutable upstream commit and installs its license; does not run upstream installer or alter user settings |
| Arch packages/fonts/theme assets | Installed package projects keep their own licenses | Install packages through package managers rather than repackaging package files |

`LICENSE`, `THIRD_PARTY.md`, and component notices now state the project license
and the separately licensed material. Recheck this map if files/assets are
added or if the lock/icon/font components change.

## Greeter and login boundary

Sparrow tracks the tested stock tuigreet configuration. On a compatible fresh
machine without a competing display manager, installation prepares tty2
recovery, backs up system configs, and enables greetd for the next boot without
starting/restarting it under the current session. A competing display manager
or conflicting system config requires explicit consent. The next boot uses
tty1 tuigreet and launches `niri-session`; Sparrow's Quickshell session lock
is unchanged. Uninstall restores unchanged Sparrow-owned files and prior
enablement while preserving user edits. The exact contract is in
`SOURCE-OF-TRUTH.json` under `system_integrations.greetd`.

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
now implements the XDG runtime copy, Niri staged validation and direct tracked
file deployment, captured portal config copy, package consent tiers, conflict backups,
ownership manifest, service enablement policy, and restore command. Its exact
automatic package lists are in `installer/package-sets.json`; AUR tools remain
manual. Remaining acceptance is a disposable Arch/CachyOS graphical user or
VM run, especially session startup, PAM lock, portal chooser and multi-output
wallpaper restore. No live-session test is substituted for that check.
