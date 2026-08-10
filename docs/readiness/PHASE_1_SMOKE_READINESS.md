# Phase 1 SiRA Smoke Readiness

Status: **profile eligible; manual-console Gate L2 required; not authorized**

Prepared: 2026-08-08

Updated: 2026-08-10

## Exact next run plan

- Experiment: `EXP-0001`
- Profile plan ID: `PLAN-EXP0001-SMOKE`
- Profile record:
  `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml`
- Condition plans: `RUN-EXP0001-SMOKE-REACTIVE` followed by
  `RUN-EXP0001-SMOKE-SIMULATIVE`
- Pair: `PAIR-EXP0001-SMOKE-0000`
- Interpretation: prohibited (`interpretation_allowed: false`)

The profile and both condition plans remain unauthorized. This readiness record and
the proposed budget are not authorization. The pilot plan is not eligible.

T07 now has a design-only x86_64 Lambda On-Demand Cloud substrate. The V1/V2 Gate L1
plans and runs are preserved as blocked historical evidence; runs 0001 and 0002 are
permanently retired. Authorized V3 run `RUN-T07-L1-LAMBDA-INVENTORY-0003` completed
all seven GETs and externally sealed its schema-valid inventory and complete request
ledger. It is historical and nonreplayable.

Gate L1.3 repaired the post-run image projection without changing run 0003: 259
regional availability rows map to 124 nonconflicting opaque aliases, and six
`gpu_1x_a10` tuples satisfy the fixed resource policy at the observed USD 1.29/hour
price. The global firewall remains non-strict because three rules expose non-SSH
ports, and no same-region per-instance ruleset exists. A future Gate L2 design must
preserve both global strictness and D-020's additive regional-ruleset requirement,
freshly prove zero running instances account-wide, and require same-instance terminal
evidence before restoring the sealed original globals. Most importantly, the
privacy-minimized inventory retained account key names
without account public-key material, so no local/account fingerprint match can be
established. At that historical Gate L1.3 checkpoint the infrastructure decision was
`inventory-evidence-insufficient`; Gate L1A later supplied the missing key evidence.

Gate L1.4 has now designed the fresh minimum evidence step without executing it:
`PLAN-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1` permits, only after a new exact
authorization, one in-process `GET /api/v1/ssh-keys` under fresh run
`RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001`. It uses a distinct fsync-backed ledger,
strict OpenSSH/RFC4716/PKCS8/PEM public-key parsing, held-no-follow local `.pub`
matching, ignored sealed private evidence, an exact source-loading wrapper, and a
separate fsync-backed post-ledger archive-finalization disposition. A terminal request
ledger alone is not complete evidence. The plan remains unauthorized; no
account request, secret access, SSH, mutation, or paid compute occurred in its design.

Gate L1A completed the minimum evidence step and sealed one unique match for
`fractal-lambda-codex`. Gate L2.0 then validated the user's private decisions and
selected `gpu_1x_a10` in `us-east-1` with `img-0111` / `22.4.5-2141`, temporary
strict global-plus-regional `/32` controls, and independent Jupyter ED25519 trust.
Raw IDs, source network, paths, and fingerprints remain in ignored parameters whose
hash-verified copy is sealed to the approved external archive.

Gate L2.1 then pinned the current launch/list/detail/terminate contract and built
fake-tested marker, journal, discovery, termination, watchdog, cap, privacy, and
archive primitives. Independent review found that these pieces do not compose one
authoritative live transaction: mutation effects/order, cleanup from every failure,
cross-process budget/lease enforcement, an independently supervised watchdog,
duplicate/terminal polling, exact process arrays, and evidence closure remain
incomplete. The automated API-launch path therefore terminated at
`manual-console-launch-required`. No executable Gate L2 plan or authorization block
exists; the V1 and draft V2 identities are rejected. Cloud mutation and paid compute
remain false. Any future Gate L2 proposal must be a newly reviewed human-operated
console launch/observation/cleanup contract with fresh identities and current-turn
authorization. Gate L3 and Gate L4 remain blocked.

## Exact user decision fields

A later current-turn authorization must state one value for every field below:

| Field | Locked or proposed value |
|---|---|
| `run_plan_id` | Exactly `PLAN-EXP0001-SMOKE` |
| `api_provider` | `OpenAI` |
| `model_revision` | Exactly `gpt-4o-2024-11-20`, used as a declared substitution for the unavailable historical `gpt-4o` serving revision |
| `maximum_api_cost_usd` | Proposed ceiling: `4.00`; the user must explicitly approve this value or a lower replacement after price reverification |
| `maximum_provider_compute_cost_usd` | Must be recomputed from the L1-selected Lambda cents/hour and freshly approved for Gate L4 |
| `maximum_wall_time_seconds` | Scientific workload ceiling remains proposed `240` total, at most `120` seconds per condition; the fresh Lambda host lifecycle needs a separate aggregate provider wall cap |
| `required_cleanup` | Stop/KILL each immutable container boundary, prove zero owned resources, preserve/copy/seal evidence, terminate the exact Lambda instance through the provider API, and confirm terminal/nonbillable state |

The authorization reference must identify that current user instruction. Within the
authorized T07 work item, the control plane may set
`paid_compute_allowed` and `prototype_execution_allowed` true only for this bounded
profile, set the profile and both condition authorization records to that reference,
bind `docs/PROJECT_STATE.yaml.authorized_run_profile` to the exact profile path and
SHA-256 plus the sealed canonical `condition_plan_sha256s`, bind both condition plans
to the same `profile_plan_id` and `profile_sha256`, and materialize condition-owned
budgets and command hashes.
Benchmark and training permissions remain false. Cloud-mutation permission remains
false now and may change only in a fresh Gate L4 authorization that binds exactly one
launch and provider termination for the exact instance ID. No field may be inferred
from this readiness document, public pricing, or an earlier infrastructure gate.

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
6. Pin and record the approved browser/runtime revision, run it only inside the
   empirically qualified private PID/cgroup container boundary,
   and verify container plus provider cleanup without a live model/API call.
7. Verify required secret names without printing, persisting, hashing, or placing
   secret values in arguments, paths, events, or artifacts.
8. Bind successful Gate L2 host/runtime/termination evidence and Gate L3 x86_64
   image/adversarial/dummy-secret/local-page evidence; revalidate exact account,
   type/region/image/key/ruleset/price and prove no duplicate T07 instance before the
   one Gate L4 launch.

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
- On any launched-attempt failure, stop/KILL the complete immutable container boundary,
  verify zero owned resources, retain the failed attempt under its immutable identity,
  hash/copy what was captured, terminate the exact Lambda instance through the
  provider API, confirm terminal/nonbillable state, and record the stop reason.
- Never overwrite or reuse an attempt directory; a retry requires a new attempt
  identity and preserves the prior evidence.
- Do not delete raw evidence as rollback. Revert only unexecuted authorization-state
  materialization after its audit record is retained.
- No Lambda persistent filesystem is permitted. A future authorized Gate L4 may own
  exactly one ephemeral instance and must terminate it on every exit; unrelated cloud
  resources, keys, firewall rules, tags, filesystems, and instances are never rollback
  targets.

## Remaining blockers and nonblocking questions

- Dataset and trace public-release licensing/privacy rules remain unresolved; private,
  access-controlled smoke retention can proceed, but publication stays blocked.
- The final repository software/content licenses and publication identity remain open.
- T07 Lambda capacity and price were observed and the candidate, SSH key, firewall,
  private `/32`, and host-key method were validated and privately sealed. Gate L2's
  automated API-launch design ended at `manual-console-launch-required`; the offline
  supervisor/watchdog primitives are not execution authority. Continuing requires a
  user-requested, newly reviewed human-operated console launch/observation/cleanup
  contract with fresh plan/run identities and fresh authority. SR²AM T11/T12 remain
  scientifically and operationally separate.
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
