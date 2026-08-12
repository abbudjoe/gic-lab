# T09 SiRA exploratory pilot plan

Status: **prepared for prerequisite closure and separate authorization; not executable**

Plan ID: `PLAN-EXP0001-PILOT`

## Primary question and boundary

Can the locked SiRA reactive/simulative pipeline produce two complete, contract-valid,
deterministically scored FanOutQA pairs while preserving task-level paired deltas,
completion/failure behavior, cost, and variance-plumbing evidence? The pilot is
directional and exploratory. It cannot establish superiority, mechanism attribution,
internalization, a confirmatory effect, production readiness, or an RQ-H2K outcome.

The T07 smoke is artifact-execution and infrastructure evidence only. Its trajectory,
noncompletion, and one-step cost are not observations in this pilot.

## Frozen task source and sample

Source: `DATA-SIRA-FANOUTQA-DEV`, revision
`76ad1feb689b754bfe4e5e24d3ea371b647efa67`, content SHA-256
`359300b029c6891567816f351bf8786e9b018d7af8a1a44b7da9ba5ef4651288`.
The subset is exactly rows `[0:1]` and `[1:2]`, task IDs `7dcbbbdc7f1120cd` and
`2120afba8009bad3`. No outcome-based substitution or expansion is allowed.

Two pairs are the minimum that can exercise both condition orders, validate complete
end-to-end scoring, observe completion/discordance, expose obvious floor or ceiling
behavior, pass paired-variance plumbing, and estimate whether a later confirmatory
study is operationally affordable. The sample is not powered and yields no stable
effect-size estimate.

## Paired design

Each task runs once per condition with seed 42 and at most 30 browser actions. Task 0
runs reactive then simulative; task 1 runs simulative then reactive. The model is the
immutable proposed snapshot `gpt-4o-2024-11-20` for every role. The upstream
historical alias lacked an immutable serving revision, so all later claims retain the
`directional-reproduction` qualifier.

Pair validity requires equal task/source, model routing, runtime, dependencies, image,
browser, instrumentation, evaluator, price calculation, tools, host class, maximum
steps, seed, and evidence code. Differences are limited to identity/output ownership,
counterbalanced order, source-declared reactive/simulative configuration, and realized
events/usage. An invalid pair is retained but excluded from aggregation; both
conditions require fresh identities for any separately authorized rerun.

## Budgets

| Ceiling | Reactive attempt | Simulative attempt | Aggregate |
|---|---:|---:|---:|
| Attempts | 2 total | 2 total | 4 |
| Model calls | 480 | 1,830 | 4,620 across declared attempts |
| Model tokens | 1,000,000 | 1,000,000 | 4,000,000 |
| Browser actions | 30 | 30 | 120 |
| Wall seconds | 3,600 | 3,600 | 14,400 |
| OpenAI spend (USD) | 10.00 | 10.00 | 40.00 |
| A10 hours | 1.0 | 1.0 | 4.0 |

The reactive model-call ceiling is 16 source-path attempts per browser step times 30;
the simulative ceiling is 61 times 30. These are hard planning maxima, not expected
usage. Each child run plan carries its condition-specific ceiling in the typed
`RunBudget.max_model_calls` field, and parent/child policy validation requires exact
reconciliation. The provider-compute proposal is USD 5.16 at the retained USD
1.29/A10-hour rate, producing a USD 45.16 combined planning ceiling. Fresh
price/capacity checks and effective inline runtime enforcement are mandatory before
authorization; typed planning limits alone do not authorize execution and no cap may
silently increase.

## Scoring and analysis contract

The primary measure is the mean within-task paired difference in the pinned FanOut
deterministic evaluator's record accuracy, simulative minus reactive. Report each task
pair before any mean. Secondary records are per-condition completion and discordance,
valid-completion rate, input/cached/output tokens, model calls, browser actions, wall
time, and reproducible USD cost. Missing task completion is not converted into
success, and infrastructure failure is not a scientific zero.

The evaluator dependency, model, task, source, environment, and scoring outputs must
be immutably bound before the first empirical action. With only two tasks, report raw
paired values and descriptive range; do not attach confirmatory p-values, power,
population generalization, or causal mechanism claims.

## Stopping rules

- Stop before any request while parent/child authorization is false or project
  execution/cloud/paid-compute permissions are false.
- Stop on any unresolved evaluator, source, model, runtime, command, price, firewall,
  evidence, privacy, or cleanup prerequisite.
- Stop before exceeding any per-attempt or aggregate model-call, token, browser,
  wall, API/provider spend, accelerator-hour, or output cap.
- Stop and retain the attempt on identity, task, configuration, pair, evaluator, raw
  artifact, secret, or cleanup drift. No in-run repair or outcome-adaptive change.
- Zero outer condition retries. Intrinsic provider/parser retries, if source-owned,
  must be individually retained and reconciled. An infrastructure rerun requires a
  fresh identity and separate authority; a pair-invalid rerun requires both sides.
- On failure, prioritize exact provider/container/browser termination and evidence
  capture. Do not delete failed evidence or treat it as a scientific negative.

## Required evidence

Retain the authorization reference; immutable parent/child plans and hashes; exact
commands/configuration and pair diff; source/model/dataset/environment/image/browser/
evaluator identities; raw session JSON, stdout/stderr, source logs, screenshots and
post-action results; per-call provider receipts when available; normalized events;
source-classified regulation-decision records; deterministic evaluator input/output;
attempt and aggregate accounting; artifact sizes/hashes; runtime cleanup; one-way
external copy equality; firewall restoration; and provider terminal/zero-instance
proof. Ephemeral provider access values must be structurally omitted or redacted.

Public raw release remains blocked pending license, privacy, and redaction review.
Execution requires the separate packet in
`docs/harness/T09_SIRA_PILOT_PREAUTHORIZATION_PACKET.md` plus a new user authorization
after all listed blockers are closed.
