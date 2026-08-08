# Phase 0.75 — Upstream Audit, Harness, and Protocol Lock

Status: **in-progress**

Started: 2026-08-07

## Source contract

The authoritative contract is the user's Phase 0.75 build instruction, beginning with
T00, “Open Phase 0.75 and repair the control plane,” plus the approved v1.1
harness-to-kernel option-preservation addendum. The original package manifest identifies
the repository state at commit `d3014d907d8f2c8526d7f671abf3f5b524cdebb4`; the
addendum inserts T04.5 between the integrated T02/T04 state and T05. This plan adapts
those packages to the repository's execution-plan and evidence conventions. T04.5 and
T05 are complete; T06 is the next permitted assembly item.

## Target contract

Prepare a reproducible, non-executing path from completed reading reconciliation to
later SiRA and SR²AM artifact evaluation. Phase 0.75 may statically audit pinned
upstream sources, build an authorization- and evidence-preserving experiment harness,
create source-grounded adapters or explicit schema-gap reports, and lock a draft
`EXP-0001` protocol with execution disabled. It also preserves source-grounded control-
decision provenance for the planned/deferred RQ-H2K option without activating that
track or changing EXP-0001. It may not execute a model, API,
benchmark, training job, or cloud resource.

## Scope

In scope: control-plane repair; static audits of pinned SiRA and SR²AM source commits;
typed harness records, schemas, tests, and CLI; source-derived fixtures; a SiRA adapter
or documented schema gaps; a draft `EXP-0001` protocol and disabled smoke/pilot run
plans; a source-neutral regulation-decision contract and source-grounded SiRA/SR²AM
capture requirements; deterministic local validation; independent review; and Phase
0.75 closeout.

Out of scope: model or API calls; prototype, benchmark, pilot, or training execution;
checkpoint downloads; browser installation; cloud mutation or paid compute; scientific
reinterpretation of the completed GIC reconciliation; and software or content license
selection. RQ-H2K implementation, learned-kernel training, a new experimental
condition, Phase 2, or any claim of latent internalization is also out of scope.

## Phase definition of done ledger

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| P075-DOD-01 | Successful Phase 0 and Phase 0.5 plans are completed, one Phase 0.75 plan is authoritative and active, and repository/public lifecycle state agrees. | Lifecycle validator, state/public generation tests, links, and rendered notebook. | met |
| P075-DOD-02 | Pinned SiRA and SR²AM commits have source-grounded static execution audits without upstream execution. | Audit documents, verified pins, and reviewer findings. | met |
| P075-DOD-03 | The harness enforces explicit authorization, budgets, argument-array commands, append-only events, raw-evidence preservation, artifact hashes, version identity, and credential isolation. | Typed modules, schemas, unit tests, CLI smoke, and review. | met |
| P075-DOD-04 | SiRA has a real source-grounded adapter or a documented schema gap; normalized fields are never invented. | Adapter tests, source-derived fixtures, provenance labels, and gap report. | met |
| P075-DOD-05 | Draft `EXP-0001` and its smoke/pilot run plans exist with execution and interpretation disabled unless their profile explicitly permits interpretation. | Schema-valid protocol/run plans and authorization regressions. | met |
| P075-DOD-06 | Full local checks and independent spec-conformance review pass with no unresolved critical issue. | `make check`, review record, fixes, and post-review `make check`. | partial |
| P075-DOD-07 | No model/API/benchmark/training/cloud execution occurs and compute accounting remains zero for the phase. | Project state, experiment registry, compute manifest, and repository diff. | partial |
| P075-DOD-08 | Phase closeout makes only the next SiRA smoke profile eligible for a later, explicit human authorization. | Closed ledger, disabled run plan, and Phase 1 handoff boundary. | not-started |
| P075-DOD-09 | RQ-H2K is planned/deferred with no active experiment; regulation decisions distinguish external assignment/control from explicit model output, preserve raw lineage, and do not change EXP-0001 or add a later phase. | T04.5 track/decision/risk records, typed event/schema, SiRA/SR²AM mappings, compatibility/negative tests, notebook boundary, review, and full gate. | met |

## Work packages and implementation mapping

| Task | Work package | Mapped phase DoD | Current permission |
|---|---|---|---|
| T00 | Repair lifecycle validation and open the Phase 0.75 control plane. | P075-DOD-01, P075-DOD-06, P075-DOD-07 | successful |
| T01 | Perform the pinned SiRA static audit. | P075-DOD-02, P075-DOD-04, P075-DOD-07 | successful |
| T02 | Perform the pinned SR²AM static audit and compatibility matrix. | P075-DOD-02, P075-DOD-07 | successful |
| T03 | Build the generic experiment harness. | P075-DOD-03, P075-DOD-07 | successful |
| T04 | Build the SiRA adapter and source-derived fixtures. | P075-DOD-03, P075-DOD-04, P075-DOD-07 | successful |
| T04.5 | Preserve the planned/deferred harness-to-kernel evidence option without activating it. | P075-DOD-03, P075-DOD-04, P075-DOD-06, P075-DOD-07, P075-DOD-09 | successful |
| T05 | Register and lock draft `EXP-0001` and disabled run plans. | P075-DOD-05, P075-DOD-07, P075-DOD-09 | successful |
| T06 | Integrate, review, and close Phase 0.75. | P075-DOD-01 through P075-DOD-09 | blocked until T01 through T05 succeed |

T04.5 began only from the combined accepted T00–T04 state, including T02, and completed
under its successful ledger. T05 depends on that result; the dependency is satisfied,
and T05 is the active workstream. T06 retains ownership of final project-state and
phase-closeout integration after T05 succeeds.

## T04.5 assembly control

Assembly status: **successful**

Target contract: preserve a future RQ-H2K comparison option through typed source
classification, raw lineage, and source-grounded SiRA/SR²AM trace requirements while
leaving EXP-0001, execution authority, and the roadmap scientifically unchanged.

The auditable DoD, implementation mapping, planned evidence, progress, and review state
are in [`docs/harness/T04_5_ASSEMBLY_LEDGER.md`](../../harness/T04_5_ASSEMBLY_LEDGER.md).
T04.5 adds no model/GPU scout; its source contract requires deterministic local gates
and forbids external execution.

## T05 assembly control

Assembly status: **successful**

Target contract: register the locked, exploratory SiRA simulative-versus-reactive
protocol and disabled smoke/pilot profiles while preserving RQ-H2K evidence as an
additive, non-scientific future-consumer contract.

The auditable DoD, implementation mapping, planned evidence, progress, and review state
are in [`docs/harness/T05_ASSEMBLY_LEDGER.md`](../../harness/T05_ASSEMBLY_LEDGER.md).
T05 adds no model/GPU scout; its source contract requires deterministic local gates and
forbids model, API, browser, benchmark, training, cloud, and paid execution.

## T00 assembly ledger

Assembly status: **successful**

Target contract: make plan lifecycle, project state, and public status one explicit,
validated control plane; open Phase 0.75 without beginning any audit or execution.

Success criterion: the baseline and post-change `make check` gates pass; lifecycle and
generated-state regressions pass; all public and canonical status surfaces agree; an
independent reviewer finds no unresolved valid T00 issue; and all execution permissions
remain false.

| ID | Required outcome | Mapped change and evidence | Status |
|---|---|---|---|
| T00-DOD-01 | Record the complete repository baseline before edits. | Exact `make check` result in the evidence log. | met |
| T00-DOD-02 | Move successful Phase 0 and Phase 0.5 plans to `completed/`. | Plan paths plus generalized lifecycle validation. | met |
| T00-DOD-03 | Validate plan placement, active/successful exclusion, authoritative-plan existence and phase/status agreement, and traversal rejection without historical path constants. | `src/giclab/validation.py` and focused regressions. | met |
| T00-DOD-04 | Make this the one authoritative active Phase 0.75 plan and keep all execution permissions false. | `docs/PROJECT_STATE.yaml`, plan validation, and state tests. | met |
| T00-DOD-05 | Make README, notebook home/navigation, and generated public status agree that Phase 0.5 is complete and Phase 0.75 is active. | Public source paths, generated copy test, Quarto render, and link validation. | met |
| T00-DOD-06 | Reclassify OQ-012 through OQ-015 as later architecture blockers while preserving their text verbatim. | `docs/OPEN_QUESTIONS.md` diff and review. | met |
| T00-DOD-07 | Add lifecycle and generated-public-state regression coverage. | Focused pytest commands and full gate. | met |
| T00-DOD-08 | Pass independent spec-conformance review and post-review `make check`. | Review result and exact final gate in the evidence log. | met |

## Progress log

- 2026-08-07: Read repository doctrine, plan policy, project state, completed phase
  ledgers, decisions, open questions, validation tests, public notebook surfaces, and
  the Phase 0.75 package contract before editing.
- 2026-08-07: Confirmed T00 requires no cloud/GPU scout and that all execution and
  mutation permissions must remain false.
- 2026-08-07: Created branch `phase-0.75/control-plane` for the package's recommended
  T00 workstream.
- 2026-08-07: Opened T00 at `in-progress`; no T01, T02, or T03 work has begun.
- 2026-08-07: Moved both successful historical ledgers to `completed/` and replaced
  the required Phase 0 filename with generalized plan discovery and one shared typed
  plan-header parser.
- 2026-08-07: Set Phase 0.75 active with every execution permission false; updated the
  README, notebook home/navigation, generated status, and public phase-transition note.
- 2026-08-07: Moved OQ-012 through OQ-015 unchanged into a later-architecture blocker
  section that explicitly does not block the first SiRA artifact execution.
- 2026-08-07: The first focused smoke exposed deleted tracked paths in repository file
  enumeration during plan moves and a line-wrap-sensitive prose assertion. Filtered
  repository enumeration to existing paths and made the prose assertion semantic, then
  reran the focused smoke successfully.
- 2026-08-07: The complete pre-review gate passed. T00 now awaits independent
  spec-conformance review and the post-review gate.
- 2026-08-07: Independent review classified T00 `review-failed`: authoritative-plan
  negative regressions were incomplete, public prose encoded a transient T00 fact that
  would become stale during permitted static audits, and generated status omitted plan
  files from its provenance statement. All three findings were accepted for repair.
- 2026-08-07: Added direct authoritative-plan existence, phase, status, active/completed,
  and successful/completed regressions; made public prose durable for the whole phase;
  and corrected generated-status provenance. The focused smoke passed with 29 tests.
- 2026-08-07: The same independent reviewer returned a clean rereview with
  T00-DOD-01 through T00-DOD-07 met and T00-DOD-08 pending only the post-review gate
  and ledger closeout.
- 2026-08-07: The complete post-review gate passed with 32 tests and a 14-page render.
  Marked every T00 DoD item met and closed T00 successfully without beginning T01,
  T02, or T03.

## Decision log

- 2026-08-07: Treat T00 as one Assembly item and stop after its review, evidence, and
  ledger closeout.
- 2026-08-07: Use directory placement plus the plan's explicit `Status` field as the
  plan lifecycle contract; do not retain required-path constants for historical plans.
- 2026-08-07: A model/GPU scout is not applicable to this control-plane-only item
  because its source contract expressly forbids execution.

## Evidence log

- Initial sandboxed baseline attempt: `make check` — did not reach repository gates;
  `uv lock --check` could not open the existing user uv cache under the filesystem
  sandbox. This is environment evidence, not a repository failure.
- Authorized baseline: `make check` — **passed**; lock check and deterministic package
  install passed, formatting/linting and strict typing passed, 23 tests passed,
  repository validation passed, Quarto rendered 13 pages, and rendered-site validation
  passed.
- Initial focused smoke: `PYTHONPATH=src .venv/bin/pytest tests/test_validation.py
  tests/test_sitegen.py -q` — **smoke-failed** with two failures: documentation-link
  validation attempted to read a deleted tracked plan during the move, and one generated
  prose assertion was line-wrap-sensitive.
- Recovered focused smoke: `PYTHONPATH=src .venv/bin/pytest tests/test_validation.py
  tests/test_sitegen.py -q` — **passed**; 24 focused tests passed.
- Pre-review gate: `make check` — **passed**; lock check and deterministic package
  install passed, formatting/linting and strict typing passed, 27 tests passed,
  repository validation passed, Quarto rendered 14 pages, and rendered-site validation
  passed.
- First independent spec-conformance review — **review-failed** with three findings:
  incomplete authoritative-plan regression branches, transient public phase wording,
  and incomplete generated-status provenance. No safety, execution, scientific, or
  source-preservation violation was found.
- Review-fix focused smoke: `PYTHONPATH=src .venv/bin/pytest tests/test_validation.py
  tests/test_sitegen.py -q` — **passed**; 29 focused tests passed, and `git diff
  --check` was clean.
- Independent rereview — **clean**; all three findings were resolved, no actionable
  issue remained, and T00-DOD-01 through T00-DOD-07 were independently classified
  `met`.
- Post-review gate: `make check` — **passed**; lock check and deterministic package
  install passed, formatting/linting and strict typing passed, 32 tests passed,
  repository validation passed, Quarto rendered 14 pages, and rendered-site validation
  passed.
- Scout/evidence run: **not applicable by T00 source contract**; this item is a local
  control-plane repair and expressly forbids model, API, benchmark, training, browser,
  checkpoint, cloud, and paid-compute activity.

## T00 outcome

T00 closed successfully. Plan lifecycle is filename-independent and enforced from one
typed plan-header contract; project state validates authoritative-plan existence,
phase, status, traversal, and active/completed placement; public status is generated
from declared state, completed plans, and zero-use compute records; and the first SiRA
artifact execution is no longer blocked by OQ-012 through OQ-015. The experiment
registry remains empty and every execution permission remains false.

## Blockers and user actions

None for T00. Any later model/API action, prototype or benchmark execution, checkpoint
download, browser installation, or cloud mutation requires a later phase contract and
the explicit authorization required by repository policy.

## Next permitted work

T00 must stop after its ledger is successful. Only then may T01, T02, or T03 begin as
separate Assembly items. No model, API, benchmark, training, or cloud execution becomes
authorized by completing T00.
