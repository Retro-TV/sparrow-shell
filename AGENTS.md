# Sparrow Shell — Agent Instructions

## Project and source of truth

Sparrow Shell is a minimal Niri-centered desktop rice built primarily with
Quickshell. Niri owns compositor behavior, outputs, workspaces and window
management; Sparrow should use those capabilities rather than duplicate them.
Quickshell owns Sparrow's desktop UI and Pill surfaces.

The canonical repository is `https://github.com/Retro-TV/sparrow-shell`.
On each development machine, use its existing `~/sparrow-shell` checkout.
GitHub and the current checkout are canonical; chat history is not a substitute
for inspecting current code and documentation. Read this file before repository
work. Use `docs/DEVELOPMENT-MAP.md` to find relevant code and architecture docs.

## Hard safety rules

- `main` is tested stable; `dev` is the development integration branch.
- Never develop directly on `main`, force-push `main` or `dev`, or create
  release tags unless explicitly requested.
- **Do not modify or promote `main` / stable without explicit stable intent.**
  The request must name `main`, `stable`, or clearly request promotion of
  `dev` to stable. “Works”, “finish it”, “commit it”, “push it”, “publish it”,
  “done”, and “feature is done” never authorize stable promotion by themselves.
- **Repository recovery rule:** Never silently or routinely use destructive
  `reset`, `clean`, `restore`, stash/discard, or history-rewriting operations to
  resolve repository state. Preserve unexpected local work and stop/report
  when it prevents safe progress. Explain any proposed recovery operation and
  get explicit authorization before using it.
- Preserve user-owned configuration, secrets, personal media, and runtime
  state. Never expose credentials.
- If `~/sparrow-shell` exists but this Work environment cannot write to it,
  stop before implementation and explain the access limitation. Do not switch
  to `/tmp`, a project mirror, or another clone.

## Request and implementation lifecycle

1. Inspect the actual checkout and relevant source, docs, ownership, and state.
2. For research or planning, remain read-only. For a proposed change, explain
   the approach and resolve only decisions that materially affect behavior,
   UX, architecture, compatibility, safety, or release state.
3. Implement only when the user asks to proceed. Keep independent work on a
   focused `feature/<name>` or `fix/<name>` branch based on current clean `dev`.
4. Make the smallest change that satisfies the request. Avoid unrelated
   cleanup, refactors, tests, or background work.
5. Run focused automated checks. If the change requires live/manual testing,
   test from the uncommitted feature/fix branch before commit, push, or
   integration. Never commit merely to make testing possible.
6. After required testing and user approval, do final checks and review. Follow
   the natural-language authorization below for commit, push, and `dev`
   integration. Stop before stable promotion unless explicitly requested.

Natural-language intent:

- “I want to add X” means inspect/research and propose the appropriate change.
- “Let's do it” / “implement this” authorizes the discussed implementation.
- “Works” is manual-test approval only. It does not authorize commit, push,
  integration, or stable promotion.
- “Commit this” authorizes a commit of approved work to the current feature/fix
  branch only. It does not authorize push or integration.
- “Push this” authorizes pushing the current approved feature/fix branch only.
  It does not authorize integration into `dev` and never means `main`. It does
  not authorize committing uncommitted changes.
- “Publish this” requires clarification when the destination is not explicit.
  Never infer `dev`, `main`, or stable.
- “Finish it” means, after required testing and approval, perform final
  validation and review, commit and push the feature/fix branch, integrate into
  `dev` if it merges cleanly, and push `dev`. If integration is blocked, stop
  and report it. It never means `main`.
- “Put it on main” or an equally clear stable-promotion request authorizes the
  stable procedure below. Clarify “release it” if tag vs. promotion is unclear.

## Checkout, branches, and cross-machine work

Before implementation on any machine:

1. Inspect `git status`, current branch, in-progress Git operations, and recent
   history in the canonical checkout. Do not assume another machine's state.
2. Fetch `origin`; treat fetched GitHub refs as canonical for shared branch
   state, and inspect local `dev` plus any feature/fix branch being continued.
3. When continuing work, resume the matching fetched remote feature/fix branch
   if it exists and its checkout is safe. Fast-forward a clean local copy only
   when it is strictly behind; stop if it is dirty or diverged. Do not create a
   duplicate branch. If work exists only uncommitted/unpushed on another
   machine and is absent here, stop and report that the work has not been
   transferred; do not recreate or guess it. Preserve local-only commits as
   untransferred work, not as shared remote state.
4. For new work, fast-forward local `dev` only when the checkout is clean and
   it is strictly behind `origin/dev`; create the new branch from that tip.
   Use `fix/<name>` to correct unintended existing behavior and
   `feature/<name>` for new or intentionally expanded behavior.
5. If the tree is dirty, branches diverge, or an update/resume is unsafe, stop
   and report the concrete state, following the repository recovery rule above.
   Never branch new work from stale `dev`.

Do not create a second clone or disposable checkout when `~/sparrow-shell` is
available. If a required remote operation or canonical-checkout access is
blocked, explain that instead of silently using another repository.

## Interrupted or crashed sessions

On resumption, reconstruct what happened from the actual checkout and relevant
filesystem/runtime state: branch and HEAD, status including untracked files,
recent commits, reflog when useful, unfinished merge/rebase/cherry-pick state,
changed files, and relevant installed files/services if deployment may have
started. Treat earlier messages and plans as clues, not proof of completion.
Do not repeat completed work blindly or claim a deploy/test succeeded without
evidence. Resolve state conservatively; ask only when an unresolved decision or
ownership question materially affects safe continuation.

## Architecture, state, and installer

- Inspect relevant source-of-truth and architecture docs before architectural
  changes. Preserve the division between tracked portable source, generated
  output, machine-specific discovery, and mutable user/runtime state.
- Prefer Niri-native or existing Sparrow ownership over duplicate systems.
- `./install.sh` is the supported deployment/update path. Verify its current
  behavior and relevant service names before relying on them.
- Installer reruns must be idempotent. Preserve user-owned state, back up
  replaced files through the established policy, and never silently overwrite
  mutable user configuration.
- Keep package requirements in the declared installer/package manifests;
  do not add undocumented manual prerequisites.
- Repository source and installed Sparrow are separate. Deploy only when
  needed for approved testing, from the checkout containing the change. Do not
  modify live desktop settings, packages, services, network, Bluetooth,
  wallpaper, login state, or hardware configuration unnecessarily.
- Before claiming live verification, verify the installed runtime contains the
  branch/change being tested. If it does not, deploy that branch through the
  supported mechanism first. Report source validation, deployment, and live
  verification as separate facts.

## UI and implementation quality

Keep Sparrow's UI compact and consistent with its established visual language.
Use shared components and semantic Theme roles where practical. Avoid
explanatory paragraphs, oversized or permanent controls, inconsistent spacing,
hardcoded colors where semantic roles exist, and overflowing text. Respect UI
scaling and elide long text where needed.

## Validation and manual verification

Validation must be proportional to the change. During iteration, run focused
checks for the changed code and its direct dependencies. Do not repeatedly run
broad installer or release suites for unrelated changes. Broader validation
belongs at relevant integration/release boundaries or when the changed
subsystem requires it.

Automated validation does not replace required manual testing or user approval.
For visual, hardware-, network-, display-, Bluetooth-dependent behavior, or
anything else meaningfully verifiable only in a live environment, require the
applicable live check before calling that behavior tested. Distinguish source
inspection, automated checks, simulated checks, and actual live testing. Never
claim UI, hardware, display, network, or Bluetooth behavior was live-tested
without doing so.

Common focused checks include Qt 6 `qmllint` (not Qt 5), `niri validate`,
relevant QML/Python tests, shell/JSON/TOML syntax checks, installer tests when
installer behavior changed, and `git diff --check`. Do not add or run unrelated
tests just to increase test volume.

When manual testing is needed, give Tadej a short behavior-focused procedure.
State what was checked and what remains unverified. For iteration after a
reported issue, continue on the same feature/fix branch unless a separate
change is clearly warranted.

## Development completion and stable promotion

For approved development completion:

1. Run appropriate final focused validation and review the diff for unrelated
   changes, secrets, debug code, generated junk, and accidental artifacts.
2. Do not commit, push, or integrate until required live/manual verification
   and user approval are complete. Testing must use the uncommitted feature/fix
   branch; never commit merely to make it testable.
3. For “finish it,” commit the approved change, push its feature/fix branch,
   integrate into `dev` if it merges cleanly, and push the updated `dev`. If
   integration is blocked, stop and report it. Separate “commit this” and
   “push this” requests have only the scope defined above.
   Never infer stable promotion from development approval.
4. Report the commit(s), destination branches, checks, manual-test status, and
   final Git state.

For explicit stable promotion only:

1. Verify `dev` is synchronized with `origin/dev`, the checkout is clean, and
   the incoming commits/diff are understood.
2. Ensure relevant automated validation passes and every required live/manual
   test and approval is complete. Automated success alone is insufficient.
3. Prefer fast-forward promotion. Never force-push `main`.
4. Push `main` only after the requested promotion succeeds; report the commit
   and validation evidence. Do not create a version tag unless separately
   requested.

## Completion reports

Keep reports practical. State what changed and why, files changed, validation
performed, what remains untested, manual verification still needed, and the
branch plus `git status --short` / `git diff --stat`. Never hide failures,
warnings, assumptions, or incomplete validation.
