# Sparrow-managed Niri configuration

Sparrow changes Niri configuration only through
`scripts/niri-config-transaction.py`, called from the public
`Niri.writeManagedFragment(id, content)` API or by Sparrow's wallpaper palette
generator. Callers pass an allowlisted fragment ID and KDL text; paths and
commands are never accepted from callers. Display previews can request a
temporary confirmation transaction; the helper arms an independent 15-second
rollback watchdog before reporting that the layout is ready to keep.

For `generated-colors`, the helper additionally permits only the two border
color properties under `layout > border`; arbitrary KDL directives and
includes are rejected before staging. Niri still validates the complete
candidate tree, including color-value semantics and KDL syntax.

## Ownership

| File | Owner | May the transaction helper write it? |
|---|---|---:|
| `~/.config/niri/config.kdl` | User, hand-written | No |
| `sparrow/appearance.kdl` | User, hand-written | No |
| `sparrow/binds.kdl` | User, hand-written | No |
| `sparrow/user-binds.kdl` | Sparrow Keybinds user overrides | Yes, ID `user-binds` |
| `sparrow/window-rules.kdl` | User, hand-written | No |
| `sparrow/generated-colors.kdl` | Sparrow-generated palette | Yes, ID `generated-colors` |
| `sparrow/display-outputs.kdl` | Sparrow Display settings | Yes, ID `display-outputs` |
| `sparrow/display-binds.kdl` | Sparrow-generated live output bindings | Yes, ID `display-binds` |
| `sparrow/input.kdl` | Portable include for optional user input state | No |
| `sparrow/user-input.kdl` | Sparrow Input settings | Yes, ID `user-input` |

Adding future managed fragments requires an explicit entry in the helper's
`MANAGED_FRAGMENTS` registry and an update to this table. The helper refuses
unknown IDs, absolute paths, and caller-selected paths.

`user-input.kdl` is the single owner of Sparrow-exposed Niri input properties.
The root config includes the tracked `sparrow/input.kdl` bridge; that file
includes `user-input.kdl` optionally. This lets the portable include be shipped
while user values remain under the Niri config directory and outside Git. It contains
complete keyboard and any configured device-class subtrees so a later block
cannot accidentally replace another Sparrow setting. The transaction validator
accepts only the keyboard, touchpad, mouse, touch, tablet, and focus-follows-mouse
settings surfaced by Sparrow; output names and XKB layout codes are escaped as
KDL strings and validated by the installed Niri parser before commit.

`niri/sparrow/binds.kdl` in the repository is the portable default keymap;
the installed `~/.config/niri/sparrow/binds.kdl` is its deployed copy.
`user-binds.kdl` is optional user state. The Keybinds surface sends a constrained
schema containing stable default-action chord overrides, selected desktop IDs
for Browser/Terminal/File manager, and custom application/command bindings.
The helper validates every field, obtains default actions from tracked KDL, and
serializes command text with `shlex` into Niri's direct `spawn` argv form; it
never generates `spawn-sh` or accepts caller-supplied KDL. Default application
roles are dispatched through the managed `sparrow-launch-app` PATH command.
Choosing Browser also asks `xdg-settings` to set that desktop entry as the
user's default web browser; installation itself does not alter MIME defaults.
Terminal and File manager remain Sparrow shortcut roles because there is no
uniform XDG default-terminal/file-manager interface. Sparrow Files still runs
its desktop entry, preserving its app-scoped `GTK_THEME=Sparrow` behavior.
Niri has no native bind-unset directive, so moving a default chord places a
harmless `spawn "true"` at its previous chord. Conflicts with Sparrow defaults,
other custom shortcuts, and generated display binds are rejected before staging.
Reset restores Sparrow's role/chord defaults while retaining independent
user-created shortcuts. Display shortcuts remain owned by Display.

## Transaction contract

The helper takes one JSON object on stdin with `fragment` and `content`; only
the display-output transaction may additionally request `confirm: true`. A
separate confirmation/rollback request requires the unpredictable token returned
for that display preview.
It serializes all callers with an advisory `flock` under
`$XDG_STATE_HOME/sparrow-shell/niri-config-transactions/`. It copies the current
Niri config directory to a private staging tree, substitutes only the selected
fragment, and invokes `niri validate -c <staged-config.kdl>`. Relative include
paths remain identical because the staged directory tree preserves the same
relative layout. Absolute references to the managed fragment, relative includes
escaping the config directory, symlinked config trees, and a managed fragment
not present in the include graph fail closed.

Only a validated candidate proceeds. The old managed fragment is backed up
under `$XDG_STATE_HOME/sparrow-shell/backups/niri-transaction-<UTC timestamp>/`
with a `manifest.json` containing the fragment ID, relative path, prior hash,
and whether the file existed. At most 20 helper-created transaction backup
directories are retained. The live file is replaced via a same-directory
temporary file, `fsync`, and `os.replace`; the containing directory is also
synced. Then the helper requests `niri msg action load-config-file`.

If the reload request fails, the old bytes are restored atomically (or the new
file is removed if no old file existed) and a second reload is attempted to
reapply the previous config. The result reports whether rollback/reload
succeeded. Validation and all writes run as the current user; no shell is used.

## Result statuses

`success`, `confirmation_pending`, `confirmed`, `rolled_back`, `invalid_fragment`,
`invalid_request`, `invalid_confirmation`, `invalid_content`, `staging_failed`,
`validation_failed`, `backup_failed`, `write_failed`, or `reload_failed`.
`success` with `changed: false` means the file was already byte-identical and no
backup or reload was needed. JSON stdout is the machine-readable result; a
nonzero process exit means the transaction did not complete successfully.

The staged config tree is temporary and removed on every normal/error return.
The persistent lock file is harmless; the kernel releases its lock when the
helper exits, including after a crash.
