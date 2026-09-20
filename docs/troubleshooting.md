# Troubleshooting

## The pill or lock screen is missing

```sh
sparrow status
sparrow doctor
sparrow restart all
sparrow log pill
```

Confirm that `qs`, `jq` and the scripts under `~/.config/hypr/scripts` are
available.

## Sparrow commands are not found

Current installers place the public commands in `/usr/local/bin` as well as
`~/.local/bin`. From an older checkout, rerun the installer once:

```sh
cd ~/.local/share/sparrow-shell
git pull --ff-only
./install.sh --packages
```

The `sparrow`, `sparrow-shell`, and `sparrow-update` commands are then available
immediately without restarting the shell.

## The on-screen keyboard opens but does not type

Rerun `./install.sh --packages`. It replaces the session-dependent user daemon
with Sparrow's root-owned input daemon and a private socket belonging to the
desktop user. The installer performs a client connection test before it exits.
Check the result with:

```sh
systemctl status sparrow-ydotool.service
sparrow status
```

Sparrow's keyboard calls the `sparrow-ydotool-key` client rather than invoking
`ydotool` directly. This is required because distro builds disagree about the
default socket path, while Sparrow's private daemon always uses the current
user's runtime directory.

For touch-only access, tap the top pill to expand it and tap the keyboard icon.
`Super+K` and `sparrow keyboard` remain available when a physical keyboard or
terminal is convenient.

## Firefox stays on its default theme

Install and enable the [Pywalfox Firefox extension](https://addons.mozilla.org/firefox/addon/pywalfox/). The native helper is not the browser extension. Then run:

```sh
pipx install pywalfox
pywalfox install
pywalfox update
```

Use the extension's fetch/update action once inside Firefox.

## Spotify or Spicetify fails with permission denied

Close Spotify and rerun:

```sh
./install.sh --apps
```

The installer grants only the current user access to `/opt/spotify` through an
ACL when that path is present. Flatpak Spotify is not supported by this config.

## Vesktop colors flicker while moving between workspaces

Keep Vesktop compositor transparency disabled. Sparrow Shell themes it with
opaque QuickCSS because native Electron transparency caused stale-frame and
workspace-move artifacts on the reference system.

## Thunar keeps the previous palette

New GTK windows pick up the generated theme immediately. If an already-open
Thunar window does not repaint, close that window and reopen it. Restarting the
GTK portal can also refresh long-lived theme state:

```sh
systemctl --user try-restart xdg-desktop-portal-gtk.service xdg-desktop-portal.service
```

## No wallpapers appear

Create `~/Pictures/Wallpapers` and place at least two supported images or videos
inside it. Then press `Super+C`, or run:

```sh
bash ~/.config/hypr/scripts/wallpaper.sh resolve
```

## An update refuses to run

`sparrow-update` intentionally stops when the checkout is dirty or its remote
does not match the official repository. Inspect with:

```sh
git -C ~/.local/share/sparrow-shell status
git -C ~/.local/share/sparrow-shell remote -v
```

Do not discard local changes until you know what they contain.
