# Architecture and update model

Sparrow Shell is split into three layers.

```text
Ricelin Quickshell foundation
        |
Sparrow custom configuration and app theming
        |
Portable installer + public updater
```

## Repository layout

- `dotfiles/` mirrors paths below the user's home directory.
- `packages/core.txt` is the portable desktop dependency set.
- `packages/apps.txt` contains the applications themed by the rice.
- `packages/pacman-explicit.txt` and `packages/aur.txt` are audit snapshots only.
- `system/` records MIME defaults and source-machine facts.
- `scripts/validate.sh` performs repository safety and syntax checks.
- `scripts/sparrow-update` is the public pull-and-apply updater.

## Install safety

`install.sh` uses `rsync` backup mode and stores replaced files outside the
checkout. Hardware monitor geometry is not shipped as the active default.
Application accounts, browser profiles, credentials and wallpaper collections
are outside the payload.

## Public updates

`sparrow-update` verifies that `origin` points to
`Retro-TV/sparrow-shell`, rejects uncommitted checkout changes, fetches the
current branch, pulls with `--ff-only`, and reruns the installer. It contains no
commit or push path.

## Maintainer publishing

The maintainer uses a separate local `rice-update` command. That private command
captures only allowlisted configuration, sanitizes machine-specific values,
checks for credential patterns, then commits and pushes. It is intentionally
not stored in or installed from the public repository.
