# Sparrow pre-installer product review

**Review date:** 2026-09-28
**Repository baseline:** `b31a192` — `document Sparrow install inventory and fix Rishot path`
**Scope:** source/history and read-only live-session audit. No runtime code, user config, package, service, wallpaper, or desktop state was changed.

This is a product and installability review, not an installer design specification. Findings below separate observed facts from recommendations. References to upstream projects and Arch packages were checked on the review date; target Arch/CachyOS repositories may differ.

## Review basis and evidence

The five baseline documents were read first, then checked against the current tracked tree, recent Git history, active Niri config/fragments, user units, runtime paths, installed packages, active processes, portal routing, and current-boot Sparrow warnings. The deliberately removed special-workspace model, Game Mode, Ricelin updater, AppImage manager, file installer, decorative CJK/glyph mode, and abandoned Hyprlock artwork were not treated as missing features.

The source tree has no active `hyprctl`, `.config/hypr`, `/home/vrabko`, or development-checkout runtime dependency. Remaining `Ricelin`/Hyprland matches are provenance, migration, generic Git prompt vocabulary, or comments—not a live compositor backend. Details are listed under “Legacy and portability sweep.”

Live read-only snapshot:

- HEAD is `b31a192`; the tree was clean before this document was created.
- Niri 26.04 and Quickshell 0.3.1 are active. Sparrow main, idle, and wallpaper user services are active; `qs list --all` showed exactly the main and idle Quickshell instances.
- `~/.config/quickshell/sparrow` resolves to this checkout in development. That is the intended developer symlink, not a portable install destination.
- `~/.config/niri/config.kdl` is a regular user-owned file, not a repository symlink. The live `~/.config/niri/sparrow/` contains both Sparrow-managed defaults and machine/user-generated fragments and backups.
- The active user portal config routes FileChooser to GTK and retains GNOME ScreenCast/RemoteDesktop/Screenshot plus its existing Secret choice. The repository now carries a merge-only FileChooser fragment; the user config remains untouched.
- `polkitd` and `sparrow-polkit-agent.service` are running. `lxqt-policykit-agent` is owned by `lxqt-policykit 2.4.0-1.1`; its listener registered. The journal's Oxygen fallback-icon warning is non-fatal; no privileged prompt was triggered. The user-owned Secret route still names absent `gnome-keyring`, unchanged and outside this task.
- Current-boot `sparrow-shell.service` warning/error query returned no entries. Niri config validation passed. These are snapshots, not fresh-install simulation or interaction tests.

## 1. Complete Sparrow v1 product map

Classifications: **CORE** is required for the Sparrow Niri desktop; **DEFAULT APP** is the chosen default integration and can be replaced by the user; **FEATURE DEPENDENCY** is required only for its named feature; **OPTIONAL** is detected/disabled gracefully or separately installed; **HARDWARE-SPECIFIC** depends on a device; **FALLBACK** is not the primary path; **MIGRATION-ONLY** reads old data; **DEVELOPMENT-ONLY** is not runtime; **REMOVE BEFORE V1** means omit from packaged runtime (not automatically delete from source).

| Component | Classification | Current product role and evidence |
|---|---|---|
| Niri 26.04 configuration | CORE | `niri/config.kdl` plus tracked Sparrow appearance, binds, input, and window-rule defaults. Native dynamic workspaces, window/layout controls, Overview, display/input/look/keybind settings, wallpaper backdrop layer rules, screenshots, and application shortcuts. The root config includes generated/user/machine fragments optionally; it must be merged with a user’s existing Niri configuration, never blindly replace it. |
| Quickshell main shell | CORE | `quickshell/sparrow/shell.qml`, Pill, Niri event-stream backend, surfaces and singletons. Starts through `sparrow-shell.service` under `graphical-session.target`, using canonical `~/.config/quickshell/sparrow`. |
| Resting Pill and morph system | CORE | Main control surface, workspace indicator, status, controls and surface launch point. Keeps Ricelin-derived dimensions/morph mechanics, but Sparrow palette, content, icon work and Niri integration form the current shell identity (visual review below). |
| Normal workspaces/window integration | CORE | `Workspaces.qml` and `Singletons/Niri.qml` use Niri’s dynamic workspaces, stable IDs, output association, event stream and native IPC. This is not a special-workspace model. |
| Launcher | CORE | Discovers ordinary `.desktop` applications and launches through `gtk-launch`; independent of removed AppImage management. Calculation result copy uses `wl-copy` if installed. |
| Wallpaper picker and restore | CORE | Wallpaper surfaces/singletons and `sparrow-wallpaper.service`; `awww-daemon` is managed by Sparrow and restores per-output state. Image and video paths are supported, with `mpvpaper` optional. Wallpaper switching is also exposed from Pill/Niri binds. |
| Matugen / palette | CORE | `wallcolors.py`, `wallpaper.sh`, `Dyn.qml`, and the generator config/template path create one wallpaper-derived palette for Quickshell, Niri borders, Kitty, and Sparrow GTK theme. Current user choices are Dynamic + Auto palette style + Auto light/dark. Static generated state stays outside Git. |
| Look and Appearance settings | CORE | Matugen source/style/mode, lock foreground, and Niri-native Look controls are applied through Sparrow state and validated Niri fragment transactions. User overrides belong in untracked per-user Niri fragments/state, not the tracked defaults. |
| Display / Input / Keybind settings | CORE | Niri-native settings surfaces. Display arrangement/number mapping, generated display outputs and user mappings are host-specific. Keyboard layout/input and user keybind fragments are user-owned. Do not install the current machine’s display fragments as defaults. |
| Power | CORE | Sparrow power surface uses systemd/Niri for lock, logout, reboot, shutdown and suspend. Confirmed logout bypasses the redundant Niri confirmation only after Sparrow’s own hold-to-confirm interaction. |
| Session lock and idle | CORE | Quickshell `WlSessionLock` + PAM is primary; Sparrow idle policy is a separate Quickshell instance/service. `sparrow-lock` falls back to Hyprlock only when Sparrow lock IPC is unavailable. Lock wallpaper follows per-output Sparrow wallpaper, including video. |
| Notifications | CORE | Sparrow owns the Quickshell notification server/surface; no separate notification daemon is required for the shell’s own notifications. Other apps can use the same D-Bus notification service. |
| Tray | CORE | Quickshell `SystemTray` with menu delegation; keeps separators, icons, check states, disabled entries, submenus and actions. Runtime null model entries are guarded at the delegate/model boundary. |
| Mixer/audio | CORE surface; FEATURE DEPENDENCY backend | Quickshell PipeWire controls and OSD; actual device control requires a running PipeWire/WirePlumber-compatible session. Cava is optional. Internal backlight shares the live `Backlight` singleton used by OSD. DDC/NVIDIA controls are independent optional device-specific rows. |
| Media | CORE surface; FEATURE DEPENDENCY backend | MPRIS players exposed through Quickshell `Players.qml`/surface; availability depends on active media players and their MPRIS interfaces. No separate Sparrow media daemon. |
| Wi-Fi / Bluetooth / battery | CORE surfaces; FEATURE DEPENDENCY services | Wi-Fi controls use Quickshell Networking and `nmcli`/NetworkManager; Bluetooth uses Quickshell Bluetooth and BlueZ; battery uses UPower. These surfaces can be unavailable on systems without the corresponding service/device. Installing/enabling a competing network manager is unsafe. |
| Recorder | FEATURE DEPENDENCY | GPU Screen Recorder, region/window helpers, folder selection through XDG FileChooser, and cache thumbnails. Requires GPU Screen Recorder for capture; portal and Python GObject/GIO are needed for folder picking. |
| Screenshots / Rishot | OPTIONAL external app | `niri/sparrow/binds.kdl` invokes `rishot` through PATH. Rishot is separate upstream software, not vendored; the bind only works when the user installs it. Do not silently run its installer. |
| Night Light | OPTIONAL | Sparrow-managed `wlsunset` process; saved state initializes at shell startup but remains off unless the user enables/schedules it. |
| System monitor | OPTIONAL surface | CPU, memory, disk and optional NVIDIA GPU stats. `nvidia-smi`/`nvidia-utils` is only for NVIDIA metrics. |
| Weather | OPTIONAL | `Weather.qml` uses IP-based geolocation via `ip-api.com`, then weather API requests and XDG cache/state. It is not needed for the core shell; make its network/privacy behavior explicit in onboarding and allow it to remain unused. |
| Wallpapers bundled with Sparrow | CORE asset | `quickshell/sparrow/wallpapers/default.png` is the author’s own SpaceEngine Pro screenshot; provenance and permission are documented. Personal wallpaper collection/state is not tracked. |
| Sparrow GTK theme | DEFAULT APP integration | Palette-generated theme built from system-installed `adw-gtk-theme`; scoped service environment themes the GTK portal, and file-manager launch explicitly uses `GTK_THEME=Sparrow`. Does not globally force unrelated apps. |
| Icon theme | DEFAULT APP integration | Small Sparrow Papirus-derived SVG subset for Thunar sidebar/device icons plus generated palette-aware file/folder artwork. Papirus GPL notice is tracked. It is not a full replacement icon pack. |
| Cursor | DEFAULT APP integration | `environment.d/90-cursor.conf` recommends `Bibata-Modern-Ice`, size 24. Theme package is external; defaults must not override an existing user cursor choice. |
| Inter and JetBrains Mono Nerd Font | DEFAULT APP integration | Inter for UI; JetBrains Mono Nerd Font for Kitty/Fish/Starship. Outfit Black is bundled with OFL notice for lock UI. Fonts are application appearance dependencies, not required by compositor. |
| Kitty / Fish / Starship | DEFAULT APP | Tracked defaults configure Kitty with generated palette include, Fish shell setup, and Starship directory/Git prompt. `zoxide` and `fastfetch` are optional Fish conveniences. Current prompt colors rely on palette-indexed ANSI colors, while Kitty consumes generated palette directly. |
| Thunar | DEFAULT APP | The default file manager (`sparrow-files.desktop`), opened with Sparrow GTK theme. `tumbler` provides thumbnails, `gvfs`/UDisks integration supports removable/remote locations. Archive context-menu support is not installed on this host and is a user-choice add-on, not core. Existing Thunar instances not live-refreshing wallpaper colors is an accepted limitation. |
| Firefox | DEFAULT APP | Niri default browser shortcut only. Browser theme integration is explicitly out of scope; ordinary `.desktop` launch is independent. |
| GTK portal/file chooser | FEATURE DEPENDENCY | Recording directory picker uses XDG FileChooser. Repository merge fragment supplies only GTK selection; GTK theme is scoped to the portal service. |
| Screen sharing portal | OPTIONAL desktop infrastructure | Niri’s documented screen-cast path uses PipeWire + `xdg-desktop-portal-gnome`; upstream also documents GTK FileChooser routing when Nautilus is not wanted. The active live route uses GNOME for ScreenCast/RemoteDesktop/Screenshot, but that config is user-owned and not tracked. |
| Polkit authentication | DEFAULT SESSION INTEGRATION | The host's guarded Niri-session unit runs the official `lxqt-policykit` agent; listener registration was confirmed. Installers must preserve an existing user agent/autostart and avoid duplicates. |
| Secret portal/keyring | OPTIONAL desktop infrastructure | Live preference routes Secret to `gnome-keyring`, but neither keyring nor `oo7-portal` is installed here. Not required by Sparrow itself; the preference must be reconciled with the user’s actual secret-service choice. |
| `applications/sparrow-files.desktop` | DEFAULT APP integration | Hides from menus and associates `inode/directory` only when the user chooses it as default. MIME associations are user-owned; installation must not seize them without consent. |
| `sparrow-shell.service`, `sparrow-idle.service`, `sparrow-wallpaper.service` | CORE | User services ordered against Niri/`graphical-session.target`; logs go to journal. Enable/start only after the canonical runtime is deployed and validation succeeds. |
| GTK portal systemd drop-in | FEATURE DEPENDENCY integration | `GTK_THEME=Sparrow` is applied only to `xdg-desktop-portal-gtk.service`, not globally. Check portal service name/version and preserve existing drop-ins. |
| `migrate-state.py` | MIGRATION-ONLY | One-time, locked, atomic Ricelin-state migration into Sparrow XDG state, with protected backup and no overwrite of existing Sparrow data. Can remain as startup compatibility code or become a one-shot install step later; it does not require Ricelin installed. |
| Generated colors, GTK theme, caches, selection | GENERATED / USER STATE | Palette JSON/KDL, generated GTK assets/icons, wallpaper selection/output map, flags/onboarding, thumbnails, recording previews and monitor layout are not portable defaults. Regenerate only after install and preserve user state. |
| `quickshell/minimal-test.qml` | DEVELOPMENT-ONLY | Standalone black-panel QML fixture has no reference in the main shell or service. Keep for contributors if useful, but exclude from runtime payload and consider removing before release. |
| Repository licensing | Defined; preserve per-component terms | Root `LICENSE` and `THIRD_PARTY.md` define GPL-3.0-only for the combined Sparrow program and map Ricelin MIT, Qylock GPL-3.0, Papirus GPL-3.0, Outfit OFL, and the author's wallpaper permission. |

### Tracked source and current live config ownership

The repository’s Niri tree contains portable defaults, not a complete snapshot of the live machine:

| Path/data | Current role | Future ownership |
|---|---|---|
| `niri/config.kdl`, tracked `niri/sparrow/{appearance,binds,input,window-rules}.kdl` | Static base/portable defaults and Sparrow include graph | Sparrow owns the fresh-install template; installer merges/preserves an existing root config. |
| `~/.config/niri/config.kdl` | Active regular user config | User owns. Back up and merge rather than overwrite. |
| `~/.config/niri/sparrow/generated-colors.kdl` | Wallpaper-generated Niri palette include | Sparrow generates; do not track or seed from this host. |
| `~/.config/niri/sparrow/display-outputs.kdl`, `display-binds.kdl` | Monitor geometry/numbers and output-specific shortcuts | User/machine state, generated by Display; never copy across hosts. |
| `~/.config/niri/sparrow/user-appearance.kdl`, `user-input.kdl`, `user-binds.kdl` | Preferences authored through Sparrow UI | User-owned mutable overrides. The tracked defaults include them optionally. |
| `~/.config/niri/sparrow/window-rules.kdl`, `appearance.kdl`, `binds.kdl`, `input.kdl` | Active Sparrow-managed static fragments corresponding to tracked defaults | Sparrow owns templates, with conflict/backup strategy on deployment. |
| `xdg-desktop-portal/niri-portals.conf.fragment` | Sparrow-owned merge input | Contains only GTK FileChooser preference; merge into the user portal file and retain all other routes. |
| `~/.config/xdg-desktop-portal/niri-portals.conf` | Active user-specific portal selection | User-owned policy; currently includes GTK FileChooser and retains ScreenCast/other choices. Do not overwrite. |
| `$XDG_STATE_HOME/sparrow-shell/` | Flags, selected wallpapers/maps, onboarding, event and app history, migration state | Runtime user state. Never seed from development machine except safe migration. |
| `$XDG_CACHE_HOME/sparrow-shell/` | Palette JSON, wallpaper/recording thumbs, transient cache | Sparrow-generated disposable cache. |
| `$XDG_DATA_HOME/...` | Generated themes/icons and downloaded/imported assets | User-local generated/added data; do not track or overwrite. |

The canonical development runtime link is currently `.config/quickshell/sparrow -> ../../Projects/sparrow-shell/quickshell/sparrow`; a real install should place the versioned runtime there (or a stable managed link into an installation directory), not a checkout-specific link. Live `display-outputs.kdl`, generated colors and user fragments must not become repository defaults.

### File/drop, handlers, and desktop basics

Pill’s remaining drop behavior is wallpaper import, not package installation. `applications/sparrow-files.desktop` is a hidden directory-handler option; generic `.desktop` application discovery/launch remains separate. Screenshot, recording, app launch, file management, audio, network, Bluetooth, brightness, media, power, notifications, system tray, wallpaper, display/input, lock/idle, and portal folder selection are all represented. This is a sufficiently complete desktop foundation; the gaps below concern integration, not a need for another dashboard or package manager.

## 2. Visual identity review

Static source review confirms Sparrow still shares a recognizable lineage with Ricelin: the 160×38 scaled resting Pill, centered top anchoring, rounded capsule, and morphing-to-surface behavior follow the Ricelin reference closely. I did not make a screenshot comparison during this read-only audit, so this is a code/geometry assessment rather than a claim of pixel-level live visual comparison.

**Keep as Sparrow identity:** the small morphing Pill as the main interaction; normal Niri workspaces; wallpaper-led Matugen palette; warm palette accents; the custom SVG icon system; per-output wallpaper; spare, focused surface set; and the no-dashboard/no-clipboard-manager stance. The shell’s Niri-native functionality, theme pipeline, screen lock, and removed legacy systems already make it a real product rather than a skin.

**Still inherited/generic:** exact Pill capsule proportions and centered top placement; repeated rounded card/panel language; some card gradient/border/sheen treatment; certain morph timing and component conventions. The source comments themselves describe portions as Ricelin-derived. These similarities are visible from the implementation model but are not a technical reason to rewrite them.

Three coherent directions, none required before packaging:

| Direction | Change / stay | Complexity and performance | Wallpaper/readability | Difference |
|---|---|---|---|---|
| **1. Sparrow Glass, restrained (recommended only if a design pass is wanted)** | Keep Pill size, morph, layouts, icons and content. Reduce repeated gradient/sheen layers across secondary panels; use a small number of translucent surface levels and one palette accent edge. | Low-to-medium; mostly surface token tuning. Transparency is cheap; avoid broad blur. | Works over still/video wallpapers; slightly translucent opaque-enough surfaces keep contrast. | Moderate: coherent polish, not a wholesale fork. |
| **2. Signature Pill** | Keep morph and UI, adjust only resting silhouette/proportion, corner asymmetry or workspace/status alignment; let the Pill have one unmistakable Sparrow feature. | Low-to-medium; geometry and animation QA across scale/output. No expensive effects. | Safe over videos; readability unaffected if text backing remains. | High visual payoff per changed component; best way to distance from Ricelin without rewriting surfaces. |
| **3. Wallpaper-reveal panels** | Keep content and Pill; make only outer panels more transparent and use wallpaper-derived border/edge accents. Prototype native Niri/layer behavior before considering blur. | Medium; requires multi-output, Overview, opacity and video testing. Transparency is light; backdrop blur is costlier and can differ by surface/compositor. | Risk of reduced text contrast on bright/animated backgrounds; maintain fallback contrast. | More distinct, but easily becomes visual noise if every surface is transparent. |

Recommendation: Sparrow is good enough to ship as a focused v1; do not block the installer on a redesign. If a pre-release polish change is wanted, choose one constrained Pill signature pass (direction 2), not a new visual system. Keep visual choices in surface tokens rather than adding many Look sliders.

Current outside examples are lessons, not templates: [Caelestia](https://github.com/caelestia-dots/shell) demonstrates a tightly art-directed shell/panel family but is Hyprland-coupled; [end-4](https://github.com/end-4/dots-hyprland) shows broad palette-driven composition and animation but is also Hyprland-oriented and substantially more feature-heavy; current [Noctalia](https://github.com/noctalia-dev/noctalia) demonstrates explicit separation between shell and compositor/system responsibilities. None should be copied or treated as a requirement for Sparrow.

## 3. Greeter/login experience

A session lock is not a greeter: Sparrow’s Quickshell `WlSessionLock` + PAM protects an already running session. A login greeter runs before the user session and normally belongs to a display manager or greetd/PAM stack. Configuring it can change system boot/login behavior and has recovery/security implications; it is outside the user-level Sparrow installer by default.

| Candidate | Security, Niri fit and recovery | Design/cost/limits | Review |
|---|---|---|---|
| Existing DM (GDM/SDDM/etc.) | Retain the user’s installed manager; select a Niri session entry. Mature session/PAM boundary and known recovery route. | Existing theme integration varies; a Sparrow wallpaper/Matugen look may be limited. No extra Sparrow dependency. | Safest default: do not switch or configure it. |
| TTY + `niri-session` | No additional greeter process/configuration; user logs in through existing console/system login, then launches the Niri session. Existing Niri integration uses `niri-session` and graphical-session targets. | Minimal visual experience, but simple and easy to recover on a TTY. | Supported fallback/documented path, not a Sparrow greeter. |
| greetd + tuigreet | greetd owns PAM login; tuigreet is a terminal UI used as greetd’s default session. Niri session can be selected/launched through its command. Recovery is through another TTY and reverting greetd config. | Very small, quick, no GTK theming or wallpaper sync, single terminal display. Official Arch package `greetd-tuigreet` exists. | Best optional lightweight route if a user chooses greetd; installer must not enable it automatically. |
| greetd + ReGreet | GTK greeter under greetd/Cage; uses greetd/PAM and offers user/session selection. Upstream explicitly describes it as single-monitor and recommends Cage’s last-connected-monitor behavior. | Themes/fonts/icons/background configurable; GTK/CSS effort to approximate Sparrow; adds Cage and GTK dependencies and greetd configuration. | Credible graphical alternative, but multi-monitor constraint and system-level handoff matter. Verify hardware before recommending as default. |
| Noctalia Greeter | Current project is a separate native Wayland client plus bundled wlroots compositor launched by greetd’s wrapper; it is not a Quickshell/QML greeter. PAM/session selection is delegated to greetd. | High visual integration potential; separate compositor, wlroots, assets, PAM/greetd system configuration and recovery path; rapidly evolving project, not a simple user-level dependency. | Interesting future user-selected option, not a Sparrow v1 dependency. |

Niri’s current “Important Software” guide calls out portals, notification support, Secret portal and Polkit agent; its screencast guide says PipeWire + `xdg-desktop-portal-gnome` and Niri session integration are needed for the supported portal screencast path. See [Niri Important Software](https://github.com/niri-wm/niri/wiki/Important-Software), [Niri Screencasting](https://github.com/niri-wm/niri/wiki/Screencasting), and [Niri Integrating](https://github.com/niri-wm/niri/blob/main/docs/wiki/Integrating-niri.md).

**Decision: C — keep greeter setup outside Sparrow v1.** Sparrow can document compatibility and let users retain their DM or use a TTY. If the user later requests a recommendation, offer tuigreet for minimal greetd or ReGreet for a graphical greetd experience, clearly state ReGreet’s single-monitor behavior, and do not write a custom greeter. No candidate should be installed/activated by the rice installer without explicit system-level opt-in.

## 4. Missing desktop basics and infrastructure

| Finding | Type | Recommendation |
|---|---|---|
| Graphical Polkit agent | Resolved on current host | `lxqt-policykit` is installed; the enabled, guarded unit is active and registered its listener. The installer must keep the existing-agent/autostart check. |
| GTK FileChooser route absent from repository | Resolved for current host; merge logic is installer work | `xdg-desktop-portal/niri-portals.conf.fragment` records only `org.freedesktop.impl.portal.FileChooser=gtk;`. The live config already routes FileChooser to GTK and preserves GNOME capture routes. A clean/populated merge test belongs to installer acceptance tests. |
| Screen sharing depends on a screen-cast portal and PipeWire | Feature-specific desktop dependency | Offer/verify Niri’s GNOME portal route if screen sharing is in scope; GNOME portal may pull Nautilus on Arch. Do not conflate this with GTK FileChooser. Niri documents this dependency in its [screencasting guide](https://github.com/niri-wm/niri/wiki/Screencasting). |
| Live Secret portal selects absent `gnome-keyring`; `oo7-portal` also absent | User’s current portal policy gap, not a Sparrow core defect | Ask whether the user wants a keyring/secrets provider or retain host policy; detect before warning. Sparrow does not need to install one. |
| Archives unavailable in current Thunar | Nice-to-have | The host has neither `thunar-archive-plugin` nor an archive GUI. This does not make file management incomplete; offer archive handling as an optional Thunar integration only if wanted. Arch provides [`thunar-archive-plugin`](https://archlinux.org/packages/extra/x86_64/thunar-archive-plugin/) and separate handlers such as File Roller. |
| Thumbnails | Feature dependency | Thunar + Tumbler are installed; video/image thumbnail generation also uses Sparrow helpers/ffmpeg. Current setup covers common previews. Some formats need optional plugins/codecs; do not promise all formats. |
| Removable storage | Mostly covered | Host has GVFS and UDisks; Thunar’s common device workflow works through them. `gvfs-udisks2` is not a separate package here; GVFS ships the udisks2 volume monitor. UDisks service/permissions remain host/system policy. |
| URL and MIME handlers | Covered with user choices | Sparrow-file-manager desktop entry handles directories only if selected; Firefox is the default Niri browser shortcut. Existing HTTP/HTTPS MIME owners must remain untouched unless chosen by user. |
| XWayland | Covered as optional host compatibility | `xwayland-satellite` is installed on this host; it is not needed by Sparrow’s native shell. Offer only for legacy X11 clients, and preserve whichever XWayland integration user already has. |
| Clipboard interoperability | CLI only | No clipboard manager UI is intended. `wl-copy` provides copy for calculator/Rishot integration. Do not add a clipboard surface. |
| Recording folder chooser | Covered with portal integration | Python GObject/GIO helper calls XDG FileChooser. A working backend plus the correct routing is required. The GTK theme service drop-in is scoped and should remain so. |

### Polkit agent candidates

| Candidate | Findings | Decision |
|---|---|---|
| LXQt PolicyKit (`lxqt-policykit`) | Current LXQt 2.4 release is in Arch Extra; package payload is small (about 95 KB installed) and has only `liblxqt` + `polkit-qt6` runtime dependencies. It is a standalone Qt6 agent, not an LXQt session requirement. Qt6/Wayland is appropriate for Niri; styling follows Qt/platform theme rather than Sparrow GTK tokens. [Arch package](https://archlinux.org/packages/extra/x86_64/lxqt-policykit/), [upstream](https://github.com/lxqt/lxqt-policykit). | **Recommended Sparrow default** when no agent exists: maintained, official repo, low additional footprint. |
| MATE PolicyKit (`mate-polkit`) | GTK3-based, and therefore visually easier to align with Sparrow GTK, but it is a MATE desktop integration and carries a larger GTK/MATE dependency surface. It is a reasonable existing user choice. [Arch package files](https://archlinux.org/packages/extra/x86_64/mate-polkit/files/). | Preserve if already selected; not Sparrow’s default. |
| KDE PolicyKit (`polkit-kde-agent`) | Maintained Qt6 agent with a polished KDE UI, but depends on KDE Frameworks/Kirigami and has a larger dependency set. [Arch package](https://archlinux.org/packages/extra/x86_64/polkit-kde-agent/). | Preserve for KDE users; too much framework surface for the default. |

`polkit-gnome` was not selected as a serious new default candidate: it is a legacy agent rather than a current GNOME-maintained standalone path. LXQt documents that its packaged agent is LXQt-only by default, while allowing other desktops to add their own autostart action; Sparrow therefore uses its guarded Niri session unit rather than relying on that desktop entry. [Arch manual](https://man.archlinux.org/man/lxqt-policykit-agent.1.en), [ArchWiki autostart notes](https://wiki.archlinux.org/title/LXQt).

Arch’s [Polkit guidance](https://wiki.archlinux.org/title/Polkit) distinguishes the daemon from an authentication agent. Sparrow’s unit does not attempt to replace/stop existing agents; the installer must detect current services and XDG autostart before enabling it.
| Notifications/tray/media/audio/network/Bluetooth/battery/brightness | Covered as surfaces, service-dependent | No further dashboard or separate daemon is needed. Require/verify the session services where the user opts in; do not start competing NetworkManager, PipeWire, or BlueZ stacks. |

The current host has active portal frontends and GTK/GNOME portal backends, PipeWire/WirePlumber, GVFS, UDisks, NetworkManager, BlueZ, UPower, and the Sparrow notification server. Those host facts do not mean the repository installs or owns those system services. Sparrow's GTK theme remains scoped to the GTK portal service. Niri documents GTK FileChooser routing separately from GNOME ScreenCast support in its [portal guidance](https://github.com/niri-wm/niri/wiki/Important-Software).

## 5. Dependency sanity and current Arch package groups

The repository’s `docs/INSTALL-INVENTORY.md` provides the exhaustive source-call inventory. This review condenses it into future install groups so the installer does not install every optional tool. Package names below were checked against current Arch package records, but the installer must query the target CachyOS/Arch repositories rather than assume version parity. See the official [Niri](https://archlinux.org/packages/extra/x86_64/niri/), [Quickshell](https://archlinux.org/packages/extra/x86_64/quickshell/), [Matugen](https://archlinux.org/packages/extra/x86_64/matugen/), [awww](https://archlinux.org/packages/extra/x86_64/awww/), [Pillow](https://archlinux.org/packages/extra/x86_64/python-pillow/), [GTK portal](https://archlinux.org/packages/extra/x86_64/xdg-desktop-portal-gtk/), [GNOME portal](https://archlinux.org/packages/extra/x86_64/xdg-desktop-portal-gnome/), and [Thunar](https://archlinux.org/packages/extra/x86_64/thunar/) records.

### MINIMUM REQUIRED — Sparrow shell runtime

| Package/tool | Why / caller |
|---|---|
| `niri` + systemd user session/D-Bus via `niri-session` or compatible display manager | Niri backend, event stream, native KDL and graphical session target. Do not configure the user’s login manager automatically. |
| `quickshell` (compatible 0.3.x/API and Qt modules) | Main shell, idle instance, PAM lock, notifications, PipeWire/MPRIS/UPower/Bluetooth services and tray. Preflight `qs` and module imports. |
| `python`, `python-pillow`, `bash`, `/bin/sh`, `jq`, standard Arch utilities | Palette processing/migration/config transactions/wallpaper scripts/state. Python GObject is separately needed for portal folder picker. |
| `matugen`, `awww` | Dynamic palette generation and default image wallpaper daemon/restore. Current host has `matugen-bin`, while repository recommends official `matugen`; install policy should explain the package/source rather than silently replace it. |
| `gtk3`/GTK launcher stack | Launcher invokes `gtk-launch` for installed desktop entries; file manager and GTK portal theme also use GTK3. |
| Qt Multimedia QML module + Qt 5Compat GraphicalEffects QML module | `Wallpaper.qml` and `Lockscreen/LastOfUs.qml` import multimedia; lock theme also imports `Qt5Compat.GraphicalEffects`. Verify Arch package naming/Quickshell Qt ABI. Current host has `qt6-multimedia`, multimedia FFmpeg backend, and qt6-5compat. |

### SPARROW DEFAULT EXPERIENCE — selected, replaceable defaults

| Package/tool | Why / caller |
|---|---|
| `kitty`, `fish`, `starship` | Chosen Super+T terminal, Kitty shell, Starship prompt. `zoxide`/`fastfetch` are separate conveniences, not needed for core. |
| `ttf-jetbrains-mono-nerd`, `inter-font` | Default terminal and UI typography. Outfit is bundled for lock UI with OFL notice. |
| `thunar`, `tumbler`, `gvfs`, `udisks2` | Chosen file manager, thumbnails, Gio remote/trash/device services. GVFS includes its UDisks monitor on Arch; do not refer to nonexistent separate `gvfs-udisks2` package. |
| `adw-gtk-theme`, GTK3/GTK4 where applications need them | System base from which Sparrow generates its GTK theme. No home-local `adw-gtk3` fallback is required. GTK application toolkit dependencies may already be pulled by apps. |
| `xdg-desktop-portal`, `xdg-desktop-portal-gtk`, `python-gobject` | Folder chooser and portal file picking; ensure Niri-specific routing. ScreenCast backend is a distinct optional group below. |
| `firefox` | Current default browser key. If user declines it, installer should offer a replacement/default shortcut plan instead of leaving a knowingly dead bind. |
| Bibata Modern Ice cursor package | Intended cursor style/size; upstream [Bibata](https://github.com/ful1e5/Bibata_Cursor) currently points users to non-core package channels. Offer as optional and never replace an existing theme without consent. |

### OPTIONAL FEATURE PACKAGES

| Package/tool | Feature / caller |
|---|---|
| `ffmpeg` | Video/GIF still extraction, media dimensions and thumbnail workflows. Static images remain usable without it. |
| `mpvpaper` (AUR/source availability must be confirmed) | Video wallpaper playback; image wallpaper remains default if omitted. |
| `gpu-screen-recorder`, `slurp`, `xdg-desktop-portal`, `python-gobject`, PipeWire | Recording, region/window selection and folder chooser. Hardware/portal compatibility must be checked. |
| `wlsunset` | Night Light, off by default. |
| `cava` | Optional visualizer. |
| `rishot`, `grim`, `wl-clipboard` | Separate screenshot application and its Niri capture/clipboard paths. `rishot` is not bundled; resolve through PATH. |
| `curl` | Optional weather and wallpaper search/download. No local wallpaper feature requires network. Explain weather’s IP geolocation. |
| `imagemagick` | Optional wallpaper search format identification/convenience; not basic local wallpaper display. |
| `xdg-utils`, `libnotify` | Open output directory / external notification feedback helpers; core Quickshell notifications remain separate. |
| `hyprlock` | Optional fallback only. Primary lock is Quickshell + PAM. Do not install a Hyprland compositor or bring back abandoned artwork. |
| `thunar-archive-plugin` plus one archive handler | Optional archive context menus; neither is installed on the current host. |

### HARDWARE-SPECIFIC / SYSTEM SERVICE PACKAGES

| Package/tool | Requirement |
|---|---|
| `pipewire`, `wireplumber`, `pipewire-pulse` | Audio and recording services. Respect the host’s chosen sound system/session. `wpctl` comes from WirePlumber. |
| `networkmanager` (`nmcli`) | Wi-Fi feature; only enable if it is the chosen network service. |
| `bluez`, `bluez-utils` | Bluetooth feature/`bluetoothctl`; service and adapter optional. |
| `upower` | Battery data and some power reporting; device-dependent. |
| `brightnessctl` | Internal backlight if exposed; hardware-specific. |
| `ddcutil` | External DDC display brightness only; optional, absence remains quiet. |
| `nvibrant` plus NVIDIA driver stack | NVIDIA vibrance only; vendor/package support varies. |
| `nvidia-utils` (`nvidia-smi`) | NVIDIA GPU stats only. |
| GNOME portal + PipeWire | Niri portal screen sharing; may bring extra GNOME/Nautilus dependencies. User can choose another supported capture mechanism if sufficient, but must be tested. |
| A Polkit authentication agent | Needed if graphical applications require authentication. Select/detect one; Polkit daemon alone is not a UI. |
| `gnome-keyring` or `oo7-portal` | Secret portal only if chosen applications need secrets. Current live preference is inconsistent with installed packages. |
| `xwayland-satellite` + Xwayland | Optional compatibility for legacy X11 clients. |

### DEVELOPMENT ONLY / EXTERNAL-SEPARATE TOOLS

| Item | Treatment |
|---|---|
| `quickshell/minimal-test.qml`, Python unit tests, Node monitor tests, QML tooling, shell format/lint tools | Developer/test payload only; not installed as services. |
| Rishot | Separate upstream app; repository records its command/PATH contract and dependency boundary. No vendoring or unattended third-party installer. |
| `niri`, Quickshell, Matugen, awww and user units | Packages/runtime dependencies listed above, not cloned source code. |
| AUR packages | Separate explicit opt-in and user-controlled build/install consent. No AUR helper bootstrap. |

Nerd Font glyph use in Kitty/Starship is intentional; it is not the removed decorative CJK mode and does not justify re-adding a “glyph mode” package or UI. PAM support comes from the compatible Quickshell build and system PAM stack; do not install or edit a second PAM stack as a normal user-level dependency. The current Arch [Qt Multimedia](https://archlinux.org/packages/extra/x86_64/qt6-multimedia/) and [Qt 5Compat group](https://archlinux.org/groups/x86_64/qt6/) records list the modules imported by the lock/wallpaper components.

## 6. Installer architecture sanity — no installer created

The future installer should be transactional and conservative. The ordering below reflects actual file/service dependencies and user ownership:

1. **Preflight, no writes:** detect Arch/CachyOS, architecture, Niri/Quickshell versions, session/target, `systemd --user`, XDG paths, installed portal, existing user services, disk space and command availability. Refuse unsupported session/backend combinations clearly.
2. **Choose installation scope:** explain Sparrow replaces/owns only named files/surfaces; ask whether to keep current DM, use current Niri session, and which optional feature groups to select.
3. **Build a complete plan:** show package list, AUR distinction, file copies/merges, systemd units to enable, MIME/default-handler changes, portal changes, and services that would be started. Never request root implicitly.
4. **Resolve system-service conflicts:** detect PipeWire/NetworkManager/BlueZ/UDisks/Polkit/portal ownership and user’s existing Polkit agent. Do not enable a competing service. Require explicit consent for system package manager operations and system-level login changes (recommended: do not offer login-manager switching in v1).
5. **Install selected packages only:** official repo group first; separate explicit AUR/source prompt. Do not bootstrap an AUR helper or run a remote install script.
6. **Back up and stage:** snapshot every destination before replacement; stage files in temporary locations; preserve permissions; keep a manifest for rollback. Existing user config is not equivalent to an empty directory.
7. **Deploy canonical Quickshell runtime:** install repository runtime at `~/.config/quickshell/sparrow` (or a clearly managed stable path). In development, a symlink to source is intentional; on user install, do not depend on `~/Projects`.
8. **Integrate Niri carefully:** keep a user-owned `~/.config/niri/config.kdl`; if absent, seed Sparrow root defaults, otherwise offer a documented include/merge instead of replacement. Deploy only tracked static fragments. Never copy this host’s outputs or generated/user fragments.
9. **Apply systemd user units:** install main/idle/wallpaper units under `~/.config/systemd/user`, daemon-reload, verify unit conditions/paths, then enable only units user approves. Don’t start a second shell instance during an active session.
10. **Portal choice:** merge only the GTK FileChooser fragment into the existing `niri-portals.conf`; preserve all other routes. Keep `GTK_THEME=Sparrow` scoped to the portal GTK service. Enable Sparrow's Polkit unit only if no existing agent/autostart owns that role.
11. **Deploy environment and app defaults:** merge rather than overwrite cursor env, Kitty, Fish, Starship, GTK theme selector and file-manager desktop entry. Respect pre-existing user choices and MIME associations.
12. **Install generated/local assets:** generate GTK theme/icons and palette-dependent templates under XDG data/config paths. Never install generated colors or selected wallpaper as if portable config.
13. **Migrate existing state once:** run the safe migration helper with its lock/backup semantics; preserve current flags, wallpaper maps and generated state. Do not initialize over established state.
14. **Handle wallpaper defaults:** seed only the bundled Sparrow Default when no prior selection exists. Do not overwrite/import personal images; validate `awww` and optional `mpvpaper` separately.
15. **Onboarding:** show supported defaults, chosen packages, controls, feature limitations and optional system integrations; don’t enable Night Light or alter gamma/display state.
16. **Validate staged result:** Python tests, QML parse/runtime load, shell syntax, Niri validation, unit verification, desktop entry and portal config checks before reload/start.
17. **Activate only after a user-approved plan:** reload user manager and start units if safe; do not restart Niri or lock/log out automatically. For live session, detect existing instances and defer tests that could duplicate them.
18. **Verify and rollback:** collect service/log status and installed-file manifest; if validation/activation fails, restore backups and prior enablement state, not user-generated wallpaper or display data.

### Destination ownership matrix

| Destination | Ownership | Safe installation policy |
|---|---|---|
| `~/.config/quickshell/sparrow` | SPARROW OWNS runtime entry; USER OWNS modifications/state within mutable stores | Managed deployment with file manifest. Preserve state/cache outside source tree. Development symlink only when explicitly selected. |
| `~/.config/niri/config.kdl` | USER OWNS / MERGE-PRESERVE | Create from Sparrow defaults only if absent; otherwise propose include integration and back up. Never replace silently. |
| `~/.config/niri/sparrow/appearance.kdl`, `binds.kdl`, `input.kdl`, `window-rules.kdl` | SPARROW OWNS portable defaults; MERGE/PRESERVE user edits | Install as tracked defaults with versioned backups; user overrides belong in optional user fragments. |
| `user-appearance.kdl`, `user-input.kdl`, `user-binds.kdl` | USER OWNS | Never overwrite. Sparrow writes through validated transaction after user action. |
| `display-outputs.kdl`, `display-binds.kdl` | USER/MACHINE OWNS; Sparrow generates | Generate on this machine only; never copy from repository/test host. |
| `generated-colors.kdl` | SPARROW GENERATES | Recreate from selected wallpaper/palette; do not track or transfer. |
| `~/.config/systemd/user/sparrow-*.service` | SPARROW OWNS named units, USER controls enablement | Back up same-name files; do not overwrite unrelated units; enable only after path/unit verification and consent. |
| `~/.config/systemd/user/xdg-desktop-portal-gtk.service.d/10-sparrow-theme.conf` | OPTIONAL SPARROW integration | Install only when GTK portal is used; preserve/merge existing drop-ins. Scope theme env to this service only. |
| `xdg-desktop-portal/niri-portals.conf.fragment` | SPARROW-OWNED merge input | Adds only GTK FileChooser preference. |
| `~/.config/xdg-desktop-portal/niri-portals.conf` | USER OWNS / MERGE-PRESERVE | Merge only needed entry and retain all unrelated routes. Never replace the whole file. |
| `~/.config/environment.d/90-cursor.conf` | MERGE/PRESERVE user preference | Set default only if unset/consented; never force Bibata over selected cursor. |
| Kitty/Fish/Starship configs | USER OWNS with optional Sparrow include/default | Install defaults only when absent or through clear backup/include flow. Keep dynamic Kitty include generated. |
| `~/.config/sparrow/hyprlock.conf` | USER OWNS; optional fallback | Seed simple fallback only if explicitly enabled and file absent. Never overwrite existing config. |
| `~/.local/share/themes/Sparrow`, `~/.local/share/icons/Sparrow` | SPARROW GENERATES | Recreate generated assets; never treat current cache/output as source. Base `adw-gtk-theme` remains a system package. |
| `~/.local/share/applications/sparrow-files.desktop` | SPARROW OWNS entry; USER OWNS default association | Install entry, but do not silently change directory MIME default. |
| `$XDG_STATE_HOME/sparrow-shell/` | USER OWNS; Sparrow manages schema | Preserve flags, wallpaper selection/maps, onboarding, history and migration backup; schema migration must be additive/backup-safe. |
| `$XDG_CACHE_HOME/sparrow-shell/` | SPARROW GENERATED, disposable | Cache only; safe to rebuild, but never delete broad user cache directories. |
| `$XDG_DATA_HOME/sparrow-shell/wallpapers/` and other imported personal images | USER OWNS | Do not seed from development user’s personal wallpaper directory; only bundled default is portable. |
| `/etc/greetd`, `/etc/pam.d`, display manager config, system services | SYSTEM/USER OWNS | Out of scope for v1 installer unless a separate explicit system-level opt-in is designed and recovery-tested. |

## 7. Final repository search: legacy, dead code, portability

| Match/finding | Classification | Evidence / decision |
|---|---|---|
| `scripts/migrate-state.py`, old `ricelin` XDG source names | MIGRATION/PROVENANCE | Explicit locked migration with backups; finite compatibility reader, no requirement for Ricelin checkout. Keep until migration policy is deliberately retired. |
| `LICENSES/Ricelin-MIT.txt`, Ricelin-origin comments in `Workspaces.qml`/`Dyn.qml`/docs | MIGRATION/PROVENANCE | Attribution/schema/algorithm lineage only; not runtime calls. Keep and preserve accurate licensing. |
| `WALLPAPER-PALETTE.md` link to end-4 `dots-hyprland` | KEEP / provenance | Link identifies algorithmic research source. No runtime Hyprland dependency; don’t remove attribution merely because the reference project is Hyprland-based. |
| `sparrow-lock` and `hyprlock/hyprlock.conf` | KEEP / FALLBACK | Hyprlock is invoked only if primary Sparrow IPC is unavailable; default fallback is simple, has no old Sparrow avatar/palette include system. Keep optional and not a compositor dependency. |
| `starship.toml` `stashed` field | KEEP | Starship Git-status symbol for Git stashes; unrelated to removed special workspaces. |
| `GlyphIcon.qml` | KEEP | Generic SVG/path icon drawing used by Sparrow. Not the removed CJK/decorative glyph mode. |
| “Washi” text in `Tooltip.qml` and `shell.qml` comments | CLEAN BEFORE V1 (tiny docs/comment cleanup) | Stale design-language comments; no Washi package or code dependency. Cosmetic source terminology only. |
| `quickshell/minimal-test.qml` | DEVELOPMENT-ONLY / exclude from runtime | No service/import/caller; standalone fixture. Retain for contributor diagnostics or remove in later release cleanup; no runtime risk if excluded. |
| `/tmp/sparrow-wp-preview-*.webm` | INVESTIGATE / minor portability hygiene | Downloaded wallpaper search preview cache is deterministic under global temp, not XDG cache. Avoids repository path; consider moving to `$XDG_CACHE_HOME` during a future scoped cleanup, not blocker. |
| `/tmp/sparrow-wallpaper-$output` mpvpaper IPC socket | INVESTIGATE / minor runtime hygiene | Predictable temporary IPC socket; currently local-user process integration. Prefer a private `$XDG_RUNTIME_DIR` subdirectory in a focused follow-up, but no active cross-user issue demonstrated in this audit. |
| `matugen-bin` installed locally, while inventory prefers `matugen` | CLEAN BEFORE V1 package-note accuracy | Current host package is AUR-style `matugen-bin 4.2.0-1`; Arch Extra publishes `matugen`. Keep the default source/package policy explicit and verify CachyOS resolution. |
| No `/home/vrabko` or checkout absolute path in active tracked runtime | KEEP / portable | The only live runtime path is the intentional dev symlink; service/source paths use `%h`, XDG, `$HOME`, Quickshell-relative roots or PATH. User config contains personal absolute locations only when generated from machine data. |
| Removed Game Mode, updater, AppImage manager, package installer, special workspaces, glyph-mode settings, old custom Hyprlock avatar/palette | KEEP REMOVED | Search found no active feature implementation. Don’t resurrect. |
| Generated/user data in live Niri fragments and caches | KEEP OUT OF GIT | Display arrangement, selected wallpaper, generated palette, user appearance/input/keybinds and backups are mutable host data. |
| Project-wide license and component map | RESOLVED for development baseline | Root `LICENSE` is GPL-3.0-only for the combined program; `THIRD_PARTY.md` and adjacent notices preserve separate Ricelin MIT, Qylock/Papirus GPL-3.0, Outfit OFL, and author wallpaper permission. |

Search did not find active Hyprland window/workspace properties or IPC, old `~/.config/hypr/scripts` calls, development checkout paths, Ricelin updater, AppImage/package installer, special workspace state, old avatar architecture, or decorative glyph mode. Hyprland’s name remains only in provenance/fallback/this review context.

## 8. Recommendation sheet

### 1. SHIP AS-IS

- Niri-native workspace/window backend and the active core Pill/morphing shell.
- Launcher with ordinary `.desktop` discovery, wallpaper picker/restore and per-output image wallpaper behavior.
- Dynamic Matugen architecture and selected Auto/Tonal/Source/Mono + Auto/Dark/Light controls.
- Niri Look, Display, Input and Keybind surfaces, subject to per-user config preservation.
- Quickshell session lock + PAM, Qylock Last of Us adaptation, wallpaper/video integration and lock text Auto/Light/Dark. Keep its GPL-3.0 notice and identify adapted files.
- Main/idle/wallpaper user services, audio/media/tray/notification/power surfaces, Mixer optional-backend guards, and accepted Thunar live-theme-refresh limitation.
- GTK theme generation from system `adw-gtk-theme`, scoped portal theme, Sparrow icon subset, Kitty/Fish/Starship defaults, and the bundled author-created SpaceEngine wallpaper.
- Intentional removal of Ricelin’s legacy feature groups; do not add clipboard UI, package manager, dashboard, or browser theming.

### 2. IMPLEMENTATION REQUIREMENTS (NOT START BLOCKERS)

The installer should implement the documented safety policies: merge the portal
preference without replacing user routes; detect existing Polkit agents and
autostart; preflight package and Qt-module availability; back up conflicting
files; and validate/rollback staged changes. Exercise those paths in a
disposable user or VM. These are installer implementation and acceptance-test
tasks, not prerequisites to beginning installer development.

### 3. OPTIONAL POLISH BEFORE INSTALLER

- Small stale “Washi” comment cleanup and omission of `quickshell/minimal-test.qml` from the installed payload.
- Move deterministic `/tmp` wallpaper preview/socket paths to private XDG cache/runtime directories in a narrow follow-up.
- Clarify Weather’s IP-geolocation network request in onboarding and let users keep it unused.
- If desired, one bounded Pill distinctiveness pass—not a new design system. Otherwise ship the present design.
- Optional Thunar archive plugin/handler and more codec thumbnailers based on explicit user interest.

### 4. DO NOT ADD

- A custom Sparrow login greeter in v1, a Sparrow package/AUR/AppImage manager, updater, clipboard UI, task/calendar dashboard, AI assistant, or weather-first home screen.
- Ricelin Stash/Private/Minimized/special-workspace model, Game Mode, decorative CJK mode, or the abandoned Sparrow Hyprlock art/avatar pipeline.
- Browser theming, automatic login-manager/PAM/system service rewrites, or silent AUR helper installation.
- A pile of toggles for every Niri option. Keep Look to rice-level settings with native validation.

### 5. VISUAL IDENTITY DECISION

Sparrow is sufficiently coherent and technically distinct to package as a focused v1; the strongest visual inheritance is the exact central Pill capsule/morph geometry, not the whole current feature set. Do not hold the installer for design work. If the owner wants one visual change, the highest return/lowest risk is to personalize the resting Pill silhouette and its spacing/status alignment while preserving its morph behavior. Restrained surface-token cleanup is second. Avoid broad blur, glass everywhere, or heavy transparency without multi-output/video contrast testing.

### 6. GREETER DECISION

**Keep greeter setup outside Sparrow v1.** Retain the user’s existing DM; document TTY + `niri-session`. If asked later, present `greetd + tuigreet` as the simple optional route and ReGreet as graphical but single-monitor. Noctalia Greeter is a separate greetd + bundled-wlroots project, not a Quickshell component; its additional compositor/system/PAM/recovery surface is disproportionate for Sparrow. Sources: [tuigreet upstream](https://github.com/tuigreet/tuigreet), [ReGreet upstream](https://github.com/rharish101/regreet), [Noctalia Greeter upstream](https://github.com/noctalia-dev/noctalia-greeter) and its [packaging notes](https://github.com/noctalia-dev/noctalia-greeter/blob/main/PACKAGING.md).

### 7. FINAL V1 COMPONENT LIST

- Sparrow Quickshell runtime: Pill, normal Niri workspace display, Launcher, wallpaper, Look/Appearance, Display, Input, Keybinds, Mixer, Recorder, Power, Settings/onboarding, lock/idle, OSD, Notifications, System Tray, Media, Wi-Fi/Bluetooth/Battery, System Monitor, and optional Weather.
- Niri portable defaults and validated user fragments: appearance, normal keybinds, input, window rules; optional generated palette and machine/user fragments kept separate.
- Four user units: shell, idle, wallpaper restore/daemon, and conditional Polkit agent, plus narrowly scoped GTK portal theme drop-in.
- Wallpaper/palette pipeline, system-derived GTK base, generated Sparrow GTK theme/icons, Kitty/Fish/Starship defaults, limited Papirus-derived sidebar icon assets, cursor environment default, default file-manager desktop entry, and author-created default wallpaper.
- Qylock-derived Quickshell/PAM lock as primary; simple optional Hyprlock fallback.
- Documentation, migration helper, tests, licenses, package manifest and onboarding. Rishot remains separate/optional, not a bundled Sparrow component.

### 8. FINAL DEPENDENCY GROUPS

Use the groups in section 5: **MINIMUM REQUIRED**, **SPARROW DEFAULT EXPERIENCE**, **OPTIONAL FEATURE PACKAGES**, **HARDWARE-SPECIFIC / SYSTEM SERVICE PACKAGES**, **DEVELOPMENT ONLY**, and **EXTERNAL/SEPARATE TOOLS**. Keep package-manager calls explicit; official Arch packages preferred; AUR and system-service changes separately opt-in.

### 9. REMAINING INSTALLER BLOCKERS

**None identified. Sparrow is READY TO START INSTALLER DEVELOPMENT.** Portal
merge behavior, conflict handling, package detection, rollback, and clean-user
installation tests are implementation/acceptance work for the installer. The
current portal route and scoped GTK theme are verified; the Polkit agent is
installed, active, and registered. This is not a claim that Sparrow is
bug-free or that a clean installation has already been tested.

### 10. MY DECISIONS NEEDED

1. Should screen-sharing portal support be a default optional package group, or should v1 limit its portal offer to GTK FileChooser? Recommendation: expose it as a separately selected capability because GNOME portal adds system dependencies.
2. Should Sparrow installer offer an optional Thunar archive integration? Recommendation: keep it opt-in and omit from minimal/default install unless you want archive context menus.
3. Do you want one small Pill-shape identity pass before v1, or ship current geometry? Recommendation: ship current version and revisit only after a user-visible comparison.

### 11. RECOMMENDED NEXT STEPS

1. Begin installer development from the install inventory and ownership matrix; keep greeter/login-manager changes outside scope.
2. Build dry-run planning, conflict backups, portal merge, agent detection, validation, and rollback into acceptance criteria.
3. Test in a disposable Arch/Niri user or VM with pre-existing configs, optional packages absent, and failure/rollback cases.
4. Run a true clean-user install and upgrade/migration rehearsal; the current development symlink/live desktop is not fresh-install proof.
