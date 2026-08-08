# T04 — SiRA Adapter and Fixtures Assembly Ledger

Assembly status: **successful**

Started: 2026-08-08

## Source contract

The authoritative item contract is `04_SIRA_ADAPTER_AND_FIXTURES.md` from build
package `GIC-PHASE-0.75-BUILD-PACKAGE-V1`, interpreted under `AGENTS.md`,
`docs/PLANS.md`, the active Phase 0.75 plan, and the reviewed T01 and T03 outputs.
T04 maps to phase items P075-DOD-03, P075-DOD-04, and P075-DOD-07. The pinned SiRA
source contract is `SRC-SIRA-REPOSITORY` at commit
`93fb8d72de71f9a4a13419670adeb34d93cf7acd`.

## Target contract

Provide a typed, source-map-driven SiRA adapter that can render a matched reactive and
simulative pair without a shell or process, refuses undeclared condition/configuration
drift, normalizes only reliable structured upstream fields, retains complete owned raw
artifacts, and makes every provenance and schema gap machine-visible. Any audited raw
artifact path outside attempt ownership must be a typed hard execution blocker rather
than a silent omission. The adapter must also prevent the audited CLI's unbounded
cost/token contract from becoming executable merely because a later plan is authorized.

## Scope

In scope: the source-specific adapter and typed configuration, generic command-safety
surface needed to expose unbounded applicable resources, pair assertions, explicitly
synthetic source-contract fixtures, schema-gap reporting, dry-run examples, tests,
documentation, and this workstream ledger.

Out of scope: SiRA, browser, model, API, evaluator, benchmark, training, or cloud
execution; dependency or browser installation; experimental outcomes or transition
predictions; EXP-0001 registration or authorization; and shared phase-plan, project
state, registry, manifest, or notebook integration owned by T05/T06.

## Definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| T04-DOD-01 | T01 and T03 reviewed outputs are present and T04 changes map only to P075-DOD-03, P075-DOD-04, or P075-DOD-07. | Git ancestry, source/audit paths, and diff inspection. | met |
| T04-DOD-02 | A typed `SiRAAdapter` and source-specific configuration bind plans to the exact audited source ID/commit, condition, profile, seed, CLI, task source, limits, output root, and secret name. | Unit and negative contract tests. | met |
| T04-DOD-03 | Reactive and simulative `CommandSpec` values are argument arrays with `shell: false`, an absolute pinned executable/cwd identity, named-only `SIRA_API_KEY`, and no subprocess side effect during construction or dry run. | Command rendering, filesystem marker, and dry-run tests. | met |
| T04-DOD-04 | One machine assertion proves paired configurations and rendered commands differ only in predeclared source or harness-owned fields and rejects any other drift or condition mismatch. | Positive pair report and parameterized negative tests. | met |
| T04-DOD-05 | The audited lack of finite SiRA cost/token controls is typed into the command contract and blocks execution even if other authorization gates later pass. | Executor dry-run/live-refusal regressions and schema-gap entry. | met |
| T04-DOD-06 | Because T01 found no released upstream sample trace, fixtures are explicitly labeled `synthetic-contract-fixture`, cite their source-field basis, and are never described as upstream evidence. | Fixture manifest and provenance tests. | met |
| T04-DOD-07 | Valid structured session fixtures normalize observations, source-named belief state, selected plan, requested action, partial outcome, and available metrics without inventing critic, prediction, evaluator, execution-result, GIC-state, or scientific-outcome fields. | Exact normalized-event assertions. | met |
| T04-DOD-08 | Every canonical adapter field has a direct source path or explicit absence, normalization rule, provenance class, and available/unavailable status; all raw trace fields remain in retained raw artifacts. | Machine-readable schema-gap report, coverage validator, and raw round-trip checks. | met |
| T04-DOD-09 | Normalization handles missing belief, missing plan, and absent critic score as explicit unavailability, and rejects malformed traces, repeated attempts, path traversal, and condition mismatch safely. | Named positive/negative tests for all seven cases. | met |
| T04-DOD-10 | Matched reactive/simulative dry-run examples are committed and demonstrably non-executing. | Example document plus installed/source-level dry-run smoke. | met |
| T04-DOD-11 | Focused smoke, static gates, pre-review `make check`, independent spec-conformance review, fixes/rereview, and post-review `make check` pass. | Exact commands and review result in the evidence log. | met |
| T04-DOD-12 | No forbidden execution or shared-state mutation occurs; EXP-0001 stays absent, execution permissions stay false, and compute accounting stays zero. | Project-state/registry/compute checks and final diff review. | met |

## Implementation mapping

| Intended change | Mapped DoD |
|---|---|
| Typed input-tree binding, unowned-output state, applicable-but-unbounded resources, and executor refusal | T04-DOD-02, T04-DOD-03, T04-DOD-05, T04-DOD-08 |
| SiRA configuration, adapter command builder, and pair assertion | T04-DOD-02 through T04-DOD-05 |
| Structured session normalizer and raw-artifact ownership | T04-DOD-06 through T04-DOD-09 |
| Synthetic fixture manifest and source-shaped fixture | T04-DOD-06 through T04-DOD-09 |
| Schema-gap report and validator | T04-DOD-05, T04-DOD-07 through T04-DOD-09 |
| Dry-run examples and operator documentation | T04-DOD-03, T04-DOD-04, T04-DOD-10 |
| Focused/full gates and independent review | T04-DOD-01 through T04-DOD-12 |

## Planned evidence

- Focused adapter and command-contract pytest suite.
- Ruff format/lint, strict mypy, schema-gap validation, and `git diff --check`.
- Full `make check` with the repository-local Quarto executable.
- Independent whole-diff review against this checklist and the T04 source prompt.
- Post-review repeat of the full gate.
- Static zero-execution inspection of project state, registry, compute records, and
  attempt/output paths.

## Progress log

- 2026-08-08: Read the Assembly skill, T04 prompt, repository doctrine and plan policy,
  active Phase 0.75 plan, project/compute/secret policies, reviewed T01 audit/command/
  trace maps, reviewed T03 ledger and harness contracts, and package harness spec.
- 2026-08-08: Confirmed T01 and T03 are merged at integration commit `c2ebee2`, created
  branch `phase-0.75/sira-adapter`, and scoped this assembly item to T04 only.
- 2026-08-08: Confirmed no cloud/GPU scout applies and no external execution is
  authorized. The source contract forbids SiRA, browser, model, API, evaluator, and
  benchmark execution.
- 2026-08-08: Baseline `make check` passed lock/install, Ruff, strict mypy, all 154
  tests, repository validation, and public-data generation, then stopped because this
  worktree has no `quarto` on `PATH`. T03 records a compatible repository-local Quarto
  executable for complete pre/post-review gates.
- 2026-08-08: T04 preflight exposed a real control-plane gap: T03 refuses opaque
  unbounded non-wall resource use, while audited SiRA has no finite total cost or token
  control and an unbounded clustering retry loop. T04 will represent that gap in typed
  command state and refuse live execution rather than falsely claiming a zero or finite
  projection.
- 2026-08-08: Implemented the generic applicable-but-unbounded resource state and live
  preflight refusal, and made adapter command construction receive pinned source and
  prospective attempt-output roots separately.
- 2026-08-08: Implemented typed SiRA task/config/mode contracts, exact plan/source
  binding, shell-free command generation, an approved-difference pair assertion,
  strict single-session discovery, structured normalization, explicit gap accounting,
  and raw-file ownership.
- 2026-08-08: Added the machine-readable schema-gap report, nonexecuting matched dry-run
  examples, explicitly labeled synthetic contract fixture, and 21 focused tests. The
  adapter creates no output path during build/dry-run and an authorized executor probe
  refused the unbounded command before the synthetic runner marker could execute.
- 2026-08-08: The complete pre-review `make check` passed with the repository-local
  Quarto executable: frozen install, Ruff, strict mypy over 18 source files, all 175
  tests, repository validation, generated public data, 14-page Quarto render, and site
  validation. T04 entered independent spec-conformance review.
- 2026-08-08: Independent spec-conformance review returned `review-failed`. Accepted
  all six findings: source/config/model/dataset identity was label-only; trace task and
  step/profile identity was not reconciled; runtime/report mappings diverged from T01;
  external source logs were not attempt-owned; symmetric pair drift could pass; and one
  ledger row incorrectly described expected missing fields as rejected. T04-DOD-02,
  T04-DOD-04, and T04-DOD-07 through T04-DOD-09 returned to `partial` for root-cause
  repair and rereview.
- 2026-08-08: Repaired source identity at the control surface: configuration now has a
  canonical digest checked against the plan; mutable model and exact dataset revisions
  are reconciled; the checkout must be the clean Git top level at the audited commit;
  and command-bound input-tree/Git identities are rechecked by the executor before
  launch, including an unchanged-tree empty-commit regression.
- 2026-08-08: Repaired trace identity and T01 parity: exact task/profile/step/instance/
  action relations are reconciled before normalization; outcome and WebArena fields now
  follow T01; every emitted field has runtime source/rule/provenance/status metadata;
  and nonempty source warnings/errors use a typed harness-owned notice channel.
- 2026-08-08: Made external raw-log ownership an inviolable command contract. The two
  audited source-root log patterns are typed as unowned outputs and independently block
  execution. The synthetic fixture includes isolated raw-only shapes under its owned
  output root; no actual source log is represented as captured evidence.
- 2026-08-08: Rebuilt the pair assertion to prove each command exactly against its own
  adapter/plan contract and explicit source/output owners before comparison, so equal
  mutations on both arms and self-authorized output-root changes fail.
- 2026-08-08: Rereview exposed narrower T01 parity edges. Moved unsupported FlightQA/
  WebArena denial to the command-authority boundary so audited trace contexts remain
  testable without becoming executable, made per-step duplicate action mandatory, and
  reconciled exactly one WebArena `output.jsonl` row against session identity and result.
- 2026-08-08: Extended parity over T01's explicit unavailable-field maps, including
  observation timing/action-result and evaluator aggregate gaps. Added typed
  `owned_output_roots` to the authorization-bound command and made the generic executor
  enforce exact attempt containment at preflight and immediately before launch.
- 2026-08-08: The same independent reviewer completed the full repaired-diff rereview
  with `review-passed` and no P0, P1, or P2 findings, independently reproducing the
  123-test affected suite and zero-execution state audit.
- 2026-08-08: The required post-review full gate passed all 199 tests plus formatting,
  lint, strict typing, repository validation, public-data generation, 14-page notebook
  rendering, and rendered-site validation. Final static inspection confirmed the empty
  experiment registry, all execution permissions false, zero compute accounting, no
  run-attempt evidence, and no EXP-0001 registration.

## Decision log

- 2026-08-08: Treat T04 as one Assembly item and do not begin T05.
- 2026-08-08: Use only synthetic contract fixtures because the reviewed T01 artifact
  inventory contains no released upstream sample trace. Synthetic shape is not
  scientific or upstream execution evidence.
- 2026-08-08: A scout/evidence execution is not applicable because T04 is a deterministic
  local adapter-contract item and its source contract expressly forbids SiRA execution.
- 2026-08-08: The extra paired `--output_dir` difference is harness-owned, not a
  scientific treatment difference. T03's immutable per-attempt evidence isolation has
  higher control-plane authority than T01's source-level CLI pair comparison, so the
  assertion permits only that one explicit harness-owned exception.
- 2026-08-08: T01's agent/global logs are outside the upstream `--output_dir` and cannot
  be safely assigned to one attempt after the fact. The durable contract is to expose
  both paths as typed unowned outputs and block launch until a future isolation wrapper
  removes them; authorization cannot waive raw-evidence ownership.
- 2026-08-08: Typed task/trace support and command authorization are distinct surfaces.
  WebArena and FlightQA trace contracts remain source-auditable, while command creation
  is denied because T01 approved neither as a pilot. No frozen-dataclass bypass or dead
  internal normalizer path is used.
- 2026-08-08: T01 marks WebArena `output.jsonl.test_result` canonical. For a one-task,
  fresh attempt, the adapter therefore requires one strict row and exact agreement with
  the session; raw retention without reconciliation would be an evidence conflict.

## Evidence log

- Baseline `make check` — **environment-partial**: all code, typing, 154-test,
  validation, and generated-data gates passed; site rendering did not start because
  `quarto` was absent from this worktree's `PATH`.
- Generic regression smoke after the command-contract extension:
  `PYTHONPATH=src uv run --no-sync pytest -o addopts='' tests/test_harness_models.py
  tests/test_harness_executor.py tests/test_harness_cli.py
  tests/test_harness_artifacts.py -q` — **passed**, 84 tests.
- Focused adapter plus affected harness smoke:
  `PYTHONPATH=src uv run --no-sync pytest -o addopts='' tests/test_sira_adapter.py
  tests/test_harness_models.py tests/test_harness_executor.py
  tests/test_harness_artifacts.py -q` — **passed**, 99 tests.
- Latest adapter-only smoke: `PYTHONPATH=src uv run --no-sync pytest -o addopts=''
  tests/test_sira_adapter.py -q` — **passed**, 21 tests. Focused Ruff and strict mypy
  over the adapter and tests also passed; `git diff --check` is clean.
- Pre-review full gate:
  `QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto make check`
  — **passed**; frozen lock/install, formatting/lint, strict mypy over 18 source files,
  175 tests, repository validation, generated public data, a 14-page Quarto render, and
  rendered-site validation all passed.
- First independent review — **review-failed** with four P1 and two P2 findings. The
  reviewer independently kept T04-DOD-01, 03, 05, 06, and 10 met; classified T04-DOD-02,
  04, 07, 08, 09, 11, and 12 partial; and observed no forbidden execution.
- Repair smoke: `PYTHONPATH=src uv run --no-sync pytest -o addopts=''
  tests/test_sira_adapter.py tests/test_harness_models.py tests/test_harness_executor.py
  tests/test_harness_artifacts.py -q` — **passed**, 111 tests. `uv run --no-sync mypy`
  passed over 18 source files, focused Ruff passed, and `git diff --check` is clean.
- Git/tree repair regression plus all affected harness tests:
  `PYTHONPATH=src uv run --no-sync pytest -o addopts='' tests/test_sira_adapter.py
  tests/test_harness_models.py tests/test_harness_executor.py
  tests/test_harness_artifacts.py tests/test_harness_cli.py -q` — **passed**, 118 tests.
  This includes refusal after an empty Git commit changes HEAD without changing source
  tree bytes.
- Repair pre-rereview full gate:
  `QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto make check`
  — **passed**; frozen lock/install, Ruff, strict mypy over 18 source files, all 187
  tests, repository validation, generated public data, the 14-page Quarto render, and
  rendered-site validation passed. The repaired diff entered independent rereview.
- Latest rereview repair smoke: `PYTHONPATH=src uv run --no-sync pytest -o addopts=''
  tests/test_sira_adapter.py tests/test_harness_models.py tests/test_harness_executor.py
  tests/test_harness_artifacts.py -q` — **passed**, 123 tests. Focused Ruff, strict mypy
  over 18 source files, and `git diff --check` also passed. Coverage includes exact
  attempt-root ownership/hash/symlink checks, mandatory action reconciliation, complete
  T01 unavailable-field parity, and strict WebArena summary reconciliation.
- Independent repaired-diff rereview — **review-passed**, no P0/P1/P2 findings. The
  reviewer independently reran the same affected suite (**123 passed**), verified
  `git diff --check`, and classified T04-DOD-01 through T04-DOD-10 and T04-DOD-12 met;
  T04-DOD-11 awaited only this parent-owned final full gate.
- Post-review full gate:
  `QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto make check`
  — **passed**; frozen lock/install, format, Ruff, strict mypy over 18 source files,
  **199 tests**, repository validation, four generated public notebook views, 14-page
  Quarto render, and rendered-site validation all passed.
- Final zero-execution/state audit — **passed**: `docs/PROJECT_STATE.yaml` keeps paid,
  prototype, benchmark, training, and cloud mutation permissions false;
  `experiments/registry.yaml` has `experiments: []`; `manifests/compute.yaml` has zero
  cloud mutations, accelerator hours, cost, prototype/benchmark/training runs, and no
  entries; no run-attempt evidence path or EXP-0001 registration exists; final
  `git diff --check` is clean.

## Blockers and user actions

None.

## Next permitted work

T04 is complete. T05 remains a separate, not-started workstream and may proceed only
under its own source contract after the required integration/prerequisite checks.
