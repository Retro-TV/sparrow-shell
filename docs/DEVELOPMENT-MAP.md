# Sparrow Shell development map

This is a navigation guide to the current repository. **Development workflow
policy lives in `AGENTS.md`; this document does not define a second workflow.**
For portable-source/runtime ownership, use [`SOURCE-OF-TRUTH.md`](SOURCE-OF-TRUTH.md),
[`SOURCE-OF-TRUTH.json`](../SOURCE-OF-TRUTH.json), and
[`PORTABILITY-ARCHITECTURE.md`](PORTABILITY-ARCHITECTURE.md).

## Architecture at a glance

Niri owns compositor behavior, outputs, workspaces, and window management.
Quickshell owns Sparrow's shell UI, settings, Pill, and desktop surfaces.
Tracked configuration and scripts integrate the remaining desktop services;
`installer/` deploys the portable source and preserves machine/user state.

## Repository layout

| Path | Purpose |
| --- | --- |
| `quickshell/sparrow/` | Quickshell runtime: shell entry point, surfaces, shared components, icons, and bundled assets. |
| `quickshell/sparrow/Singletons/` | Shared runtime services/state, including Flags, Theme, Niri, Walls, devices, weather, and media. |
| `quickshell/sparrow/scripts/`, `lib/` | Runtime helpers and reusable JS modules. |
| `quickshell/sparrow/systemd/` | User service units shipped with the runtime. |
| `niri/` | Niri root config, portable fragments, and default input seed. |
| `installer/` | Installer implementation, package profiles, helper modules, and focused tests. |
| `kitty/`, `fish/`, `starship/`, `gtk/`, `icons/`, `applications/`, `environment.d/`, `greetd/`, `hyprlock/`, `xdg-desktop-portal/` | Supporting desktop configuration and assets. |
| `docs/` | Architecture, install, dependency, audit, and user-facing project documentation. |
| `SOURCE-OF-TRUTH.json` | Machine-readable tracked-source/deployment contract. |

## Where to start

| Work area | Start here |
| --- | --- |
| Shell startup and composition | `quickshell/sparrow/shell.qml` |
| Pill behavior and per-display settings | `quickshell/sparrow/Pill.qml`, `PillSettings.qml`, `PillSurface.qml`, `Singletons/Flags.qml` |
| General settings and appearance | `Settings.qml`, `Appearance.qml`, `Look.qml`, `Singletons/Theme.qml`, `Singletons/Flags.qml` |
| Runtime state and ownership | `quickshell/sparrow/Singletons/Flags.qml` and [`PORTABILITY-ARCHITECTURE.md#current-runtime-and-ownership`](PORTABILITY-ARCHITECTURE.md#current-runtime-and-ownership) for state/cache ownership. |
| Wallpaper library, applying wallpapers, and output mapping | `Wallpaper.qml`, `Singletons/Walls.qml`, `scripts/wallpaper.sh`, `scripts/wallpaper-thumbs.sh` |
| Wallhaven search and API key | `Wallpaper.qml` owns search UI/results; `scripts/wallpaper-search.sh` calls providers and downloads; `scripts/wallhaven-key.py` stores/reads the optional key; `ApiKeys.qml` manages API-key settings; related checks are in `installer/test_wallpaper_search_api.py` and `installer/test_wallhaven_key.py`. |
| Palette generation | `scripts/wallcolors.py`, `WALLPAPER-PALETTE.md`, and the wallpaper/Niri transaction helpers. |
| Niri configuration and transactions | `niri/config.kdl`, `niri/sparrow/`, and `quickshell/sparrow/NIRI-CONFIG-TRANSACTIONS.md` plus `scripts/niri-config-transaction.py`. |
| Packages and deployment | `installer/package-sets.json`, `installer/sparrow_installer.py`, `install.sh`, `docs/DEPENDENCIES.md`, `docs/INSTALL-INVENTORY.md` |

The wallpaper picker combines a local user library with bundled defaults and
online search. Wallhaven controls include category and purity filters, sorting,
and a toplist period. Search settings live in Sparrow Flags; the optional API
key is kept separately under private per-user state. Search results/downloads
and local wallpaper application pass through the wallpaper helpers. Personal
images, API keys, generated palette output, and saved wallpaper choices are
user/runtime data; their ownership is described in the references above.

## Source and runtime state

Repository files are not the installed desktop. The installer copies the
tracked Quickshell tree to `~/.config/quickshell/sparrow` and deploys other
tracked configuration to their documented destinations. Runtime preferences
and secrets belong in user state; generated palettes and thumbnails belong in
cache; monitor and hardware details are discovered on the target machine;
personal wallpapers and recordings remain user-owned. These ownership
boundaries are described in the source-of-truth and portability documents.

For runtime deployment or state ownership, consult
[`PORTABILITY-ARCHITECTURE.md`](PORTABILITY-ARCHITECTURE.md) and
[`INSTALL-INVENTORY.md`](INSTALL-INVENTORY.md). For package requirements, see
[`DEPENDENCIES.md`](DEPENDENCIES.md). The repository's supported deployment
entry point is `./install.sh`.
