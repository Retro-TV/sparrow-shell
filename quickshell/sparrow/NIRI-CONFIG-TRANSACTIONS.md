# Sparrow-managed Niri configuration

Sparrow changes Niri configuration only through
`scripts/niri-config-transaction.py`, called from the public
`Niri.writeManagedFragment(id, content)` API or by Sparrow's wallpaper palette
generator. Callers pass an allowlisted fragment ID and KDL text; paths and
commands are never accepted from callers.

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
| `sparrow/window-rules.kdl` | User, hand-written | No |
| `sparrow/generated-colors.kdl` | Sparrow-generated palette | Yes, ID `generated-colors` |

Adding future managed fragments requires an explicit entry in the helper's
`MANAGED_FRAGMENTS` registry and an update to this table. The helper refuses
unknown IDs, absolute paths, and caller-selected paths.

## Transaction contract

The helper takes one JSON object on stdin with exactly `fragment` and `content`.
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

`success`, `invalid_fragment`, `invalid_request`, `invalid_content`, `staging_failed`,
`validation_failed`, `backup_failed`, `write_failed`, or `reload_failed`.
`success` with `changed: false` means the file was already byte-identical and no
backup or reload was needed. JSON stdout is the machine-readable result; a
nonzero process exit means the transaction did not complete successfully.

The staged config tree is temporary and removed on every normal/error return.
The persistent lock file is harmless; the kernel releases its lock when the
helper exits, including after a crash.
