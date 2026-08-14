# Phase 1 SiRA Smoke Readiness

Status: **T07 smoke closed; T09 Retry 4 stopped after one invalid unscored attempt**

Prepared: 2026-08-08

Updated: 2026-08-14

T08 update: 2026-08-12

## Current T08 checkpoint

The T07 Retry 2 pair executed under its now-exhausted authority. T08 independently
rehashes and reconstructs it as
`matched_pair_valid_with_documented_evidence_gaps`: both artifacts passed, both task
completions were not observed, evidence is complete enough for the smoke, and cleanup
is `cleanup_verified_with_nonmaterial_gap`. EXP-0001 remains planned, scientifically
not evaluated, and outcome-pending.

Pilot protocol preparation is now eligible. `PLAN-EXP0001-PILOT` remains
`authorized: false` and `blocked-pending-prerequisites`; see
`docs/harness/T08_SIRA_PILOT_READINESS.md` and
`docs/harness/T09_SIRA_PILOT_PREAUTHORIZATION_PACKET.md`. Every execution permission
below remains false. The rest of this document preserves historical T07 readiness and
authorization fields; none is current pilot authority.

## Current T09 pragmatic checkpoint

`PLAN-EXP0001-PILOT-V3` was frozen at clean package
`9dc7363561ec96812072e2c7824141d75b028332` and its one-launch private authority was
consumed. Exactly one Lambda `gpu_1x_a10` host launched in `us-east-1` with no
persistent filesystem. Dynamic preflight stopped before the empirical boundary when
the pinned runtime rebuilt to
`sha256:07875dc67336b90021df5ab920860a56268bbc9f3aada70accec23848d9905cf`
rather than the required frozen image
`sha256:035edf61718e84a8156f4f0f7817b134b0ce31488d3f0b50bbfba2b4a30cc61c`.
The exact frozen image was not retained as a loadable artifact, and substitution was
not authorized.

All four condition attempts and evaluator attempts are `not-run`; no model call,
token, task browser action, score, or OpenAI charge exists, and the Task A checkpoint
was not reached. The exact host is terminal/absent, zero T09 instances and restored
security state are verified, and the estimated Lambda charge is USD
0.414064252316667 for 0.320980040555556 A10-hours. Terminal state is
`t09-pilot-blocked-material-risk`. V3 is exhausted and unauthorized; future execution
requires either the exact verified loadable image or a fresh reviewed successor that
requalifies a replacement runtime, plus new current-turn authority.

## Current T09 Retry 2 checkpoint

`PLAN-EXP0001-PILOT-V4` consumed its private single-use overlay. Exact replacement
image `sha256:e2603f5a…` passed the final-container, evaluator-fixture, browser,
pair-diff, credential, and one-metadata-GET gates and was frozen before empirical
entry. Task A reactive then ran once: exit zero, task completed, exact evaluator
valid, descriptive score 0.0, 52 model calls, 121,900 tokens, 13 browser actions,
199.196380 seconds, and USD 0.3626425 OpenAI cost.

The frozen host finalizer read `output_root` from the wrong manifest level and then
selected an interpreter without the qualified evaluator/control dependency closure.
One network-disabled reconstruction preserved the already-consumed attempt with zero
additional model/browser activity, but independent review correctly rejected using
that changed invocation for later conditions. Task A simulative and both Task B
attempts are `not-run`; no first-pair checkpoint, realized pair, comparison, or
scientific outcome exists. The exact host is terminal/absent, zero T09 instances and
restored security are verified. New campaign cost is USD 2.116752203373909 and
cumulative T09 cost is USD 2.5308164556905757. Terminal state is
`t09-pilot-blocked-material-risk`; future execution needs both finalizer repairs,
fresh identities, independent review, and new current-turn authority.

## Current T09 Retry 3 checkpoint

`PLAN-EXP0001-PILOT-V5` repaired the raw/finalized evidence boundary and reproduced
the corrected downstream finalizer twice over the immutable V4 archive with no new
network, model, browser, or condition activity. The first authorized host built and
preserved candidate image `sha256:abe8ed38…`, then stopped before the sole metadata
GET and empirical entry because the private regression archive was mounted at the
wrong host path. It terminated cleanly and yielded the source-bound eligibility for
the second and final launch.

The second launch passed the code-enforced pre-POST 4,500-second headroom gate, but
provider activation and source-bound entry observation consumed the remaining margin.
At active entry the nonreset campaign could no longer admit one 3,600-second condition
plus its protected 900-second cleanup reserve. The run stopped immediately, before
host access, image import, dynamic qualification, metadata GET, browser use, or a V5
attempt. Both provider resources are terminal or absent; zero T09 instances, restored
security, two exact termination requests, 4,215.638175 active Lambda seconds, USD
1.5106036795496942 Retry3 Lambda cost, and USD 0 OpenAI cost are reconciled. The
two-launch capability and campaign clock are exhausted. Terminal state is
`t09-pilot-blocked-material-risk`; any future paired campaign requires fresh
identities, a new clock, independent review, and new current-turn authority.

Current machine authority comes from the registry/project-state-bound
`T09_PRAGMATIC_RETRY3_TERMINAL_CONTROL.json`. It cryptographically preserves the
historical smoke/V5 profiles and V5 execution contract while superseding their
embedded pre-run readiness strings; policy rejects both consumed plan IDs as
nonreplayable. No registered successor profile exists.

## Current T09 Retry 4 checkpoint

`PLAN-EXP0001-PILOT-V6` repaired the Retry 3 archive-path and campaign-clock
failures. On its second and final provider slot, clean package `2b40b8a8…` imported
the exact retained image `sha256:abe8ed38…`, passed the pinned package, evaluator,
real-evidence, browser, pair-diff, credential, and one-model-metadata gates, and froze
run manifest `c633c835…` before a fresh empirical clock.

Task A reactive crossed empirical entry once. Its evidence records 20 model calls,
38,779 tokens, five requested browser actions, four post-action results, and USD
0.1175275 OpenAI cost. A 234,479,616-byte core artifact expanded the raw attempt tree
beyond the 67,108,864-byte hard cap. The host stopped the container with exit 143,
then the immutable raw seal failed closed. Consequently task completion, answer,
evaluator validity, and score are unavailable. Task A simulative and both Task B
attempts are `not-run`; no condition retry, realized pair, first-pair checkpoint,
comparison, or EXP-0001 outcome exists.

The maximal private prefix was copied and verified before cleanup and termination.
Both Retry 4 hosts are terminal or absent; zero T09 instances and restored security
are verified. Retry4 used 4,419.078072 active Lambda seconds / USD 1.5835029759 plus
USD 0.1175275 OpenAI, for USD 1.7010304759 new and USD 5.7424506112 cumulative T09
cost. Post-termination review preserved the original archive byte-exact and added one
private 597,140-byte sidecar member under overlay manifest `1eedf1d9…`; frozen-runtime
reconstruction passes at `c633c835…`. Separate clock receipt `989d5625…` records
2,353.116390 seconds of slot-2 preflight and 680.255410 seconds from empirical start
through terminal/zero observation without rewriting the provider closeout. The two-
launch/campaign authority is exhausted. Current machine authority is
`T09_PRAGMATIC_RETRY4_TERMINAL_CONTROL.json`, which makes the smoke and V6 profiles
historical, consumed, and nonreplayable and names no successor.

## Historical consumed smoke record

- Experiment: `EXP-0001`
- Profile plan ID: `PLAN-EXP0001-SMOKE`
- Profile record:
  `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml`
- Condition plans: `RUN-EXP0001-SMOKE-REACTIVE` followed by
  `RUN-EXP0001-SMOKE-SIMULATIVE`
- Pair: `PAIR-EXP0001-SMOKE-0000`
- Interpretation: prohibited (`interpretation_allowed: false`)

The smoke profile and both condition plans are historical records whose separate
bounded authority was consumed. They are neither eligible nor reusable. No exact
successor run profile currently exists, and this readiness record is not authorization.

T07's high-assurance infrastructure track is frozen at
`high-assurance-infrastructure-frozen`. Gate L1/L1A evidence is complete, sealed and
nonreplayable. The automated Lambda launch path was rejected, and the manual-console
qualification was designed but never executed. Its V3/run 0003 stopped after six
read-only observations and before mutation.

The later one-GET firewall capture run
`RUN-T07-L2M-FIREWALL-BASELINE-CAPTURE-0001` is also burned and immutable. It retained
a complete HTTP-200 provider response, but the historical parser stopped at
`schema_drift` because the data object included one additive metadata key. Offline
adjudication preserved that original disposition and classified the response as
`compatible_additive_top_level_extension`. All four rules pass the strict,
description-aware canonicalizer; the exact private baseline and PATCH restoration
payload are retained and sealed, while the public records contain only structural
names, types, counts and hashes.

No executable high-assurance plan or authorization block remains active. Bounded-smoke
V1 stopped before its first account request and is preserved as blocked historical
provenance. Its eventual bounded successor executed and is also closed and
nonreplayable.

Historical consumed bounded plan: `PLAN-T07-BOUNDED-SIRA-SMOKE-V3`.

Its host run is `RUN-T07-BOUNDED-HOST-0003`; the plan is at
`containers/sira-smoke/bounded/bounded-smoke-plan-v3.json`, with the exact byte size
and SHA-256 recorded in the V3 implementation ledger and authorization packet. Its
governance, exact caps, user runbook, and future authorization packet are under
`docs/harness/T07_BOUNDED_SMOKE_*`. Every execution permission remains false; the
bounded T07 smoke ran under its now-exhausted separate authority, and Gate L2M/L3/L4
do not continue.

## Historical bounded-smoke authorization fields

The consumed bounded-smoke authorization bound one value for every field below. This
table is historical audit context and is not a current authorization template:

| Field | Locked or proposed value |
|---|---|
| `run_plan_id` | Exactly `PLAN-EXP0001-SMOKE` |
| `api_provider` | `OpenAI` |
| `model_revision` | Exactly `gpt-4o-2024-11-20`, used as a declared substitution for the unavailable historical `gpt-4o` serving revision |
| `maximum_api_cost_usd` | Proposed ceiling: `4.00`; the user must explicitly approve this value or a lower replacement after price reverification |
| `bounded_substrate_cost_cap_usd` | Exact ceiling `2.00` for one Lambda instance under the bounded V3 plan |
| `maximum_provider_compute_cost_usd` | Exact ceiling `2.00`; observed/projected normal one-hour list cost `1.29` |
| `maximum_wall_time_seconds` | `3,600` from authorization materialization for the complete provider-supervised window, with termination click by `3,300`; scientific workload is `240` total, at most `120` per condition |
| `required_cleanup` | Stop/KILL each immutable container boundary, prove zero owned resources, preserve/copy/seal evidence, have the user terminate the exact Lambda instance through the provider console, and confirm terminal/nonbillable state through the read-only observer |

The historical control plane materialized those fields as a mode-0600, Git-ignored
single-run overlay bound to its clean commit, plan, 3,600-second window, private
resource binding, budgets, command hashes, and condition identities. That overlay is
consumed. Repository permission fields, benchmark, and training permissions remain
false. The frozen Gate L2M/L3/L4 and bounded-smoke contracts cannot be reauthorized,
and no field may be inferred from this readiness document, public pricing, or an
earlier gate.

## Historical bounded-smoke API spend cap

The historical profile cap was **USD 4.00**: two condition attempts, each limited to
200,000 model tokens and conservatively priced at the recorded USD 10.00 per million
output-token rate. The dated price record is
`experiments/EXP-0001-sira-simulative-vs-reactive/pricing.yaml`. It does not supply a
current budget or authorization.

## Historical bounded-smoke pre-execution materialization

The consumed T07 bounded contract required these deterministic preflight obligations
after authorization but before the first live model, API, or browser action:

1. Bind the clean GIC Lab commit, pinned SiRA checkout, immutable model substitution,
   protocol hash, condition-owned configuration hashes, environment fingerprint, and
   exact argument-array command hashes.
2. Validate the complete authorized parent profile, require no unresolved execution
   blocker, verify every declared child plan, and materialize the exact canonical child
   fingerprint set. Reject any invoked plan outside that set even if it copies the
   profile ID, profile hash, or authorization reference.
3. Machine-diff the two resolved commands/configurations and permit only the declared
   condition and identity differences.
4. Enforce finite command-level token, API-cost, wall-time, tool-call, and output-byte
   limits; stop if the upstream surface cannot make them effective.
5. Redirect source session JSON, text logs, stdout, stderr, screenshots, and evaluator
   output into fresh harness-owned attempt roots before launch.
6. Pin and record the approved browser/runtime revision. Apply the Occam admission
   rule to the concrete topology, including whether a private PID/cgroup boundary is a
   hard blocker, and verify bounded runtime plus provider cleanup without a live
   model/API call.
7. Verify required secret names without printing, persisting, hashing, or placing
   secret values in arguments, paths, events, or artifacts.
8. Bind the bounded child's own host/runtime/termination evidence; revalidate every
   selected billable resource and price; and prove its cleanup boundary before the
   separately authorized scientific attempt. No frozen Gate L2M/L3/L4 identity or
   authority may satisfy this obligation.

Failure of any preflight obligation would have stopped T07 before execution and
preserved the authorization record; it did not relax the protocol.

## Historical bounded-smoke evidence contract

For each condition attempt and for the paired profile, retain and validate:

- the authorization reference, materialized run plan, resolved argument-array command,
  resolved configuration, and source/protocol/config/environment/command identities;
- raw upstream session JSON and text logs, stdout and stderr, browser screenshots and
  runtime identity, evaluator output when produced, and every failed or retried attempt;
- append-only normalized events, artifact records with byte sizes and SHA-256 hashes,
  token/model-call/tool-call/browser-action counts, wall time, and estimated API cost;
- one source-grounded `regulation_decision` record per condition with
  `source_kind: experiment_assignment`, the derived selected mode, the assignment
  policy/config revision when known, raw artifact or resolved-configuration references,
  and field-level provenance;
- null/unavailable status for confidence, override, fallback, critic, configurator,
  or per-step planning fields that the pinned source does not expose;
- pair-equivalence evidence showing that trace instrumentation did not change the
  treatment/control contract; and
- cleanup evidence showing immutable container-boundary termination, zero live browser
  processes, sealed append-only artifacts, reconciled API/compute accounting, container
  removal, zero owned host resources, hash-verified transfer, provider termination,
  and terminal/nonbillable state.

These are artifact-execution and infrastructure records. The smoke may not classify
the EXP-0001 hypothesis or any RQ-H2K outcome.

## Historical bounded-smoke rollback and cleanup

- Stop before launch on identity, command, configuration, secret, budget, or artifact-
  ownership drift.
- On any launched-attempt failure, stop the complete bounded runtime boundary, verify
  zero owned resources, retain the failed attempt under its immutable identity,
  hash/copy what was captured, terminate every exact billable provider resource,
  confirm terminal/nonbillable state, and record the stop reason.
- Never overwrite or reuse an attempt directory; a retry requires a new attempt
  identity and preserves the prior evidence.
- Do not delete raw evidence as rollback. Revert only unexecuted authorization-state
  materialization after its audit record is retained.
- The bounded child must explicitly constrain persistent storage and exact provider
  ownership. Unrelated cloud resources, keys, firewall rules, tags, filesystems and
  instances are never rollback targets.

## Current publication limits and next-control boundary

- Dataset and trace public-release licensing/privacy rules remain unresolved; private,
  access-controlled smoke retention can proceed, but publication stays blocked.
- The final repository software/content licenses and publication identity remain open.
- T07's high-assurance path and bounded successor are terminally frozen and cannot be
  revived. SR²AM T11/T12 remain scientifically and operationally separate.
- No exact SiRA successor profile is currently eligible or authorized. A future paired
  calibration requires a fresh plan and identities, a new campaign clock with
  provider-activation/preflight slack, independent review, and new current-turn user
  authorization.
- RQ-H2K external-versus-explicit-model comparison feasibility remains undetermined.
  Missing optional regulation fields do not invalidate EXP-0001 when its primary
  evidence contract is complete.

## Future-track interpretation boundary

Any regulation-decision coverage or trace-sufficiency output is **infrastructure
evidence only**. A fixed reactive/simulative condition is an external experiment
assignment. It is not learned regulation, latent internalization, a new EXP-0001
condition, or evidence that an internal or external controller is superior.

All such outputs remain infrastructure evidence only; none is scientific outcome
evidence.
