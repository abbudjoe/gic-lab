# EXP-0001 — SiRA Simulative Versus Reactive

Status: **planned / not-evaluated / pending**

Execution authorization: **false**

A two-condition T07 artifact smoke has run and T08 validated its retained evidence.
That smoke has no scientific interpretation: task completion was not observed. One
T09 V3 preflight-only host campaign later stopped on exact container-identity drift
before any pilot condition or evaluator ran. T09 V4 then qualified a replacement
runtime and produced one valid scored Task A reactive calibration attempt, but stopped
before its paired simulative attempt because of frozen finalizer control defects. No
pair or comparative result exists. T09 V5 repaired and offline-verified those
downstream controls, but its two authorized launches both stopped before empirical
entry and produced zero new attempts. EXP-0001 therefore remains unevaluated.

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
[`run-plans/pilot.yaml`](run-plans/pilot.yaml) is the calibration-only
`PLAN-EXP0001-PILOT-V5`; V2 through V4 remain preserved under
`run-plans/proposals/`. Tracked authorization stays false and every condition plan
requires a single-use private current-turn overlay.

The pragmatic V3 repair makes the 14,400-second provider campaign effective with a
900-second cleanup reserve and 13,500-second normal termination cutoff. It admits
each attempt against actual elapsed time only when its full 3,600-second condition
wall, 600-second evaluator/evidence handoff, 60-second termination-dispatch margin,
and cleanup reserve remain; it does not reserve every theoretical maximum at campaign
start. Its single-use authority was consumed by one preflight-only A10 launch. The
dynamic runtime gate stopped before empirical entry because the exact frozen T07 image
was not retained as a verified loadable artifact and the source rebuild produced a
different digest. All four attempts remain `not-run`; the exact host was terminated
and zero remaining T09 instances were verified. V3 cannot be replayed. Public raw
release remains separately blocked pending license/privacy review.

The exhausted historical plan identity is `PLAN-EXP0001-PILOT-V3`.

Retry 2 preserves that V3 disposition byte-for-byte and classifies it as
`preflight_blocked_by_overstrict_cross_run_image_digest_requirement`. V4 permits a
different replacement digest only after one source-derived build passes the exact
Python, package, patched-runner, browser, evaluator-fixture, command-pair, credential,
and dated-model metadata gates. A mode-0600 O_EXCL run manifest then binds that exact
image for every condition before empirical entry. Those gates passed for replacement
`sha256:e2603f5a…`, and Task A reactive ran exactly once. Retained evidence establishes
task completion and an exact-evaluator descriptive score of 0.0. The frozen host
finalizer then failed on an incorrect output-root projection and an interpreter/
dependency mismatch. One network-disabled reconstruction preserved that consumed
attempt, but using its corrected invocation for later conditions would violate the
post-entry freeze. Task A simulative and both Task B attempts did not run; no pair,
checkpoint, condition comparison, or EXP-0001 outcome exists.

The tracked plan remains `authorized: false`; its private single-use overlay is
exhausted. Provider cleanup is verified: secret/container residue is absent, the exact
host is terminal/absent, zero T09 instances remain, and security state is restored.
Future execution requires both finalizer repairs, fresh plan/run/evaluator/pair/stage/
archive/provider identities, independent review, and new current-turn authority.
Public raw release remains separately blocked pending privacy and publication review.

Retry 3 implemented and twice reproduced the repaired pure finalizer against the
immutable V4 archive with networking disabled and no new model or browser activity.
Its first authorized host built and preserved candidate image `sha256:abe8ed38…`, then
stopped before the metadata gate because the private regression archive was supplied
at the wrong host path. After exact cleanup and a source-bound slot-2 transition, the
second and final launch passed the pre-POST headroom gate, but provider activation and
entry observation consumed the remaining positive margin. The campaign therefore
stopped before host access, dynamic qualification, metadata GET, browser use, or any
V5 condition. Both hosts are terminal or absent; zero T09 instances, restored
security, USD 1.5106036795496942 Retry3 Lambda cost, and zero Retry3 OpenAI cost are
reconciled. All four V5 attempts remain `not-run`, the frozen run manifest was never
written, and the two-launch/nonreset-campaign authority cannot be replayed. Any future
paired calibration needs fresh identities, campaign clock, review, and current-turn
authorization; the retained image archive may be reused only through a new
source-bound contract. The registry/project-state-bound Retry 3 terminal-control
record is the current machine authority: it preserves the frozen profile and execution
contract bytes as history while rejecting their consumed plan IDs as nonreplayable.
