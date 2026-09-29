# Sparrow current baseline

This document records the repository and the active development machine as
audited on 2026-09-27. It describes the implementation as it exists; it is not
an installer, a promise that every optional feature is available everywhere,
or a replacement for user configuration. Do not treat the live home directory
as a clean-install template. Installer v1 is implemented in this working
baseline. Its first real bare-metal CachyOS test exposed validation-before-
installation ordering. The ordering fix and isolated regression coverage are in
place; the second bare-metal run is still required before clean-install
acceptance is claimed.

## Current SSD source-of-truth capture (2026-09-28)

For the packaging convergence pass, the active external-SSD desktop is the
product source. The byte-level source/install policy is recorded in
[`installer/live-source-map.json`](../installer/live-source-map.json). This
supersedes older recommendations below to reconstruct Niri includes, merge a
portal fragment, or omit the current Look baseline. The installer deploys
tracked files directly to their XDG destinations, requests consent before
replacing conflicts, and backs them up. It does not edit the live reference
configuration during this capture.

Captured defaults include the current Niri root/fragments, Quickshell runtime,
systemd units, valid portal routing, scoped GTK portal theme, Kitty, Fish,
Starship, GTK icon setting, Sparrow desktop entry, and fallback Hyprlock file.
Canonical Look defaults are static in `appearance.kdl`; `user-appearance.kdl`
is generated only when a user saves a change and is not seeded on fresh install.
Monitor layout/bindings, generated colors/CSS/icons, selected wallpaper,
personal state, histories, caches, recordings, and separately installed
Rishot remain excluded. Niri root normalization is limited to making generated
colors optional, extracting the conditional Bibata cursor block, removing the
commented host-output example, promoting canonical Look defaults into the
static fragment, removing an unavailable Secret portal route, and restoring
Rishot's `PATH` invocation.

## 1. What Sparrow is

Sparrow is a Quickshell desktop shell integrated with Niri 26.04. The main
Quickshell instance owns the pill, its surfaces, notifications/OSDs and
wallpaper/theme coordination. Niri remains the compositor and source of truth
for outputs, workspaces, windows, layout and keybindings. A separate Quickshell
instance implements idle policy. State and generated theme/configuration files
live outside the source tree.

The frozen presentation defaults are Inter for Sparrow's interface (the current
user preference is Inter Black), JetBrains Mono Nerd Font for Kitty/Fish/
Starship, Bibata Modern Ice at size 24 for the cursor, and bundled Outfit Black
for the lockscreen. Decorative CJK glyphs are not part of Sparrow; no Zen Kaku
font is required.

The development checkout is `~/Projects/sparrow-shell`. The active runtime
entry point is `~/.config/quickshell/sparrow`, currently a symlink into that
checkout. The checkout is therefore not yet independently installed: moving or
removing it breaks the current development symlink and one active systemd unit
link (see [runtime ownership](#8-runtime-paths-and-ownership)).

## 2. Intended feature classification

These classifications describe intent, not a claim that every subsystem has
been tested on a clean installation.

| Class | Current components |
| --- | --- |
| **A — Final / intended** | Niri-native output/workspace/window integration; main pill and surfaces; desktop-entry Launcher; Wallpaper picker and image/video wallpaper backend; Matugen palette and shell theme; Niri Look/Display/Input/Keybind settings; PipeWire Mixer; notification/OSD/tray/media integration; Quickshell secure lock with PAM; power/idle policy; Kitty/Fish/Starship and Thunar/GTK defaults. |
| **B — Final but needs polish** | Live GTK3 recoloring (running Thunar windows require closing/reopening); multi-output wallpaper-specific lock backgrounds share one global palette; some monitor/application/package assumptions remain host-dependent; app-default configs need conservative install/merge behavior. |
| **C — Optional feature** | Night Light (`wlsunset`); spectrum (`cava`); internal brightness (`brightnessctl` plus a backlight device); DDC/CI (`ddcutil`); NVIDIA vibrance (`nvibrant` and NVIDIA device); recording (`gpu-screen-recorder`, with Niri selection helpers); screenshot integration through separately installed Rishot; optional online wallpaper search/download and optional zoxide/Fastfetch conveniences. |
| **D — Compatibility / migration only** | `scripts/migrate-state.py` reads selected legacy Ricelin state paths and copies data into Sparrow XDG state only when the destination is absent, retaining a backup. Ricelin provenance comments and included notices are attribution, not runtime dependencies. |
| **E — Development / testing only** | Python unit tests, Node test for monitor helpers, QML/config validation, transaction documentation, and the checked-in minimal QML test surface. These should remain available to contributors but are not session runtime requirements. |
| **F — Legacy / dead / not part of Sparrow** | Ricelin's special workspaces/Stash/Private/Minimized model; Game Mode; Ricelin updater; AppImage/package manager UI; the Pill file installer; abandoned Hyprlock visual redesign/avatar and its generated palette/link architecture. No replacement special-workspace or package-manager system is intended. |
| **G — Uncertain / user decision** | Whether to keep Hyprlock fallback indefinitely; whether Rishot should remain a separate user-installed application or become a documented optional dependency only; whether all current reference app defaults (Kitty/Thunar/Firefox) should ship enabled by default in a public rice. |

## 3. Runtime architecture and surfaces

`shell.qml` instantiates the compositor-facing pill on each Quickshell screen,
eagerly initializes the lock, device restoration, wallpaper restoration and
Night Light probe, and starts the separate idle unit after importing the
Wayland/Niri environment into the user service manager. Most major pill
surfaces are lazy-loaded. IPC routes to surfaces and one-shot actions; normal
Niri workspaces are consumed from Sparrow's Niri event-stream singleton, not
from a Hyprland compatibility layer.
For a genuinely fresh state, the Pill opens Getting Started once after its
startup-settling period. It remains reopenable from Settings.

The visible/runtime feature set is:

| Area | Current role / backend | Baseline status |
| --- | --- | --- |
| Rest pill / morph | Multi-output Quickshell layer-shell surfaces, Niri spacing/struts, flags-driven scale and opacity; opens surfaces through Sparrow IPC. | Intended core; visually tested, still a high-coupling QML area. |
| Launcher | Discovers ordinary `.desktop` entries and launches with `gtk-launch`; independent of AppImage/package management. | Intended core. |
| Settings | Navigation for Appearance, Look, Display, Input, Keybinds, Idle/Lock, and Getting Started. | Intended core; configuration writes use Niri transaction helper where applicable. |
| Appearance / palette | Sparrow palette mode/style, palette-derived colors and lock foreground selection; state persisted by `Flags`. | Intended core. |
| Look | Niri-managed gaps, struts, border/shadow/radius/animation preferences as supported by current Niri schema; writes a Sparrow user fragment and validates/reloads transactionally. | Intended core; Niri-version-sensitive. |
| Display | Queries Niri outputs and transactionally applies output arrangement/numbering. Generated output KDL is machine-specific. | Intended core; preserve host state. |
| Input | Niri input configuration bridge with detected device information and generated user overrides. | Intended core; device-specific values are user state. |
| Keybinds | Catalog-backed editing of Sparrow Niri bindings through generated user fragment and transaction helper. | Intended core; user customization must survive updates. |
| Workspaces | Normal Niri dynamic workspaces with stable IDs and output association. | Intended core; explicitly not the old Ricelin special-workspace model. |
| Wallpaper | awww images/still backdrop plus required mpvpaper animated playback per output, persisted per-output map, switching/search/picker and Matugen generation. | Core; video backend is installed/required, online search tools remain optional. |
| Mixer | PipeWire volume/source, hardware brightness, optional DDC and NVIDIA vibrance. | Intended core with adaptive optional controls. |
| Night Light | Quickshell-managed `wlsunset`, persisted off/on/scheduled mode. | Optional backend; runtime probe/restoration occurs at shell startup. |
| Recorder | GPU Screen Recorder with Niri output/window/region selection and directory portal helper. | Optional feature requiring capture backend and portal integration. |
| Notifications / DND | Quickshell notification service and Sparrow notification UI/state. | Intended core; depends on session D-Bus/notification service. |
| Tray | Quickshell SystemTray model and delegates, including menu interaction. | Intended core; null-model hardening was added in the previous tray task. |
| Media | Quickshell MPRIS discovery/controls and current-player presentation. | Intended core when MPRIS players exist. |
| Calendar / weather / battery / devices | Events/calendar state, optional weather lookup, UPower battery/peripheral data, NetworkManager Wi-Fi, BlueZ Bluetooth. | Mixed core/optional service integrations; availability depends on the relevant host daemon/device/network. |
| Power / idle / Keep Awake | Pill power actions, dedicated idle monitor, lock/screen-off/suspend policy, Niri output power and idle inhibitor. | Intended core; destructive power actions are never part of static validation. |
| Lock screen | Quickshell `WlSessionLock`, Quickshell PAM, Qylock Last of Us composition, per-output selected wallpaper, and Auto/Light/Dark foreground based on wallpaper metadata. | Intended primary lock. This pass added a null-screen guard; live lock was not invoked to test it. |
| Screenshot | Niri binding invokes separately installed `rishot` through `PATH`. | Optional external application; not vendored. |
| File drop | Pill's accepted local media files are routed to wallpaper selection/application. No generic software installer remains. | Wallpaper-only behavior; do not restore package install UI. |
| Sysmon / Cava | System monitor surface and optional Cava visualizer. | Optional and independent of removed Game Mode. |

## 4. Niri integration and configuration ownership

The repository `niri/config.kdl` is the portable starting point. It includes
static Sparrow fragments and optional generated/user fragments. The active
`~/.config/niri/config.kdl` is still the user's Niri entry point and must not
be replaced wholesale. Niri's live configuration currently has generated
colors, machine output arrangement, display-number bindings, and user Look,
Input and Keybind overrides in addition to tracked defaults.

Tracked portable defaults are under `niri/`: appearance, binds, input, window
rules and root include configuration. Generated/user files remain under the
live `~/.config/niri/sparrow/` and are not repository defaults:

- `generated-colors.kdl`: Matugen border/focus colors. It is included after
  static and user appearance so palette colors override only those color
  properties rather than replacing unrelated layout settings.
- `display-outputs.kdl`, `display-binds.kdl`: machine-specific output
  positions/modes/scales and display numbering.
- `user-appearance.kdl`, `user-input.kdl`, `user-binds.kdl`: settings changed
  through Sparrow UI.
- live backup files: user recovery material; do not delete or copy to a new
  installation.

`niri-config-transaction.py` stages managed fragments, validates the candidate
configuration, and supports confirm/rollback for risky display changes. Tests
exercise the transaction logic in temporary trees. Look/Input/Keybinds should
continue to use the managed-fragment API rather than editing the root config.
The host's four-output layout is not portable and must never be a default.

Niri normal dynamic workspaces, native window rules, overview layer behavior,
and the current user-facing binds are part of the intended Niri model. The
portable layout also centers a lone column without changing normal multi-column
scrolling. No active special-workspace binding or Hyprland IPC is intended.

## 5. Wallpaper and color pipeline

There is one Sparrow palette-generation implementation: `scripts/wallcolors.py`
is invoked by `wallpaper.sh` after applying a wallpaper or when startup finds
that the palette must be initialized. The flow is:

1. The picker, wallpaper keybind, startup restore, or wallpaper-only drop calls
   `Walls.qml` / `wallpaper.sh`.
2. Global selection and per-output selection are persisted below
   `$XDG_STATE_HOME/sparrow-shell` (default `~/.local/state/sparrow-shell`).
   Startup resolves each connected Niri output from its saved selection, then
   the saved global wallpaper, then the bundled `wallpapers/default.png`.
3. awww displays static images. GIF/video uses an extracted still for the
   persistent layer/palette path; mpvpaper renders animated media per output.
4. `wallcolors.py` reads the selected source/still and generates a palette
   using the selected Matugen style. Video is not continuously re-analyzed.
5. The generated JSON lives in `$XDG_CACHE_HOME/sparrow-shell/palette.json`.
   It contains Sparrow tone roles, source/style metadata, wallpaper luminance,
   recommended lock foreground, and terminal colors. QML `Dyn` watches that
   file and maps roles into pill, surfaces and lock UI.
6. Niri border colors are written through the Niri config transaction helper
   to `~/.config/niri/sparrow/generated-colors.kdl`.
7. Kitty's generated sibling `sparrow-colors.conf`, Sparrow GTK3/GTK4 CSS under
   `$XDG_DATA_HOME/themes/Sparrow`, and generated folder/text icon assets under
   `$XDG_DATA_HOME/icons/Sparrow` are written from the same palette. Kitty is
   signalled to reload when its colors change.
8. Fish and Starship do not independently analyze the wallpaper: the prompt
   uses Kitty's generated ANSI/extended color slots. Thunar is started with
   Sparrow's GTK theme integration; existing GTK3 processes do not reliably
   reload changed CSS and require closing/reopening all Thunar windows.
9. The lock uses each output's selected wallpaper but reads the same global
   Sparrow palette/luminance decision. Thus backgrounds may differ by output
   while the global shell/Niri/app theme and lock text decision are shared.

Generated app theme files are outputs, not inputs. The wallpaper pipeline is
the color source of truth. Fresh `Flags.qml` state defaults `paletteMode` to
`dynamic`; an explicit value already saved in `flags.json` remains
authoritative and is not migrated. The generated palette feeds Sparrow QML,
Niri, Kitty, GTK/icons, and lock luminance. `Theme.qml` also uses its
hand-maintained fallback when palette data is unavailable. Niri's
generated color fragment is a consumer, not a second palette generator.

On a fresh system with no wallpaper directory/state, the bundled default is
used and appears as a read-only `Sparrow Default` entry in the Wallpaper
picker; it does not need to exist in or get copied into the personal wallpaper
directory. Personal-library shuffle remains limited to that directory. If
palette generation fails, the old/usable fallback theme is retained and errors
are reported; the pipeline's Niri fragment uses the transaction path rather
than writing the active root config directly. Optional GTK/icon writes can fail
independently.

## 6. Lockscreen and failure model

The intended path is `Super+L` → tracked Niri lock binding → `sparrow-lock` →
Sparrow `screenlock` IPC → `WlSessionLock` secure state → Last of Us UI → PAM
success → session unlock. `ScreenLock.qml` uses Quickshell's PAM service and
does not unlock on an authentication failure. Power-off/suspend requests from
the lock UI are deferred until the compositor reports the lock secure.

The visual implementation is adapted from Darkkal44's Qylock Last of Us GPL-3.0
theme. The GPL text and attribution are under `Lockscreen/`; Outfit font and
SIL OFL notice are also included. Hyprlock is not the primary UI. The tracked
Hyprlock config and `~/.config/sparrow/hyprlock.conf` are fallback config only;
the wrapper launches it when Quickshell IPC is unavailable. This fallback is
meaningful if the shell process/IPC is unavailable before a lock is acquired,
but it is not equivalent to the compositor-secured Sparrow lock flow in every
failure timing. Keep it until a deliberate decision and failure-path test.

Niri's session-lock security model specifies that if a lock client dies after
locking, the compositor keeps the session locked (with a solid red background
in Niri's documented behavior) and can allow another lock client to take over;
the Wayland ext-session-lock protocol likewise forbids unlocking merely because
the lock client disappears. This is a secure but visibly poor recovery state,
not a reason to assume the desktop unlocked. See [Niri's security model](https://github.com/niri-wm/niri/blob/main/docs/wiki/Security-Model.md)
and the [ext-session-lock-v1 protocol](https://sources.debian.org/src/mir/2.20.2-2/wayland-protocols/ext-session-lock-v1.xml).

The earlier journal contained repeated
`ScreenLock.qml: Cannot read property 'name' of null` warnings at the
`lockSurface.screen.name` access. This pass added a narrow null guard; because
the lock must not be invoked as part of this audit and `qmllint` is not
installed, the runtime fix still needs a manual lock test in a safe session.

## 7. Systemd and session startup

Four tracked units are under `quickshell/sparrow/systemd/`:

- `sparrow-wallpaper.service`: starts awww and runs wallpaper restore in the
  graphical Niri session.
- `sparrow-shell.service`: starts the main `qs --no-duplicate --path` instance.
- `sparrow-idle.service`: starts the dedicated idle-policy QML instance.
- `sparrow-polkit-agent.service`: conditionally starts LXQt's agent in Niri
  when the package exists and no recognized agent is already running.

On this machine the first three are active/enabled and exactly two Quickshell
instances are present (main shell and idle shell). The Polkit unit is enabled
and active; `lxqt-policykit-agent` is owned by the `lxqt-policykit` package and
its listener registered successfully. Main and idle services use
the canonical runtime path. The live wallpaper unit symlink is an absolute
link to the development checkout, unlike the other two relative links. Its
unit contents are portable, but moving the checkout can break service
resolution. This is a known active portability defect; do not modify the live
unit link during a baseline audit.

## 8. Runtime paths and ownership

`XDG_*` below means the standard environment variable, falling back to the
shown home-relative path when unset.

| Path | Current contents / ownership | Install/upgrade rule |
| --- | --- | --- |
| Repository `quickshell/sparrow/` | Runtime source, QML, scripts, default wallpaper, units, tests. | Source-controlled; install as one tree or one symlink, never create divergent editable copies. |
| `~/.config/quickshell/sparrow` | Current symlink to checkout `quickshell/sparrow`. | Canonical runtime entry. Installer must refuse to overwrite unrelated existing content. |
| `~/.config/niri/config.kdl` | User's active include root; current machine has Sparrow includes. | Preserve and back up; never silently replace. |
| `~/.config/niri/sparrow/` | Static fragments currently mixed with generated/user fragments and dated backups. | Install static managed defaults; preserve machine output, user override and backup files. |
| `~/.config/systemd/user/sparrow-*.service` | Active links to repository units; wallpaper link is absolute. | Future installer should copy units into XDG config, then validate/daemon-reload/enable with explicit reporting. |
| `~/.config/sparrow/hyprlock.conf` | User active fallback config. | Preserve; only seed a default if absent and after explaining fallback role. |
| `~/.config/kitty/kitty.conf` | Current copy of repository Kitty defaults. | User-editable; back up and merge/seed only under explicit install policy. |
| `~/.config/kitty/sparrow-colors.conf` | Generated palette include. | Generated and replaceable; never track. |
| `~/.config/fish/config.fish`, `~/.config/starship.toml` | Current copied Sparrow Fish/Starship defaults, potentially user-edited. | Preserve/merge; not safe to overwrite. |
| `~/.config/gtk-3.0/settings.ini` | GTK theme/icon selection. | User preference; preserve and offer integration rather than blind replacement. |
| `~/.local/state/sparrow-shell/` | Flags, wallpaper and output selections, event/launcher state, recorder settings/history, generated monitor numbering/user settings as applicable, migration backups/journals. | Persistent user state; do not track, reset, or delete during install/upgrade. |
| `~/.cache/sparrow-shell/` | Palette, previews/thumbnails, weather location, temporary video stills, recording thumbnails/logs and older generated residue. | Cache/regenerable; safe cleanup requires identifying current readers and user consent. This host still has abandoned Hyprlock palette/link/avatar cache artifacts with no active repository consumer. |
| `~/.local/share/sparrow-shell/` | Absent on audited host. | Create only if a feature needs it. |
| `~/.local/share/themes/Sparrow/` | Generated GTK theme CSS. | Regenerable from palette and adw-gtk3 base. |
| `~/.local/share/icons/Sparrow/` | Tracked fixed Papirus-derived files plus generated palette-colored assets on this host. | Generated assets are regenerable; preserve any user additions. |
| `~/.local/share/applications/` | User/local desktop entries including Sparrow file integration and local app entries. | Preserve; install only Sparrow-owned entries with collision backups. |
| `~/Pictures/wallpapers/` | User wallpaper library; selected wallpaper and per-output map are state. | Personal data; never overwrite/delete or bundle wholesale. |
| `~/Videos/Recordings/`, screenshots | User outputs. | Preserve; never seed from repository. |

The safe Ricelin migration copies selected state/cache files only if a Sparrow
destination is missing and stores a source backup under Sparrow state. It is
compatibility code, not an ongoing dependency on Ricelin being installed. The
currently audited flags contain ordinary user preferences; generated colors
and selected wallpaper are not source-controlled defaults.

## 9. Dependencies by class

`docs/DEPENDENCIES.md` is the detailed package/tool inventory. The useful
classification is:

**Core/session:** Niri, Quickshell 0.3.1-compatible runtime/Qt modules, Python,
Bash, jq and standard base utilities; user systemd, D-Bus and graphical-session
environment; PipeWire/WirePlumber for Mixer/OSD; GTK `gtk-launch` for ordinary
desktop entries; NetworkManager/BlueZ/UPower for their respective live
integration surfaces. Their daemons/hardware are environmental requirements.

**Feature requirements:** awww and Matugen/Pillow for normal wallpaper/palette
operation; FFmpeg for still extraction/thumbnails/recording thumbnails;
GPU Screen Recorder and slurp for recording; compatible portal backend and
Python GObject for folder selection; a Polkit agent (Sparrow recommends
`lxqt-policykit` only if the user has no existing agent); GTK3 and adw-gtk3 source CSS for the
generated Thunar theme; Thunar, Kitty, Fish, Starship and JetBrains Mono Nerd
Font for the chosen default-app bundle; Bibata cursor assets for the selected
cursor. Actual user app choices can be changed.

**Optional:** wlsunset Night Light, cava, brightnessctl
on backlight hardware, ddcutil, nvibrant on supported NVIDIA hardware, optional
online wallpaper functions, zoxide/Fastfetch, imagemagick conveniences, and
Hyprlock fallback. Missing optional controls should remain absent/adaptive, not
fail the main shell.

The tested stock tuigreet profile is tracked. Installer package deployment is
separate from the explicit system-login opt-in: the root helper prepares tty2,
keeps backups, and only enables greetd for the next boot. It never starts or
restarts greetd during an active graphical install. See
`system_integrations.greetd` in `SOURCE-OF-TRUTH.json`.

**Separate app:** Rishot is installed on this host via a user-local launcher
and is not vendored. Niri's screenshot binding resolves `rishot` through
`PATH`, so the installer must ensure its separate installation provides that
command (and its Niri capture dependency, grim). Decide/install it separately
from Sparrow core.

**Development/test:** git, QML lint/Qt tools, Python unittest, Node for the
monitor helper test, and Niri validation. They need not all be runtime
dependencies.

The current dependency document's Hyprlock row was corrected in this audit:
Hyprlock is fallback-only. The package list still needs a later clean Arch
package-name/dependency verification before it is used by an installer.

## 10. Third-party code, assets and app defaults

- Qylock Last of Us QML adaptation: GPL-3.0 attribution/license in
  `quickshell/sparrow/Lockscreen/`.
- Outfit Black font: SIL OFL 1.1 notice under the lockscreen font directory.
- Selected Papirus-Dark SVG icons: GPL-3.0 plus notice/license in `icons/`.
- Sparrow generated theme builds on installed upstream adw-gtk3 CSS; this is a
  runtime input, not vendored upstream CSS. Generated stylesheet includes the
  upstream licensing attribution.
- `LICENSES/Ricelin-MIT.txt` is retained for the portions with Ricelin
  provenance; comments in normal Workspaces and palette adapter explain
  provenance/schema compatibility. `research/Ricelin` is a reference checkout,
  not an active runtime dependency and should not be installed as Sparrow.
- `wallpapers/default.png` is the Sparrow author's original SpaceEngine Pro
  screenshot. The author retains copyright and permits distribution bundled
  with Sparrow as its default wallpaper. No upstream SpaceEngine asset or
  additional SpaceEngine license requirement is claimed. See
  `quickshell/sparrow/wallpapers/README.md`.
- Kitty/Fish/Starship/Thunar/Firefox defaults are portable starting points, not
  proof those applications must be installed or their existing user config
  overwritten.

## 11. Legacy and explicitly excluded systems

Active source search found no Hyprland compositor command/config runtime,
special-workspace model, Game Mode, updater, AppImage manager, or file installer.
The remaining meaningful mentions are:

- migration paths/source names in `scripts/migrate-state.py` (keep to preserve
  existing users' settings);
- Ricelin provenance/schema comments in `Workspaces.qml`, `Dyn.qml`, and
  `WALLPAPER-PALETTE.md` (non-runtime attribution/context);
- `LICENSES/Ricelin-MIT.txt` (attribution/license);
- Hyprlock fallback executable/config and related dependency/policy docs
  (intentional fallback, not Hyprland compositor integration).

The current cache contains old generated `hyprlock-palette.conf`,
`lock-wallpaper`, and `avatar.png` entries from the abandoned Hyprlock visual
experiment. Current repository code does not consume those files. They are
user cache residue; they were not removed. Research checkout, backups, state,
and caches were excluded from active-source classification.

## 12. Known limitations and unresolved findings

- Existing Thunar GTK3 processes do not live-refresh Sparrow's regenerated
  colors; close all Thunar windows and reopen. This is known and intentionally
  not addressed here.
- Palette is global even when wallpaper selection differs per output; lock
  backgrounds are per-output but foreground recommendation is currently global.
- Missing optional service/device/executable means its surface/control is
  omitted or reports unavailable; package installation is not managed by
  Sparrow.
- The absolute live wallpaper-unit symlink prevents a fully checkout-independent
  installation today. Rishot is a separate PATH dependency.
- Live user Niri config contains host-specific output settings and user edits
  absent from repository defaults; the current machine is not a clean-install
  test.
- Current Quickshell journal includes repeated `lockSurface.screen.name` null
  warnings. The lock still logged PAM attempts, but this audit did not invoke
  it or prove recovery under output hotplug. Fix and test separately before
  calling the lock runtime warning-free.
- Fresh-start behavior for absent GTK/adw-gtk3 defaults, portal backend,
  package variations and unavailable Niri generated fragments still needs an
  isolated test.
- The live portal setup already routes FileChooser to GTK and scopes Sparrow's
  GTK theme to `xdg-desktop-portal-gtk.service`. The repository now carries a
  merge-only FileChooser fragment; a clean-install merge test remains required.
- `lxqt-policykit-agent` is active under the guarded Niri session unit and its
  listener registered. The only startup warning is a missing optional Oxygen
  fallback icon theme; privileged prompt behavior was not deliberately tested.
- Fresh `Flags.qml` state defaults `paletteMode` to `dynamic`; saved explicit
  choices are preserved. The bundled default is selectable without a personal
  wallpaper directory. Its provenance is documented, and wallpaper
  redistribution is no longer an unresolved release blocker.

## 13. Migration, permissions, and failure boundaries

The state migration is copy-if-destination-absent and backed up; it should not
be run as a destructive reset. Wallpaper/user paths may contain spaces or
Unicode and scripts generally pass them as argv/quoted positional parameters;
QML's process API is preferred over interpolating arbitrary paths into shell
commands. The wallpaper service controls awww and wallpaper scripts own their
mpvpaper processes; do not add a second daemon instance.

Niri config transactions stage/validate and retain a rollback path, especially
for display edits. Optional backends are probed before use. Power actions call
systemd and are destructive by design; never run them in automated validation.
PAM failures retain the session lock. A dead Quickshell lock client should not
unlock a conforming Niri session; recovery is a security/compositor behavior,
not tested by this audit.

## 14. Installer v1 boundary and remaining acceptance

Installer v1 is intended to retain these conservative boundaries:

1. detect Niri/XDG/session availability and show a non-mutating plan;
2. separate core and optional packages, ask before package/AUR operations, and
   verify actual Arch package names;
3. use one canonical runtime tree and never leave live units tied to checkout;
4. back up/merge user config and desktop files on conflict; never replace the
   Niri root, Kitty/Fish/Starship config, Hyprlock user config, portal choices,
   monitor arrangement, or user application defaults silently;
5. install portable static Niri fragments while leaving generated/user
   fragments and monitor state outside Git;
6. install units only after runtime paths exist, validate them, and avoid
   duplicate Quickshell/awww instances;
7. preserve state, caches, personal wallpapers, recordings and screenshots;
8. treat palettes, CSS, generated icons and palette Niri fragment as
   regenerable outputs, with a safe fallback if generation fails;
9. preserve migration backups and never delete old user state automatically;
10. validate staged config and QML before enabling services, without restarting
    Niri or logging out as an install side effect.

Installer v1 is implemented by `install.sh`, `uninstall.sh`, and
`installer/sparrow_installer.py`. It offers the tested greetd login setup as
an explicit system-level opt-in, does not automatically install AUR packages,
remove shared packages, seed machine state, or start/restart greetd in the
current session. The first bare-metal test failed because
systemd units were validated before pacman supplied `qs`, `awww`, and the
conditional Polkit executable. The current working fix installs approved
packages and checks required executables before staged Niri/unit validation;
tests use a closed package/command simulator and cannot call live Niri or
systemd. The fresh bare-metal retest is still required before release.

## 15. Proposed isolated fresh-default audit

Do not simulate a fresh install by clearing the active home directory. First
build a disposable test copy/worktree and run non-graphical checks with
temporary `HOME`, `XDG_CONFIG_HOME`, `XDG_STATE_HOME`, `XDG_CACHE_HOME`, and
`XDG_DATA_HOME` directories. Exercise state migration, wallpaper selection
resolution, palette generation, generated Niri fragments and unit paths only
inside those temporary roots, with Niri/Quickshell/systemd actions stubbed or
disabled. Add fixtures for no wallpaper folder, malformed flags, missing
optional tools, and spaces/Unicode in file paths.

For real UI behavior, use a separate disposable Niri session/user or VM with
its own session bus, compositor, output configuration and systemd user manager.
Do not point a test service at the active graphical session, use the current
user-state directories, start a second awww daemon, or attempt a lock/power
action. Capture logs, screenshots and `niri msg` state in that isolated
session. A plain temporary XDG tree alone cannot validate layer-shell,
exclusive zones, PAM or compositor IPC; those require the isolated graphical
session. Establish the exact test matrix before implementing an installer.

Suggested cases, in order:

1. empty state/config/data/cache and no wallpaper directory: migration,
   static Niri validation, default wallpaper selection, one palette creation;
2. existing user files: verify installer policy would back up/refuse conflicts
   rather than overwrite;
3. one and multiple outputs: per-output map, missing/disconnected output,
   reconnected output and global palette semantics;
4. image, GIF and video with/without mpvpaper; verify one daemon/process owner;
5. missing optional dependencies independently (wlsunset, cava, brightnessctl,
   ddcutil, nvibrant, recorder, Rishot) and confirm main shell stays healthy;
6. launch ordinary desktop entries, inspect tray/menu, MPRIS, audio/network,
   theme generation and lock; test PAM success/failure and compositor recovery
   only in the disposable session;
7. test Niri Look/Input/Keybind/Display transaction success, validation failure,
   confirmation timeout and rollback with disposable configuration;
8. inspect logs and generated-vs-user files, then destroy only the disposable
   test environment.

## 16. Audit status

The prior baseline document and dependency correction are now in HEAD
`79823be` (`document final Sparrow baseline`). No runtime configuration, user
state, wallpapers, packages, service state or desktop session was changed in
this pass. The only implementation edit is the `ScreenLock.qml` null-screen
guard; the fresh-install findings are in `docs/FRESH-INSTALL-AUDIT.md`. This
pass has not been committed.
