# Sparrow portability and installation architecture

This is an architecture note, not an installer. No live configuration is
managed by this document, and the files under a user's home directory are not
copied into the repository.

## Current runtime and ownership

| Live item | Current role | Ownership for a portable install |
| --- | --- | --- |
| `~/.config/quickshell/sparrow` | Canonical runtime path; currently a symlink to the development checkout's `quickshell/sparrow` tree | Keep this single canonical path. In development, symlink it to the clone. An installer may make the same symlink or install a managed copy, but must not create two editable trees. |
| `~/.config/niri/config.kdl` | Active include root and user entry point | Repository supplies `niri/config.kdl` as a default. Installer must preserve an existing file and merge/back up explicitly; it must never replace it silently. |
| `~/.config/niri/sparrow/appearance.kdl`, `window-rules.kdl`, `binds.kdl`, `input.kdl` | Static settings; binds/input already have repository counterparts | Portable defaults now live under `niri/sparrow/`. |
| `generated-colors.kdl` | Wallpaper/Matugen-produced Niri border colors | Generated theme output; never track. The default root includes it optionally after static appearance, so generated colors win. |
| `display-outputs.kdl`, `display-binds.kdl` | Sparrow Display's detected monitor arrangement and number bindings | Machine-specific generated configuration; never track or copy from this host. |
| `user-appearance.kdl`, `user-input.kdl`, `user-binds.kdl` | Look, Input, and Keybinds user changes | Generated user configuration; never track. Niri defaults tolerate their absence. |
| `~/.config/systemd/user/sparrow-{shell,idle,wallpaper}.service` | User services; source unit files are tracked in `quickshell/sparrow/systemd/` | Future installer should copy units to the canonical systemd user unit directory, then daemon-reload and enable them. Copying avoids a service continuing to depend on the checkout's location. |
| `~/.config/sparrow/hyprlock.conf` | Simple screenshot-based fallback used only if Sparrow's Quickshell lock IPC is unavailable | An installer should preserve an existing user config and copy the portable fallback only when absent. This host's former Layout 9 config is backed up outside Git. |
| `~/.local/bin/rishot` and `~/.local/share/rishot` | Separate upstream Rishot install, not Sparrow source | Install as a separate dependency. Sparrow should call `rishot` from `PATH`; do not vendor it. |
| `~/.local/state/sparrow-shell/` | User preferences, selected wallpaper/output map, transaction journals, migrated flags/events and migration backups | Persistent machine/user state; never track. |
| `~/.cache/sparrow-shell/` | Palette, thumbnails, weather location, recording thumbnails and transient outputs | Regenerable cache; never track. Startup migration now creates its root for clean first run. |
| `~/Pictures/wallpapers/` | User-owned images and videos | Personal assets; not bundled. A missing directory is treated as an empty library. |
| `~/Videos/Recordings/` | User recording destination | Personal output; not bundled. Recording selection/default path creates or handles it when used. |
| `~/.config/environment.d/90-cursor.conf` | XCursor defaults for user-manager services and toolkit clients | Tracked as `environment.d/90-cursor.conf`; install only when absent or after preserving/confirming existing cursor preferences. |
| `~/.local/share/icons/Bibata-Modern-Ice` | Unowned local copy of the current Bibata Modern Ice theme (metadata identifies v2.0.6) | External asset, not vendored. The recommended Arch source is `bibata-cursor-theme-bin` from AUR; the live Niri file selects the theme at size 24. |

The live wallpaper unit is the exception among the current systemd links: its
home-directory symlink is absolute and resolves into the current checkout,
while the other two resolve relatively through the canonical Quickshell link.
The tracked unit contents use `%h/.config/quickshell/sparrow` and contain no
checkout path. This is an installation-link defect, not a reason to restart or
replace the active unit during this pass.

## Niri include and precedence model

`niri/config.kdl` is a portable Sparrow entry point. It includes static
appearance, window rules, binds, and the input bridge. Generated palette and
display files plus user overrides are optional and remain outside Git. The
appearance fragment includes `user-appearance.kdl` before the root includes
`generated-colors.kdl`; this matches the live arrangement and lets the
wallpaper-generated active/inactive border colors override static defaults
without overwriting gaps, struts, or border width. Niri includes are positional
and merged settings override earlier settings. Missing optional includes are
non-fatal but Niri logs a warning on each reload until the generated file is
created.

Static defaults represent the current working Niri behavior: transparent
workspace background for Overview, gaps/struts, width/height presets, border
and shadow defaults, stationary awww/mpvpaper wallpaper layer rules, Overview
workspace-shadow disablement, Firefox PiP floating, the WezTerm width
workaround, normal dynamic-workspace keybinds, and the user input bridge. No
output names, resolutions, scales, focus-at-startup choices, hardware input
settings, generated Matugen colors, or per-user Look/Input/Keybind edits are
included.

The root also preserves the current cursor name/size, hotkey overlay startup
choice, no-CSD preference, screenshot path, and Niri's default animation feel.
App binds currently name Kitty, Thunar, and Firefox; those remain configurable
user application choices and must be installed or changed by the user.

Cursor defaults have two runtime paths because Sparrow itself is a
systemd-launched Quickshell service: Niri's native `cursor` block selects the
compositor cursor and sets `XCURSOR_THEME`/`XCURSOR_SIZE` for Niri-spawned
clients, while `environment.d/90-cursor.conf` supplies those same values to
user-manager services. GTK reads its cursor through GtkSettings/GSettings; the
current GSettings values match Bibata Modern Ice at 24. This is independent of
the `GTK_THEME=Sparrow` setting scoped to Thunar/the GTK portal for widget
colors. A future installer should preserve non-default existing GSettings,
environment, and Niri cursor choices rather than force these recommended
fresh-install defaults over them. The GTK file chooser follows the same GTK
cursor preference; Qt/Wayland clients use the standard XCursor environment.
The portable default is Bibata Modern Ice at 24. Sparrow's UI uses Inter (this
user's saved preference is Inter Black); Kitty uses JetBrains Mono Nerd Font.
The Quickshell lockscreen uses its bundled Outfit Black font. No separate
decorative-glyph font or CJK glyph setting is part of the runtime.

## Quickshell and systemd installation model

Use `~/.config/quickshell/sparrow` as the stable runtime entry point. For a
development clone, symlink that path to the repository's
`quickshell/sparrow` directory. Quickshell is already running from this
canonical path in the current session, so edits to the symlink target remain
live-development friendly. The cloned repository may live anywhere; shell
scripts are resolved relative to the Quickshell shell root or canonical XDG
paths, not the checkout.

The three tracked user units launch through the canonical runtime root and
their `ExecStartPre` migration is idempotent. A future installer should copy
the unit files (not leave absolute checkout symlinks), ensure the Quickshell
runtime path exists first, run `systemctl --user daemon-reload`, then enable
the units for `graphical-session.target`. It must not manually start a second
Quickshell process while the service is active. The installed Niri session
must expose `XDG_CURRENT_DESKTOP=niri` and `graphical-session.target` as in the
tested current session.

## Wallpaper and lock defaults

`quickshell/sparrow/wallpapers/default.png` is a source-controlled, read-only
first-run fallback and a selectable `Sparrow Default` entry in the Wallpaper
picker. On startup `wallpaper.sh init` chooses each output's saved selection,
then the saved global selection, then this bundled file. It records the choice
in user state and runs the existing color pipeline once if the palette is
absent or the selected image changed. It does not copy the default into the
user's wallpaper folder or overwrite an existing selection. Personal-library
shuffle remains limited to the configured personal wallpaper directory.

The primary lockscreen is Sparrow's Quickshell `WlSessionLock` with PAM
authentication, using the adapted Qylock Last of Us composition. It obtains the
selected wallpaper for each output directly from Sparrow's existing wallpaper
state, so image and muted looping video wallpapers need no separate
lock-wallpaper symlink. Its Auto/Light/Dark foreground choice uses luminance
metadata already written by Sparrow's wallpaper palette pipeline; no
Hyprlock-specific generated palette is needed.

The shell lock has no account-avatar subsystem; its appearance follows the
upstream Qylock theme without adding a Sparrow profile-image requirement.

`sparrow-lock` requests the Quickshell lock through Sparrow IPC first. Only if
that IPC path is unavailable does it launch Hyprlock using the user's existing
`~/.config/sparrow/hyprlock.conf`. The repository's tracked Hyprlock file is a
plain screenshot-based fallback; it is not the Sparrow visual lock design.
The wrapper does not prepare avatars, wallpaper links, or generated color
includes for Hyprlock. The Quickshell lock reads Sparrow's selected wallpaper
and palette directly.

Rishot remains upstream software. On Arch it is available as an AUR package
(`rishot-git`) and also documents a standalone installer; prefer the package
or a reviewed manual installation rather than vendoring the app. Sparrow's
Niri shortcut invokes the `~/.local/bin/rishot` user-local install through a
home-relative shell command, and `~/.local/bin` is present in the current Niri
PATH. Rishot's required Arch dependencies are `quickshell`, Qt 6 declarative,
SVG, 5compat and Wayland components, and `wl-clipboard`; on Niri, `grim` is the
capture tool. Its optional conveniences include ImageMagick, cliphist, curl,
kdialog and libnotify.

## Fresh-install behavior

- With no state tree, the unit pre-start migration creates Sparrow's state
  root and migration backup location without overwriting an existing state
  file. It now also creates the Sparrow cache root, which Weather needs before
  writing its first location record.
- With no generated Niri files, optional includes let static Niri defaults
  validate; Display and wallpaper/Look generate their own fragments later.
- With no wallpaper directory or saved selection, wallpaper initialization
  uses the bundled `default.png`, creates the normal per-output/global state,
  and initializes the palette through the existing pipeline. It leaves the
  missing personal wallpaper directory alone.
- With no recording directory, recording-history thumbnail indexing exits
  without error; recordings are user output and are not installed.
- No repository file is copied from the live generated/state/cache trees.

## Future installer design (not implemented)

1. Detect Arch/CachyOS, Niri session state, XDG roots, existing configs and
   services; print a plan before mutation.
2. Check required binaries and show separate core/optional package lists.
   Package installation must be opt-in, and AUR helpers/assets must be
   separately confirmed.
3. Stage a timestamped backup/transaction directory before touching any target.
4. Create the canonical Quickshell path as one managed symlink (or one clearly
   selected copy strategy) and refuse to overwrite an unrelated directory.
5. Install Niri fragments under `~/.config/niri/sparrow`; if a root config
   exists, offer a backed-up include merge or stop for manual resolution. Never
   replace the user's config wholesale.
6. Copy systemd units into `~/.config/systemd/user`, validate them, and reload
   the user manager only after all staged files are ready.
7. Copy Hyprlock defaults only to absent paths; leave screenshots, wallpapers,
   generated palettes and user state untouched.
8. Create XDG state/cache directories and run the safe legacy migration.
9. Let Sparrow generate display, Look, Input, keybind and palette fragments;
   don't synthesize hardware values in the installer.
10. Run Niri validation and unit/QML checks against the staged result before
    enabling services. On failure, restore only files created or replaced by
    this installation transaction from its backup; never roll back user data
    or generated state.
11. Enable user units only after successful validation and report exact manual
    logout/login checks. Do not restart Niri as an installation side effect.

This is a plan only. There is no installer in this change.
