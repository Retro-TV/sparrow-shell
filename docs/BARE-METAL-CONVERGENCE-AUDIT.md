# Bare-metal CachyOS convergence audit

Reference: the active Sparrow desktop on the external SSD, compared with the
files and behavior deployed by installer baseline `9c0e550`. This report
records the live-vs-source findings that motivated the convergence fixes; it
does not copy generated or host-specific state into the repository.

## Ownership boundary

| Live input | Live observation | Installer/source counterpart | Decision |
| --- | --- | --- | --- |
| `~/.config/niri/config.kdl` and included `sparrow/*.kdl` | Loads Sparrow appearance, generated colors, optional output/user fragments, window rules, binds and input. Active `user-appearance.kdl` contains Look-produced values. | `niri/config.kdl` → `sparrow/entry.kdl` and tracked fragments. | Track product defaults; never copy display outputs, generated colors, or user fragments. |
| Niri display/output state | `eDP-1`, 1920×1080 physical, 1536×864 logical at 1.25 scale on the audit host. | Optional `display-outputs.kdl`/`display-binds.kdl`. | Machine state; do not track. |
| Niri appearance override | Live user fragment: top strut `-6`, 12px geometry radius with clipping, animation slowdown `1.5`; base repository fragment already supplies gaps 6, side/bottom struts 12, 50% column width, centering, border/shadow, presets, wallpaper layer rules and Overview styling. | These three defaults were absent from tracked portable fragments. | Promote the established Sparrow defaults into tracked Niri defaults, while keeping user overrides separate. |
| Niri palette | Live generated active/inactive border colors are wallpaper-derived. | `wallcolors.py` writes optional `generated-colors.kdl` after static appearance. | Generated state; preserve generation and precedence, do not copy current hex values. |
| Sparrow QML runtime | Canonical config path resolves to the development checkout; main + idle instances are healthy. Installer copies repository runtime to XDG data and creates the canonical config entry. | `quickshell/sparrow/**`. | Current source is the portable runtime; do not capture live cache/state. |
| Sparrow flags | Live saved `uiFont` is `Inter Black`; UI scale 1 and palette/appearance choices are user state. | Empty `Flags.uiFont` currently falls back to regular Inter. | Use Inter Black as the code-level fresh-install/reset default; do not seed flags or other personal settings. |
| GTK appearance | Global GTK theme remains Adwaita; global icon theme is Sparrow. Sparrow colors are scoped to Thunar, pavucontrol and GTK FileChooser. GTK3/4 CSS is generated from the current Matugen palette. | Installer deploys the Sparrow icon/theme scaffolding, portal routing and scoped GTK_THEME overrides, but did not choose the Sparrow icon theme on a blank account. | On a fresh account only, select Sparrow icons if no explicit user icon-theme value exists. Do not set global GTK_THEME or change global GTK colors. |
| Kitty / Fish | Active Kitty and Fish configs match repository source. Kitty's current colors are generated separately by the wallpaper pipeline. | Tracked `kitty/kitty.conf`, `fish/config.fish`; generated Kitty palette is a sibling include. | Portable config is already represented; colors remain generated. |
| Sparrow desktop file handler | `inode/directory` currently resolves to `sparrow-files.desktop`. | Installer deploys the Sparrow Files desktop entry but intentionally does not take over MIME defaults. | Preserve policy; do not change MIME associations during convergence. |
| CachyOS Hello | Package owns `/etc/skel/.config/autostart/cachyos-hello.desktop`; the fresh account inherited it and launched the welcome app. No global autostart override was found. | Installer had no targeted user-level suppression. | Add a narrowly scoped per-user `Hidden=true` override only for the verified CachyOS Hello desktop ID; leave distro files and other autostarts alone. |
| Cursor | Live Niri, GTK and environment use Bibata Modern Ice, size 24. The cursor package is not installed through pacman on this host; upstream documents an AUR route. | Installer selects Bibata only when its assets are detected, otherwise leaves the cursor default untouched. | Keep manual AUR policy and sane fallback; do not install or add an AUR helper. |
| Wallpaper/palette startup | `sparrow-wallpaper.service` starts a single awww daemon, restores per-output/global selection, and generates missing/stale palette outputs before the main shell service. | Tracked wallpaper unit is ordered before `graphical-session.target`; shell and idle units are ordered after it. Default wallpaper is bundled. | Existing bootstrap ordering is correct; retain generated colors, Kitty, GTK and icons as first-login output, not tracked state. |

## Effective defaults and generated state

Portable tracked sources already provide the 50% default column width,
single-column centering, gaps, borders/shadows, wallpaper backdrop rules,
Overview switcher styling, normal workspace bindings, app bindings, and scoped
GTK launchers. The canonical live output arrangement, generated border hexes,
selected wallpaper, palette cache, flags, font selection, and output-specific
wallpaper map remain outside tracked defaults.

Wallpaper bootstrap runs before `graphical-session.target` completes. It starts
awww and restores the selected wallpaper; the existing color pipeline then
creates Matugen JSON, Niri colors, GTK3/GTK4 styles, Kitty colors, and generated
icons if missing or stale. Sparrow's main Quickshell service starts after the
target. Niri can initially parse static fallback colors before wallpaper
initialization; its generated-color transaction reloads the validated config
after palette generation. This is an intentional short-lived first-frame
fallback, not missing persistent generated state.

## First-login failures explained

The visibly different Niri window geometry came from a user-generated Look
fragment that was not encoded in tracked defaults. The typography difference
came from a saved `Inter Black` flag while a fresh user fell back to regular
Inter. CachyOS Hello came from the CachyOS package's `/etc/skel` user autostart
file. The active Sparrow icon appearance also depended on a GSettings icon-theme
value absent on a blank user. These are distinct from display arrangements,
wallpaper selections, palette caches, and other personal state, which must not
be cloned from the SSD.

## Guardrails for convergence

- Installer updates replace unchanged installer-owned files, prompt before
  replacing genuine file edits, and retain backups/ownership data.
- Fresh defaults may initialize an unset icon-theme preference, but an explicit
  GSettings user value is preserved; uninstall resets only a Sparrow-owned
  value that remains unchanged.
- CachyOS Hello suppression is a per-user XDG autostart override for that one
  exact desktop entry. It does not edit `/etc/skel`, package files, or unrelated
  autostarts.
- No monitor arrangement, wallpaper, generated palette/cache, flags, GTK color
  theme, MIME association, or display-manager setting is seeded from this host.
