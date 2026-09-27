# Fresh-install / zero-state audit

Audit date: 2026-09-27. This is a first-run investigation with follow-up
verification of Dynamic palette defaults and the built-in wallpaper picker,
plus one narrow QML null guard. It is not an installer and does not replace a
clean graphical VM test. State/palette experiments used temporary directories.
The active wallpaper, Niri config, services, caches, preferences and wallpaper
selection were left alone.

## Zero-state result

The modeled user has no Sparrow or Ricelin state, generated palette/fragments,
personal wallpaper directory, app configuration, Sparrow desktop entries or
units, or personal Hyprlock configuration. The repository files are assumed
installed at their documented canonical paths. Crucially, the Niri entry
config and static Sparrow fragments must be integrated before palette
generation can commit the generated Niri fragment.

With required dependencies and those Niri includes, the default path is
coherent: runtime creates state/cache roots, then the wallpaper unit restores
the bundled image and generates palette outputs before the shell service
starts. This was verified with isolated migration and palette-generation
checks, not by starting a second Niri/awww session. A genuine graphical
zero-state first login remains untested.

Fresh installations default to Dynamic palette mode. Explicit palette choices
already saved in `flags.json` remain unchanged because the JsonAdapter default
only supplies missing state or keys. The Wallpaper picker includes a read-only
`Sparrow Default` item independently of the personal wallpaper directory;
personal-library shuffle remains personal-only. The bundled image's provenance
is documented in `quickshell/sparrow/wallpapers/README.md`; redistribution is no
longer an unresolved release blocker.

## Initialization sequence

1. `sparrow-wallpaper.service` runs `migrate-state.py` as `ExecStartPre`. It
   creates `$XDG_STATE_HOME/sparrow-shell`, a protected migration-backup root,
   and `$XDG_CACHE_HOME/sparrow-shell`; there is no legacy data to copy for a
   new user.
2. It starts awww. `ExecStartPost` runs `wallpaper.sh init` with the
   systemd-managed-daemon marker. It queries Niri outputs and resolves each
   output from saved output selection, saved global selection, then
   `wallpapers/default.png`. With no prior state/map/personal wallpaper, the
   bundled image is applied and written as the initial selection.
3. Palette generation runs synchronously in that post-start step. It reads
   Matugen colors, creates Sparrow roles/luminance, validates a candidate Niri
   color fragment through the managed-fragment helper, then writes
   `palette.json` and Kitty/GTK/icon outputs.
4. The wallpaper unit is ordered before `graphical-session.target`; the main
   shell unit is ordered after it. Main shell `ExecStartPre` runs migration
   again, then starts `qs --no-duplicate --path ~/.config/quickshell/sparrow`.
5. `shell.qml` initializes the lock, restores Devices state, requests wallpaper
   restore (an idempotent second init check), probes Night Light, imports
   Wayland/Niri environment into the user service manager, and starts the
   separate idle service. It does not need to open Wallpaper or Mixer UI to
   initialize those startup paths.
6. Most surfaces are lazy. Launcher usage and UI-specific preference files are
   read/written when first used. The wallpaper picker shows the bundled default
   separately from discovered images in the selected personal folder.

This ordering depends on the installer integrating the Niri root and static
managed-fragment include graph before enabling the wallpaper unit. If the
transaction helper cannot validate the generated Niri colors, `wallcolors.py`
does not write the new JSON/app palette outputs; `wallpaper.sh init` preserves
wallpaper restoration despite palette failure. Quickshell then has its baked-in
fallback colors and Kitty its defaults, but GTK/icon outputs may be missing
until a later successful generation.

## First-run state and generated files

| State/output | Creator and timing | Missing/malformed behavior | Installer policy |
| --- | --- | --- | --- |
| State/cache roots | Migration pre-start on each unit | Created even with no legacy state. Legacy copies are copy-if-destination-absent and backed up. | Runtime creates; don't seed synthetic state. |
| `flags.json` | `Flags.qml` JsonAdapter after FileNotFound; parent exists from migration | Defaults include Auto lock text, Dynamic palette mode, tonal palette style, Night Light off, empty wallpaper override, and default record/idle preferences. Missing keys use declarations; explicit saved choices remain. An isolated JsonAdapter fixture confirmed malformed JSON leaves defaults in memory without rewriting the file; the complete Sparrow singleton was not tested with corrupted state. | Runtime creates. Never ship a user's flags. |
| `launcher-usage.json` | Launcher reads missing/invalid as `{}`; writes after a launch selection | No usage history is a normal state. | Runtime creates on use. |
| `events.json` | Events singleton; missing file writes `[]` | Invalid JSON is treated as empty in memory; event changes persist the new list. | Runtime creates when instantiated. |
| `weather-loc.json` | Weather after successful lookup/geocode | Invalid/missing cache falls through to network lookup. Failed lookup leaves weather unready, not fabricated. | Runtime creates; no installer location. |
| `nvibrant-value` | Devices defaults to 40; persists after user changes vibrance with backend available | Invalid value reads as 40. Tool/device probing is lazy when Mixer opens; existing value is applied then, not by independent startup probing. | Runtime creates on use. |
| `wallpaper`, `wallpaper-map` | `wallpaper.sh init` after output restore | Bad/missing map entries are ignored; missing files fall through to saved global/bundled default. | Runtime creates. Never seed a host map. |
| Shuffle bag/lock | Wallpaper `next` path | No personal candidates means no shuffle result; bundled startup image remains displayed. | Runtime creates on shuffle. |
| `wallpaper-still.png` | GIF/video application/palette extraction | Static image doesn't need it; FFmpeg failure prevents animated still/palette work and reports an error. | Runtime/cache output. |
| `palette.json` | `wallcolors.py` during startup/selection/recolor | Startup checks luminance and lock recommendation; stale/missing metadata triggers generation. Failed Niri transaction preserves old JSON. | Runtime generates; don't install a fake. |
| `generated-colors.kdl` | Palette generator via Niri transaction helper | Requires Sparrow's Niri include graph and valid staged Niri syntax. | Runtime generates; integrate static Niri defaults first. |
| Kitty `sparrow-colors.conf` | Palette generator | The tracked Kitty config uses `globinclude`, allowing the include to be absent; Kitty then uses its built-in/default colors. [Kitty config docs](https://sw.kovidgoyal.net/kitty/conf/) document glob inclusion. | Runtime generates; do not seed colors. |
| Sparrow GTK CSS | Palette generator transforms installed adw-gtk3 stylesheet | Missing source CSS prevents optional theme output; GTK falls back to its selected installed theme. | Runtime generates; installer offers adw-gtk3 for themed Thunar. |
| Sparrow colored icons | Palette generator; static Papirus-derived files/theme metadata are tracked | Optional writes/cache refresh may fail; base icon fallback remains. | Install static licensed theme files; runtime generates palette variants. |
| Recording preferences/output | Flags defaults and Recorder UI; `mkdir -p` on first recording | No recording directory required before recording; history empty. | Runtime creates on use. Never copy recordings. |
| Thumbnails | Wallpaper/recording helper on first list/refresh | No media yields an empty list; generation needs FFmpeg. | Runtime cache, not installer data. |
| Lock luminance/mode | Same generated `palette.json`; lock preference in Flags | Auto default; if recommendation is unknown, Last of Us uses light foreground. Startup normally generates metadata before lock use. | Runtime generates; no separate lock palette. |
| Display/user fragments | Display/Look/Input/Keybind settings after user saves changes | Optional includes permit absence; Niri defaults apply. | Runtime creates; never copy this machine's output/user fragments. |
| Hyprlock user config | Not needed by primary Quickshell lock | Fallback requires Hyprlock and readable `~/.config/sparrow/hyprlock.conf`. | Seed fallback only if chosen and absent; never overwrite. |

The clean migration harness succeeded in a temporary HOME/XDG tree. It created
the state/cache/migration-backup roots without fabricating `flags.json` or
copying legacy data. This verifies the normal systemd pre-start path, not
arbitrary manual QML launch without migration.

## Bundled wallpaper / palette test

`quickshell/sparrow/wallpapers/default.png` was passed to the actual palette
generator with all writes redirected into temporary XDG config/cache/data
directories. Matugen ran; the Niri transaction call, Kitty signal, and icon
cache refresh were stubbed. The results were:

- palette: `source_color=#787878`, `palette_style=tonal`,
  `wallpaper_luminance=0.077689`, `recommended_lock_foreground=light`,
  `surface=#191c1d`, `primary=#c4c7c7`;
- captured Niri border fragment: active `#c4c7c7`, inactive `#505354`;
- palette JSON, Kitty include, Sparrow GTK CSS, folder SVG and document SVG all
  existed in the temporary tree.

Existing tests cover source selection across neutral/vivid images, lock
foreground recommendation, and synchronized consumer outputs. The bundled
image's neutral seed generates a grayscale palette. This test did not validate
actual Quickshell watchers, Niri reload, Kitty/GTK rendering, or screenshots.

## Niri defaults and default apps

`niri/config.kdl` plus tracked `niri/sparrow/` fragments supply static
appearance, binds, input and window rules. Generated colors, output layout,
display numbers and user overrides are optional. Repository-default
`niri validate` succeeds with expected warnings for absent optional fragments;
active `~/.config/niri/config.kdl` also validated read-only. No active monitor
name is required; generated output arrangement must be per-install.

Bindings cover Kitty, Thunar, Firefox, Sparrow lock, separate Rishot screenshot,
Recorder, Launcher, Wallpaper picker/next, normal Niri workspace 1–9, Overview,
window/layout controls, and hardware media/brightness. App binds require the
named app or user changes. Rishot at `~/.local/bin/rishot` is separate, not
bundled. Recorder needs GPU Screen Recorder; window/region pick additionally
needs slurp.

### Kitty/Fish/Starship

Installer offers Kitty, Fish, Starship and JetBrains Mono Nerd Font and installs
tracked Kitty/Fish/Starship defaults with backup/merge policy. Palette runtime
creates the Kitty include. With no include Kitty remains usable with its
defaults. Without Starship config, Starship uses its own default prompt, not
Sparrow's custom directory pill. Without Fish, Kitty's `shell fish` selection
cannot provide the intended setup. Without the Nerd Font, glyph appearance
depends on font fallback. These are dependencies of the complete reference
terminal experience, not the Quickshell shell itself.

### Thunar/GTK

Installer offers Thunar, GTK3/`gtk-launch`, adw-gtk3 source CSS, Tumbler,
Sparrow icon metadata/static Papirus-derived assets, GTK settings integration,
and `applications/sparrow-files.desktop` as optional Sparrow-owned integration.
Niri's file bind launches Thunar with `GTK_THEME=Sparrow`. Palette runtime
generates GTK CSS and colored folder/document icons. Existing Thunar windows
still require close/reopen to pick up CSS; this remains parked.

## Lockscreen defaults / safety

The path is `Super+L` → `sparrow-lock` → Sparrow IPC → `WlSessionLock` →
Qylock-derived Last of Us UI → PAM. Fresh lock foreground mode is Auto. Palette
luminance comes from the same generated JSON; per-output wallpaper backgrounds
share one global recommendation. If metadata is absent, `Dyn` says unknown and
Last of Us falls back to its original light foreground. The bundled wallpaper
test recommended light.

Hyprlock is fallback-only, not needed by the primary lock. If Sparrow IPC is
unavailable, fallback requires both Hyprlock and a readable user config. No
lock was invoked in this audit.

The prior journal had repeated `lockSurface.screen.name` null warnings. A guard
now returns an empty path while Quickshell has not assigned a screen, then the
binding resolves the output wallpaper. No PAM/session-lock logic changed. This
needs a manual safe lock test across one/multiple outputs; `qmllint` is not
installed here.

## Optional/unavailable behavior

Based on code guards and empty-state UI; only installed-host binary absence was
queried. Other missing-service scenarios were not forced by removing packages.

| Missing or empty feature | Current behavior | Audit result |
| --- | --- | --- |
| Cava | Probed; visualizer stays unwanted unless preference and availability are both true; no rapid restart loop. | Graceful. |
| DDC / ddcutil | Probe is lazy on Mixer open and checks `command -v` in a shell; no detected monitors means no DDC rows. | Graceful. |
| nvibrant | Requires tool and NVIDIA modeset device; control is inactive/hidden; no missing executable launch. | Graceful. |
| Backlight / brightnessctl | One sysfs poller exits if no device; UI gated by shared hardware presence and CLI availability. | Graceful. |
| Bluetooth devices/adapter | Empty list says “No devices found”; pairing errors are surfaced after user action. | Code path graceful; no adapter-absent runtime test. |
| Wi-Fi service/network | NetworkManager UI handles scan/connect failures; absent-daemon initial rendering not runtime-tested. | VM test remains. |
| MPRIS player | `Players.active` is null; media IPC does nothing when player list is empty. | Graceful. |
| Recorder/slurp | Surface opens; recorder failures become notifications; missing slurp reports Window picker unavailable; direct screen target is separate. | Action feedback; missing binary not forced. |
| FFmpeg | Needed for thumbnails and GIF/video still extraction. Thumbnail helpers suppress ffmpeg stderr; animated still failure is reported. Static image wallpaper remains. | Full media dependency. |
| wlsunset | Night Light reports Unavailable; off mode starts no process. | Graceful. |
| Battery / UPower device | `Battery.present` false and battery UI is gated. | Code path graceful. |
| No tray entries / notifications | Tray hides when model empty; notification count/history starts at zero. | Graceful by code. |
| No events | Events starts `[]`; calendar has no-event behavior. | Graceful. |
| Empty wallpaper folder | Picker still shows the read-only built-in Sparrow Default; personal results remain empty. | No crash; built-in remains selectable. |

Installed-host check found no `ddcutil` or `nvibrant`; absence is quiet in
the Mixer detection design. Other absent-device cases need the VM matrix below.

## Minimal welcome page recommendation

Keep a single compact first-run card, not a tutorial: three actions (Launcher,
Wallpaper, Settings), a short Pill interaction hint, a compact reference for
Launcher/wallpaper/terminal/files/lock/screenshot with a link to Keybind
Settings, and one sentence explaining personal wallpaper folder plus Dynamic
palette mode. Show optional features only when their backend is missing; do not
list internal paths or present a package-install prompt. Store `welcomeShown`
in Sparrow Flags and provide a reopen route in Settings. The installer should
not own this preference. Page not implemented.

## Future installer inventory — no code

### Packages

- Core/session: Niri 26.04-compatible; Quickshell 0.3.1-compatible and required
  Qt modules; Python, Bash, jq, base utilities; systemd user manager and D-Bus.
- Session features: PipeWire/WirePlumber, NetworkManager/nmcli, BlueZ/bluez-utils,
  UPower, GTK3, xdg-utils, libnotify, portal frontend plus compatible chooser
  backend.
- Wallpaper/theme: awww, Matugen (verify Arch package name), Pillow, FFmpeg,
  adw-gtk3 source stylesheet; mpvpaper optional.
- Default apps: Kitty, Fish, Starship, JetBrains Mono Nerd Font, Thunar and
  Tumbler, Firefox. These app choices can be changed by the user.
- Feature-specific: GPU Screen Recorder and slurp; Qt Multimedia modules for
  video previews; Rishot separately with its dependencies and grim for Niri.
- Optional: wlsunset, cava, brightnessctl on backlight hardware, ddcutil on DDC
  displays, nvibrant on supported NVIDIA systems, mpvpaper, imagemagick,
  zoxide/Fastfetch, Hyprlock fallback. AUR operations always need explicit
  user choice. Verify all package names before installer work.

### Static files, links, directories, generated outputs

- Install one Quickshell runtime tree; tracked Niri root/fragments; three unit
  files; Kitty/Fish/Starship defaults; GTK/theme/icon defaults; Sparrow desktop
  entry; optional simple Hyprlock fallback; and the provenance-documented
  Sparrow default screenshot.
- Establish one canonical `~/.config/quickshell/sparrow` runtime entry. Do not
  make release services depend on checkout paths. Copy systemd units into
  `~/.config/systemd/user`; don't leave links into a development clone.
- Create only needed XDG parents: Quickshell, Niri, user units, app config/data
  roots. Migration creates state/cache roots. Do not create a fake user
  wallpaper library.
- Runtime creates Flags/events/usage/weather/vibrance state, wallpaper and
  shuffle state, recording preferences/output, palette JSON, Niri generated
  colors, Kitty include, GTK CSS, colored icon SVGs, Display output/number KDL,
  user Look/Input/Keybind KDL, and thumbnails/stills.

### Units, integration, preservation and rollback

- Install and validate wallpaper/shell/idle units; enable for
  `graphical-session.target` only after runtime path and Niri include graph
  exist. Daemon-reload, confirm one shell + one idle instance and one wallpaper
  daemon owner.
- Merge Niri includes, validate staged config, then reload only after success;
  generate monitor configuration on target hardware.
- Offer app config/bind integration and check named commands. Rishot stays a
  separate install. Do not add a package manager.
- Back up before any changes to Niri root/fragments, units, runtime symlink,
  Kitty/Fish/Starship, GTK settings, desktop entries, Hyprlock config or
  existing theme/icon directories.
- Never silently overwrite user Niri/output/override config, all persistent
  Sparrow state, personal wallpapers, recordings/screenshots, app configs,
  Hyprlock config, portal selection, or unrelated files. Don't clear cache as
  an installation shortcut.
- First run performs idempotent migration, starts wallpaper restore/palette,
  then shell/idle; reports optional backends unavailable without toggling
  hardware/session settings.
- Roll back only files this transaction changed from verified backups. Never
  roll back user state, wallpaper selections or files that predated install.

The source wallpaper unit is portable and uses the canonical runtime path. The
active laptop service symlink is absolute into the development checkout; do
not change it during this audit. A release installer should copy the unit and
daemon-reload. Development links should resolve through the canonical runtime
path and never encode username/clone path.

## Licensing and release blockers

- The bundled wallpaper is an original screenshot captured in SpaceEngine Pro
  by the Sparrow author and distributed by that screenshot author as Sparrow's
  default. The author confirmed the SpaceEngine/Steam terms permit keeping and
  distributing screenshots made in the software. This documents provenance,
  not a separate third-party license; it is no longer an unresolved wallpaper
  redistribution blocker. See `quickshell/sparrow/wallpapers/README.md`.
- Qylock Last of Us adaptation has GPL-3.0 text/attribution; Outfit font has
  SIL OFL 1.1; Papirus-derived icons have GPL-3.0 notice; Ricelin-provenance
  code retains `LICENSES/Ricelin-MIT.txt`.
- adw-gtk3 is an installed upstream source, not vendored. Generated CSS has an
  upstream attribution; check upstream license/notice requirements for the
  generated output. There is no root `LICENSE` yet, so choose a project-level
  licensing policy before distribution.
- Remaining open choice before final defaults: whether to keep the Hyprlock
  fallback after failure-path testing. Fresh palette mode is Dynamic and the
  bundled wallpaper is selectable; neither decision overwrites saved user
  preferences or personal wallpaper state.

## VM/separate-user/manual tests still required

1. Fresh Arch/Niri VM: session target ordering, first visible wallpaper,
   palette startup, exactly one awww owner, shell/idle count and no startup
   warnings.
2. Isolated output session: static/GIF/video wallpaper, no mpvpaper fallback,
   multiple/disconnected/reconnected output names, failed Matugen and failed
   Niri transaction.
3. Live Quickshell: absent/malformed flags/events/palette; null-screen guard;
   Auto foreground; PAM success/failure; one/multi-output lock. Never test lock
   failure on the daily session.
4. Screenshot theme review of bundled gray-neutral palette in Dynamic mode and
   generated Kitty/GTK/icon consumers.
5. Missing Wi-Fi/Bluetooth services, UPower, MPRIS, Cava, FFmpeg, recorder,
   slurp, wlsunset, backlight, DDC/NVIDIA, tray, notifications, events and
   empty wallpaper folder. Source guards were reviewed, but not all absences
   forced at runtime.
6. Kitty config parse, GTK stylesheet/icon-theme validation, Thunar restart
   behavior, app startup and Rishot install/launch in clean user.
7. Installer conflict/backup/rollback tests in temporary roots before any real
   home installation.

Temporary XDG roots are suitable for migration/palette generators, not PAM,
layer-shell, portals, Niri IPC or systemd graphical-session behavior. Use a VM
or separate disposable user/session; never clear/reset the daily home as a
fresh-state shortcut.

## Validation performed

- Clean-state migration harness in temporary HOME/XDG paths: passed.
- Actual Matugen generation from bundled wallpaper to temporary palette,
  captured Niri fragment, Kitty include, GTK CSS and two generated icons: passed.
  The Niri transaction was mocked; Matugen ran normally.
- Existing Python suite: 35 tests passed, including wallpaper/palette and Niri
  transaction tests.
- Repository and active Niri validation: passed; repository config emitted
  expected warnings for missing optional fragments.
- Shell syntax, Fish syntax, systemd unit verification and `git diff --check`:
  passed.
- `qmllint` and Node are absent; no QML lint or Node helper test ran. Kitty
  parsing and GTK/icon rendering were not tested. Lock was not invoked; no Niri
  reload, Sparrow restart, wallpaper change, package install or live-state
  modification occurred.
- The lock null guard remains to be tested by a manual lock test in an isolated
  or otherwise safe session.

## Wallpaper/default follow-up verification — 2026-09-27

- A–C: an isolated Quickshell 0.3.1 `FileView`/`JsonAdapter` fixture matching
  `Flags.qml` produced Dynamic with no saved file, preserved explicit Static,
  and preserved explicit Dynamic. A malformed JSON fixture left the default
  Dynamic in memory and did not rewrite the corrupt file. `Flags.qml` only
  writes defaults for `FileNotFound`; it does not migrate saved choices.
- D–E: verified the bundled resource resolves inside the runtime tree and is
  prepended independently of the personal-entry list, including with a
  missing or empty personal directory. The thumbnail uses the bundled image
  itself; no user-folder copy/cache entry is required.
- F–G: temporary HOME/XDG test ran the real `wallpaper.sh set` and restart-style
  `init` path with only awww and palette execution stubbed. The built-in path
  was saved globally and for the selected output; restore recognized it as
  already displayed and did not reapply it.
- H: actual Matugen generation from `default.png` wrote temporary palette
  JSON, Niri border fragment, Kitty include, GTK CSS, and folder/document icon
  outputs. The result was `source_color=#787878`, tonal style, luminance
  `0.077689`; the Niri transaction and host-side reload/cache commands were
  mocked.
- I–J: personal-folder listing still found an ordinary image. With no personal
  candidates, `next` returned no selection and left the saved bundled wallpaper
  unchanged; built-in is intentionally excluded from personal shuffle.
- The live picker was opened and visually checked, then closed without
  selecting anything. Quickshell hot reload completed successfully. Current
  saved palette mode and wallpaper paths remained unchanged. Existing
  ScreenLock null-screen and SearchField width-loop warnings remain unrelated.
- Both active and repository Niri configs validated. The 35-test Python suite,
  shell syntax checks, and `git diff --check` passed. `qmllint` is unavailable;
  the active Quickshell hot reload loaded the changed QML without a new
  Wallpaper/Flags/Walls error.
