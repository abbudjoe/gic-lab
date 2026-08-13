# T09 SiRA Calibration Pilot Lock — Assembly Ledger

## V3 pragmatic campaign-wall successor

V3 assembly status: **blocked-user-action; single-use execution authority exhausted**

Terminal state: **`t09-pilot-blocked-material-risk`**

Source contract SHA-256:
`1f8285ea3fc52f4084a945f1712870203463cb7fb92cc61ac2eeae47d119e4c7`.
Starting branch/commit: `phase-1/sira-pilot-pragmatic` at
`6ff5ea6a8c3c43d0b860ad69081c0f546ee5f93d`.

The source contract explicitly supersedes only V2's 3,600-second infrastructure
lifecycle restriction. It preserves every task, evaluator, model, SiRA, pairing,
order, budget, evidence, cleanup, zero-retry, and calibration-only boundary. V2 is
retained at `run-plans/proposals/PLAN-EXP0001-PILOT-V2.yaml`; V3 mints fresh plan,
pair, host, condition, evaluator, stage, and archive identities.

| V3 ID | Requirement | Status |
|---|---|---|
| T09-V3-01 | Parameterize one actual-time 14,400-second provider campaign with 900-second cleanup reserve and 13,500-second termination cutoff. | met locally: the existing observer and one-shot provider boundary share one typed immutable V3 limit set; T07 defaults remain 3,600/1,800 |
| T09-V3-02 | Admit an attempt only when its full 3,600-second condition wall, 600-second evaluator/evidence handoff, 60-second termination-dispatch margin, and cleanup reserve remain; do not sum future maxima. | met locally: exact admission/cutoff fake-clock regressions pass |
| T09-V3-03 | Preserve science/evaluator/tasks/order/pairing and machine-diff four exact V3 commands. | met statically: plan `0b17da814f9b20326a7220cec5f41e84c968a46c9d38e913f327afe267c26210`; command package `8e8d5827df4688a8748828145ea0990d8397c771ae3add43790bbd45f732984d`; both pairs valid |
| T09-V3-04 | Keep calls/tokens/actions/cost/wall/output/disk/attempt/zero-retry and evidence counters effective. | met: focused controls passed and the runtime stopped before empirical entry on exact image-identity drift |
| T09-V3-05 | Pass independent spec-conformance review, repair/rereview, and post-review smoke before freeze. | met: source ancestor `6f7c3112777a8b253f085d058972259fad30778f` and frozen package `9dc7363561ec96812072e2c7824141d75b028332` received independent PASS verdicts |
| T09-V3-06 | Freeze a clean pre-run package and single-use private authorization/cloud ledger before one launch. | met: package `9dc7363` and the plan/hash/identities were ledger-bound; the overlay was consumed by exactly one launch |
| T09-V3-07 | Execute Task A pair, checkpoint, eligible Task B pair, and pinned evaluators with zero retry. | blocked before empirical entry: exact frozen image identity could not be materialized; all four attempts and evaluators are `not-run`, and the checkpoint was not reached |
| T09-V3-08 | Seal evidence, terminate exact provider resource, prove zero residue/security restoration, reconcile accounting, and update public/control surfaces without a scientific conclusion. | met: private preflight evidence is sealed, exact host terminal/absent and zero-instance/security restoration are verified, and USD 0.414064252316667 Lambda / USD 0 OpenAI is reconciled |

Focused evidence: the combined existing-observer and T09 source suite passes;
source-derived provider entry,
malformed-response ambiguity, multi-ID incident cleanup, source-bound exact-target
closeout, cutoff, off-host attempt-export acknowledgement, full condition wall,
campaign admission, science lock, evaluator, pair, budget, and checkpoint regressions
pass. Final repaired-source review returned **PASS** at
`6f7c3112777a8b253f085d058972259fad30778f`. The rebound package passes 43 T09
tests, 13 Phase-1 tests, repository validation, Ruff, strict mypy, and exact pair
rendering. The portable-Quarto 1.9.38 full gate passes all 1,332 tests and renders
all 16 notebook pages with site validation. The definitive package then launched one
authorized A10 host. Its dynamic preflight failed before empirical entry because the
pinned sources rebuilt a different container digest and the exact frozen image was
not retained as a loadable artifact. No OpenAI/model request, task browser action,
SiRA/FanOutQA attempt, evaluator attempt, or empirical entry occurred.

The preflight-only campaign used 1,155.528146 provider seconds and
0.320980040555556 A10-hours, estimated at USD 0.414064252316667. The maximal private
failure prefix was externally sealed; its stage archive is 1,195,031 bytes at
`941c61b58ac2fd8717c06ae2f8ef25616ed23c7e36ba64e88d9944924d084bc1`.
Provider closeout proves terminal/absent state, zero T09 instances, and security
restoration. EXP-0001 remains unevaluated.

Post-run reconciliation passes 57 focused T09/Phase-1 tests, repository validation,
Ruff, strict mypy over 61 source files, all 1,333 repository tests, portable Quarto
1.9.38 render of all 16 pages, site validation, and diff hygiene. Independent
closeout review remains the final Assembly gate.

The complete active DoD and command/evidence log are maintained in
`docs/harness/T09_PRAGMATIC_CALIBRATION_PILOT_EXECUTION_PLAN.md`.

---

## Historical V2 blocked-state assembly (superseded only by V3)

Assembly status: **complete at the material-risk boundary; execution remains blocked**

Terminal state: **`t09-pilot-blocked-material-risk`**

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
| T09-DOD-06 | Predeclare one identical plausible finite browser-step maximum, expected steps, action/condition/pair/total wall limits, stop behavior, and incomplete-answer scoring rule using source and T07 evidence. | Budget derivation and schema-valid runtime contract. | blocked: 14,400-second candidate envelope is incompatible with the frozen 3,600-second provider hard wall; the smaller envelope cannot credibly cover four tasks plus safe cleanup |
| T09-DOD-07 | Freeze the T07 pragmatic Python/container/model/service-tier runtime and exact preflight/freeze boundary without creating another infrastructure qualification system. | Runtime identity and preflight contract; offline import/render/load checks. | blocked: inherited manual lifecycle cannot cover the requested attempt/cleanup envelope; a replacement control plane is prohibited |
| T09-DOD-08 | Retain reconstructable per-attempt calls, usage, lineage, requested actions and post-action results, answer/scoring, artifacts, cleanup, and explicit unavailable H2K fields while structurally excluding secrets/private values. | Evidence schema/contract, redaction tests, privacy scan, cleanup receipt contract. | met |
| T09-DOD-09 | Freeze fresh host/attempt/evaluator/archive identities and machine-render/diff all four commands/configurations, permitting only declared treatment, identity/output, order, and realized-event differences. | Four command manifests, pair-diff artifact, exact equality/difference tests. | met |
| T09-DOD-10 | Compute expected attempt/pair/total cost, effective hard attempt/aggregate caps, and an automatic first-pair continuation decision with the exact declared pass/stop criteria. | Current primary-source pricing record, arithmetic record, checkpoint schema/tests. | partial: expected/candidate arithmetic and checkpoint are exact; the Lambda hard cap is not effective on a source-compatible lifecycle |
| T09-DOD-11 | Make model-call, token, OpenAI-cost, browser-step, condition/pair/total-wall, output-byte, disk, Lambda-duration/cost, attempt-count, and zero-retry caps effective on the selected runtime path. | Straightforward runtime counters/stops, fail-closed integration tests, rendered command bindings. | blocked: no effective 14,400-second provider path exists; preflight and empirical entry now refuse unconditionally |
| T09-DOD-12 | Record nonzero-GPU accounting honestly; retain `PLAN-EXP0001-PILOT` only if tasks, conditions, evaluator, and scientific meaning remain unchanged; bind the final plan while keeping `authorized: false`. | GPU metadata contract, plan/child identities and hashes, schema validation. | met |
| T09-DOD-13 | Update experiment registry, project state, active Phase 1 plan, decision log, readiness record, and sanitized notebook without passing/failing EXP-0001; emit an authorization packet only when truthful. | Control/public-surface diffs and negative-boundary tests. | met: every surface converges on blocked-material-risk and the packet is an explicit refusal, not an authorization template |
| T09-DOD-14 | Pass focused fixtures/dataset/evaluator/pair/budget/evidence/cap tests, privacy scans, Ruff, strict mypy, repository validation, independent review and repair/rereview, post-review smoke, and full portable-Quarto `make check`; finish on a clean commit in exactly one allowed terminal state. | Exact commands/results, reviewer verdict, final hashes/bytes, clean Git status. | met: blocked-state review is a clean pass; pre-review and post-review full gates pass; final clean commit is the handoff reported with this ledger |

The allowed blocked terminal state is required because T09-DOD-06/07/10/11 cannot be
closed without weakening cleanup or reopening the prohibited T07 infrastructure
design. The separate publication blocker remains an access/release restriction and
is not the reason execution is blocked.

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
  initial reviewed implementation ancestor was
  `06cf17023380b206302082293f87e9b0d84e0e72`.
- 2026-08-13: The repository privacy gate conservatively interpreted local variables
  named `secret` as assigned tokens. Renamed those variables without changing the
  control behavior, issued reviewed ancestor
  `ec7ce957c37801eb51f3d6f2995e9d1e6859be03`, and regenerated every dependent
  runtime, child-plan, execution-contract, argv, and command-package hash.
- 2026-08-13: Independent review found that the inherited T07 observer fixes a
  3,600-second provider hard wall and 1,800-second normal termination target, whereas
  the candidate T09 plan needs up to 14,400 seconds. Retained timing plus worst-case
  checkpoint/poll/seal/transfer bounds cannot cover four plausible attempts and safe
  cleanup inside 3,600 seconds.
- 2026-08-13: Rejected the draft automated provider lifecycle because it reopened
  T07 infrastructure design. Removed its adapter/verifier/schemas, made provider
  preflight and condition entry fail closed, and changed every control/public surface
  to `t09-pilot-blocked-material-risk` with `authorized: false`.
- 2026-08-13: Issued blocked-state implementation ancestor
  `9ab0bb1000de0049a9067704db9533f4409ccf31`, bound it into all four child
  attempts, and regenerated the execution contract and exact four-command package.
  Both pair diffs report required equality and are valid.

## Review and gate log

- Blocked-state focused suite: **68 passed** across the T09 pilot, EXP-0001, and
  Phase 1 closeout tests, including dataset/evaluator fixtures, actual-argv pair
  diffs, budget arithmetic, cap refusal, evidence reconstruction, structural
  redaction, and Task B's direct normalization-edge score regression.
- Historical T07 and synthetic harness fixtures now resolve immutable inputs from
  their commit bindings instead of conflating them with T09's versioned mutable
  protocol/configuration and license records. The full test suite passes with
  **1,322 tests**.
- Repository validation, the tracked-file secret/privacy validator, Ruff formatting
  and lint, and strict mypy over all 59 source files pass.
- Pre-rereview full gate passed with portable Quarto 1.9.38: lock/sync, Ruff,
  strict mypy, all 1,322 tests, repository validation, all 16 notebook pages, and
  site validation.
- Independent blocked-state spec-conformance review of package
  `0757cf9a02ffcdcf78475643781c394be9b893d8` and reviewed runtime ancestor
  `9ab0bb1000de0049a9067704db9533f4409ccf31` returned **CLEAN PASS** with no
  undisclosed material finding. The verdict explicitly does not grant execution
  readiness or authorization. The reviewer independently reproduced the 68 focused
  tests, all 1,322 tests, Ruff, strict mypy, repository validation, portable Quarto
  render of all 16 pages, and site validation.
- Post-review focused and full portable-Quarto gates passed unchanged. The final
  handoff commit closes only this ledger; it does not change the reviewed runtime,
  plan, execution, command, evaluator, dataset, budget, or evidence bytes.

## Historical V2 next permitted work

V2 was closed at `t09-pilot-blocked-material-risk`. It grants no live or cloud
authority. The current V3 section above is the fresh successor requested by the user;
it may proceed only after its own byte bindings, rereview, clean freeze, exact
preflight, and private single-use authorization overlay pass.
