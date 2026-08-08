# T04.5 — Harness-to-Kernel Option Preservation Assembly Ledger

Assembly status: **successful**

Started: 2026-08-08

## Source contract

The authoritative item contract is
`GIC_Lab_H2K_Option_Preservation_Addendum_v1_1/prompts/04_5_H2K_OPTION_PRESERVATION_RETROFIT.md`,
interpreted under `AGENTS.md`, `docs/PLANS.md`, the active Phase 0.75 plan, the
reviewed T01 through T04 outputs, the original experiment-harness specification,
`H2K_OPTION_PRESERVATION_SPEC.md`, and `EXPERIMENT_HARNESS_SPEC_ADDENDUM.md`.

The implementation item is T04.5 only. It begins at integration commit
`2ff5ed34835ddb6598295757f77ebf3ebcefce06`, which contains the accepted T02 SR²AM
audit and T04 SiRA adapter. T05 is not part of this item.

## Target contract

Preserve source-grounded evidence needed for a possible later comparison between
external harness regulation and progressively internalized regulation without adding
an experiment, condition, training path, learned kernel, Phase 2, or execution
authority. The generic harness must represent who selected a reasoning mode without
claiming latent internalization; the SiRA adapter must record its fixed condition as an
external experiment assignment; and the accepted SR²AM audit must gain a later-capture
addendum that keeps unsupported fields unavailable.

## Success criterion

The deferred track, source classifications, schema-version boundary, SiRA mapping,
SR²AM capture requirements, and non-interpretation boundary are explicit and
machine-testable; existing v0.1 event evidence remains readable; every required
negative and pair-parity test passes; the complete repository gate and independent
spec-conformance review are clean; EXP-0001 remains absent and scientifically
unchanged; every execution permission and compute counter remains false or zero; and
the work stops before T05.

## Scope

In scope: deferred-track governance; decision/risk records; a source-neutral typed
regulation-decision event; deliberate event-schema versioning and backward-compatible
reads; SiRA assignment normalization based only on T01/T04 evidence; an SR²AM trace-
capture addendum based only on T02; focused fixtures/tests; active-plan dependency
repair; harness documentation; and minimal public-notebook explanation.

Out of scope: changing or registering EXP-0001; adding an executable experiment or
condition; parsing ordinary reasoning prose as a control decision; training data,
fine-tuning, learned-kernel, or benchmark construction; model/API/browser/benchmark/
cloud/paid execution; Phase 2; and edits to the frozen human reading, agent extraction,
reconciliation, or completed T00–T04 ledgers.

## Definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| T04.5-DOD-01 | T04 and T02 are integrated, the combined T00–T04 baseline passes, the worktree contains no execution artifact, and the prescribed T04.5 branch is active. | Git ancestry/status plus baseline `make check` with portable Quarto. | met |
| T04.5-DOD-02 | `RQ-H2K` is repository-native, planned/deferred, has no active experiment, names planning regulation first, states Phase 1 capture/conclusion limits, leaves EXP-0001 unchanged, and authorizes no later phase. | Research-track documentation, research-question entry, decision entry, risk record, and public notebook. | met |
| T04.5-DOD-03 | The generic harness has a typed, source-neutral regulation-decision contract covering every required source kind, selected mode, optional policy/mode/confidence/override/fallback data, input references, raw/config evidence references, and field provenance. | Typed models, payload builder/parser, JSON Schema, and positive/negative tests. | met |
| T04.5-DOD-04 | Event schema v0.2 is explicit, adapters declare the emitted version, v0.1 event streams remain readable without reinterpretation, mixed-version appends fail, and regulation decisions cannot appear under v0.1. | Schema constants, legacy fixture, compatibility and append tests, and harness docs. | met |
| T04.5-DOD-05 | Required regulation evidence is enforced: source kind is typed, selected mode is nonempty, raw or deterministic resolved-config evidence is present, unavailable optional fields remain null/unavailable, and no internalization assertion field exists. | Dataclass and schema negative tests, including unsupported source and missing-evidence cases. | met |
| T04.5-DOD-06 | The SiRA adapter emits exactly one `experiment_assignment` regulation decision per run, derives mode from the exact bound config/command, references retained raw and resolved configuration evidence, and leaves absent confidence/override/fallback unavailable. | Adapter mapping addendum and exact normalized-event tests for both modes. | met |
| T04.5-DOD-07 | SiRA emits no invented per-step configurator decision; malformed upstream control-like fields remain byte-preserved raw and unnormalized; all existing upstream fields remain retained. | Malformed-control fixture mutation and raw-hash/normalized-event regressions. | met |
| T04.5-DOD-08 | Reactive and simulative SiRA assignments have identical source/policy metadata outside the approved decision/condition and attempt-local evidence references. | Pair-metadata regression tied to the existing matched-command assertion. | met |
| T04.5-DOD-09 | A distinct SR²AM addendum records later Phase 1 capture requirements for explicit regulation/configurator output, plan choice/horizon, structured futures, reactive output, identities, raw paths, and parser provenance, with T02-grounded availability and unknowns preserved. | Machine-readable addendum plus source-path/status coverage tests. | met |
| T04.5-DOD-10 | The active plan inserts T04.5 and makes T05 depend on it; repository harness docs and the public notebook explain evidence-preservation-only scope, no learned kernel/Phase 2, and unchanged EXP-0001. | Plan/doc/notebook diffs and site tests/render. | met |
| T04.5-DOD-11 | All prompt-mandated positive, negative, compatibility, pair-parity, and raw-preservation cases have focused regression coverage. | Focused pytest commands and test inventory. | met |
| T04.5-DOD-12 | Focused smoke, strict typing, schema/repository validation, full pre-review `make check`, independent spec-conformance review, fixes/rereview, and post-review `make check` pass. | Exact commands, outputs, and review verdict in the evidence log. | met |
| T04.5-DOD-13 | EXP-0001 remains absent and unchanged, every execution permission remains false, compute remains zero, and no model/API/browser/benchmark/training/cloud/paid action or artifact occurs. | Registry/project-state/compute/diff inspection. | met |
| T04.5-DOD-14 | T04.5 is recorded as a distinct change without rewriting completed T00–T04 history, and work stops before T05. | Scoped Git diff, unchanged completed ledgers/reading artifacts, and final next-work boundary. | met |

## Implementation mapping

| Intended change | Mapped DoD |
|---|---|
| RQ-H2K track, research question, decision, risk, plan, and notebook surfaces | T04.5-DOD-02, T04.5-DOD-10, T04.5-DOD-14 |
| Typed regulation-decision model and v0.2/legacy event-schema boundary | T04.5-DOD-03 through T04.5-DOD-05 |
| SiRA assignment normalization and mapping addendum | T04.5-DOD-06 through T04.5-DOD-08 |
| SR²AM later-capture audit addendum | T04.5-DOD-09 |
| Compatibility, negative, raw-preservation, pair, document, and site tests | T04.5-DOD-04 through T04.5-DOD-13 |
| Review, full gates, zero-execution audit, and ledger closeout | T04.5-DOD-12 through T04.5-DOD-14 |

## Planned evidence

- Focused regulation/event/schema/SiRA/document pytest suite.
- Ruff format/lint, strict mypy, YAML/JSON/schema validation, and `git diff --check`.
- Full `make check` using the existing portable Quarto 1.9.38 executable.
- Independent whole-diff review against this checklist and the authoritative prompt.
- Post-review repeat of the focused smoke and complete repository gate.
- Static inspection of project state, experiment registry, compute ledger, changed
  paths, and forbidden execution-artifact patterns.

## Progress log

- 2026-08-08: Read the Assembly skill, T04.5 prompt and addendum specifications,
  repository doctrine and plan policy, active Phase 0.75 plan, research/decision/risk/
  reproducibility surfaces, all schemas, the original harness specification, reviewed
  T01/T02 audit contracts, and the relevant T03/T04 harness, adapter, fixture, report,
  and test surfaces before editing implementation code.
- 2026-08-08: Confirmed integration commit `2ff5ed3` contains accepted T02 and T04
  ancestry, the tracked worktree is clean, and no run/model/cloud artifact is present.
- 2026-08-08: The first plain baseline reached the site gate after 199 passing tests
  but found no `quarto` on `PATH`. Repeated the exact gate with the repository's existing
  portable Quarto 1.9.38 executable; all 199 tests, strict typing, validation, 14-page
  render, and rendered-site validation passed.
- 2026-08-08: Created `phase-0.75/h2k-option-preservation`, opened this distinct T04.5
  ledger at `in-progress`, and confirmed no scout or external execution is applicable.
- 2026-08-08: Implemented the mapped governance, typed event-contract, SiRA,
  SR²AM-addendum, compatibility, plan, documentation, notebook, and regression-test
  changes. The first focused run exposed an omitted top-level `field_provenance` key in
  the strict parser's expected-key set; fixed that primitive and retained exact-key
  rejection for all interpretive extensions.
- 2026-08-08: Focused behavior, lint, typing, data-parse, and diff checks passed. The
  first full pre-review gate requested Ruff formatting for five changed Python files;
  formatted them and repeated the complete gate successfully.
- 2026-08-08: Confirmed the experiment registry remains empty, all five project-state
  execution permissions remain false, every compute counter remains zero, the compute
  ledger has no entries, and the scoped diff does not touch frozen reading,
  reconciliation, or completed T00–T04 ledger artifacts.
- 2026-08-08: Independent review found one assembly-blocking contract-plane mismatch:
  JSON Schema accepted value/provenance contradictions that the canonical typed parser
  rejected. No other spec-conformance, correctness, provenance, compatibility, safety,
  execution, or scope finding was reported. Marked DOD-03, DOD-05, DOD-11, and DOD-12
  partial pending repair and rereview.
- 2026-08-08: Strengthened JSON Schema with bidirectional value/provenance constraints
  for all locally expressible fields; added 22 schema/parser contradiction cases; and
  documented/tested selected-mode membership as a semantic parser boundary because
  Draft 2020-12 cannot compare sibling values.
- 2026-08-08: The first rereview caught that an explicit Ruff invocation had reformatted
  the schema as JSONC with trailing commas after the earlier passing smoke. Removed only
  those mechanical commas, restored strict JSON, repeated the focused/static checks,
  and returned the same repaired contract for rereview.
- 2026-08-08: The same reviewer verified agreement across 112 valid/invalid
  value-provenance combinations, all 22 contradiction regressions, strict JSON, the
  documented semantic-parser boundary, and the 99-test focused suite. Rereview was
  clean with no remaining actionable finding.
- 2026-08-08: Post-review focused/static gates and the complete repository gate passed:
  strict typing, 236 tests, repository validation, four generated views, all 14 notebook
  pages, and rendered-site validation. Marked every T04.5 DoD item met and stopped
  without beginning T05.

## Decision log

- 2026-08-08: Treat T04.5 as one Assembly item and stop before T05.
- 2026-08-08: A model/GPU scout is not applicable: this item is a deterministic local
  schema, adapter, provenance, and documentation retrofit whose source contract forbids
  every model, API, browser, benchmark, cloud, and paid execution path.
- 2026-08-08: Preserve accepted T01/T02/T04 history by adding explicitly named T04.5
  mapping/audit addenda rather than relabeling their original evidence as if it had
  always contained the new track.

## Evidence log

- Plain baseline: `make check` — **environment-partial**; lock/install, Ruff, strict
  mypy, all 199 tests, repository validation, and public-data generation passed, then
  the site command could not find `quarto` on `PATH`.
- Complete baseline:
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — **passed**; frozen install, format/lint, strict mypy, 199 tests, repository
  validation, four generated views, 14-page render, and rendered-site validation all
  passed.
- Focused smoke:
  `PYTHONPATH=src uv run --no-sync pytest -o addopts='' tests/test_harness_regulation.py tests/test_harness_events.py tests/test_harness_schemas.py tests/test_sira_adapter.py tests/test_h2k_contracts.py -q`
  — **passed**, 76 tests.
- Focused static/data gates: scoped `ruff check`, strict `mypy`, YAML/JSON parse, and
  `git diff --check` — **passed**.
- Complete pre-review gate:
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — **passed**; 34 Python files formatted, Ruff clean, strict mypy clean, 213 tests,
  repository validation, four generated views, 14-page render, and rendered-site
  validation all passed.
- Zero-execution/scope audit: empty experiment registry; false project execution
  permissions; zero compute counters and entries; no frozen history edits — **passed**.
- Independent review, first pass — **one medium assembly-blocking finding**: public
  JSON Schema under-enforced typed-parser provenance consistency; all other DoD areas
  clean.
- Repaired focused smoke — **passed**, 99 tests. An intermediate explicit formatter
  produced invalid JSONC punctuation; same-reviewer rereview caught it before closeout,
  and strict JSON plus the 99-test smoke passed again after mechanical correction.
- Independent rereview — **clean**; schema/parser decisions agreed across 112
  combinations, all contradiction regressions passed, and no actionable finding
  remained.
- Post-review focused/static gate — **passed**; 99 tests, scoped Ruff, strict mypy,
  strict JSON parse, and `git diff --check`.
- Complete post-review gate:
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — **passed**; frozen install, format/lint, strict mypy, 236 tests, repository
  validation, four generated views, 14-page render, and rendered-site validation all
  passed.
- Scout/evidence execution: **not applicable and prohibited** by the T04.5 contract.

## Unresolved source gaps

- The accepted SiRA source exposes no explicit per-step configurator/regulation record;
  confidence, override, fallback, and per-step control input sequences remain
  unavailable. Fixed reactive/simulative mode is only an experiment assignment.
- The accepted SR²AM audit exposes no typed configurator decision, plan/no-plan choice,
  model-selected horizon/depth, structured predicted futures, prediction confidence,
  or selected plan. Complete default-chat usage plus upstream-recorded model,
  environment, and UTC-event identity also remain unavailable.
- These gaps leave a future external-versus-explicit-model comparison feasibility
  **undetermined** and support no latent-internalization or learned-kernel claim.

## Blockers and user actions

None.

## Next permitted work

No additional work is permitted under this T04.5 item. T05 is a separate, not-started
task whose dependency is now satisfied; it was not begun by this change.
