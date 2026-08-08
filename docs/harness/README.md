# Generic Experiment Harness

The Phase 0.75 harness is a source-neutral boundary for later experiment execution. It
does not contain SiRA or SR²AM logic and does not itself grant permission to execute.

The installed CLI is `giclab-harness` with four operations:

- `validate-plan PLAN` validates the run-plan schema and typed semantic invariants.
- `render-command PLAN --timeout-seconds N -- ARGV...` renders a `shell: false`
  command and its canonical SHA-256 digest without reading named secret values or
  executing it.
- `run-local PLAN --artifact-workspace PATH --dry-run --timeout-seconds N -- ARGV...`
  reports both project-state and run-plan blockers without creating evidence.
- `validate-artifacts ATTEMPT_DIR` verifies the append-only event stream and every
  retained file against its size and SHA-256 record.

Omit `--dry-run` only in a later phase whose project state permits the declared
workload and whose run plan contains a current explicit authorization reference plus
the exact `command_sha256` returned by `render-command`. The digest binds the argument
array, absolute resolved executable path and file digest, resolved working directory,
working-directory device/inode identity, timeout, literal environment, digests of
explicitly inherited non-secret environment values, secret environment names, and
resource projection. An inherited value, executable, or effective working directory
that changes after authorization is refused before evidence or a process is created;
filesystem identity is checked again immediately before process launch. Live runs use
a new `RUN-ID/attempt-NNNN` directory, refuse collisions, inherit no ambient variables
by default, and inject secret variables by name through `--secret-env`. Dry-run and
unauthorized paths never enumerate the ambient environment or read named secret values.
NUL-bearing arguments and environment values are rejected before evidence creation.

Secret-like literal arguments and environment entries are refused. One session-owned
exact-value scrubber checks the retained plan, command, events, adapter raw artifacts,
logs, manifest, and every other physical attempt entry. Named secret values are
redacted from captured stdout and stderr before either log is written; an exact value
found in a declared or omitted raw entry is refused and the unsafe attempt entry is
removed. Safe files must be explicitly claimed by normalization before sealing. The
redaction replacement is itself checked so even a one-character secret cannot survive
inside the marker.

Local subprocesses run in a dedicated process session. Output is streamed through a
single hard byte quota and boundary-safe redactor; timeout or quota exhaustion kills
the complete process group. A successful execution returns an open `RunSession` so a
source adapter can add normalized events, source-supported raw artifacts, and
an explicit non-wall accounting attestation before calling `seal()`. Session-owned plan,
command, budget guard, event writer, and scrubber authority cannot be replaced by a
caller. Sealing rechecks that authority, writes terminal events, and only then hashes the
final evidence set. A process budget excess raises `LocalExecutionError` with its open
failure `RunSession`, so an adapter can claim safe upstream raw output and close non-wall
accounting before sealing the available failure evidence. The adapterless CLI seals that
session directly when no adapter-owned files are present. The stop decision cannot be
recovered by replacing the original limits. Artifact validation also reconciles budget
event totals with the retained plan.

Wall time and captured output are metered directly. Any command that can consume cost,
GPU time, model tokens, or tool calls must declare a before-action upper bound and use
`--incremental-limit-enforcement adapter-command`, asserting that its adapter encodes
those maxima into hard command-level controls. Opaque subprocess resource use without
that typed enforcement contract is refused. The projection is checked against the run
budget before launch, and normalized observed usage must not exceed either the original
budget or the authorized projection. Each projected unit must be attested as observed
or explicitly unavailable before sealing. Unavailable use is recorded as unavailable
and conservatively charged at the authorized projection; it is never invented as zero.
The adapterless `run-local` CLI refuses nonzero projections because it has no adapter
accounting channel.

The `--` command delimiter is mandatory for render and run operations so harness
options and subprocess arguments have one unambiguous boundary.

Artifact roots in plans are always relative to the operator-supplied artifact workspace.
The retained `run-plan.json` and `command.json` preserve the full source/version and
authorization-bound execution contract. Unavailable source commits or digests are
recorded as the explicit value `unknown`; any such value blocks live execution until it
is replaced by a pinned identity. The metadata file `artifact-records.jsonl` is
control metadata and therefore excludes itself from hashing; every other retained
regular file must have exactly one record.
