# Sparrow Shell — Agent Instructions

## Project

Sparrow Shell is a minimal Niri-centered desktop rice built primarily with
Quickshell.

Niri owns window management, workspaces, outputs, gestures, and compositor
behavior. Sparrow should integrate with Niri rather than reimplement those
features.

Quickshell owns Sparrow's desktop UI and Pill surfaces.

## Git policy

- `main` is the tested stable branch.
- `dev` is the integration/development branch.
- New substantial work should normally branch from `dev`.
- Never commit directly to `main`.
- Never force-push `main` or `dev`.
- Never commit or push unless explicitly requested.
- `v0.1.0` is the first tested stable baseline.

## Development policy

Before editing:

1. Inspect the relevant implementation.
2. Inspect related architecture/source-of-truth documentation.
3. Understand existing ownership and state behavior.
4. Prefer the smallest change consistent with Sparrow's architecture.
5. Do not add duplicate implementations when Niri, Quickshell, or an existing
   Sparrow subsystem already owns the feature.

Do not redesign unrelated components while fixing a focused issue.

## Live-system policy

The repository checkout and installed Sparrow are separate.

Repository:
`~/sparrow-shell`

Installed/runtime files are deployed by the installer.

Do not modify the live desktop directly unless explicitly requested.
Prefer changing tracked source and deploying it through the installer.

Do not:
- change the user's wallpaper
- alter saved appearance settings
- disrupt networking
- pair/remove Bluetooth devices
- reboot/logout
- install/remove packages
- restart critical services

unless required for an explicitly approved test.

## Installer

`./install.sh` is the supported deployment/update path.

Installer reruns must be idempotent.

Preserve user-owned state.

Do not silently overwrite mutable user configuration.

Packages required for a Sparrow feature belong in the installer/package
manifest rather than being undocumented manual prerequisites.

## UI

Sparrow's visual language is compact and minimal.

Use the existing Appearance and polished Pill surfaces as visual references.

Avoid:
- explanatory paragraphs inside settings UI
- unnecessary labels
- oversized controls
- inconsistent margins
- hardcoded colors when semantic Theme roles exist
- text colliding with controls
- unnecessary permanent UI

Long text must elide or otherwise fit cleanly.

Respect Sparrow UI scaling.

Use existing shared components and semantic Theme roles where practical.

## Architecture

Read the repository's current source-of-truth and architecture documentation
before making architectural changes.

Important distinctions:

- tracked canonical configuration
- generated state
- machine-specific state
- mutable user/runtime state

Do not turn generated or machine-specific state into canonical configuration
without a deliberate reason.

## Validation

Run tests relevant to the change.

Common checks include:

- Qt 6 qmllint, not Qt 5 qmllint
- Niri config validation
- installer tests
- focused Python/QML tests
- JSON/TOML/shell syntax checks where applicable
- `git diff --check`

Do not claim a live hardware/UI test was performed when it was not.

## Completion reports

Report:

- what changed
- why
- files changed
- tests performed
- anything not tested
- manual verification still needed
- `git status --short`
- `git diff --stat`

Do not commit or push unless explicitly requested.
