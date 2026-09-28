# Sparrow Installer v1 — bare-metal CachyOS test

Development checklist for a genuinely fresh install. Do not preconfigure Sparrow
or manually repair an unexpected installer failure: stop, record the output, and
send the diagnostics at the end of this document.

## Phase A — fresh CachyOS

- [ ] Record install type/options, network status, and whether Niri was already installed.
- [ ] Record every package manually installed before Sparrow. Ideally this is only Git if it was unavailable.
- [ ] Do not copy the old Niri/Quickshell config, Sparrow state, wallpapers, generated palette, units, portal overrides, app configs, cursor setup, GTK theme, Polkit setup, or Rishot from the external SSD.
- [ ] Confirm the external development SSD is disconnected and the test is on the disposable internal install.

## Phase B — installer

- [ ] Obtain the exact test branch/tree, enter the repository, and run `./install.sh` from a terminal.
- [ ] If Python is absent, confirm the installer's explicit Python bootstrap prompt; otherwise record the version already present.
- [ ] Record detected and missing package groups, every yes/no choice, backups/merge decisions, warnings/errors, and final instructions.
- [ ] Confirm required/default/optional package choices match what was intended; AUR items must remain manual.
- [ ] Stop on an unexpected error. Do not manually install the missing Sparrow packages, edit generated config, or rerun until the output has been captured.

## Phase C — first Niri login

- [ ] Verify a Niri session is available; log into it and confirm Niri starts.
- [ ] Confirm the Sparrow Pill appears and `qs list --all` shows the expected main shell and idle instances only.
- [ ] Verify the bundled Sparrow Default wallpaper, Dynamic palette, Auto palette preset, Auto appearance mode, Niri border colors, cursor, and Inter UI font.
- [ ] Confirm Getting Started appears for the new Sparrow state and no unexpected error dialogs appear.

## Phase D — core Sparrow features

- [ ] Launcher; Wallpaper picker; change image wallpaper; palette regeneration.
- [ ] Video wallpaper if its optional player is installed.
- [ ] Appearance, Look, Display, Input, Keybinds, Settings, and Mixer.
- [ ] Audio controls; internal brightness; Wi-Fi; Bluetooth; Battery; Calendar.
- [ ] Media controls with a real MPRIS player; tray; notifications; OSD.
- [ ] Night Light only if installed; Recorder only if its dependencies are installed.
- [ ] Open the Power menu, but do not select logout/reboot/shutdown until ready.

## Phase E — desktop integration

- [ ] Kitty, Fish, Starship, Thunar, GTK FileChooser, and pavucontrol launch and look usable.
- [ ] Check Bibata cursor across apps and scoped Sparrow GTK theme; verify an unrelated GTK app remains on its normal theme and Firefox remains unthemed.
- [ ] Trigger an ordinary Polkit-protected action only when safe; confirm the graphical prompt appears and authenticates.
- [ ] Test Rishot only if separately installed.

## Phase F — Niri behavior

- [ ] One 50%-width column centers; multiple windows in one column remain centered; two columns split normally.
- [ ] Test workspace scrolling, Alt+Tab, W/O scope switching inside Alt+Tab, and Super+Tab tabbed-column toggle.
- [ ] Test movement/navigation keybindings and wallpaper-colored borders.

## Phase G — lock and session

- [ ] Super+L opens the lock; test wrong then correct PAM authentication.
- [ ] Verify image wallpaper, video playback when applicable, Auto foreground on bright and dark wallpapers, and idle lock.
- [ ] Test suspend/resume only if safe for the laptop and current work.

## Phase H — persistence

- [ ] Reboot. Verify Niri and Sparrow autostart, wallpaper and settings persist, palette remains valid, onboarding does not reappear, and user services are healthy.

## Phase I — installer rerun

- [ ] Run `./install.sh` again. Check for duplicated Niri includes, portal routing, or service integration; reset preferences; repeated onboarding; or lost generated state.

## Phase J — conflict preservation

- [ ] Make one harmless edit to a documented user-editable managed config, rerun the installer, and verify it asks/preserves rather than silently overwriting the edit.
- [ ] Record the exact file and choice; restore the test edit only after recording the result.

## Phase K — uninstall

- [ ] Run `./uninstall.sh`. Verify Sparrow-owned integration is removed/restored, personal state remains, unrelated configuration survives, and packages are not removed.
- [ ] Verify backup paths and restoration behavior. Optionally reinstall once more and record results.

## Failure diagnostics to paste back

Run these from the affected user session; include the first error and the phase where it occurred:

```sh
systemctl --user status sparrow-shell.service sparrow-idle.service sparrow-wallpaper.service sparrow-polkit-agent.service --no-pager -l
journalctl --user -b -u sparrow-shell.service -u sparrow-idle.service -u sparrow-wallpaper.service -u sparrow-polkit-agent.service --no-pager
qs list --all
niri validate -c "${XDG_CONFIG_HOME:-$HOME/.config}/niri/config.kdl"
```

Also capture relevant installed/user config and installer ownership state:

```sh
find "${XDG_CONFIG_HOME:-$HOME/.config}/niri" -maxdepth 2 -type f -print
find "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user" -maxdepth 3 -type f -print
cat "${XDG_STATE_HOME:-$HOME/.local/state}/sparrow-shell/installer/manifest.json"
git status --short
```

If the installer fails before writing its manifest, paste the full terminal
output; it does not currently maintain a separate installer log file.
