# T03 — Generic Experiment Harness Assembly Ledger

Assembly status: **successful**

Started: 2026-08-07

Completed: 2026-08-07

## Source contract

The authoritative item contract is `03_HARNESS_CORE.md` from build package
`GIC-PHASE-0.75-BUILD-PACKAGE-V1`, interpreted under the repository's active Phase
0.75 plan, `AGENTS.md`, and `docs/PLANS.md`. T03 maps to phase items P075-DOD-03 and
P075-DOD-07. The package reference harness is design input, not an implementation to
copy without repository-native safety and validation contracts.

## Target contract

Provide a source-neutral, typed, evidence-preserving local-run boundary. A dry run is
non-executing and safe under disabled project state. A live subprocess is possible only
when both the immutable run plan and typed project state permit its declared workload;
it must use an argument array, a fixed budget, isolated credentials, an artifact root
inside the configured workspace, a fresh attempt directory, append-only events, and
content-hashed retained files.

## Scope

In scope: harness modules, run/event/cloud schemas, harness tests, one repository-native
CLI entry point, the schema-validation hook, and this workstream ledger.

Out of scope: source-specific adapters or fixtures; EXP-0001 registration; shared
project state, manifests, navigation, experiment registry, or authoritative-plan
integration; network, API, browser, model, benchmark, training, cloud, GPU, and paid
execution. Shared integration remains T06-owned.

## Definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| T03-DOD-01 | Typed, immutable records cover run identity/profile, authorization, version identity, budgets/usage, commands, events/provenance, and artifacts. | Strict mypy plus model unit and negative tests. | met |
| T03-DOD-02 | Draft 2020-12 schemas define run plans, harness events, and generic cloud-run contracts and are part of repository schema validation. | Schema checks and positive/negative contract tests. | met |
| T03-DOD-03 | Smoke interpretation is forbidden; live authorization requires a nonempty reference; unknown version fields remain explicit rather than invented. | Schema and typed-plan negative tests. | met |
| T03-DOD-04 | A hard budget guard rejects negative use, projected or observed excess, and any attempt to replace/increase limits during a run. | Budget unit tests. | met |
| T03-DOD-05 | JSONL events use exclusive append semantics and one strictly increasing, schema-valid sequence for one run attempt. | Event stream unit/contract tests, including corrupt and nonmonotonic inputs. | met |
| T03-DOD-06 | Every retained run file has relative-path, byte-size, UTC-time, and SHA-256 metadata; artifact validation detects missing, changed, duplicate, extra, symlinked, or escaping files. | Artifact unit tests and CLI smoke. | met |
| T03-DOD-07 | Commands are nonempty argument arrays and local execution always uses `shell=False`; dry run renders without executing or creating evidence. | Executor and CLI tests with a synthetic command. | met |
| T03-DOD-08 | Live execution is refused unless the run plan is authorized and current project-state workload/paid/cloud gates permit it. | Policy/executor negative tests against disabled and temporary enabled state. | met |
| T03-DOD-09 | Plan artifact roots stay inside an explicit workspace and each `(run_id, attempt)` gets a new directory; retries cannot overwrite raw logs or prior events. | Path traversal, symlink escape, and retry collision tests. | met |
| T03-DOD-10 | Command rendering never exposes inherited secret values; secret-like literals are refused and explicitly named secret environment values are redacted from captured output. | Secret refusal, render, stdout, and stderr negative tests. | met |
| T03-DOD-11 | A source-neutral adapter protocol builds commands and normalizes only source-supported evidence; no SiRA or SR²AM module/assumption is added. | Protocol typing/tests and repository diff review. | met |
| T03-DOD-12 | CLI operations validate a run plan, render a command, dry-run or execute an authorized local run, and validate an artifact directory. | In-process CLI tests plus installed `giclab-harness` smokes. | met |
| T03-DOD-13 | Unit and contract tests include required negative paths and all focused correctness gates pass. | Focused pytest, Ruff, mypy, and diff checks. | met |
| T03-DOD-14 | Full repository checks, site validation, independent spec-conformance review, and the post-review gate pass. | Review record and exact `make check` output. | met |
| T03-DOD-15 | T03 performs no source/model/API/browser/benchmark/training/cloud/paid execution and does not edit shared state or register EXP-0001. | Diff inspection, project-state validation, and scout disposition. | met |

## Implementation mapping

| Intended change | Mapped DoD |
|---|---|
| Harness models, loading, policy, and safety contracts | T03-DOD-01, T03-DOD-03, T03-DOD-08, T03-DOD-10 |
| Budget, event, artifact, and local-run primitives | T03-DOD-04 through T03-DOD-10 |
| Source-neutral adapter protocol | T03-DOD-11 |
| Run/event/cloud JSON Schemas and validation hook | T03-DOD-02, T03-DOD-03 |
| Harness CLI and packaging entry point | T03-DOD-06 through T03-DOD-10, T03-DOD-12 |
| Positive/negative tests and evidence gates | T03-DOD-01 through T03-DOD-15 |

## Progress log

- 2026-08-07: Read the repository doctrine, plan policy, active Phase 0.75 plan,
  project state, compute/storage/secret policies, T03 prompt, harness specification,
  roadmap, risk register, package reference implementation, repository validation,
  schemas, and test conventions before editing implementation code.
- 2026-08-07: Confirmed T00 is successful, T03 is eligible, and no cloud/GPU scout or
  external execution is applicable or authorized.
- 2026-08-07: Created branch `phase-0.75/harness-core` at
  `cd16fb9429d1f72f2c7bd8579a060e72e0910d12`.
- 2026-08-07: Opened this T03 ledger at `in-progress`. Kept the shared active plan
  untouched because the package assigns authoritative-plan integration to T06.
- 2026-08-07: Implemented source-neutral typed models, run-plan loading, immutable
  budget accounting, exact append-only event history, artifact confinement/hashing,
  dual-plane policy gates, secret-safe local execution, an adapter protocol, three
  schemas, one CLI, documentation, and positive/negative tests.
- 2026-08-07: The first code smoke found ambiguous CLI option parsing at the command
  boundary. Required an explicit `--` delimiter and reran the focused suite cleanly.
- 2026-08-07: Static review found that a secret-like host variable could otherwise use
  the non-secret inheritance path. Closed that bypass and added a regression before the
  full gate.
- 2026-08-07: The first full gate found only synthetic credential literals in tests
  matching repository hygiene rules. Rewrote the fixtures without weakening their
  runtime checks, then completed the full pre-review gate.
- 2026-08-07: Independent spec-conformance review returned `review-failed`. Accepted
  seven findings: authorization was not bound to the exact command; evidence sealed
  before adapter normalization/non-wall accounting; timeout handling did not contain
  process trees or bound output memory; JSON duplicates were ambiguous; an event writer
  did not own existing stream identity; retained evidence omitted the complete
  plan/version contract and launch events were premature; and nested payload plus
  authorization-reference credential isolation was incomplete.
- 2026-08-07: Repaired all seven accepted findings at their contract boundaries. Run
  authorization now binds a canonical command digest; an owned run session defers
  sealing until adapter normalization and all-unit accounting; subprocesses use an
  isolated process group, streamed redaction, and a shared output quota; every JSON
  decoder rejects recursive duplicates; writers own existing stream identity; sealed
  evidence retains and verifies the full plan/command contract; launch events reflect
  successful process creation; and event payloads are recursively immutable and
  credential-safe.
- 2026-08-07: Added focused regressions for command-field mutation, adapter pre-seal
  normalization and non-wall budget failure, descendants retaining output pipes,
  output quota exhaustion, cross-chunk redaction, launch failure semantics, nested
  duplicate authorization/budget/event/artifact keys, existing-stream identity,
  semantic command tampering after rehashing, nested payload mutation, and unsafe
  authorization references. Sent the repaired snapshot to independent rereview.
- 2026-08-07: Independent rereview cleared the original seven findings but returned
  `review-failed` at three remaining root boundaries. Accepted all three: non-wall
  resource usage lacked a typed before-action projection/enforcement contract;
  inherited environment values and executable resolution were not authorization-bound;
  and exact injected-credential isolation did not yet cover retained plans, normalized
  events, adapter raw artifacts, or replacement-marker collisions.
- 2026-08-07: Repaired those three boundaries. Canonical command identity now binds an
  absolute resolved executable plus its content hash and digest-bound, explicitly named
  non-secret inherited environment values. Non-wall resource consumers require a typed
  before-action projection backed by an adapter-command hard-limit contract; projections
  are checked before launch and reconciled against observed normalized usage. One
  run-owned exact-value scrubber now gates every retained JSON/event/raw/file surface and
  supplies an exact-safe streaming-output replacement.
- 2026-08-07: Added marker-based pre-action budget and inherited-`PATH` substitution
  regressions, projection-reconciliation failure evidence, exact-value plan/event/raw
  artifact refusals, executable-path typing, explicit resource-enforcement typing, and
  the one-character replacement-marker case. Updated the operator contract and queued
  the repaired snapshot for the same independent reviewer.
- 2026-08-07: The next whole-diff rereview reproduced six additional control-plane
  failures and returned `review-failed`: callers could replace session budget authority;
  projected non-wall usage could seal without an observed/unavailable close step; a
  bound working directory could be replaced by a symlink; omitted or refused
  credential-bearing raw files could remain physically in an attempt; executor
  construction eagerly copied every ambient variable; and NUL-bearing commands could
  fail after creating unrecoverable partial evidence.
- 2026-08-07: Repaired all six at their ownership boundaries. Run sessions now own
  read-only plan/command/guard/writer/scrubber authority and recheck the retained limits
  on accounting and sealing. Adapter results require explicit typed non-wall accounting;
  applicable unavailable units are recorded as unavailable and conservatively charged
  at the authorized projection, while direct seal and the adapterless live CLI refuse
  unclosed accounting. Working-directory filesystem identity is authorization-bound and
  double-checked before launch. Sealing scans every attempt entry, removes exact-value
  credential entries, and refuses all unowned files. Ambient values are accessed lazily
  by explicit name only, and NUL input is rejected before attempt creation.
- 2026-08-07: Added regressions for public/private authority replacement, retained-plan
  budget-event reconciliation, direct seal and omitted accounting, adapterless CLI
  refusal, post-authorization cwd symlink substitution, declared and omitted raw
  credential removal, safe unowned files, trap-mapping ambient access, and argv/literal/
  named-environment NUL input. Sent this ownership-repaired snapshot back to the same
  independent reviewer.
- 2026-08-07: Rereview of the ownership repair exposed three related edge cases. Unsafe
  nonregular entries were detected but FIFO-like nodes were not unlinked; the session's
  accounting-closed transition flag was ordinarily assignable; and nested guard,
  writer, and exact-value scrubber capabilities remained ordinarily mutable even though
  their session references were fixed. Offline validation also could not distinguish a
  projected run whose in-memory closure flag had been forged from a genuinely accounted
  run.
- 2026-08-07: Closed that ownership root. Sanitization now unlinks every non-directory
  entry without following links. Every session transition field and each nested guard,
  writer, and scrubber capability is slot-backed and write-owned, with internal state
  changes confined to owner methods. The session retains no mutable guard or writer
  capability: it stores frozen usage, creates an identity-bound writer per append, and
  exposes retained ownership through an immutable mapping. Projected runs emit exactly one typed non-wall
  accounting record, and offline artifact validation rejects missing, duplicate,
  malformed, under-reserved, or projection-inconsistent accounting history. Added FIFO,
  transition/capability reassignment, and removed-accounting-record regressions and
  returned the snapshot to the same reviewer.
- 2026-08-07: The next conformance audit found six final semantic boundaries still
  implicit: adapters could name control-plane event types; offline validation accepted
  incomplete lifecycles and loose accounting evidence; process-budget failures sealed
  before adapters could claim failure output; unavailable commit/digest provenance had
  no explicit state; invalid raw paths could echo a secret-derived name; and an
  over-wall-budget outcome could report zero usage.
- 2026-08-07: Repaired all six at the typed/offline boundaries. Adapter drafts now use
  a scientific-event-only enum and reserve harness control-source ownership; sealed
  streams require a unique ordered lifecycle. Accounting-bearing events require every
  numeric total, coherent status/projection pairs, and universal single-record
  cardinality. Budget failures attach an open session for adapter normalization, while
  the adapterless CLI closes safe zero-projection failures. Source commits/digests admit
  only a concrete pin or `unknown`, and any unknown blocks live execution. Raw paths are
  scrubbed before resolution with secret-neutral diagnostics, and failure outcomes
  retain the actual observed wall/output usage under their matching stop state.
- 2026-08-07: Added lifecycle/source-ownership, malformed/duplicate accounting,
  explicit-unknown execution-gate, raw failure artifact, adapterless failure-seal,
  secret-derived invalid-path, and observed wall-overage regressions. The 118-test
  focused harness suite and all static/validation gates passed; sent this snapshot to
  the same independent reviewer.
- 2026-08-07: The same independent reviewer completed the required conformance rereview
  on the repaired snapshot and returned `review-clean` with no remaining blocker. The
  workstream advanced to the post-review full repository gate.
- 2026-08-07: The post-review `make check` passed the frozen package install, Ruff,
  strict mypy, all 154 repository tests, repository validation, the 14-page Quarto
  render, and rendered-site validation. A refreshed installed-CLI smoke validated the
  committed fixture, rendered the pinned local command, reported the real Phase 0.75
  execution blockers without executing, and left its temporary workspace empty. All
  T03 DoD items are met; the assembly status is `successful`.

## Evidence log

- Baseline: `make check` — Python/package, Ruff, strict mypy, 32 tests, repository
  validation, and public-data generation passed; the site render then stopped because
  this fresh worktree had no `quarto` executable. A compatible repository-local Quarto
  1.9.38 installation exists in the main worktree and will be supplied explicitly to
  the final gate. This is an environment preflight issue, not a repository failure.
- Initial focused smoke: `uv run --no-sync pytest tests/test_harness_*.py -q` — did not
  collect because the pre-T03 non-editable wheel was still installed. This was an
  environment/package-refresh issue; the source-targeted command below is the relevant
  correctness gate.
- Source-targeted focused smoke after the first implementation:
  `PYTHONPATH=src uv run --no-sync pytest tests/test_harness_*.py -q` —
  **smoke-failed** with four CLI delimiter failures and one wording-sensitive schema
  assertion; 46 tests passed.
- Recovered focused smoke after root-cause fixes: the same command — **passed** with 51
  tests.
- Static gate: `PYTHONPATH=src uv run --no-sync mypy src/giclab`, Ruff format/lint, and
  `git diff --check` — **passed** across 17 source files after two initial mypy narrowing
  errors were repaired.
- Expanded focused gate after credential-inheritance and exact-history regressions:
  the source-targeted pytest command — **passed** with 53 tests.
- First pre-review `make check` with repository-local Quarto — **smoke-failed** after 84
  tests passed because two synthetic secret fixtures triggered repository hygiene in
  `test_repository_contract_passes`; no harness behavior test failed.
- Recovered pre-review `make check` with
  `QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto` — **passed**;
  lock/install, Ruff, strict mypy over 17 source files, 85 tests, repository validation,
  a 14-page Quarto render, and rendered-site validation all passed.
- Installed CLI smoke: validated the committed synthetic unauthorized plan, rendered
  `/usr/bin/printf synthetic` with `shell: false`, and dry-ran it under the real disabled
  Phase 0.75 state. The CLI reported both blockers, set `executed: false`, and left the
  temporary artifact workspace empty.
- Latest focused pre-review gate after adding the committed fixture: 54 harness tests,
  Ruff, strict mypy over 17 source files, and `git diff --check` — **passed**. A scoped
  source-assumption scan found no SiRA or SR²AM term in harness code, schemas, fixtures,
  or tests.
- First independent spec-conformance review — **review-failed** with four P1 and three
  P2 findings. The reviewer classified T03-DOD-07, T03-DOD-09, and T03-DOD-15 `met`;
  all other items remain `partial` pending the accepted repairs, rereview, and final
  post-review gate.
- Post-repair focused gate:
  `PYTHONPATH=src uv run --no-sync pytest -o addopts='' tests/test_harness_*.py tests/test_registry.py -q`
  — **81 passed**. Ruff, strict mypy over 17 source files, all three schema JSON parses,
  and `git diff --check` also passed. The process-tree and quota regressions exercised
  only short-lived synthetic local Python commands; no prohibited external workload
  was run.
- The first post-repair broad `make test` probe imported the pre-repair non-editable
  wheel and stopped at collection. `make setup` refreshed the package through the
  repository's frozen, non-editable install contract. The next broad probe reached all
  tests and found two synthetic variable names matching repository credential hygiene;
  the names were made non-secret-shaped without changing test data or weakening the
  scanner.
- Recovered broad pre-rereview gates: `make test` — **110 passed**; `make validate` —
  **passed**; `make lint`, strict `make typecheck`, and `git diff --check` — **passed**.
- Refreshed installed CLI smoke: the committed unauthorized fixture validated;
  `render-command` returned a `shell: false` command plus canonical digest
  `2eec4ccda189c15dcc40a0fe03b9677d4b6d0634050afce0ba06e623f912c22b`; dry-run
  reported both the real run-plan and Phase 0.75 project-state blockers, set
  `executed: false`, and left the supplied artifact workspace empty.
- First independent rereview — **review-failed** with three P1 findings. The reviewer
  classified T03-DOD-02, T03-DOD-03, T03-DOD-05 through T03-DOD-07, T03-DOD-09, and
  T03-DOD-15 `met`; the remaining items are `partial` pending the accepted fixes,
  another rereview, and the final post-review gate.
- Second-repair model/executor smoke:
  `PYTHONPATH=src .venv/bin/pytest -o addopts='' -q tests/test_harness_models.py tests/test_harness_executor.py`
  — **45 passed**. This includes zero-action marker evidence for projected tool-call
  excess and inherited-`PATH` substitution, plus exact-value checks for retained plans,
  normalized events, adapter raw artifacts, and a one-character credential contained in
  the normal redaction marker.
- Expanded second-repair focused gate:
  `PYTHONPATH=src .venv/bin/pytest -o addopts='' -q tests/test_harness_*.py tests/test_registry.py`
  — **94 passed**. Targeted Ruff format/lint and strict mypy over 17 source files also
  passed.
- Second whole-diff rereview — **review-failed** with four P1 and two P2 findings. The
  reviewer independently reproduced the 94-test, Ruff, strict-mypy, validation, and diff
  gates; all earlier repaired boundaries remained clean. T03-DOD-02, T03-DOD-03,
  T03-DOD-05, T03-DOD-07, T03-DOD-09, and T03-DOD-15 remained `met`; the others remained
  `partial` pending the six accepted ownership repairs, rereview, and final gate.
- Ownership-repair focused gate:
  `PYTHONPATH=src .venv/bin/pytest -o addopts='' -q tests/test_harness_*.py tests/test_registry.py`
  — **107 passed**. Targeted Ruff format/lint and strict mypy over 17 source files also
  passed. The new probes prove session authority cannot be replaced, non-wall accounting
  cannot be omitted, substituted cwd/PATH markers do not execute, unsafe raw entries are
  physically removed, ambient trap values remain unread, and NUL inputs create no
  attempt evidence.
- Nested-ownership recovery gate: the executor/artifact/budget/event subset — **56
  passed**; Ruff and strict mypy over 17 source files also passed. This includes physical
  FIFO removal, refusal of ordinary session/nested-capability reassignment, and offline
  rejection after a projected run's accounting record is removed and the manifest is
  rehashed.
- Expanded nested-ownership gate:
  `PYTHONPATH=src .venv/bin/pytest -o addopts='' -q tests/test_harness_*.py tests/test_registry.py`
  — **109 passed**. Ruff, strict mypy, repository validation, and `git diff --check`
  passed on the same snapshot.
- Final nested-capability focused gate: the expanded command above — **112 passed**.
  Ruff, strict mypy, repository validation, and `git diff --check` remained clean after
  removing session-held mutable guard/writer capabilities and adding fixed artifact-path
  refusal plus immutable writer/guard/retained-map regressions.
- Final semantic-boundary focused gate after reinstalling the repository's deliberately
  non-editable package: the eight harness test modules — **118 passed**. `make lint`,
  strict `make typecheck` over 17 source files, `make validate`, and `git diff --check`
  passed on the same snapshot. The initial collection attempt before `make sync` loaded
  the prior installed wheel; no harness assertion ran or failed in that environment
  refresh step.
- Final independent conformance rereview — **review-clean**. All previously reported
  authorization, ownership, lifecycle, accounting, evidence-preservation, provenance,
  credential, and usage-reporting boundaries were accepted as repaired.
- Post-review full gate:
  `QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto make check`
  — **passed**. The frozen non-editable package install, Ruff, strict mypy over 17
  source files, **154 tests**, repository validation, 14-page notebook render, and
  rendered-site validation all completed successfully.
- Final installed CLI smoke: `validate-plan` accepted the committed synthetic
  unauthorized fixture; `render-command` produced `shell: false` and canonical command
  digest `2417a95cc56df0a3c9a3f52c16691a2f2ec8ae3ea4e3cd26e45797d7bea8cee4` for
  `/usr/bin/printf synthetic`; `run-local --dry-run` reported the real plan/project
  blockers with `executed: false`; the temporary artifact workspace remained empty and
  was removed.

## Decisions

- The fixed project-state booleans and the run-plan authorization are separate gates;
  neither may imply the other.
- Dry-run is a deterministic non-executing path. It may report why live execution is
  blocked but must not create run evidence or require authority to execute.
- Secret-bearing environment variables are named, never serialized with their values;
  one exact-value contract checks all retained surfaces, and captured output is redacted
  before it is committed to artifact storage.
- Commands inherit no ambient environment by default. Explicit non-secret inherited
  values and the resolved executable's content identity are authorization-bound.
- Non-wall resource use requires a pre-launch upper bound plus an explicit
  adapter-command incremental-enforcement contract; opaque unbounded use is refused.
- Projected non-wall resource evidence requires one explicit observed/unavailable close
  step. Unavailable applicable units are charged conservatively at their projection,
  never represented as observed zero.
- Session authority and every physical attempt entry have one owner. A sealed attempt
  cannot contain unowned files, and unsafe exact-value raw entries are removed before a
  seal can succeed.
- Adapter scientific evidence and harness lifecycle/control events have disjoint typed
  event surfaces and source ownership; completed evidence is validated as a stateful
  stream, not merely as independently schema-valid lines.
- Unknown source commits and digests remain explicit in non-executing plans, but live
  execution requires every such identity to be concretely pinned.
- A process-budget stop is irreversible but does not prematurely close evidence: its
  attached failure session remains available for adapter ownership and normalization
  before the terminal seal.
- Artifact metadata JSONL is control metadata and is excluded from self-hashing; every
  other retained regular file must have exactly one verified record.

## Blockers and user actions

None. No paid/cloud authorization is needed or usable for T03.

## Scout disposition

Not applicable. T03's source contract permits deterministic local validation only and
expressly forbids model, API, browser, benchmark, training, cloud, GPU, and paid runs.
