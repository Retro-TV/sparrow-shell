# Troubleshooting

## The pill or lock screen is missing

```sh
sparrow-shell status
sparrow-shell restart all
sparrow-shell log pill
```

Confirm that `qs`, `jq` and the scripts under `~/.config/hypr/scripts` are
available.

## Firefox stays on its default theme

Install and enable the Pywalfox Firefox extension. Then run:

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
