# T06 — Phase 0.75 Integration and Closeout Assembly Ledger

Assembly status: **successful**

Started: 2026-08-08

## Source contract

The authoritative item contract is
`GIC_Lab_H2K_Option_Preservation_Addendum_v1_1/prompts/06_PHASE_0_75_INTEGRATION_REVIEW_V1_1.md`,
interpreted under `AGENTS.md`, `docs/PLANS.md`, the active Phase 0.75 plan, the
original Phase 0.75 build package, the v1.1 option-preservation specification, and
the successful T01 through T05 ledgers.

The implementation item is T06 only. It begins at integration commit
`979ff7aa11c39b04eb8578d103cccf29606c6e60`, whose ancestry contains the accepted
T01, T02, T03, T04, T04.5, and T05 branch tips. T07 execution is not part of this
item.

## Target contract

Close Phase 0.75 as one coherent, independently reviewed repository state; open one
active Phase 1 artifact-execution plan while keeping all execution and compute
authority false; preserve EXP-0001 as exactly the SiRA simulative-versus-reactive
comparison; and make the only next action an explicit human authorization for the
single disabled smoke profile. RQ-H2K remains a planned/deferred infrastructure-
evidence consumer and creates no experiment, condition, interpretation, or later
phase.

## Success criterion

The completed Phase 0.75 plan and active Phase 1 plan satisfy lifecycle validation;
project, registry, public-site, schema, source-pin, and event-version state agree;
the readiness handoff names the exact smoke plan, exact authorization decisions,
proposed cap, retained evidence, cleanup, and nonblocking questions; an independent
adversarial reviewer has no unresolved valid finding; the post-review `make check`
passes; and static zero-execution evidence confirms that no model, API, benchmark,
training, cloud, or paid-compute action occurred.

## Scope

In scope: accepted-output ancestry and integration audit; source-grounded manifest
integration; lifecycle and public-state transition; Phase 0.75 ledger closeout;
creation of the active Phase 1 execution plan; the Phase 1 smoke-readiness handoff;
focused compatibility, boundary, safety, and public-state regressions; independent
review; and deterministic local gates.

Out of scope: executing EXP-0001; authorizing a run; model or API calls; browser or
benchmark execution; training; checkpoint downloads; cloud mutation; paid compute;
scientific interpretation; a new EXP-0001 condition; an H2K experiment or learned
kernel; Phase 2; and edits to frozen reading or reconciliation artifacts.

## Definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| T06-DOD-01 | The closeout base contains accepted T01–T05 ancestry, including T04.5, and shared manifests contain only source-supported facts while unknowns remain null or unavailable. | Git ancestry checks, manifest/audit cross-checks, repository validation, and review. | met |
| T06-DOD-02 | Plan lifecycle, project state, experiment registry, public navigation, schemas, source pins, and event-version compatibility validate as one coherent state. | Focused lifecycle/schema/site/registry/compatibility tests and `make check`. | met |
| T06-DOD-03 | Independent adversarial review covers hidden execution paths, unauthorized operations, fabricated fields, pair leakage, secrets, budgets, retry/overwrite safety, stale prose, scientific wording, source classification, EXP-0001 isolation, and compatibility; every valid finding is fixed and rereviewed. | Reviewer verdicts, mapped fixes, focused smokes, and post-review gate. | met |
| T06-DOD-04 | RQ-H2K remains planned/deferred, has no active experiment, and adds no Phase 2 or other later phase to this package. | Research-track, registry, roadmap, state, notebook, and negative-boundary tests. | met |
| T06-DOD-05 | EXP-0001 still tests exactly SiRA simulative versus reactive behavior, with no internalization claim, H2K condition, or future-track influence on its hypothesis, estimand, metrics, validity, or outcome. | Protocol/config/profile/appendix assertions and review. | met |
| T06-DOD-06 | Smoke and pilot plans preserve source-grounded regulation-decision evidence without interpreting it; future-track sufficiency is infrastructure evidence only. | Run-profile/condition-plan validation, retention contracts, readiness wording, and tests. | met |
| T06-DOD-07 | The Phase 0.75 DoD and evidence ledger are complete, successful, and placed under `docs/exec-plans/completed/`. | Final plan path, lifecycle validation, and complete evidence/status tables. | met |
| T06-DOD-08 | One authoritative active Phase 1 artifact-execution plan exists and names T07 as the next gated item. | Active plan content, state pointer, lifecycle tests, and rendered status. | met |
| T06-DOD-09 | Project state is Phase 1 active while paid compute, prototype execution, benchmark execution, training, and cloud mutation remain false. | `docs/PROJECT_STATE.yaml`, policy validation, tests, and zero-execution audit. | met |
| T06-DOD-10 | `docs/readiness/PHASE_1_SMOKE_READINESS.md` records the exact next run-plan ID, exact user decision fields, proposed API cap, expected artifacts including regulation-decision evidence, rollback/cleanup, unresolved nonblocking questions, and the infrastructure-only future-track boundary. | Readiness document plus semantic regressions and review. | met |
| T06-DOD-11 | Canonical and public lifecycle surfaces accurately report Phase 0.75 complete and Phase 1 active but non-executable. | README/notebook/generated-status tests, Quarto render, and site validation. | met |
| T06-DOD-12 | No EXP-0001, model, API, benchmark, browser, training, cloud, or paid-compute execution occurs; compute accounting remains zero. | Project state, compute manifest, registry/results state, forbidden-artifact audit, and diff review. | met |
| T06-DOD-13 | Focused smoke, full pre-review gate, clean independent rereview, post-review smoke, and final `make check` all pass. | Exact commands and outputs in the evidence log. | met |

## Implementation mapping

| Intended change | Mapped DoD |
|---|---|
| Integration ancestry and source/manifests audit | T06-DOD-01, T06-DOD-02, T06-DOD-12 |
| Phase 0.75 ledger completion and lifecycle move | T06-DOD-02, T06-DOD-07, T06-DOD-11 |
| Active Phase 1 plan and non-executable project state | T06-DOD-08, T06-DOD-09, T06-DOD-11, T06-DOD-12 |
| Phase 1 smoke-readiness handoff | T06-DOD-04 through T06-DOD-06, T06-DOD-10 |
| Boundary, compatibility, safety, and public-state regressions | T06-DOD-02 through T06-DOD-06, T06-DOD-09 through T06-DOD-13 |
| Independent review, repair loop, gates, and evidence closeout | T06-DOD-03, T06-DOD-07, T06-DOD-12, T06-DOD-13 |

## Planned evidence

- Exact ancestry checks for every accepted T01–T05 branch tip and the T04.5 dependency.
- Focused lifecycle, project-state, experiment, run-profile, schema, event,
  source-pin, H2K-boundary, authorization, budget, safety, and site tests.
- Source-tree repository validation, Ruff, strict mypy, strict YAML/JSON parsing, and
  `git diff --check`.
- Full `make check` with the existing portable Quarto 1.9.38 executable before review
  and after the clean rereview.
- Independent whole-tree spec-conformance review against every T06 DoD item.
- Static zero-execution audit of state, compute counters, results, authorization,
  artifact roots, secrets, and changed paths.

## Progress log

- 2026-08-08: Read the Assembly skill, v1.1 T06 prompt, repository doctrine and plan
  policy, original T06 contract, updated roadmap/git flow, H2K and harness addenda,
  active Phase 0.75 plan, and accepted task ledgers before implementation.
- 2026-08-08: Verified that integration commit
  `979ff7aa11c39b04eb8578d103cccf29606c6e60` contains every accepted T01–T05 branch
  tip, including T04.5, found a clean worktree, and created the prescribed
  `phase-0.75/closeout` branch.
- 2026-08-08: The baseline `make check` passed with 256 tests, repository validation,
  four generated public views, a 15-page Quarto render, and rendered-site validation.
- 2026-08-08: Opened T06 as one Assembly item. No execution or cloud action is
  authorized or required; the item-specific evidence run is deterministic local
  validation rather than a model/GPU scout.
- 2026-08-08: Implemented the integrated manifests, Phase 1 plan/readiness/public
  surfaces, lifecycle contracts, and closeout regressions. The initial focused closeout
  suite and the wider harness safety/schema suite passed.
- 2026-08-08: Independent review returned `review-failed` with three accepted findings:
  profile eligibility was advisory rather than an authorization/runtime invariant; the
  pilot blocker label was tied to a later-phase transition; and two public research
  pages retained stale Phase 0/0.5 wording.
- 2026-08-08: Coupled profile authorization to eligibility, added exact parent ID/hash
  bindings to condition plans and project state, added pre-process policy regressions,
  made the pilot blocker phase-independent, and corrected the stale pages. The focused
  repair suite passed 103 tests.
- 2026-08-08: Rereview closed the stale-state/prose findings but reproduced a parent-
  identity replay by an undeclared child and found that the first binding revision had
  silently tightened run-plan v0.1.
- 2026-08-08: Repaired the primitive: runtime now schema-validates the complete parent,
  requires zero readiness blockers, validates every declared child, and accepts only
  canonical child fingerprints. Restored additive v0.1 compatibility for legacy
  unauthorized plans while requiring parent bindings for authorized plans.
- 2026-08-08: Sealed canonical child fingerprints into project authorization state and
  enforced the parent's exact pair/task identities, order, task source, model/dataset
  lineage, fixed inputs, aggregate budgets, and unique IDs. Shared exact source grammar
  rejects open-query prefix drift while condition-owned config and command hashes remain
  valid differences.
- 2026-08-08: The pre-transaction rereview returned clean with lifecycle-only work
  pending. Moved the successful Phase 0.75 plan to `completed/`, opened the sole active
  Phase 1 plan, and changed project state to Phase 1 while every execution permission
  and authorization binding remained false or empty.
- 2026-08-08: The final whole-tree review found one stale EXP-0001 README statement
  assigning resolved integration work to T06. Reassigned snapshot/materialization work
  explicitly to T07 preflight, stated that it is not an unresolved integration blocker,
  and added a semantic regression. The same reviewer returned a clean implementation
  rereview with T06-DOD-01 through T06-DOD-12 met and only the mechanical post-review
  gates pending for T06-DOD-13.

## Decision log

- 2026-08-08: Treat T06 as one Assembly item and do not begin T07.
- 2026-08-08: A model/GPU scout is not applicable and is prohibited because the T06
  contract expressly forbids EXP-0001, model, API, browser, benchmark, training,
  cloud, and paid-compute execution.
- 2026-08-08: Parent authorization owns an exact typed child-membership set. Copying
  the parent's ID, hash, or authorization reference is insufficient; the invoked plan
  must match a declared canonical child document before process creation.
- 2026-08-08: Extend run-plan/run-profile v0.1 additively: legacy unauthorized and
  authorized documents remain readable and round-trip without invented bindings.
  Current runtime policy, not historical parsing, refuses execution without a sealed
  parent/child contract. Do not rewrite historical fixtures to hide a migration break.
- 2026-08-08: Treat task-source identity as a typed grammar, not a substring heuristic,
  and make exact parent/child membership, lineage, and aggregate limits runtime-visible
  before workspace or process creation.

## Evidence log

- Accepted ancestry: `git merge-base --is-ancestor <T01-through-T05 branch> HEAD` for
  all six task branches, including T04.5 — **passed** at
  `979ff7aa11c39b04eb8578d103cccf29606c6e60`.
- Baseline:
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — **passed**; frozen lock/install, Ruff formatting and lint, strict mypy, 256 tests,
  repository validation, four generated views, a 15-page render, and rendered-site
  validation all passed.
- Scout/evidence execution: **not applicable and prohibited** by the T06 source
  contract; deterministic local gates are the required item evidence.
- Initial implementation focused smoke:
  `PYTHONPATH=src uv run --no-sync pytest -o addopts='' tests/test_phase1_closeout.py
  tests/test_exp0001_protocol.py tests/test_validation.py -q` — **passed** with 5
  closeout tests after correcting the installed-package path; the wider focused
  harness/schema/safety suite passed 138 tests.
- Initial independent review — **review-failed** with three accepted findings:
  unenforced profile eligibility, phase-stale pilot blocker state, and stale resource/
  research-question public text. No execution, manifest, secret, pair-isolation, H2K,
  or scientific-boundary violation was found.
- First repair focused suite — **passed**: 103 selected policy/schema/CLI/EXP/state
  tests, Ruff, and strict mypy.
- First rereview — **review-failed**: two original findings were resolved; the reviewer
  reproduced undeclared-child parent-binding replay and identified a run-plan v0.1
  compatibility regression.
- Second repair focused suites — **passed**: 61 model/schema/policy/CLI tests, 95
  executor/artifact/SiRA tests, and 271 wider tests with only the five intentionally
  pending final-lifecycle assertions deselected; strict mypy passed.
- Final authorization-integrity repair suite — **passed**: Ruff formatting/lint and
  strict mypy passed; 46 policy/CLI/EXP tests passed with one pending-lifecycle test
  deselected. The complete pre-transaction suite had 284 passing tests and only the
  five expected pending-lifecycle failures.
- Independent pre-transaction rereview — **clean**: no authorization, compatibility,
  scientific-boundary, or safety finding remained; T06 lifecycle movement could
  proceed.
- Lifecycle closeout smoke:
  `PYTHONPATH=src uv run --no-sync pytest -o addopts='' tests/test_phase1_closeout.py
  tests/test_validation.py tests/test_sitegen.py tests/test_h2k_contracts.py
  tests/test_exp0001_protocol.py -q` — **passed** with 64 tests; `git diff --check`
  passed.
- Full pre-review closeout gate:
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — **passed**; frozen lock/install, Ruff, strict mypy, 289 tests, repository
  validation, four generated views, a 16-page Quarto render, and rendered-site
  validation passed.
- Final whole-tree review — **review-failed** on one implementation issue and one
  intentional ledger-closeout item: the EXP-0001 README assigned T07 preflight work to
  completed T06, and this ledger still awaited the reviewer verdict and final gates.
- Review repair smoke — **passed**: the stale snapshot/materialization wording and its
  semantic regression passed the 65-test lifecycle/H2K/EXP/site/validation suite,
  Ruff, and `git diff --check`.
- Independent implementation rereview — **clean**: every required adversarial category
  was covered; the reviewer independently passed the same 65 tests and `make validate`,
  found no stale lifecycle text, and classified T06-DOD-01 through T06-DOD-12 met.
- Static zero-execution audit — **passed**: exactly one active plan; successful Phase
  0.75 plan under `completed/`; no frozen reading/reconciliation edit; no changed-file
  credential-pattern match; all five execution/mutation flags false; null/empty run-
  profile authorization; zero compute counters and entries; EXP-0001 `not-run` with
  empty measurements/artifacts; and no `artifacts/` or `traces/` root.
- Post-review smoke:
  `PYTHONPATH=src uv run --no-sync pytest -o addopts='' tests/test_phase1_closeout.py
  tests/test_validation.py tests/test_sitegen.py tests/test_h2k_contracts.py
  tests/test_exp0001_protocol.py -q` — **passed** with 65 tests; `git diff --check`
  passed.
- Final post-review gate:
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — **passed**; frozen lock/install, Ruff, strict mypy, 290 tests, repository
  validation, four generated views, a 16-page Quarto render, and rendered-site
  validation passed.
- Final independent ledger/gate verification — **clean / review-complete**: the reviewer
  classified T06-DOD-01 through T06-DOD-13 met with none partial or blocked, independently
  reran the full 290-test gate and `git diff --check`, and reconfirmed the lifecycle,
  zero-authority, zero-compute, and no-artifact state.

## Blockers and user actions

None for T06. A later T07 turn must supply the exact explicit authorization fields
listed in the Phase 1 readiness handoff before the smoke pair can execute.

## Next permitted work

T06 is successful and stops here. The only next action is a separate, explicit,
current-turn human authorization containing every decision field in
`docs/readiness/PHASE_1_SMOKE_READINESS.md`. Without it, T07 remains blocked and no
model, API, browser, benchmark, training, cloud, or paid-compute execution is permitted.

## T06 outcome

Phase 0.75 is successful and completed; Phase 1 is the sole active control-plane phase
with every execution and mutation permission false. EXP-0001 remains exactly the
unauthorized SiRA simulative-versus-reactive comparison, RQ-H2K remains planned/deferred
with no experiment or later phase, and the runtime now verifies a fully validated,
eligible parent profile plus its sealed canonical child fingerprints and exact paired
contract before any workspace or process creation. No empirical result was produced.
