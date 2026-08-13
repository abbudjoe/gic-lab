# T09 SiRA Calibration Pilot Lock — Assembly Ledger

Assembly status: **in-progress**

Terminal state: **pending**

## Source and target contracts

The authoritative source contract is the user-supplied **T09 — Lock the Two-Task
SiRA Calibration Pilot and Produce Execution Authorization** instruction dated
2026-08-13. Repository authority is additionally constrained by `AGENTS.md`,
`docs/PLANS.md`, `docs/COMPUTE_POLICY.md`, `docs/SECURITY_AND_SECRETS.md`, and
`docs/exec-plans/active/PHASE_1_ARTIFACT_EXECUTION.md`.

The target is one exact, executable, counterbalanced two-task FanOutQA calibration
pilot package that remains unauthorized. T09 is an offline planning and
implementation task. It may not call Lambda, OpenAI, or another model provider;
launch, stop, resize, restart, or delete cloud resources; mutate firewalls; use SSH,
Jupyter, a live browser, SiRA, or a FanOutQA task; access a real API key; train a
model; begin the pilot; change GIC reading/reconciliation records; or claim a
scientific result.

The pilot may describe task completion, deterministic scoring, pair validity,
gross floor/ceiling behavior, task-level resource use, and feasibility. It may not
support an effect-size, variance, significance, condition-superiority, EXP-0001,
H2K, or GIC architectural conclusion.

## T09 definition of done

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| T09-DOD-01 | Verify the exact branch and clean required starting commit, preserve the T08/T07/SiRA identities, map the work to Phase 1, and maintain every offline prohibition. | Git identity/status; source-contract review; execution-free command log. | met |
| T09-DOD-02 | Audit the proposal and classify every known gap as execution blocker, analysis blocker, publication-only blocker, or nonblocking optional evidence gap under the Occam rule. | Compact gap ledger in the T09 plan with source-grounded disposition. | met |
| T09-DOD-03 | Freeze exactly two valid, non-outcome-selected FanOutQA records with release, source, split, stable ID, text/reference hashes, selection/exclusion rules, order, pair, license, and retention classification. | Dataset contract plus machine-readable task-selection contract and focused tests. | met |
| T09-DOD-04 | Bind the exact upstream evaluator, dependency/assets and licenses, output schema, scoring/normalization rules, and deterministic/nondeterministic fields; pass all required offline fixtures without substituting an evaluator. | Evaluator contract, pinned machine record, fixture corpus/results, focused tests. | met |
| T09-DOD-05 | Separate process exit, artifact execution, task completion, answer production, evaluator validity, score, infrastructure invalidity, condition failure, missing evidence, and evaluator failure. | Typed attempt/score contract, documentation, and boundary tests. | met |
| T09-DOD-06 | Predeclare one identical plausible finite browser-step maximum, expected steps, action/condition/pair/total wall limits, stop behavior, and incomplete-answer scoring rule using source and T07 evidence. | Budget derivation and schema-valid runtime contract. | met |
| T09-DOD-07 | Freeze the T07 pragmatic Python/container/model/service-tier runtime and exact preflight/freeze boundary without creating another infrastructure qualification system. | Runtime identity and preflight contract; offline import/render/load checks. | met |
| T09-DOD-08 | Retain reconstructable per-attempt calls, usage, lineage, requested actions and post-action results, answer/scoring, artifacts, cleanup, and explicit unavailable H2K fields while structurally excluding secrets/private values. | Evidence schema/contract, redaction tests, privacy scan, cleanup receipt contract. | met |
| T09-DOD-09 | Freeze fresh host/attempt/evaluator/archive identities and machine-render/diff all four commands/configurations, permitting only declared treatment, identity/output, order, and realized-event differences. | Four command manifests, pair-diff artifact, exact equality/difference tests. | met |
| T09-DOD-10 | Compute expected attempt/pair/total cost, effective hard attempt/aggregate caps, and an automatic first-pair continuation decision with the exact declared pass/stop criteria. | Current primary-source pricing record, arithmetic record, checkpoint schema/tests. | met |
| T09-DOD-11 | Make model-call, token, OpenAI-cost, browser-step, condition/pair/total-wall, output-byte, disk, Lambda-duration/cost, attempt-count, and zero-retry caps effective on the selected runtime path. | Straightforward runtime counters/stops, fail-closed integration tests, rendered command bindings. | met |
| T09-DOD-12 | Record nonzero-GPU accounting honestly; retain `PLAN-EXP0001-PILOT` only if tasks, conditions, evaluator, and scientific meaning remain unchanged; bind the final plan while keeping `authorized: false`. | GPU metadata contract, plan/child identities and hashes, schema validation. | met |
| T09-DOD-13 | Update experiment registry, project state, active Phase 1 plan, decision log, readiness record, and sanitized notebook without passing/failing EXP-0001; emit a truthful ready-to-copy authorization packet. | Control/public-surface diffs and negative-boundary tests. | met |
| T09-DOD-14 | Pass focused fixtures/dataset/evaluator/pair/budget/evidence/cap tests, privacy scans, Ruff, strict mypy, repository validation, independent review and repair/rereview, post-review smoke, and full portable-Quarto `make check`; finish on a clean commit in exactly one allowed terminal state. | Exact commands/results, reviewer verdict, final hashes/bytes, clean Git status. | partial |

No required T09 item may remain `partial`, `blocked`, or `not-started` in
`ready-for-t09-pilot-authorization`. A publication-only blocker is carried as an
explicit release restriction and does not block private access-controlled execution.

## Starting evidence

- Required branch: `phase-1/sira-pilot`.
- Required clean starting commit:
  `e7bd4cd7158a0f0cb209e87fe1ca15d7c39711f1`.
- T08 terminal state: `smoke_evidence_validated_pilot_planning_eligible`.
- Frozen T07 execution commit:
  `5698f04dfd08bc85a66d2355b0a4bd7d3ce24a23`.
- T07 post-run commit:
  `27f66e6a82edffa57e497516bf3969a199675f06`.
- Frozen SiRA commit:
  `93fb8d72de71f9a4a13419670adeb34d93cf7acd`.
- Starting plan: `PLAN-EXP0001-PILOT`, `execution.authorized: false`.

## Progress and evidence log

- 2026-08-13: Read the complete T09 instruction and Assembly skill, confirmed the
  offline/no-execution boundary, and mapped the work to the DoD above.
- 2026-08-13: Confirmed the worktree was clean at the exact required commit and
  created `phase-1/sira-pilot` from that commit.
- 2026-08-13: Preserved the materially different starting proposal, froze
  `PLAN-EXP0001-PILOT-V2`, two exact dataset rows, the exact evaluator/dependency
  closure, four fresh counterbalanced attempts, and the calibration-only boundary.
- 2026-08-13: Implemented the smallest T07-runtime overlay for pre-action provider
  and browser counters, durable aggregate accounting, per-call usage/lineage,
  post-action results, task/evaluator state separation, structural secret cleanup,
  resource caps, zero retry, the automatic Task-A checkpoint, and cleanup receipts.
- 2026-08-13: Focused offline smoke passed: 48 dataset/evaluator/budget/evidence/cap
  tests, Ruff, and strict mypy for all seven selected execution-control files. The
  reviewed implementation ancestor is
  `06cf17023380b206302082293f87e9b0d84e0e72`.
- 2026-08-13: Bound the ancestor into all four child attempts and generated the exact
  four-command package. Both pair diffs report required equality and are valid.

## Review and gate log

Focused smoke is green. Repository validation, privacy scans, independent review,
post-review smoke, full portable-Quarto `make check`, terminal ledger closeout, and
the final clean package commit remain pending.

## Next permitted work

Run the focused repository gates, obtain the required independent review, repair and
rereview any material finding, then run the full offline gate and bind the clean
terminal commit. No live or cloud execution is permitted.
