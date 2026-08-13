# EXP-0001 — SiRA Simulative Versus Reactive

Status: **planned / not-evaluated / pending**

Execution authorization: **false**

A two-condition T07 artifact smoke has run and T08 validated its retained evidence.
That smoke has no scientific interpretation: task completion was not observed, and
the EXP-0001 pilot has not run.

## Scientific question and scope

This calibration protocol compares exactly two externally assigned modes from the
pinned SiRA artifact: `SIRA-SIMULATIVE` as treatment and `SIRA-REACTIVE` as control.
It asks whether both conditions can complete and be exactly scored on two matched
FanOutQA tasks, whether their evidence remains reconstructable, and what task-level
resource behavior implies for a larger exploratory pilot. Report only the four
attempts and two pairs descriptively.

Two pairs cannot estimate an effect or variance, support significance or condition
superiority, accept or reject EXP-0001, or support an H2K/GIC architectural claim.
There is no statistical null or primary effect estimand in this calibration pilot.

## Treatment and control

`SIRA-SIMULATIVE` externally selects the pinned upstream `simulative` mode. It resolves
to the source's world-model planner path and its audited search, sampling, temperature,
and critic settings. `SIRA-REACTIVE` externally selects the upstream `reactive` mode
and its policy planner settings. These source-defined mode effects are the intended
treatment contrast, not uncontrolled drift.

The mode assignment is made by the experiment before execution. It is an
`experiment_assignment`; it is not evidence that the model learned, selected, or
internally represented a regulation policy. Neither trace completeness nor an
explicit model output would by itself establish internalization.

## Fixed variables

Within every pair, the upstream commit, model/provider contract, task text or dataset
slice, agent, maximum steps, action timeout, outer retry count, browser settings,
dataset-order seed, evaluator contract, harness limits, secret channel, and environment
identity are fixed. The dataset-order seed does not seed provider sampling, the browser,
or the live web. The model and browser workload therefore remain nondeterministic.

The upstream source requested the mutable alias `gpt-4o` and did not record the exact
historical serving revision. T07 bound the immutable substitute
`gpt-4o-2024-11-20` across all SiRA roles through an audited routing adaptation. The
historical serving revision remains unknown, so T07 is an **artifact execution under a
declared model substitution**, not an unqualified historical reproduction. Any pilot
must preserve or explicitly revise that immutable binding before authorization.

## Tasks, sampling, and order

The smoke profile is the pinned SiRA README query `go to google flights`, run once in
each mode with one maximum browser step during T07. T08 validated command, runtime,
trace, accounting, pair, and cleanup evidence. Each session retained one requested
browser action, but no structured post-action result; action performance is inferred
from normal exit and task completion was not observed. Interpretation is prohibited.

The pilot locks the first two rows of the pinned SiRA FanOutQA development file:

1. `7dcbbbdc7f1120cd`, index `[0, 1)`, reactive then simulative.
2. `2120afba8009bad3`, index `[1, 2)`, simulative then reactive.

Each condition runs once per task. Conditions are kept close in time and their order is
counterbalanced across tasks. Two pairs can test completion, evaluator plumbing,
pairing, reconstruction, gross floor/ceiling behavior, and cost capture. The sample
was not selected from an unseen condition outcome and cannot estimate variance or an
effect.

## Retry, exclusion, and invalid-run policy

Upstream outer retry remains disabled (`--max_retry 0`), provider fallback and implicit
provider retries are disabled, and every provider call attempt is retained. Once the
first task model request or browser action occurs, no infrastructure or scientific
retry is permitted under this plan. Any later rerun requires a new plan, identities,
review, and authorization; no evidence is overwritten.

Task failure is an outcome, not an exclusion. Scientific aggregation uses only complete
contract-valid pairs. A pair is infrastructure-invalid—not scientific no-support—if
authorization is absent, a budget boundary is violated, source/model/environment/task/
configuration identity drifts, the deterministic evaluator contract fails, required
raw evidence cannot be verified, or supervised browser-child cleanup cannot be shown.
All invalid, interrupted, excluded, and replacement attempts remain in operational and
cost accounting.

## Metrics and interpretation

Primary records are per-attempt completion, answer production, exact FanOut evaluator
validity/score, and reconstructability. Secondary descriptive records are each
condition's task-level score, directly reported input/cached/output tokens,
reproducibly derived or directly billed provider USD cost, harness wall time, upstream
model-call count, browser action count, valid completion, and availability of
source-supported state and selected-plan fields. No paired mean is an authorized
estimand.

Candidate actions, predicted futures, critic evaluations, action results, model
revision, and token usage are not invented when the accepted source trace does not
support them. Mechanism fields are descriptive trace evidence only. They cannot prove
causal use, learned regulation, or internalization.

## Falsification and outcome classification

Missing complete pairs make the calibration incomplete or infrastructure-invalid
rather than evidence for either condition. A validly executed condition that does not
finish is a calibration condition failure, not an infrastructure failure. No p-value,
confidence interval, effect estimate, variance estimate, population generalization,
frontier claim, support/no-support classification, or condition-superiority statement
is authorized. Lifecycle, evidence strength, process exit, artifact execution, task
completion, evaluator validity, and score remain separate fields.

## Raw retention and public release

Every attempt preserves session JSON, source text logs, harness stdout/stderr,
evaluator output, resolved command/configuration, environment and revision identity,
UTC events, cleanup evidence, and content hashes before normalization. Raw prompts,
screenshots, accessibility trees, URLs, and web content are potentially sensitive and
may carry third-party terms.

Raw traces are retained outside Git under immutable attempt roots. Public release is
blocked until dataset/site licensing, privacy, secret scanning, and redaction are
reviewed. Until then, only validated aggregate summaries and provenance-safe metadata
may be public. No missing license or provenance fact is inferred.

## H2K future-consumer boundary

[`EVIDENCE_RETENTION_APPENDIX.yaml`](EVIDENCE_RETENTION_APPENDIX.yaml) adds a
source-grounded trace-retention contract for planned/deferred `RQ-H2K`. It is not a new
hypothesis, outcome, metric, treatment, control, ablation, or experiment. It cannot
change EXP-0001 outcome classification. Its only role is to prevent loss of evidence
that a separately approved future study might consume.

## Run plans and current blockers

[`run-plans/smoke.yaml`](run-plans/smoke.yaml) is the historical one-step matched-pair
control record. The starting effect-oriented pilot proposal is preserved at
[`run-plans/proposals/PLAN-EXP0001-PILOT.json`](run-plans/proposals/PLAN-EXP0001-PILOT.json).
[`run-plans/pilot.yaml`](run-plans/pilot.yaml) is now the calibration-only
`PLAN-EXP0001-PILOT-V2`; its profile and every condition plan remain unauthorized.

T09 resolves the static dataset, evaluator, scoring, matching, budget-enforcement,
evidence, privacy, and identity blockers documented by T08. The package is ready for a
fresh exact authorization, but project execution permissions and every authorization
field remain false. A later authorized turn must bind the final clean commit and
packet, pass the single exact dynamic preflight, enforce the automatic Task-A
checkpoint, terminate the exact provider resource, and verify zero instances. Public
raw release remains separately blocked pending license/privacy review.
