# Security policy

Do not open a public issue containing credentials, tokens, private keys, Wi-Fi
passwords, browser profiles or account databases.

For a suspected secret in the repository, contact the maintainer privately
through the GitHub account that owns this repository and identify the affected
path and commit. Revoke the exposed credential before waiting for repository
history to be cleaned.

The installer should be reviewed before execution. It uses `sudo` only for
package installation, optional system keymap changes, and a current-user ACL for
the system Spotify installation.
