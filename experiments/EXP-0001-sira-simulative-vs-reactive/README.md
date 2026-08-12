# EXP-0001 — SiRA Simulative Versus Reactive

Status: **planned / not-evaluated / pending**

Execution authorization: **false**

A two-condition T07 artifact smoke has run and T08 validated its retained evidence.
That smoke has no scientific interpretation: task completion was not observed, and
the EXP-0001 pilot has not run.

## Scientific question and scope

This exploratory protocol compares exactly two externally assigned modes from the
pinned SiRA artifact: `SIRA-SIMULATIVE` as treatment and `SIRA-REACTIVE` as control.
It asks whether simulative mode changes deterministic FanOutQA accuracy relative to
reactive mode within the same locked tasks, and what observable cost accompanies any
difference. The primary estimand is the mean of the two within-task accuracy
differences, simulative minus reactive. With two task pairs, the pilot tests paired
execution, scoring, and variance plumbing; it cannot establish a stable effect size,
adequate power, or a confirmatory result.

The null is that the mean paired accuracy difference is nonpositive, or that any
positive difference is dominated by reactive mode on all declared cost measures. A
nonpositive accuracy difference weakens the proposed benefit. A positive difference
without a favorable success-cost tradeoff does not support a frontier improvement.

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
counterbalanced across tasks. The choice of two pairs is the mathematical minimum for
testing a paired variance calculation and was made for workflow and variance plumbing,
not from an unseen effect size or power calculation.

## Retry, exclusion, and invalid-run policy

Upstream outer retry remains disabled (`--max_retry 0`). Intrinsic provider, parser,
and clustering attempts must be retained rather than selecting only successful output.
An infrastructure retry receives a new immutable attempt ID; it never overwrites the
failed attempt. If pair validity is lost, both conditions are rerun under a new pair
identity after the root cause is repaired.

Task failure is an outcome, not an exclusion. Scientific aggregation uses only complete
contract-valid pairs. A pair is infrastructure-invalid—not scientific no-support—if
authorization is absent, a budget boundary is violated, source/model/environment/task/
configuration identity drifts, the deterministic evaluator contract fails, required
raw evidence cannot be verified, or supervised browser-child cleanup cannot be shown.
All invalid, interrupted, excluded, and replacement attempts remain in operational and
cost accounting.

## Metrics and interpretation

The primary metric is deterministic FanOut evaluator record accuracy; the primary
estimand is the mean paired difference. Secondary outcomes are paired success
discordance, directly reported input/cached/output tokens, reproducibly derived or
directly billed provider USD cost, harness wall time, upstream model-call count,
browser action count, valid completion rate, and the availability of source-supported
state and selected-plan fields.

Candidate actions, predicted futures, critic evaluations, action results, model
revision, and token usage are not invented when the accepted source trace does not
support them. Mechanism fields are descriptive trace evidence only. They cannot prove
causal use, learned regulation, or internalization.

## Falsification and outcome classification

A nonpositive paired accuracy difference weakens the benefit claim. A positive
difference that is cost-dominated does not improve the success-cost frontier. Missing
complete pairs make the pilot inconclusive or infrastructure-invalid rather than
negative. With only two exploratory pairs, no p-value, confidence-based confirmatory
claim, or stable population effect is authorized. Support, no support, mixed evidence,
invalidation, and infrastructure invalidity remain distinct from lifecycle and
evidence-strength state.

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

[`run-plans/smoke.yaml`](run-plans/smoke.yaml) is one minimal matched pair with
interpretation prohibited. [`run-plans/pilot.yaml`](run-plans/pilot.yaml) is the
two-pair exploratory pilot. The smoke plan is now a historical control record; the
pilot profile and every pilot condition plan remain unauthorized.
The proposed caps are derived in [`pricing.yaml`](pricing.yaml) from current official
OpenAI rates using the conservative assumption that every permitted token is charged
at the more expensive output-token rate.

T08 makes pilot protocol preparation eligible, not pilot execution. Before a later
current-turn authorization can bind the pilot, the repository must close every blocker
in [`../../docs/harness/T08_SIRA_PILOT_READINESS.md`](../../docs/harness/T08_SIRA_PILOT_READINESS.md),
including a reviewed nonzero-GPU protocol version, immutable source/config/environment/
image/browser/evaluator/command hashes, effective enforcement for every child and
aggregate cap, dataset/license/privacy review, and dynamic cloud preflight. Pilot
scoring also requires an immutable spaCy and `en_core_web_sm` evaluator dependency
contract.
