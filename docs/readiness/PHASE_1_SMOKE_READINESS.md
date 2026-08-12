# Phase 1 SiRA Smoke Readiness

Status: **T07 smoke closed and adjudicated; pilot planning eligible; pilot execution blocked and unauthorized**

Prepared: 2026-08-08

Updated: 2026-08-11

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

## Exact next run plan

- Experiment: `EXP-0001`
- Profile plan ID: `PLAN-EXP0001-SMOKE`
- Profile record:
  `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml`
- Condition plans: `RUN-EXP0001-SMOKE-REACTIVE` followed by
  `RUN-EXP0001-SMOKE-SIMULATIVE`
- Pair: `PAIR-EXP0001-SMOKE-0000`
- Interpretation: prohibited (`interpretation_allowed: false`)

The historical smoke profile and both condition plans remain unauthorized after their
separate bounded authority was consumed. This readiness record and the historical
proposed budget are not authorization. The pilot planning package is eligible, but
pilot execution is not.

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
provenance. The reviewed prospective replacement remains unauthorized.

Prospective bounded plan: `PLAN-T07-BOUNDED-SIRA-SMOKE-V3`.

Its host run is `RUN-T07-BOUNDED-HOST-0003`; the plan is at
`containers/sira-smoke/bounded/bounded-smoke-plan-v3.json`, with the exact byte size
and SHA-256 recorded in the V3 implementation ledger and authorization packet. Its
governance, exact caps, user runbook, and future authorization packet are under
`docs/harness/T07_BOUNDED_SMOKE_*`. Every execution permission remains false, T07 has
not run, and Gate L2M/L3/L4 do not continue.

## Exact user decision fields

A later current-turn authorization must state one value for every field below:

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

The authorization reference must identify that current user instruction. The bounded
control plane materializes it as a fresh mode-0600, Git-ignored single-run overlay
bound to the final clean commit, plan, 3,600-second window, private resource binding,
budgets, command hashes, and condition identities. Repository permission fields remain
false and `CMP-0001` remains a planned record with zero actual time/cost; the overlay
does not silently rewrite either authority plane. Benchmark and training permissions
remain false. The frozen Gate L2M/L3/L4 contracts cannot be reauthorized, and no field
may be inferred from this readiness document, public pricing, or an earlier gate.

## Proposed API spend cap

The proposed profile cap is **USD 4.00**: two condition attempts, each limited to
200,000 model tokens and conservatively priced at the recorded USD 10.00 per million
output-token rate. The dated price record is
`experiments/EXP-0001-sira-simulative-vs-reactive/pricing.yaml` and must be reverified
before authorization. A changed provider rate, unavailable model revision, or
unbounded charge category stops preflight; it does not silently increase the cap.

## Required pre-execution materialization

T07 must complete these deterministic preflight obligations after authorization but
before the first live model, API, or browser action:

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

Failure of any preflight obligation stops T07 before execution and preserves the
authorization record as an unconsumed/blocked attempt; it does not relax the protocol.

## Expected artifacts

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

## Rollback and cleanup

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

## Remaining blockers and nonblocking questions

- Dataset and trace public-release licensing/privacy rules remain unresolved; private,
  access-controlled smoke retention can proceed, but publication stays blocked.
- The final repository software/content licenses and publication identity remain open.
- T07's high-assurance path is terminally frozen and cannot be revived. The bounded
  child has a concrete topology, exact caps, cleanup/evidence contract, and reviewed
  unauthorized plan. It remains blocked on a fresh current-turn authorization and all
  dynamic preflight checks. SR²AM T11/T12 remain scientifically and operationally
  separate.
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
