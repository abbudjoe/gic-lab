# Phase 1 — Artifact Execution

Status: **in-progress**

Started: 2026-08-08

## Source contract

The authoritative package contract is the original Phase 0.75-to-Phase 1 build
package as amended by
`GIC_Lab_H2K_Option_Preservation_Addendum_v1_1`, especially its updated execution
roadmap and T07 through T15 prompts. Repository authority is further constrained by
`AGENTS.md`, `docs/PLANS.md`, `docs/COMPUTE_POLICY.md`,
`docs/SECURITY_AND_SECRETS.md`, the locked EXP-0001 protocol/run profiles, and the
successful Phase 0.75 plan.

T06 opens this plan but authorizes no execution. Each live API/model/browser or cloud
work item requires the exact current-turn human authorization declared by its task
contract. A proposed budget, eligible profile, historical conversation, or this plan
is not authorization.

## Target contract

Produce a source-grounded artifact-execution and directional-reproduction record for
the released SiRA and SR²AM artifacts through sequential, separately authorized smoke
and pilot gates. Preserve raw-to-normalized lineage, exact cost and compute accounting,
condition isolation, safe cleanup, and precise reproduction-level labels. RQ-H2K may
consume trace-completeness infrastructure evidence only; it remains planned/deferred
and cannot add an experiment, condition, training path, learned kernel, or later phase.

## Scope

In scope: T07 through T15; the authorized SiRA paired smoke and pilot; evidence-only
analysis between execution gates; read-only SR²AM Lambda preflight; separately
authorized SR²AM smoke and pilot; raw artifact retention and hashes; regulation-
decision provenance; compute/API accounting; public preliminary reporting; and the
current Phase 1 closeout.

Out of scope: any execution without the exact current-turn authorization; protocol
adaptation to observed effects; confirmatory claims; a new EXP-0001 condition; a
harness-to-kernel comparison; learned-kernel training or distillation; Phase 2; and
cloud mutation outside the exact T12/T14 authorization contract.

## Phase definition of done ledger

| ID | Required outcome | Planned evidence | Status |
|---|---|---|---|
| P1-DOD-01 | Phase 0.75 is successful/completed; this is the one authoritative active plan; project execution/compute permissions remain false; only the disabled smoke profile is eligible for a later exact authorization. | Plan lifecycle/state/profile/readiness validation and public render. | met |
| P1-DOD-02 | T07 executes at most the one authorized SiRA smoke pair with complete raw, normalized, regulation-decision, budget, scoring, and cleanup evidence and no interpretation. | Immutable run/authorization records, artifacts/hashes, accounting, cleanup proof, and validation. | not-started |
| P1-DOD-03 | T08 independently reproduces the smoke summary, separates infrastructure/protocol/upstream/future-track gaps, and leaves any pilot unauthorized. | Raw-to-summary checks, infrastructure-only trace-sufficiency report, review, and gate. | not-started |
| P1-DOD-04 | T09 executes only a freshly authorized locked SiRA pilot without outcome-adaptive changes and reconciles every attempt. | Frozen task/order records, complete paired artifacts, budgets, and attempt dispositions. | not-started |
| P1-DOD-05 | T10 produces a reproducible exploratory EXP-0001 analysis with uncertainty, exact reproduction level, cost/deviation reporting, and no internalization or mechanism-attribution overclaim. | Validated result summary, registry/notebook/ledger updates, review, and gate. | not-started |
| P1-DOD-06 | T11 produces a read-only, launch-ready SR²AM-v0.1-8B Lambda contract with current price, hard termination, source-grounded trace requirements, failure tests, and no mutation. | Audited runbook/contracts, dry-run/failure tests, authorization sentence, and gate. | not-started |
| P1-DOD-07 | T12 launches only the exactly authorized SR²AM smoke, retains and transfers required evidence, reconciles cost, and verifies provider termination. | Immutable cloud attempt, raw artifacts/hashes, compute ledger, monitoring, and terminal-state proof. | not-started |
| P1-DOD-08 | T13 validates SR²AM artifact fidelity, runbook safety/cost predictability, and infrastructure-only trace sufficiency before proposing an unauthorized pilot. | Recomputed evidence, source/adapter lineage, repaired tests, review, and gate. | not-started |
| P1-DOD-09 | T14 executes only a freshly authorized locked SR²AM pilot and verifies artifact transfer, accounting, and termination without in-run design changes. | Immutable pilot records, artifacts/hashes, compute reconciliation, and terminal-state proof. | not-started |
| P1-DOD-10 | T15 closes the current Phase 1 unit with validated SiRA/SR²AM evidence, precise reproduction levels, uncertainty/cost/deviation reporting, and one proposed next scientific workstream that is not begun. | Result summaries, registry/notebook/decision/risk updates, review, final gate, and plan disposition. | not-started |
| P1-DOD-11 | Every executed attempt has explicit current-turn authorization, immutable identity, append-only raw evidence, version/hash lineage, finite budget enforcement, secret isolation, and verified cleanup; failed infrastructure is never a scientific negative. | Run/compute/artifact ledgers, policy checks, failure evidence, and cross-task review. | not-started |
| P1-DOD-12 | Regulation/control evidence remains source classified; experiment assignment and ordinary prose are never called learned regulation; RQ-H2K outputs are infrastructure-only and do not affect EXP-0001 validity or interpretation. | Typed events, trace-sufficiency reports, negative boundary tests, and public wording. | not-started |
| P1-DOD-13 | Every implementation/analysis task passes focused smoke, independent spec-conformance review, post-review smoke, and its required full gate before the next dependency begins. | Per-task assembly ledgers with exact commands, artifacts, reviewer verdicts, and status. | not-started |

## Work packages and implementation mapping

| Task | Work package | Mapped phase DoD | Current permission |
|---|---|---|---|
| T07 | Execute one authorized local/API SiRA smoke pair; capture regulation-decision evidence without interpretation. | P1-DOD-02, P1-DOD-11 through P1-DOD-13 | Gate B1.7 complete; local runtime rejected; no B2a authority |
| T08 | Analyze smoke infrastructure evidence and prepare an unauthorized pilot package. | P1-DOD-03, P1-DOD-11 through P1-DOD-13 | blocked until T07 succeeds |
| T09 | Execute the freshly authorized exploratory SiRA pilot. | P1-DOD-04, P1-DOD-11 through P1-DOD-13 | blocked until T08 and authorization |
| T10 | Analyze and publish the exploratory SiRA pilot. | P1-DOD-05, P1-DOD-11 through P1-DOD-13 | blocked until T09 succeeds |
| T11 | Build and validate the read-only SR²AM Lambda preflight. | P1-DOD-06, P1-DOD-11 through P1-DOD-13 | blocked until T10 succeeds |
| T12 | Launch and monitor the separately authorized SR²AM Lambda smoke. | P1-DOD-07, P1-DOD-11 through P1-DOD-13 | blocked until T11 and authorization |
| T13 | Analyze the SR²AM smoke and prepare an unauthorized pilot. | P1-DOD-08, P1-DOD-11 through P1-DOD-13 | blocked until T12 succeeds |
| T14 | Launch and monitor the separately authorized SR²AM Lambda pilot. | P1-DOD-09, P1-DOD-11 through P1-DOD-13 | blocked until T13 and authorization |
| T15 | Analyze SR²AM pilot evidence and close the current Phase 1 unit. | P1-DOD-10 through P1-DOD-13 | blocked until T14 succeeds |

Work is sequential. A completed execution does not authorize its analysis successor,
and an analysis recommendation does not authorize the next execution.

## T07 assembly control

Assembly status: **Gate B1.7 complete; runtime-candidate-rejected; no executable Gate B2a plan**

Exact next profile: `PLAN-EXP0001-SMOKE`.

Target contract: materialize and execute one matched reactive/simulative pair under an
exact human-approved provider/model, API-cost cap, wall-time cap, and cleanup contract;
preserve complete artifact and source-grounded regulation-decision evidence; and stop
without scientific interpretation or pilot progression.

The exact authorization fields, proposed USD 4.00 cap, pre-execution obligations,
expected artifacts, cleanup, questions, and infrastructure-only interpretation boundary
are in [`docs/readiness/PHASE_1_SMOKE_READINESS.md`](../../readiness/PHASE_1_SMOKE_READINESS.md).
The locked profile is
[`PLAN-EXP0001-SMOKE`](../../../experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml).

### Gate B1.5 definition of done

Source contract: the user's 2026-08-09 Gate B1.5 storage-topology instruction.
Baseline: `b8752765594de0b3486edfd9fad84d144b78b7b7`.

| ID | Obligation | Status | Evidence |
|---|---|---|---|
| T07-B15-01 | Preserve branch/baseline and all prohibitions. | met | Starting checks; no execution or scientific change. |
| T07-B15-02 | Classify exposure as block mount, network filesystem, remote mechanism, or separate host. | met | MacBook Pro storage is exported by Thunderbolt Target Disk Mode as UTDM `/dev/disk6`, synthesized as APFS `/dev/disk7s5`, and mounted locally by the Mac mini; no SMB/NFS/FUSE mount. |
| T07-B15-03 | Record every requested identity, capacity, durability, permission, escape, and suitability field. | met | `docs/harness/T07_GATE_B1_5_STORAGE_TOPOLOGY_DECISION.md`. |
| T07-B15-04 | Default to sealed-retention-only unless stronger suitability is positively established. | met | Active/Docker suitability remains unapproved. |
| T07-B15-05 | Encode the network-backed copy/seal branch even though it is not the observed topology. | met | Storage policy and decision contract. |
| T07-B15-06 | If fully suitable locally, issue exact roots and regenerated plans/hashes; otherwise stop. | blocked | Docker VM-disk and reconnect suitability cannot be proven without a selected topology and later authorized runtime-specific evidence. No new plan/hash issued. |
| T07-B15-07 | Present alternatives a/b/c without selecting one. | met | Decision and both blocked packets. |
| T07-B15-08 | Update B1.5, B2a, and B2b documents and keep old Gate B2 hash superseded. | met | Three target documents under `docs/harness/`; no replacement plan/hash issued. |
| T07-B15-09 | Pass validation, independent spec review, repairs, and post-review smoke. | met | `make validate` and `git diff --check` passed; independent rereview was clean after topology/identity/governance repairs; post-review validation passed. |

Gate B1.5 maps T07-B15-02 through T07-B15-07 to the topology decision;
T07-B15-04 through T07-B15-06 to `docs/STORAGE_POLICY.md` and
`docs/DECISIONS.md`; T07-B15-06 through T07-B15-08 to the Gate B2a/B2b packets;
and T07-B15-01 through T07-B15-09 to this active plan.

### Gate B1.6 definition of done

Source contract: the user's 2026-08-09 Docker-storage qualification instruction,
SHA-256 `52d05ce39998f1a0ff81c7bbc23d936d1a61e1d709c0adafdfd07b7fb0279e60`.
Baseline: `e224e781e752869041c78a3e93687aaa5d8c6430`.

The detailed 22-item DoD, mappings, test evidence, blockers, and closeout are maintained
in `docs/harness/T07_GATE_B1_6_IMPLEMENTATION_LEDGER.md`. Gate B1.6 implements the
two-volume storage control plane, exact path roles, UUID/physical-store/APFS/UTDM
guards, reconnect state, minimized placement evidence, and one-way seal/copy
lifecycle. It does not live-qualify Docker or the topology.

Gate B1.6 is intentionally blocked on two facts that cannot be manufactured locally:
fresh official Docker metadata and a numeric source-grounded Mac mini operational
floor. Version-specific first-start internal allocation, settings/default paths,
update control, and reconnect semantics also require current official evidence. A
hashed blocked-design B2a plan may record the proposed sequence but cannot confer
installation authority while those terms remain unknown. B2b remains a
requirements-only stub.

### Gate B1.7 terminal runtime decision

Source contract: the user's 2026-08-09 final local-runtime selection instruction.
Baseline: `87d0a759dce2cfb6a6be964b2cf462ae43a1d9c9`.

The detailed DoD, mappings, source locks, repairs, validation, and terminal blockers
are maintained in `docs/harness/T07_GATE_B1_7_IMPLEMENTATION_LEDGER.md`. Gate B1.7
supersedes Gate B1.6's proposed Docker next-work path without deleting its evidence.
Docker Desktop remains blocked provenance. The evaluated Colima v0.10.3/Lima v2.2.0
candidate is `runtime-candidate-rejected`: required external `LIMA_HOME` would contain
Lima's private SSH identity on an ownership-disabled volume, the supported image does
not provide a current immutable pre-start Docker runtime, and required numeric caps
remain unresolved. No replacement plan ID, path, hash, argv array, or authorization
block exists. The sealed-artifact retention decision remains in force.

This was the final local-runtime selection gate. It does not create another B1.x turn,
authorize installation or a runtime probe, or alter the EXP-0001 treatment contrast.

## Authorization and mutation boundary

Current project state keeps paid compute, prototype execution, benchmark execution,
training, and cloud mutation false. T07 cannot begin a live action until a later user
turn names every readiness authorization field. T09 requires a fresh pilot
authorization. T12 and T14 separately require their exact cloud mutation, hardware,
data, cost/time, artifact-transfer, and termination authority. Read-only inspection or
preflight never supplies mutation authority.

## Planned evidence

- One Assembly ledger per T07–T15 task with DoD mappings and exact evidence.
- Schema-valid immutable plans, commands, events, artifacts, summaries, and compute
  records linked to pinned source/model/dataset/environment revisions.
- Focused deterministic tests plus independent spec-conformance review and post-review
  `make check` for each work item.
- Real CUDA/cloud evidence only for the separately authorized SR²AM execution tasks;
  local/API SiRA evidence is never presented as CUDA evidence.
- Public notebook updates that separate infrastructure, exploratory evidence,
  reproduction level, and unsupported claims.

## Progress log

- 2026-08-08: T06 created the Phase 1 control plane after integrating and reviewing
  Phase 0.75. `PLAN-EXP0001-SMOKE` is the only profile eligible for a later human
  authorization; the pilot and all SR²AM execution remain blocked.
- 2026-08-08: All project execution and compute permissions opened as false. No model,
  API, browser, benchmark, training, cloud, or paid-compute action occurred during the
  transition.
- 2026-08-08: Parent-profile eligibility became a typed authorization gate: condition
  plans bind the exact profile plan ID and SHA-256; project state fully validates and
  binds the same profile and its canonical declared-child fingerprints before
  execution; and blocked or undeclared plans cannot materialize authorization.
- 2026-08-08: T07 Gate A implemented immutable all-role routing, durable finite
  provider accounting, owned attempt/log/environment evidence, exact output capping,
  external installation contracts, smoke-only authorization materialization, and a
  machine condition diff. Independent review proved polling cannot guarantee cleanup
  for a fast reparented child, so the command now fails preflight until kernel-enforced
  containment exists. No SiRA dependency/browser installation or live action occurred.
- 2026-08-09: T07 Gate B1 implemented and independently reviewed a private-PID,
  cgroup-backed OCI containment control plane without installing or launching a
  runtime. A later storage rule superseded its internal-disk Gate B2 plan.
- 2026-08-09: Gate B1.5 observed the MacBook Pro exporting storage through
  Thunderbolt Target Disk Mode to a locally mounted APFS block device on the Mac mini,
  then positively tested sparse files, same-volume rename, file/full/directory sync,
  and mode bits. Owners are disabled, symlink escape is possible, Target Disk Mode
  reconnect/unlock behavior is untested, and Docker disk-image suitability is unknown.
  It is therefore approved for sealed retention only.
- 2026-08-09: Independent Gate B1.5 review corrected the initial direct-disk
  classification to UTDM, separated volume/container/partition/transport identities,
  reconciled D-017 across historical packets, scoped volume checks to sealed-copy
  actions, and made positive active/runtime suitability mandatory before B2a plan
  issuance. Post-repair rereview was clean and post-review validation passed.
- 2026-08-09: The user selected the Mac mini plus MacBook Target Disk Mode topology
  for Gate B1.6 qualification. The local control plane now separates external Docker,
  staging, and sealed-artifact roles from the bounded Mac mini attempt root; rejects
  fallback and stale storage guards; and implements deterministic reconnect and
  one-way sealed-copy contracts. No Docker or network action occurred. Installation
  remains blocked because current metadata and an evidence-based internal floor are
  unresolved.
- 2026-08-09: Gate B1.7 audited pinned Colima/Lima/Docker release and source metadata,
  rejected the replacement topology under the binary decision rule, and created no
  executable B2a plan. Independent review hardened exact-path lease transfer,
  positive writer-closure evidence, issuer-bound rollback ownership, and authoritative
  control-plane alignment. No runtime payload, VM, container, browser, API, secret, or
  SiRA condition was installed, launched, accessed, or executed.

## Decision log

- 2026-08-08: Keep authorization eligibility distinct from live readiness. T07 owns
  deterministic command/environment/budget/log/cleanup materialization after exact
  authorization and must stop before execution if any requirement fails.
- 2026-08-08: Treat all RQ-H2K trace-sufficiency outputs as infrastructure evidence;
  they neither block EXP-0001 on optional-field absence nor support an internalization
  claim.
- 2026-08-09: Approve the MacBook Pro Target Disk Mode destination only for sealed,
  hash-verified artifact retention. Do not infer active-attempt or Docker-disk
  suitability from its block interface or capacity.
- 2026-08-09: Evaluate, without yet approving, the user-selected external Docker VM
  disk topology under a new `/Volumes/Macintosh HD - Data/GIC-Lab` root. Preserve the
  MacBook volume's sealed-retention approval while requiring a later authorized B2a
  reconnect probe before runtime-storage qualification.
- 2026-08-09: Terminate the current local-runtime selection under D-019. Preserve the
  sealed-retention root, retain Docker artifacts only as blocked provenance, reject
  the reviewed Colima/Lima topology, and require a new user topology choice before any
  installation or qualification authority can be proposed.

## Blockers and user actions

T07 has no selected local runtime and no executable B2a plan. Docker Desktop plans are
superseded blocked provenance; the reviewed Colima/Lima candidate is rejected. The
user must select one of the three terminal alternatives below before a new topology
can be reviewed. No existing packet may authorize installation or probes, and no
other Phase 1 work package may begin first.

## Next permitted work

There is no further B1.x design gate. The next user decision must select, without
automatic preference, one of: (1) a directly attached local external SSD on the Mac
mini; (2) a separately approved Linux execution host; or (3) a deliberately less
strict containment/storage-confidentiality contract approved as a scientific-
governance change. Only that newly reviewed topology can define later permitted work.
Gate B2a, Gate B2b, both SiRA conditions, and the smoke remain blocked.
