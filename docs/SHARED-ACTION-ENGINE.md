# Shared Action Engine — Phase 1

Backend infrastructure only. No Modes, Routines, snapshots, shell IPC endpoint,
new UI, definition database, scheduler, or additional resident service.

## Components and integration

- `quickshell/sparrow/lib/action-engine.js`: version-1 action validation,
  serialization, descriptions, passive previews, execution state machine,
  deadlines, resource leases and guarded endings. It has no desktop side effects.
- `Singletons/Actions.qml`: lazy Quickshell adapter. A future caller explicitly
  calls `Actions.attach(Flags, Walls, Niri)` **after those owners have initialized**.
  It never initializes them during preview. The optional fourth argument is a
  PipeWire-compatible owner for tests; production uses Quickshell PipeWire.
- `Singletons/Walls.qml`: existing wallpaper owner; action requests expose
  completion and serialize with manual selection, random wallpaper, startup
  restore and recolor. Appearance now calls `Walls.recolor()` rather than
  starting a competing helper. New engine requests fail if this owner is busy;
  existing manual requests are queued and invalidate action generations. Pending
  selections coalesce by recency, so older random choices cannot override a newer
  explicit choice. Recolor requests remain independent.
- `scripts/action-probe.py`: read-only file/tool checks and persisted wallpaper
  state reads under the existing wallpaper writer lock. No directories, cache,
  migrations, thumbnails or files are created. State reads are size-limited,
  reject FIFOs/symlinks, and check metadata again before returning.

Actions is registered but not eagerly attached by shell startup. Importing the
module adds no new automation or writes. The existing owners remain responsible
for Flags persistence, wallpaper maps, palette generation, and Niri transactions.
No hand-written Niri configuration is changed by this feature; normal wallpaper
palette work still uses the existing managed generated-color transaction.

## Definition schema

```json
{
  "version": 1,
  "type": "wallpaper.output",
  "params": {"target": "make model serial", "value": "/absolute/path/image.png"},
  "capturePrevious": true,
  "ending": {"policy": "restore"},
  "timeoutMs": 15000
}
```

`validate()` returns `{ok, action}` or `{ok:false, message}`. Unknown fields,
versions/types, invalid values and restoration without capture are rejected.
`serialize()` emits canonical JSON; `deserialize()` parses and validates it.
Defaults are ending `keep`, no previous-state capture, and a 15-second deadline
(allowed range 100–120000 ms). `restore` implies capture. An explicit ending is
`{"policy":"set","value":...}` with the same value type as the action.

| Type | Parameters | Read-back guarantee |
| --- | --- | --- |
| `desktop.dnd` | boolean `value` | `verified`: shared Flags value, not acknowledgement from every notification consumer |
| `desktop.keepAwake` | boolean `value` | `verified`: shared Flags value, not proof of idle-daemon/hardware behavior |
| `wallpaper.output` | output identity `target`, absolute media path `value` | `degraded`: helper exited successfully and persisted output selection matches; pixels/player liveness unverified |
| `appearance.mode` | `auto`, `light`, or `dark` `value` | `degraded`: Dynamic palette prerequisite, persisted preference checked before recolor, helper success and Flags read-back; rendered applications unverified |
| `audio.defaultOutput` | unique PipeWire node name `value` | `verified`: effective default sink name, not merely preferred-default assignment |
| `audio.defaultInput` | unique PipeWire node name `value` | `verified`: effective default source name; monitor sources excluded |
| `audio.outputVolume` | unique sink name `target`, numeric `value` in 0–1 | `verified`: bound node volume within 0.005; no audible-output guarantee |
| `audio.outputMute` | unique sink name `target`, boolean `value` | `verified`: bound node mute state; no audible-output guarantee |

Use Niri's existing output `identity` (make/model/serial, connector fallback).
No output-name guessing occurs. Audio names are selectors, not object IDs;
missing, unready, duplicate, stream or wrong-direction nodes are rejected.
Node names can change with profiles/hardware, requiring a future editor to repair
the definition. No per-app streams, profile switching or routing are exposed.

`fromObserved(type, target, observation)` converts exactly one caller-provided
`{supported,value,ambiguous?}` observation into a validated definition. Unsupported
or ambiguous observations fail explicitly. It does not enumerate or capture a
snapshot. `describe()` and preview provide human-readable action descriptions.

## Preview, execution and results

`Actions.preview(definition, callback)` validates, resolves capabilities and reads
state. It never calls setters or mutating helpers. It may start the passive
Python probe. Its result includes the normalized action, description, primary
`resource`, full `resources`, and observation. Preview is not a reservation:
execution checks prerequisites again, and restoration checks them again.

`execute(definition)` returns an operation ID. Subscribe to
`resultChanged(result)` **before** executing: simple actions may finish
synchronously. `result(id)` returns a copy; `forget(id)` releases completed
history when the caller no longer needs it.

Results contain `status`, `accepted`, `applied`, `verified`, `message`, resource
keys and, when requested, `previous`. `running` is nonterminal; terminal states
are `verified`, `degraded`, `skipped`, `failed`, `timed_out`, and `cancelled`.
Acceptance is reported when a setter is submitted/helper starts. `applied` is
only evidence of helper completion or successful value read-back; it does not
mean every side effect succeeded. `verified` has the deliberately narrow scope
in the table. Backend failures can leave partial changes; they never acquire a
restoration lease or trigger a blind rollback.

Only one non-quarantined engine execution is active at once; another request is
explicitly `skipped`, not silently queued. Read-back retries until the deadline.
Production deadlines use Quickshell's monotonic `ElapsedTimer`, not wall-clock
time. The 100 ms checking timer stops while idle (including while quarantine is
waiting without an explicit recovery check). No background polling daemon is added.
Result observers may chain operations after completion, are isolated if they
throw, and the core `onResult()` registration returns an unsubscribe function.
`resultChanged` can also report changed recovery metadata on an already-terminal
operation: consumers must not treat that as a second activation/completion.

`cancel(id)` succeeds only before setter/transaction dispatch (including an
asynchronous prerequisite probe). It returns false once dispatched. A writer is
never killed by this API. Passive probes have a separate two-second deadline,
are safe to stop, clean up their objects, and have a maximum of eight concurrent
instances; public preview cancellation is not exposed.

### Timeout recovery

If a dispatched backend never completes, the operation becomes `timed_out` with
`recoveryRequired:true`. Its resource set moves into quarantine; unrelated actions
can proceed, while conflicting actions/previews report `blockedBy` operation IDs.
`Actions.blocked()` returns those IDs/resources and recovery instructions. There
is no unsafe force-unlock API. History for a quarantined operation cannot be
forgotten. Late backend completion clears its quarantine but never upgrades the
terminal status, creates a lease, or replays an action.

`Actions.recover(id, callback)` checks quiescence with a two-second bound. It
refuses recovery while the wallpaper owner or deferred appearance work is still
active. An idle owner is insufficient: a passive probe must also confirm that
the existing `wallpaper.lock` is idle. A failed, unavailable or timed-out check
leaves quarantine intact and returns a reason. This check makes no desktop
changes and does not retry the action. Concurrent recovery checks are rejected.

A genuinely stuck writer cannot safely be terminated automatically in the middle
of palette/configuration commits. To recover that resource, inspect the owning
process/service first. After explicit operational approval, use the existing
`sparrow-shell.service` lifecycle to restart it, after verifying its effective
`KillMode=control-group` and stop timeout on that machine. A bounded request is
`systemctl --user --no-block restart sparrow-shell.service`; this only queues the
restart. Confirm its result with `systemctl --user status sparrow-shell.service`
and do not start a second shell. If a writer survives or remains uninterruptible,
the wallpaper lock keeps new wallpaper/appearance preflights blocked even after
shell restart. Resolve the underlying process/device fault; never unlink the
lock file or guess PIDs to bypass it. No service restart was performed by the
automated tests or the desktop handoff task.

## Ownership and endings

No continuous enforcement occurs. A successful action with `restore` or `set`
gets an opaque, session-scoped `ownershipToken`. `release(token)` starts the
ending operation; `abandon(token)` relinquishes the lease without writing.
`keep` retains no lease. Leases are not a persisted second configuration store.
They are intentionally lost on shell restart; old tokens are invalid and no
automatic replay or restoration occurs. Tokens and operation IDs are receipts for
one engine instance, not serializable Mode state or evidence of current ownership.
Calling `release()` with an old token, even after new operations reuse numeric
IDs, is a skipped no-op. Already-applied settings remain at the current user's
values. A new activation captures a new baseline; it does not inherit an old one.
Quarantine receipts also expire, but writer-lock checks survive the shell because
the lock is kernel-managed and held by the existing helper/descendants.

A release rechecks capability, current value and resource generation immediately
before dispatch. Observed manual changes (including change-away-and-back),
resource disappearance, audio graph changes, or dependency changes invalidate
restoration. File metadata fingerprints also reject a previous wallpaper that was
replaced/edited while a lease was active; the requested ending must still match
the captured asset identity. Unavailable previous files/devices are skipped. Unknown/stale
tokens return a structured skipped result. A busy operation retains its lease
for a later release attempt; an invalidated lease can be explicitly abandoned.

Primary keys identify the selected preference/device/output. Wallpaper and
appearance also declare shared `appearance.palette`, because output selection
can regenerate the global palette. Overlapping live leases are rejected rather
than resolved by priority. Wallpaper/appearance revisions are conservative:
changes to related output maps/palette settings can invalidate another ending.
This provides future conflict handling with resource/dependency contracts,
without building concurrent Mode arbitration.

Generation tracking covers observable QML changes and persisted wallpaper file
metadata/content. A single consistent state read prevents mixing an old value
with a newer file generation. It is not a cross-process compare-and-swap protocol
for all external tools. Unobservable same-value user intent cannot be detected. A
wallpaper action uses the existing focused-output/global palette policy; it does
not promise to restore every palette/cache side effect independently. The shared
lane coordinates Sparrow UI and this engine, not arbitrary external scripts.
No future phase should serialize runtime leases or equate them with Mode state.

## Validation and review

Run from the repository root (no installed Sparrow or hardware changes):

```sh
node --test quickshell/sparrow/lib/actions.test.mjs
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s quickshell/sparrow/scripts -p test_action_probe.py -v
PYTHONDONTWRITEBYTECODE=1 python3 tests/actions/run.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s installer -p test_wallpaper_runtime.py -v
/usr/lib/qt6/bin/qmllint -I /usr/lib/qt6/qml -i quickshell/sparrow/Singletons/qmldir quickshell/sparrow/Singletons/Actions.qml quickshell/sparrow/Singletons/Walls.qml quickshell/sparrow/Appearance.qml
git diff --check
```

The Qt harness stages the **production** Actions/Walls QML with inert fixture
modules in a temporary directory. Quickshell embeds its native plugins in `qs`,
so stock `qmltestrunner` cannot load them directly. The harness never imports
production Flags/Niri startup and never connects to real PipeWire, launches a
wallpaper backend, or writes desktop state. Fixtures live outside the installed
runtime tree. Qt tests validate adapter wiring/state transitions, not native
Quickshell plugin behavior. Python probes use temporary files and mock tools;
existing wallpaper-runtime tests use their existing closed command doubles.

For safe branch transfer and laptop continuation, see
[the Phase 1 handoff](PHASE-1-LAPTOP-HANDOFF.md). The feature branch is a source
handoff for native acceptance, not a stable release.

Live acceptance remains required before integration: after separately approved
deployment, check actual Flags consumers, device defaults/volume/mute, per-output
wallpaper application, recoloring, manual-change suppression, and error recovery.
Do not run a second shell or deploy merely to review this implementation.
