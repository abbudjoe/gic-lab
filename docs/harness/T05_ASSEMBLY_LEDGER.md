# T05 — EXP-0001 Protocol Lock Assembly Ledger

Assembly status: **successful**

Started: 2026-08-08

## Source contract

The authoritative item contract is
`GIC_Lab_H2K_Option_Preservation_Addendum_v1_1/prompts/05_EXP0001_PROTOCOL_LOCK_V1_1.md`,
interpreted under `AGENTS.md`, `docs/PLANS.md`, the active Phase 0.75 plan, the
research questions and falsification notes, the reproducibility contract, the
experiment and run-plan schemas, and the accepted T01 through T04.5 artifacts.

The implementation item is T05 only. It begins at integration commit
`471d6950087a1a10983aaa97bde8b2becf3b6aca`, which contains the successful T04.5
option-preservation work. T06 is not part of this item.

## Target contract

Register a review-ready exploratory `EXP-0001` comparison of exactly
`SIRA-SIMULATIVE` and `SIRA-REACTIVE`, with a locked scientific protocol, disabled
smoke and pilot profiles, explicit directional-reproduction/model-substitution
identity, current official-price-derived proposed caps, and an additive H2K evidence-
retention appendix that cannot affect EXP-0001 outcomes or imply learned internal
regulation.

## Success criterion

A human can review the scientific comparison and later approve the smoke protocol by
changing only authorization fields and the exact spend cap. Separate later-phase
runtime materialization must bind the immutable model substitution, source/protocol/
config/environment hashes, commands, cost enforcement, log ownership, and browser
cleanup before execution; those operational bindings may not change the locked science.
All protocol, registry, run-plan, notebook, provenance, and future-track boundaries are
machine-tested; local validation and independent spec-conformance review are clean; no
run has occurred; all current execution permissions remain false; compute accounting
remains zero; and work stops before T06.

## Scope

In scope: the EXP-0001 directory; scientific protocol and configuration; results stub;
profile-level smoke and pilot plans plus schema-valid condition attempt plans;
registry entry; protocol notebook page; official price record and cap calculations;
additive H2K trace-retention appendix; focused validation and public-site tests; active
plan status; independent review; and evidence closeout.

Out of scope: any API, model, browser, prototype, benchmark, evaluator, training,
checkpoint, cloud, or paid-compute execution; Phase 1 authorization; new experimental
conditions or ablations; an H2K experiment or outcome; a sample-size/power claim from
unseen effects; and Phase 0.75 closeout under T06.

## Definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| T05-DOD-01 | The accepted T01–T04.5 baseline and exact integration ancestry are recorded, the prescribed branch is active, and no execution artifact exists. | Git ancestry/status and baseline local gates. | met |
| T05-DOD-02 | `experiments/EXP-0001-sira-simulative-vs-reactive/` is complete and registered with independent `planned`, `not-evaluated`, and `pending` state. | Protocol/config/results files, registry validation, and tests. | met |
| T05-DOD-03 | The question, null, treatment/control, fixed variables, selected task family/data revision, pairing/counterbalancing, retry/exclusion rules, estimand, metrics, falsification, invalid-run rules, retention, and release policy are locked without adding a condition. | Protocol documents and semantic contract tests. | met |
| T05-DOD-04 | Treatment and control are exactly `SIRA-SIMULATIVE` and `SIRA-REACTIVE`, and their assignment is explicitly external experiment assignment rather than evidence of learned regulation. | Protocol/config/run-plan assertions and negative prose checks. | met |
| T05-DOD-05 | The evidence-retention appendix captures only source-grounded source kind, selected/available modes, policy identity/revision, raw references, optional override/fallback/confidence, field provenance, and trace sufficiency. | Appendix plus exact-key/required-field tests. | met |
| T05-DOD-06 | The appendix is additive, non-scientific for EXP-0001, future-consumable by planned/deferred RQ-H2K, and cannot change the hypothesis, estimand, metrics, outcome classification, or interpretation. | Cross-document boundary tests and notebook text. | met |
| T05-DOD-07 | The smoke profile is one minimal matched pair, execution unauthorized, and interpretation prohibited. | Profile manifest plus two schema-valid condition plans and tests. | met |
| T05-DOD-08 | The pilot is an exploratory paired sample chosen for workflow/variance estimation rather than unseen-effect power, with counterbalanced order and execution unauthorized. | Profile manifest plus schema-valid condition plans and tests. | met |
| T05-DOD-09 | Provider/model identity uses an immutable supported snapshot where possible, declares any historical substitution, and calls the intended evidence level directional reproduction rather than unqualified reproduction. | Model-strategy section, official provider source, run-plan identity, and tests. | met |
| T05-DOD-10 | Proposed spend caps are arithmetically derived from current official prices while every authorization field remains false. | Versioned pricing/cap record and arithmetic regression. | met |
| T05-DOD-11 | A public notebook protocol page states that no run has occurred and does not claim results, internalization, trace-to-internalization support, or H2K activation. | Notebook page, navigation, render, and tests. | met |
| T05-DOD-12 | Focused smoke, schema/repository validation, full pre-review `make check`, independent spec-conformance review, fixes/rereview, and post-review `make check` pass. | Exact commands, outputs, and reviewer verdict. | met |
| T05-DOD-13 | No prohibited execution occurs; all project execution permissions and compute counters remain false/zero; work stops before T06. | State/compute/diff/forbidden-artifact audit. | met |

## Implementation mapping

| Intended change | Mapped DoD |
|---|---|
| EXP-0001 protocol/config/results and registry | T05-DOD-02 through T05-DOD-04 |
| Scientific protocol detail and evidence-retention appendix | T05-DOD-03 through T05-DOD-06 |
| Disabled smoke and pilot profile/condition plans | T05-DOD-07, T05-DOD-08, T05-DOD-10 |
| Model substitution, immutable revision, official prices, and cap calculation | T05-DOD-09, T05-DOD-10 |
| Public notebook protocol page and navigation | T05-DOD-06, T05-DOD-11 |
| Validation/tests, review, zero-execution audit, and ledger closeout | T05-DOD-01, T05-DOD-12, T05-DOD-13 |

## Planned evidence

- Focused registry, protocol, run-plan, pricing-arithmetic, boundary, and site tests.
- YAML/JSON/schema validation, Ruff, strict mypy, and `git diff --check`.
- Full `make check` using the existing portable Quarto 1.9.38 executable.
- Independent whole-diff spec-conformance review against this checklist.
- Post-review focused smoke and complete repository gate.
- Static inspection of project state, registry, compute ledger, changed paths, and
  forbidden execution-artifact patterns.

## Progress log

- 2026-08-08: Read the Assembly skill, T05 prompt, repository doctrine and plan
  policy, active Phase 0.75 plan, research/falsification/reproducibility surfaces,
  experiment and run-plan schemas, accepted SiRA audit/command/adapter contracts, and
  T04.5 H2K evidence-preservation contract before editing experiment artifacts.
- 2026-08-08: Confirmed the clean integration commit contains accepted T04.5 ancestry,
  created `phase-0.75/exp0001-protocol`, and preserved all execution permissions as
  false.
- 2026-08-08: The initial `make check` passed lock/install, formatting, lint, strict
  typing, 236 tests, repository validation, and site-data generation, then Quarto
  failed compiling the existing theme. This is environment-partial until the isolated
  site gate determines whether the renderer failure is transient.
- 2026-08-08: Consulted the official OpenAI GPT-4o model catalog for current standard
  token rates and available dated snapshots without calling any model or experimental
  browser workload.
- 2026-08-08: The isolated site rerun passed all 14 existing pages, establishing that
  the baseline theme-compile failure was transient rather than a repository defect.
- 2026-08-08: Added the registered protocol/config/not-run result, exact treatment and
  control, paired smoke and pilot profile contracts, six schema-valid condition plans,
  official-price cap record, source-grounded future-consumer appendix, notebook page,
  and focused tests. Added a run-profile schema and repository-wide discovery so these
  plans cannot remain unvalidated implicit records.
- 2026-08-08: The first focused smoke stopped at an import-order finding; after the
  mechanical fix it exposed bare-name-only experiment-directory discovery and one
  line-wrap-sensitive prose assertion. Generalized discovery to descriptive
  `EXP-NNNN-*` directories, added a regression, and made the prose assertion semantic.
  The repaired 48-test focused smoke and repository validation passed.
- 2026-08-08: The first full gate found two stale T04.5 assertions that incorrectly
  equated “no active H2K experiment” with an empty global registry and permanently
  prohibited T05. Updated them to preserve the real deferred-track boundary while
  permitting registered EXP-0001. The complete pre-review gate then passed.
- 2026-08-08: Independent review returned `review-failed` with six valid findings:
  condition plans lacked task/pair/order bindings; authorization schema contradicted a
  later approval transition; non-completion was misclassified as falsification; the
  control-plane SHA/prose was stale; generic validation hardcoded EXP-0001; and pricing/
  model/dataset provenance was self-referential or unresolved. Marked the affected DoD
  entries partial and began root-cause repair.
- 2026-08-08: Replaced implicit pair prose with typed task/pair/order state on every
  condition plan and in the harness `RunPlan`; loading and retained run-plan documents
  now round-trip that identity. Registry-declared generic profile validation enforces
  exact plan bindings, true pair invariants, task sources/slices, model/dataset
  revisions, order, budgets, and current authorization policy. EXP-0001-specific locks
  are isolated from the generic profile schema and validator.
- 2026-08-08: Separated reusable authorization schema from current false-authorization
  policy, permitted required condition-owned config/command hashes during later
  materialization, added typed invalid/inconclusive criteria, corrected control-plane
  SHA/state, and added schema-valid official pricing plus canonical selected model and
  dataset manifest records.
- 2026-08-08: The first rereview confirmed the invalid-run, control-plane, pricing, and
  manifest fixes but found typed run-plan retention, materialized pair comparison, and
  generic profile-schema breadth incomplete. Added immutable typed task/pair models and
  round-trip evidence, narrowed pair comparisons to real invariants, and generalized
  profile stage/revision/substitution/readiness contracts. The repaired 85-test focused
  gate, Ruff, strict typing, source-tree validation, and diff check passed before the
  third reviewer pass.
- 2026-08-08: The same reviewer returned a clean third pass with no actionable finding,
  independently reran 93 focused tests, repository validation, and diff hygiene, and
  classified T05-DOD-01 through T05-DOD-11 and T05-DOD-13 met pending only the required
  post-review full gate.
- 2026-08-08: The post-review `make check` passed with 256 tests and a 15-page render.
  The final zero-execution audit found all project permissions false, every compute
  counter zero, no compute entries, no data/trace/run artifact directory, and no live
  authorization outside negative test fixtures. Marked every T05 DoD item met.
- 2026-08-08: The first final-tree closeout gate found one stale lifecycle assertion
  that still expected T05 to be in progress after its successful transition; the other
  255 tests passed. Updated the plan summary and regression to the completed T05 / next
  T06 state. The first repeat requested formatting for the edited regression, and the
  next repeat exposed one line-wrap-sensitive closeout assertion after 255 other tests
  passed. Made that assertion semantic, then repeated the complete gate on the final
  tree.

## Decision log

- 2026-08-08: Treat T05 as one Assembly item and stop before T06.
- 2026-08-08: A model/GPU scout is not applicable and is prohibited: T05 is a local
  protocol, schema, documentation, and validation item whose source contract forbids
  model, API, browser, benchmark, training, cloud, and paid execution.
- 2026-08-08: Treat the historical mutable `gpt-4o` alias as unavailable for exact
  identity; propose a dated GPT-4o snapshot as a declared substitution and classify
  any later result as directional reproduction.

## Evidence log

- Initial baseline:
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — **environment-partial**; frozen install, formatting/lint, strict typing, 236 tests,
  repository validation, and site-data generation passed, then Quarto reported an
  existing-theme compilation failure before completing the render.
- Official price/model source: OpenAI GPT-4o model catalog, retrieved 2026-08-08;
  standard text prices are USD 2.50 per million input tokens, USD 1.25 per million
  cached-input tokens, and USD 10.00 per million output tokens; dated snapshots are
  listed for `gpt-4o`.
- Baseline site recovery:
  `make site QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — **passed**; 14 pages rendered and rendered-site validation passed.
- Initial focused smoke — **smoke-failed** at Ruff import ordering, then at two tests:
  experiment discovery only accepted bare `EXP-NNNN` directory names, and one notebook
  assertion was line-wrap-sensitive.
- Repaired focused smoke:
  `PYTHONPATH=src uv run --no-sync pytest -o addopts='' tests/test_exp0001_protocol.py
  tests/test_exp0001_registry_discovery.py tests/test_validation.py
  tests/test_harness_schemas.py tests/test_sitegen.py -q` — **passed**, 48 tests;
  source-tree repository validation and `git diff --check` also passed.
- First full pre-review attempt — **smoke-failed**, 244 tests passed and two stale
  T04.5 boundary assertions failed after the now-authorized T05 registry transition.
- Complete pre-review gate:
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — **passed**; frozen install, formatting/lint, strict typing, 246 tests, repository
  validation, four generated views, 15-page render, and rendered-site validation all
  passed.
- Independent review — **review-failed**; six local contract findings, with no H2K,
  safety, execution, cloud, or scope violation.
- First repaired focused/static gate — **passed**; 58 focused tests, Ruff, strict
  typing, source-tree repository validation, and `git diff --check` passed.
- Independent rereview — **review-failed**; three remaining findings in typed task/pair
  retention, materialized pair comparison, and generic profile-schema breadth.
- Second repaired focused/static gate — **passed**; 85 focused tests, Ruff, strict
  typing, source-tree repository validation, and `git diff --check` passed.
- Independent third review — **clean**; the reviewer independently ran 93 focused
  tests, repository validation, and diff hygiene and found no remaining actionable
  spec-conformance or correctness issue.
- Complete post-review gate:
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — **passed**; frozen install, formatting/lint, strict typing, 256 tests, repository
  validation, four generated views, 15-page render, and rendered-site validation all
  passed.
- Final-tree closeout gate after the lifecycle and line-wrap regression repairs:
  `make check QUARTO=/Users/joseph/Documents/gic-lab/.tools/quarto-1.9.38/bin/quarto`
  — **passed**; frozen install, formatting/lint, strict typing, 256 tests, repository
  validation, four generated views, 15-page render, and rendered-site validation all
  passed.
- Final zero-execution/scope audit — **passed**; all project execution permissions are
  false, compute counters and entries are zero/empty, no run/data/trace artifact root
  exists, the registry state is `planned` / `not-evaluated` / `pending`, and the only
  `authorized: true` search hit is an intentional negative test fixture.
- Scout/evidence execution — **not applicable and prohibited** by the T05 source
  contract.

## Blockers and user actions

None. Execution authorization is intentionally absent and was not needed for T05.

## Next permitted work

T05 is successful and stops here. T06 is the next permitted workstream; it owns Phase
0.75 integration and closeout. No execution becomes authorized by completing T05.

## T05 outcome

EXP-0001 is registered and protocol-locked with exact scientific, task, paired-order,
model-substitution, pricing, validity, retention, and public-state contracts. The
generic harness now retains typed task/pair identity, the two run profiles and all six
condition plans remain unauthorized, H2K is an additive future evidence consumer only,
and no empirical evidence or result has been produced.
