# Manual steps on a new machine

Some integrations intentionally cannot be copied as raw profile data.

## Firefox dynamic colors

Install Pywalfox in the target Firefox profile, then install the native helper
if it is not already present:

```sh
pipx install pywalfox
pywalfox install
```

Enable the Pywalfox extension and use its update/fetch action once. The
wallpaper script then exports the shared palette and calls `pywalfox update`.

## Spotify

The repository includes the selected local Spicetify themes and Marketplace
configuration, but intentionally does not include Spotify account data. Close
Spotify before applying Spicetify changes. The current setup does not reapply
Spotify automatically on every wallpaper change.

## Vesktop

Vesktop/Vencord must be installed separately if it is not available on the
target machine. The tracked settings keep QuickCSS enabled and compositor
transparency disabled because native transparency previously caused workspace
movement glitches.

## Hardware review

Review monitors, GPU-specific options, output names, and device-specific
window rules before applying them to a different computer. The repository
captures the current desktop layout as a reference, not a universal default.

