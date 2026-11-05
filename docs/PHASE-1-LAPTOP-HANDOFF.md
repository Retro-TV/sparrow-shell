# Phase 1 laptop handoff

Continue `feature/shared-action-engine` in the laptop's existing `~/sparrow-shell`
checkout. This branch is for native acceptance testing; Phase 2 is not authorized.
No `dev` or `main` integration or deployment was part of the desktop handoff.
Read `AGENTS.md` on the laptop rather than assuming the desktop's state applies.

## Inspect before switching

```sh
cd ~/sparrow-shell
cat AGENTS.md
cat docs/DEVELOPMENT-MAP.md
git status --short --branch
git status
git branch -vv
git remote -v
git log -6 --oneline
readlink -f ~/.config/quickshell/sparrow
git fetch origin
git log -1 --oneline origin/feature/shared-action-engine
```

Confirm `origin` is `https://github.com/Retro-TV/sparrow-shell.git` (or its
intentional SSH equivalent), and compare the fetched tip with the commit in the
desktop handoff report. If the canonical checkout is absent, stop rather than
silently creating a different clone. Respect any alternate XDG configuration root.

If the worktree is dirty, a Git operation is in progress, relevant local-only
commits exist, or branches diverge, preserve everything and report it. Do not
reset, force-checkout, clean, discard, automatically stash, overwrite a branch,
or recreate work that has not been transferred. Resolve ownership with the user
before dependent work. Fetching does not require discarding local changes.

If the installed runtime is a symlink into the checkout, switching branches would
change live source. Obtain approval for that live effect before switching; do not
assume source-only review is isolated from the installed shell. The desktop used
a separate installed directory, but the laptop must be checked independently.

## Resume the exact feature branch

Only proceed once the preceding checks establish a safe, clean checkout.

If no local `feature/shared-action-engine` exists:

```sh
git switch --track origin/feature/shared-action-engine
```

If it already exists, inspect before updating:

```sh
git rev-list --left-right --count feature/shared-action-engine...origin/feature/shared-action-engine
```

- `0 0`: `git switch feature/shared-action-engine`.
- `0 N`: switch to that branch, then `git merge --ff-only origin/feature/shared-action-engine`.
- Any nonzero left count: stop and inspect the local-only work; do not overwrite,
  rebase, or merge it automatically.

Then verify:

```sh
git status --short --branch
git rev-parse HEAD origin/feature/shared-action-engine
cat docs/SHARED-ACTION-ENGINE.md
```

The two hashes should match for an unchanged handoff. Do not update `dev` or
`main`, and do not create a duplicate feature branch.

## Validate source, then arrange native acceptance

Run the exact focused commands in `SHARED-ACTION-ENGINE.md`: Node engine tests,
Python probe tests, isolated Qt/QML tests, wallpaper runtime tests, Qt **6** lint,
and Git diff checks. If the laptop lacks a tool, report it and use the declared
installer/dependency policy; do not install software without authorization.
The tests use doubles and temporary state, not the live desktop.

Inspect the installed version and shell service separately. Phase 1 has no UI or
production action IPC endpoint and does not attach its engine automatically.
Native adapter testing therefore needs an explicitly reviewed, temporary test
invocation in the existing shell lifecycle. Prepare that minimal test hook as an
uncommitted change on this feature branch, without adding Modes/Routines UI or a
second shell. Obtain approval for its desktop changes and deployment first.

For approved deployment, use **this branch's** supported `./install.sh`, preserving
user-owned configuration through its existing prompts/backups. Do not manually
copy generated palettes, device IDs, flags, or Niri configuration between machines.
Confirm installed `Actions.qml`, `Walls.qml`, `Appearance.qml`, `qmldir`,
`lib/action-engine.js`, and `scripts/action-probe.py` match the checkout, using the
actual installed XDG path. Confirm which runtime the existing service runs before
claiming any live result. Installer completion and native verification are
separate facts. Use the service's supported restart lifecycle if required and
approved; never run a competing second shell.

Native acceptance should check:

1. DND/Keep Awake Flags and their real consumers.
2. Effective audio defaults, volume/mute, missing devices, and manual changes.
3. Per-output wallpaper and Dynamic Auto/Light/Dark recoloring, including errors.
4. Previews leave settings unchanged; ending policies do not undo manual changes.
5. Lease expiry on restart; timeout diagnostics/recovery refuse unsafe unlocks.

Do not deliberately hang real hardware or kill a palette writer to simulate a
failure. The dangerous interleavings have automated doubles/temporary-lock tests.
Remove the temporary invocation after acceptance, revalidate, and report the
uncommitted diff plus actual live results. Get explicit approval before any
follow-up commit/push, integration, deployment beyond that plan, or Phase 2 work.
