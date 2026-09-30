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

# Development workflow

Sparrow Shell uses a protected stable-development workflow.

## Branch roles

- `main` is the stable, tested release branch.
- `dev` is the integration branch for ongoing development.
- New independent features should normally use `feature/<short-name>`.
- Bug fixes should normally use `fix/<short-name>`.

Never develop directly on `main`.

## Starting work

When the user asks to implement a new feature or fix:

1. Read this file and relevant architecture/source-of-truth documentation.
2. Inspect the existing implementation before editing.
3. Determine whether the request is a feature, fix, polish change, documentation change, or research task.
4. Ask the user questions only when an unresolved decision materially affects behavior, architecture, safety, or UX. Otherwise make the smallest reasonable choice consistent with Sparrow.
5. Ensure the repository is clean enough to safely start work.
6. Update local remote information before branching.
7. Base normal development work on the latest `dev`.
8. Create an appropriately named `feature/*` or `fix/*` branch when the work is an independent change.
9. Never discard unrelated user work.

The user should not need to know or provide Git commands. Handle repository and branch operations yourself when tools permit.

## Research-only requests

If the user asks to research, inspect, audit, investigate, or propose something:

- Do not modify files unless explicitly asked.
- Inspect the repository and relevant documentation.
- Research upstream/current external behavior when appropriate.
- Explain findings and recommend the smallest appropriate implementation.
- Do not create unnecessary branches for purely read-only investigation.

## Implementation

When implementing:

- Keep changes focused on the requested feature or fix.
- Preserve Sparrow's existing architecture and visual language unless the task explicitly changes them.
- Avoid unrelated cleanup and refactoring.
- Update tests and documentation when behavior or architecture changes.
- Run the relevant automated validation before presenting the work for testing.
- Do not hide failed tests, warnings, incomplete validation, or assumptions.

## Manual testing

When automated work is complete:

1. Clearly explain what changed.
2. Clearly state what was and was not automatically verified.
3. Give the user a short, concrete manual test procedure when live verification is needed.
4. Prefer giving the user the behavior to test rather than requiring them to understand implementation details.
5. Do not consider visually sensitive or hardware-dependent work fully verified until the required live test has been performed.

If the user reports a problem, continue fixing it on the same feature/fix branch unless a separate change is clearly more appropriate.

## Approval and integration

Do not treat implementation completion as permission to publish stable code.

When the user says the change works, is approved, or asks to finish/publish it:

1. Re-run appropriate final validation.
2. Review the final diff for unrelated changes, secrets, generated junk, temporary files, and debug code.
3. Commit the approved work with a concise descriptive commit message.
4. Push the feature/fix branch.
5. Integrate it into `dev` only after user approval.
6. Push the updated `dev`.
7. Report exactly what was committed and where.

Do not merge into `main` merely because a feature is complete.

## Stable promotion

`main` represents the stable Sparrow Shell state.

Only promote `dev` to `main` when the user explicitly asks to release, publish to main, merge to main, promote dev to stable, or gives an equivalently clear instruction.

Before modifying `main`:

1. Confirm the requested promotion is intentional if the user's wording is ambiguous.
2. Ensure relevant work is committed.
3. Ensure `dev` is synchronized with its remote.
4. Run the appropriate full validation suite.
5. Check that the working tree is clean.
6. Review the commits/diff that will enter `main`.
7. Prefer a fast-forward promotion when branch history permits.
8. Push `main` only after successful validation.
9. Never force-push `main`.
10. Report the resulting commit hash and validation results.

A request such as "push this", "save this", or "commit this" does NOT by itself mean promote to `main`.

## Releases

Do not create release tags automatically.

When the user explicitly asks to create a release/tag:

- verify `main` is at the intended stable commit;
- use an appropriate version tag;
- never move or overwrite an existing release tag without explicit instruction;
- report exactly which commit was tagged.

## Safety

Never:

- force-push `main` or `dev`;
- use destructive reset/clean operations to solve ordinary repository problems;
- silently discard local changes;
- silently overwrite user-owned configuration;
- expose credentials or secrets;
- merge untested hardware-dependent behavior while claiming it was tested;
- modify `main` without explicit user intent.

If repository state is unexpected, stop and explain the problem instead of trying to repair it destructively.

## Natural-language operation

The user is not expected to manage Git manually.

Interpret ordinary instructions according to this workflow.

Examples:

- "I want to add X" → inspect/research it and discuss important decisions before implementation.
- "Let's do it" → implement it on the appropriate development branch.
- "Fix this" → investigate and implement the focused fix.
- "How do I test it?" → provide the shortest useful live test procedure.
- "Works" → treat the implementation as manually approved, but do not assume this means `main`.
- "Finish it" → validate, commit, push, and integrate into `dev` when appropriate.
- "Push this" → push the current approved development work; do not infer `main`.
- "Put it on main" → perform the stable-promotion procedure.
- "Release it" → clarify whether the user means main promotion, a version tag/release, or both if not already clear.

Prefer handling routine technical details autonomously while keeping irreversible or stable-release decisions explicit.

## Canonical local development checkout

On Tadej's development machines, the normal local Sparrow repository is:

`~/sparrow-shell`

When that checkout is available to the working environment, it is the canonical
local development checkout.

For implementation work:

1. Prefer the existing `~/sparrow-shell` checkout.
2. Inspect its Git state before making changes.
3. Start independent work from the latest clean `dev`.
4. Create and switch to an appropriate `feature/*` or `fix/*` branch in that
   checkout.
5. Make source changes there.
6. Run repository validation there.
7. When live testing is required, deploy from that same checkout using the
   repository's supported deployment path.
8. Leave the feature/fix branch available for continued iteration until the
   work is approved and integrated.

Do not create a second clone, `/tmp` checkout, project mirror, or disposable
repository merely for isolation when the canonical local checkout is available.

If the execution environment cannot access or write to `~/sparrow-shell`:

- do not silently substitute another checkout and continue as though it were
  the user's development repository;
- explain the environment limitation;
- request access to the canonical checkout when possible;
- only use a temporary clone when necessary for read-only investigation or when
  the user explicitly agrees to that workflow.

A temporary clone is never the authoritative local Sparrow checkout.

Do not instruct the user to deploy or install from a temporary clone without
explicitly explaining why that clone exists and receiving approval.

## Local deployment and testing

Repository state and the currently installed Sparrow desktop are separate.

Before giving deployment/restart commands:

1. Verify the supported deployment method from the current repository.
2. Verify relevant service/unit names rather than assuming them.
3. Deploy from the branch/check-out containing the change being tested.
4. Do not commit merely to make a change testable.
5. Tell the user exactly what behavior needs manual verification.

When possible, perform non-destructive automated validation before asking the
user to test manually.

Hardware-dependent and visual behavior must not be reported as verified until
it has actually been tested in the appropriate live environment.

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
