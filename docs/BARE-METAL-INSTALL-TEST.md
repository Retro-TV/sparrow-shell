# Sparrow Installer v1 — second bare-metal CachyOS test

This is the manual acceptance run after the first fresh-install attempt stopped
before installing packages. Keep this machine separate from the development
checkout and record the complete terminal output and every installer answer.

## Before running the installer

1. Boot the disposable internal CachyOS installation and connect to the
   network. Keep the external development SSD disconnected.
2. Do not copy Sparrow/Niri/Quickshell configuration, state, wallpaper
   selection, generated palette, user units, portal settings, app settings,
   cursor files, GTK theme, Polkit setup, or Rishot from another installation.
3. Check whether the previous attempt left any user integration behind. These
   checks are read-only; **do not delete or overwrite anything found**. If any
   Sparrow path exists, inspect it and report it before retrying:

   ```sh
   cfg=${XDG_CONFIG_HOME:-$HOME/.config}
   state=${XDG_STATE_HOME:-$HOME/.local/state}
   data=${XDG_DATA_HOME:-$HOME/.local/share}
   find "$cfg/niri" "$cfg/systemd/user" "$cfg/xdg-desktop-portal" \
     "$cfg/quickshell/sparrow" "$state/sparrow-shell" \
     "$data/sparrow-shell" -maxdepth 4 -print 2>/dev/null
   systemctl --user is-enabled sparrow-shell.service sparrow-idle.service \
     sparrow-wallpaper.service sparrow-polkit-agent.service 2>&1 || true
   ```

   The first failure was caused by checking optional package-dependent unit
   executables before the package transaction. Since it stopped at that
   preflight stage, before package resolution or file deployment, it should
   not have installed packages, created a backup/manifest, written Sparrow
   files, or enabled units. Confirm rather than assume. If anything is present,
   stop and send its paths/output; don't manually clean it up.

## Obtain and run the exact tree

If Git is missing, install only Git first. Then use the repository's intended
fresh-install flow:

```sh
sudo pacman -S --needed git
git clone https://github.com/Retro-TV/sparrow-shell.git
cd sparrow-shell
./install.sh
```

If the repository is already cloned on the test machine, verify it is the
intended revision before running `./install.sh`; do not copy the development
checkout's live config or state into the test home.

## Installer answers for the base v1 test

- If Python is missing, answer **yes** to the explicit Python installation
  prompt; otherwise record the installed version.
- Review the detected/missing required packages. Accept installation of the
  **required Sparrow runtime** packages.
- Accept the **recommended desktop apps, fonts, GTK theme and portal
  integrations** bundle to exercise the documented default desktop profile.
  The installer may omit the GNOME portal backend when an existing ScreenCast
  route is already configured; that preservation is expected.
- The optional feature-package group prompt is separate. For a full laptop
  feature test, answer **yes**, then choose Recording, Network/Bluetooth/
  Battery, Night Light, Audio Visualizer, Brightness Hardware, and Wallpaper
  Search as appropriate. These packages do not automatically enable competing
  system network services. `hyprlock-fallback` should be **no**: Quickshell is
  the primary lock. If you prefer a minimal baseline, answer **no** to the
  optional group prompt and record that choice.
- Approve the displayed official pacman package list only after reviewing it.
  Sparrow does not install AUR packages or bootstrap an AUR helper.
- Existing portal routes and config conflicts should be preserved/merged with
  an explicit explanation and backup. Stop if the installer proposes replacing
  unrelated choices or files.
- Record the cursor note. Bibata Modern Ice is manual AUR-only; when absent,
  Sparrow must leave the system/Niri cursor default alone rather than point at
  a missing theme.
- Rishot and `mpvpaper` are separate/manual. Their absence is expected unless
  you installed them independently. The screenshot key may therefore be
  unavailable; the installer should say so rather than fail the install.
- Do not install the optional Hyprlock fallback just to test Sparrow's primary
  Quickshell + PAM session lock.

On any unexpected error, stop. Capture the full output and phase; do not
manually install a missing Sparrow dependency, edit generated files, or rerun
until the failure is understood.

## First Niri login

After a successful install, log out of the installer session and choose Niri
from the login session menu. A reboot is not inherently required. If no display
manager is installed/configured, use a TTY and launch `niri-session` as the
normal user. Do not change the test machine's login manager merely for Sparrow.

Check the following before adjusting settings:

- Niri starts and the Sparrow Pill appears.
- `qs list --all` shows the main shell and idle instance, without duplicates.
- Wallpaper restoration runs automatically; default wallpaper and generated
  palette appear without opening the Wallpaper UI.
- The Getting Started experience appears once for new state.
- User services and logs are healthy; no optional-feature warnings are
  mistaken for core failures.
- GTK chooser theme is scoped to the portal service; unrelated GTK apps and
  Firefox are not globally forced to Sparrow colors.
- Polkit unit is enabled only if Sparrow supplied its agent; an existing agent
  should be preserved without a second agent.

## Feature acceptance checklist

- [ ] Launcher, normal dynamic workspaces, Wallpaper picker and wallpaper
      switching; palette update.
- [ ] Look, Appearance, Display, Input, Keybinds, Settings, Mixer and Power.
- [ ] Audio controls; available internal brightness; Wi-Fi/Bluetooth/Battery
      only when the corresponding optional packages/services/devices exist.
- [ ] Media controls with an MPRIS player; tray, notifications and OSD.
- [ ] Night Light and Recorder only if their optional dependencies were chosen.
- [ ] Kitty, Fish, Starship, Thunar, GTK FileChooser and pavucontrol launch.
- [ ] Existing Thunar windows may need quit/reopen after theme palette changes.
- [ ] Alt+Tab, W/O scope switching, Super+Tab tabbed columns, workspace and
      window movement bindings; do not test by disrupting important windows.
- [ ] Super+L Quickshell lock, wrong/correct PAM authentication, and idle lock.
- [ ] Video wallpaper only if `mpvpaper` was separately installed.
- [ ] Rishot only if separately installed.

Avoid changing wallpaper, monitor layout, audio devices/volume, brightness,
gamma, or power state just to test unrelated installation behavior. Suspend and
reboot tests are optional and should only be done when safe for the hardware.

## Repeat-install and uninstall checks

After recording the first-login results:

- [ ] Run `./install.sh` again. Confirm includes/routes/units do not duplicate,
      user choices/state survive, and modified managed files are backed up or
      preserved rather than silently overwritten.
- [ ] If safe, make one harmless change to a documented user-editable managed
      config, rerun, and verify conflict handling; record and then restore it.
- [ ] Run `./uninstall.sh` only after saving useful diagnostics. Confirm
      Sparrow-owned integration is restored/removed while user state remains,
      unrelated choices survive, and packages are not removed.

## Diagnostics to paste back

From the affected user session, capture:

```sh
systemctl --user status sparrow-shell.service sparrow-idle.service \
  sparrow-wallpaper.service sparrow-polkit-agent.service --no-pager -l
journalctl --user -b -u sparrow-shell.service -u sparrow-idle.service \
  -u sparrow-wallpaper.service -u sparrow-polkit-agent.service --no-pager
qs list --all
niri validate -c "${XDG_CONFIG_HOME:-$HOME/.config}/niri/config.kdl"
systemd-analyze --user verify \
  "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/sparrow-shell.service" \
  "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/sparrow-idle.service" \
  "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/sparrow-wallpaper.service"
cat "${XDG_STATE_HOME:-$HOME/.local/state}/sparrow-shell/installer/manifest.json"
git status --short
```

If Polkit is not Sparrow-managed, its unit may be absent; that is expected.
Include the first error, complete installer output, chosen package groups, and
the read-only leftover-path check if installation fails. The installer does
not maintain a separate terminal transcript.
