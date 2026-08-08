# Phase 1 — Artifact Execution

Status: **in-progress**

Started: 2026-08-08

## Source contract

The authoritative package contract is the original Phase 0.75-to-Phase 1 build
package as amended by
`GIC_Lab_H2K_Option_Preservation_Addendum_v1_1`, especially its updated execution
roadmap and T07 through T15 prompts. Repository authority is further constrained by
`AGENTS.md`, `docs/PLANS.md`, `docs/COMPUTE_POLICY.md`,
`docs/SECURITY_AND_SECRETS.md`, the locked EXP-0001 protocol/run profiles, and the
successful Phase 0.75 plan.

T06 opens this plan but authorizes no execution. Each live API/model/browser or cloud
work item requires the exact current-turn human authorization declared by its task
contract. A proposed budget, eligible profile, historical conversation, or this plan
is not authorization.

## Target contract

Produce a source-grounded artifact-execution and directional-reproduction record for
the released SiRA and SR²AM artifacts through sequential, separately authorized smoke
and pilot gates. Preserve raw-to-normalized lineage, exact cost and compute accounting,
condition isolation, safe cleanup, and precise reproduction-level labels. RQ-H2K may
consume trace-completeness infrastructure evidence only; it remains planned/deferred
and cannot add an experiment, condition, training path, learned kernel, or later phase.

## Scope

In scope: T07 through T15; the authorized SiRA paired smoke and pilot; evidence-only
analysis between execution gates; read-only SR²AM Lambda preflight; separately
authorized SR²AM smoke and pilot; raw artifact retention and hashes; regulation-
decision provenance; compute/API accounting; public preliminary reporting; and the
current Phase 1 closeout.

Out of scope: any execution without the exact current-turn authorization; protocol
adaptation to observed effects; confirmatory claims; a new EXP-0001 condition; a
harness-to-kernel comparison; learned-kernel training or distillation; Phase 2; and
cloud mutation outside the exact T12/T14 authorization contract.

## Phase definition of done ledger

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| P1-DOD-01 | Phase 0.75 is successful/completed; this is the one authoritative active plan; project execution/compute permissions remain false; only the disabled smoke profile is eligible for a later exact authorization. | Plan lifecycle/state/profile/readiness validation and public render. | met |
| P1-DOD-02 | T07 executes at most the one authorized SiRA smoke pair with complete raw, normalized, regulation-decision, budget, scoring, and cleanup evidence and no interpretation. | Immutable run/authorization records, artifacts/hashes, accounting, cleanup proof, and validation. | not-started |
| P1-DOD-03 | T08 independently reproduces the smoke summary, separates infrastructure/protocol/upstream/future-track gaps, and leaves any pilot unauthorized. | Raw-to-summary checks, infrastructure-only trace-sufficiency report, review, and gate. | not-started |
| P1-DOD-04 | T09 executes only a freshly authorized locked SiRA pilot without outcome-adaptive changes and reconciles every attempt. | Frozen task/order records, complete paired artifacts, budgets, and attempt dispositions. | not-started |
| P1-DOD-05 | T10 produces a reproducible exploratory EXP-0001 analysis with uncertainty, exact reproduction level, cost/deviation reporting, and no internalization or mechanism-attribution overclaim. | Validated result summary, registry/notebook/ledger updates, review, and gate. | not-started |
| P1-DOD-06 | T11 produces a read-only, launch-ready SR²AM-v0.1-8B Lambda contract with current price, hard termination, source-grounded trace requirements, failure tests, and no mutation. | Audited runbook/contracts, dry-run/failure tests, authorization sentence, and gate. | not-started |
| P1-DOD-07 | T12 launches only the exactly authorized SR²AM smoke, retains and transfers required evidence, reconciles cost, and verifies provider termination. | Immutable cloud attempt, raw artifacts/hashes, compute ledger, monitoring, and terminal-state proof. | not-started |
| P1-DOD-08 | T13 validates SR²AM artifact fidelity, runbook safety/cost predictability, and infrastructure-only trace sufficiency before proposing an unauthorized pilot. | Recomputed evidence, source/adapter lineage, repaired tests, review, and gate. | not-started |
| P1-DOD-09 | T14 executes only a freshly authorized locked SR²AM pilot and verifies artifact transfer, accounting, and termination without in-run design changes. | Immutable pilot records, artifacts/hashes, compute reconciliation, and terminal-state proof. | not-started |
| P1-DOD-10 | T15 closes the current Phase 1 unit with validated SiRA/SR²AM evidence, precise reproduction levels, uncertainty/cost/deviation reporting, and one proposed next scientific workstream that is not begun. | Result summaries, registry/notebook/decision/risk updates, review, final gate, and plan disposition. | not-started |
| P1-DOD-11 | Every executed attempt has explicit current-turn authorization, immutable identity, append-only raw evidence, version/hash lineage, finite budget enforcement, secret isolation, and verified cleanup; failed infrastructure is never a scientific negative. | Run/compute/artifact ledgers, policy checks, failure evidence, and cross-task review. | not-started |
| P1-DOD-12 | Regulation/control evidence remains source classified; experiment assignment and ordinary prose are never called learned regulation; RQ-H2K outputs are infrastructure-only and do not affect EXP-0001 validity or interpretation. | Typed events, trace-sufficiency reports, negative boundary tests, and public wording. | not-started |
| P1-DOD-13 | Every implementation/analysis task passes focused smoke, independent spec-conformance review, post-review smoke, and its required full gate before the next dependency begins. | Per-task assembly ledgers with exact commands, artifacts, reviewer verdicts, and status. | not-started |

## Work packages and implementation mapping

| Task | Work package | Mapped phase DoD | Current permission |
|---|---|---|---|
| T07 | Execute one authorized local/API SiRA smoke pair; capture regulation-decision evidence without interpretation. | P1-DOD-02, P1-DOD-11 through P1-DOD-13 | blocked-user-action |
| T08 | Analyze smoke infrastructure evidence and prepare an unauthorized pilot package. | P1-DOD-03, P1-DOD-11 through P1-DOD-13 | blocked until T07 succeeds |
| T09 | Execute the freshly authorized exploratory SiRA pilot. | P1-DOD-04, P1-DOD-11 through P1-DOD-13 | blocked until T08 and authorization |
| T10 | Analyze and publish the exploratory SiRA pilot. | P1-DOD-05, P1-DOD-11 through P1-DOD-13 | blocked until T09 succeeds |
| T11 | Build and validate the read-only SR²AM Lambda preflight. | P1-DOD-06, P1-DOD-11 through P1-DOD-13 | blocked until T10 succeeds |
| T12 | Launch and monitor the separately authorized SR²AM Lambda smoke. | P1-DOD-07, P1-DOD-11 through P1-DOD-13 | blocked until T11 and authorization |
| T13 | Analyze the SR²AM smoke and prepare an unauthorized pilot. | P1-DOD-08, P1-DOD-11 through P1-DOD-13 | blocked until T12 succeeds |
| T14 | Launch and monitor the separately authorized SR²AM Lambda pilot. | P1-DOD-09, P1-DOD-11 through P1-DOD-13 | blocked until T13 and authorization |
| T15 | Analyze SR²AM pilot evidence and close the current Phase 1 unit. | P1-DOD-10 through P1-DOD-13 | blocked until T14 succeeds |

Work is sequential. A completed execution does not authorize its analysis successor,
and an analysis recommendation does not authorize the next execution.

## T07 assembly control

Assembly status: **blocked-user-action**

Exact next profile: `PLAN-EXP0001-SMOKE`.

Target contract: materialize and execute one matched reactive/simulative pair under an
exact human-approved provider/model, API-cost cap, wall-time cap, and cleanup contract;
preserve complete artifact and source-grounded regulation-decision evidence; and stop
without scientific interpretation or pilot progression.

The exact authorization fields, proposed USD 4.00 cap, pre-execution obligations,
expected artifacts, cleanup, questions, and infrastructure-only interpretation boundary
are in [`docs/readiness/PHASE_1_SMOKE_READINESS.md`](../../readiness/PHASE_1_SMOKE_READINESS.md).
The locked profile is
[`PLAN-EXP0001-SMOKE`](../../../experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml).

## Authorization and mutation boundary

Current project state keeps paid compute, prototype execution, benchmark execution,
training, and cloud mutation false. T07 cannot begin a live action until a later user
turn names every readiness authorization field. T09 requires a fresh pilot
authorization. T12 and T14 separately require their exact cloud mutation, hardware,
data, cost/time, artifact-transfer, and termination authority. Read-only inspection or
preflight never supplies mutation authority.

## Planned evidence

- One Assembly ledger per T07–T15 task with DoD mappings and exact evidence.
- Schema-valid immutable plans, commands, events, artifacts, summaries, and compute
  records linked to pinned source/model/dataset/environment revisions.
- Focused deterministic tests plus independent spec-conformance review and post-review
  `make check` for each work item.
- Real CUDA/cloud evidence only for the separately authorized SR²AM execution tasks;
  local/API SiRA evidence is never presented as CUDA evidence.
- Public notebook updates that separate infrastructure, exploratory evidence,
  reproduction level, and unsupported claims.

## Progress log

- 2026-08-08: T06 created the Phase 1 control plane after integrating and reviewing
  Phase 0.75. `PLAN-EXP0001-SMOKE` is the only profile eligible for a later human
  authorization; the pilot and all SR²AM execution remain blocked.
- 2026-08-08: All project execution and compute permissions opened as false. No model,
  API, browser, benchmark, training, cloud, or paid-compute action occurred during the
  transition.
- 2026-08-08: Parent-profile eligibility became a typed authorization gate: condition
  plans bind the exact profile plan ID and SHA-256; project state fully validates and
  binds the same profile and its canonical declared-child fingerprints before
  execution; and blocked or undeclared plans cannot materialize authorization.

## Decision log

- 2026-08-08: Keep authorization eligibility distinct from live readiness. T07 owns
  deterministic command/environment/budget/log/cleanup materialization after exact
  authorization and must stop before execution if any requirement fails.
- 2026-08-08: Treat all RQ-H2K trace-sufficiency outputs as infrastructure evidence;
  they neither block EXP-0001 on optional-field absence nor support an internalization
  claim.

## Blockers and user actions

T07 is blocked on one current-turn human authorization containing every exact field in
the smoke-readiness document. No other Phase 1 work package may begin first.

## Next permitted work

After that authorization only, T07 may perform its required preflight and, if every
gate passes, execute exactly `PLAN-EXP0001-SMOKE`. It must stop after the one pair.
