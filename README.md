# Sparrow Shell

Sparrow is a wallpaper-aware Quickshell desktop for the Niri Wayland compositor.
Niri manages windows, workspaces, outputs and input; Sparrow provides the Pill,
launcher, wallpaper/theme pipeline, settings, mixer, recorder, notifications,
tray, media controls, power and session lock.

The installer targets current Arch Linux and CachyOS user sessions. It does
not install a greeter, replace a display manager, configure system PAM, manage
pacman/AUR for you, theme browsers, or copy personal wallpapers and monitor
layouts.

## Install

On a basic Arch/CachyOS install with internet, pacman, and an account allowed
to use `sudo`, obtain this repository with Git (install Git first if needed),
then run the installer from a terminal:

```sh
./install.sh
```

The installer can install Niri as part of its required package set. Python is
the bootstrap prerequisite; if it is missing, the launcher offers to install
it with `sudo pacman`. When Niri is already installed, the planned Niri graph
is validated before package changes. On a fresh system, required packages are
installed using `sudo pacman` and the staged Niri graph is validated before any
Sparrow/Niri files are deployed. Packages already installed are skipped and
never removed if a later validation or file operation fails. Sparrow never
bootstraps an AUR helper. The default package transaction installs the complete
tested Sparrow profile; Bibata Modern Ice v2.0.6 and Rishot are installed from
checksum-pinned upstream sources. `./install.sh --yes` accepts normal default-
yes operations but never overrides conflict, overwrite, or display-manager
replacement decisions. `mpvpaper` must be installed or available in configured
pacman repositories.

Existing Niri configuration remains the user's file. Sparrow validates a
staged include integration before applying it; Niri may automatically reload
that file when it changes. Existing monitor/output blocks, portal routes,
app settings, cursor selections and default handlers are preserved unless a
specific replacement is approved. Conflicting files are backed up before any
replacement.

On a clean system with no competing display manager, Sparrow prepares the
tested greetd/tuigreet login for the next boot after enabling tty2 recovery.
It asks before replacing another login manager or meaningful existing system
configuration, and never starts/restarts greetd during the current session.

The complete runtime is copied directly to the stable
`$XDG_CONFIG_HOME/quickshell/sparrow` entry point (normally
`~/.config/quickshell/sparrow`). It does not depend on the clone remaining in
place.

After installation, select the newly available Niri session in your login
manager, or use your existing `niri-session` workflow. Sparrow does not install
or choose a login manager. After installation, log out and back into Niri. The installer enables user
services but deliberately does not start/restart Sparrow, Niri, portals, or
other session services in the current session. Your first Niri login restores
the bundled Sparrow Default wallpaper if no saved selection exists, generates
the initial Matugen palette, and opens Getting Started only for a genuine new
Sparrow state.

## First login and keybinds

The central Pill is Sparrow's main entry point. The current default bindings
include:

- `Super+Space`: Launcher
- `Super+C`: Wallpaper picker
- `Super+B`: next wallpaper
- `Super+T`: Kitty
- `Super+E`: Thunar
- `Super+F`: Firefox
- `Super+O`: Niri Overview
- `Super+L`: Sparrow session lock
- `Super+Shift+S`: Rishot screenshot

Open Settings from the Pill to configure Niri appearance, displays, input,
keybindings, idle behavior, palette mode and lock foreground. Hardware and
optional features adapt to installed tools and connected devices.

## Update

Fetch the desired repository version, inspect its changes, then rerun:

```sh
git pull --ff-only
./install.sh
```

The installer updates only files it previously managed and that still match
its recorded version. Edited conflicts are kept unless you approve replacement;
the prior contents are retained in `$XDG_STATE_HOME/sparrow-shell/installer/backups/`.
After updating an active session, log out and back in to load the copied runtime
and portal environment cleanly. Niri config changes may be applied live after
the installer explicitly warns and you approve the merge.

## Restore / uninstall

Run:

```sh
./uninstall.sh
```

This disables Sparrow's user units and restores files changed by the installer
when it is safe to do so. It does not remove packages, user state, caches,
personal wallpapers, recordings, or screenshot files. If Sparrow is active,
the default is to leave its current processes running until the session ends;
the runtime entry remains in place while those processes may still use it.
After logging out, run `./uninstall.sh` again to finish removing those paths.
To close the shell and wallpaper immediately, explicitly use:

```sh
./uninstall.sh --stop-now
```

Backups remain under `$XDG_STATE_HOME/sparrow-shell/installer/backups/` for
manual recovery. User-edited files are preserved and listed rather than
blindly overwritten during restore.

## Troubleshooting

- Check user service logs with `journalctl --user -u sparrow-shell.service -b`.
- Inspect service state with `systemctl --user status sparrow-shell.service sparrow-wallpaper.service sparrow-idle.service`.
- Validate Niri configuration with `niri validate -c "${XDG_CONFIG_HOME:-$HOME/.config}/niri/config.kdl"`.
- If optional controls are unavailable, see [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md).
- Read [docs/INSTALL-INVENTORY.md](docs/INSTALL-INVENTORY.md) for file ownership and [docs/PORTABILITY-ARCHITECTURE.md](docs/PORTABILITY-ARCHITECTURE.md) for runtime paths.
- For the pre-release bare-metal rehearsal, follow [docs/BARE-METAL-INSTALL-TEST.md](docs/BARE-METAL-INSTALL-TEST.md).

Sparrow does not replace an existing display manager or choose the Niri session
for you. Select Niri in your current login manager, or use your existing
`niri-session` workflow. A first clean Arch/Niri graphical login should still
be tested in a disposable user or VM before treating the setup as release-ready.
