# Sparrow Shell manual steps on a new machine

Some integrations intentionally cannot be copied as raw profile data.

## Firefox dynamic colors

The native helper alone does not theme Firefox. Install the Pywalfox extension
from [Mozilla Add-ons](https://addons.mozilla.org/firefox/addon/pywalfox/) in
the target Firefox profile, then install the helper if it is not already
present:

```sh
pipx install pywalfox
pywalfox install
```

Enable the extension and use its Fetch colors action once. The installer now
creates the Spotify prefs file, renders the current Ricelin wallpaper palette
immediately, and the wallpaper script calls `pywalfox update` thereafter.

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

The active monitor file uses portable defaults. Review GPU-specific options,
output names, and device-specific window rules after the first boot. The
motherboard RGB synchronization unit is hardware-specific and remains disabled
unless a user explicitly enables and adapts it.
