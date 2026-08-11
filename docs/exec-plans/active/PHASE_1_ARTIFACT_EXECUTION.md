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
cloud mutation outside a fresh exact current-turn T07 Gate L2/L4 or T12/T14
authorization contract. Gate L0 and L3 design work and Gate L1 read-only inventory
grant no mutation authority; one gate's authorization never carries into another.

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
| T07 | Execute one authorized contained SiRA smoke pair; capture regulation-decision evidence without interpretation. | P1-DOD-02, P1-DOD-11 through P1-DOD-13 | Gate L1/L1A complete/sealed; Gate L2M V3 burned; fresh one-GET firewall baseline capture required and unauthorized |
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

Assembly status: **Gate L1/L1A complete and sealed; Gate L2M V3 stopped before
mutation and is burned; one fresh read-only firewall-baseline GET is the sole
unauthorized next proposal**

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

### Gate L0 Lambda host pivot

Source contract basename: `T07_GATE_L0_LAMBDA_LINUX_HOST_PIVOT.md`,
SHA-256 `d630b569864a3a1125cd62fb92ad67b023faa2195bdc529829aafcb8dfa12efd`.
Baseline: `0ce094778f979e303794bbfe01acc93829a7ff1d` on parent
`phase-1/sira-smoke`; implementation branch `phase-1/sira-smoke-lambda`.

The detailed DoD, implementation mapping, source locks, tests, independent review,
and final gate evidence are maintained in
`docs/harness/T07_GATE_L0_IMPLEMENTATION_LEDGER.md`. Gate L0 selects a short-lived
x86_64 Lambda On-Demand Cloud host as T07's planned substrate, with no persistent
Lambda filesystem and provider-API termination as the authoritative billing boundary.
It created the now-historical eight-GET L1 inventory plan, an unauthorized
non-account-bound L2 host-qualification packet, an L3 requirements-only x86_64 B2b
successor, and an unauthorized L4 live-pair boundary.
L1 success includes a held-descriptor, hash-verified one-way copy to the approved
MacBook archive; L2 cannot consume a Mac-mini-only inventory. L2 also remains blocked
on an authenticated first-contact SSH server-host-key bootstrap.

The plan remains `lambda-host-selected-design-only`. Current capacity, exact
type/region/image/price, existing key/ruleset, and running-instance facts are
intentionally unknown until L1; an account/workspace LRN is not required. No account
API, cloud mutation, paid
compute, SSH, runtime/container/browser/model/SiRA action, secret access, or scientific
field change occurred. Docker Desktop and Colima/Lima remain terminal rejected
alternatives, not active blockers to L1.

### Gate L1.1 request-ledger repair

Source contract: the user's 2026-08-09 Gate L1.1 request-ledger observability repair
instruction. Baseline: `f9a80332da409789fefc435583aa0f1a10d3eb11` on
`phase-1/sira-smoke-lambda`; frozen implementation commit:
`0b900213801315f4312105297774b8ea5a6d9f04`.

The detailed DoD, implementation mapping, exact caps, test evidence, and independent
review record are maintained in
`docs/harness/T07_GATE_L1_1_IMPLEMENTATION_LEDGER.md`. The repair adds an
exclusive-create, append-only, flush-and-fsync request ledger; commits request intent
and send-started evidence before entering the future transport; records only closed,
secret-safe response/failure categories; fails closed on ledger unavailability; and
requires a complete validated ledger before an inventory can become eligible for
Gate L2. Fake transports and a public dummy canary are the only request/credential
surfaces exercised by the repair tests.

The immutable historical V1 plan remains byte-identical at SHA-256
`c7151737bd029e3ebad45d59dc2d9fcd58f401dc7d8658021f1d384129555c69`.
Both prior V1 authorizations are blocked historical attempts, and
`RUN-T07-L1-LAMBDA-INVENTORY-0001` may never be replayed. The fresh, still
unauthorized contract is plan `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V2`, run
`RUN-T07-L1-LAMBDA-INVENTORY-0002`, at
`containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v2.json`, SHA-256
`02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e`.
No account request, real-secret access, cloud mutation, paid compute, SSH, runtime,
browser, model, SiRA, or scientific execution occurred in Gate L1.1.

### Gate L1.2 audit-schema adjudication and minimal plan repair

Source contract: the user's 2026-08-10 Gate L1.2 instruction. Baseline:
`258ccc3c524e96e0fadc3afc23a43fa40f6a7d7a`; frozen implementation commit:
`718c75c694b3033fa7ef2ed5e7c4696fd8c389f3`.

The detailed DoD, historical evidence classification, source identity, tests, and
independent privacy/spec review are maintained in
`docs/harness/T07_GATE_L1_2_IMPLEMENTATION_LEDGER.md`. The authorized V2 run 0002
durably recorded one audit GET with HTTP 200, 18,058 response bytes, and a parser
`schema_drift` stop; no later request ran. Its raw body was not retained, so the exact
live mismatch is `unadjudicated_raw_body_absent` and cannot be reconstructed or blamed
on the provider, credential, endpoint, network, or transport. The original V2 ledger
remains byte-identical and run 0002 is permanently nonreplayable.

Under D-022, the fresh V3 plan removes audit history and account-LRN retrieval because
neither is required for Gate L2. It binds exactly seven GETs, endpoint-specific public-
contract schemas, compatible-addition structural reporting without unknown values,
hard pagination stops, strict redaction, exact implementation/execution ancestry, and
complete ledger/archive cross-validation. The unauthorized plan is
`PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V3`, run
`RUN-T07-L1-LAMBDA-INVENTORY-0003`, at
`containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v3.json`, SHA-256
`b5ec82aaa84882a7c3269ebdb695a6c694f891d66d367c05f82eaf9797515331`.
Gate L1.2 made no authenticated account/model request, accessed no real secret, and
performed no cloud mutation, paid compute, SSH, runtime, browser, SiRA, or scientific
execution.

### Gate L1.3 resource identity and Gate L2 security design

Source contract: the user's 2026-08-10 Gate L1.3 instruction. Baseline:
`42f74481e5a500cacb4973c6b29da4c3470679fe`.

Authorized V3 run `RUN-T07-L1-LAMBDA-INVENTORY-0003` completed all seven GETs with
HTTP 200/schema-valid outcomes, zero pagination, and zero running instances. Its
59,653-byte inventory, 32,287-byte/44-event request ledger, external seal, and copy
record remain byte-bound and source/archive-equal.

Offline adjudication classified the duplicate-image failure as `verifier_key_bug`:
259 regional availability rows represent 124 official `Image.id` identities. Fifteen
identities appear in ten regions with identical intrinsic metadata; there are no
same-ID/same-region duplicates and no conflicting metadata. A sealed ignored alias
map now supports a 124-alias public projection. The fixed Gate L0 policy yields six
unselected `gpu_1x_a10` tuples at the observed USD 1.29/hour price.

The current global firewall has one SSH and three non-SSH rules, so it is not strict.
Temporary global replacement is the preferred future design only after a dependency
attestation, exact approved public IPv4 `/32`, and fresh proof of zero running
instances account-wide. The original rules require a durable exact seal; the same
immutable qualification instance must be provider-terminal before verified
restoration, or the state is a high-severity incident. No regional/per-instance
ruleset exists, so a future gate must separately authorize its strict same-region
create/attach/delete lifecycle or explicitly supersede D-020's regional-ruleset
requirement. Host-key trust remains an independent console/Jupyter fingerprint
decision.

Gate L2 cannot progress to human choices because run 0003 retained account SSH-key
names but not account public-key material. Local/account fingerprint matching is
therefore `evidence_unavailable`. Resolving that fact requires independently verified
account fingerprints or a fresh reviewed and separately authorized minimal read-only
evidence plan. L1.3 created no executable plan and performed no account/model request,
real-secret access, cloud mutation, paid compute, SSH, runtime, browser, SiRA, or
scientific execution.

### Gate L1.4 SSH-key fingerprint design

Source contract: the user's 2026-08-10 Gate L1.4 instruction. Baseline:
`ae0ec40cb2da067a66f1a8d3d0e5aca857fd9491`.

Gate L1.4 pins the first-party OpenAPI 1.10.0 `GET /api/v1/ssh-keys` response and
creates fresh unauthorized plan `PLAN-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1`,
run `RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001`, at
`containers/sira-smoke/lambda/gate-l1a-ssh-key-fingerprint-plan-v1.json`, 12,448
bytes, SHA-256
`23b29823b8daf94cfb463b275149ed562656c735955a4f449b8703334de531bc`.
It is exactly one no-query/no-redirect/no-pagination/no-retry in-process GET after a
future current-turn authorization; broad inventory and prior run identities are not
reused.

The implementation parses OpenSSH, RFC4716, PKCS8/SPKI, and PEM RSA public-key forms
in process and computes standard SHA-256 fingerprints over canonical SSH wire blobs.
The plan-bound shell-free supervisor resolves the current UID's passwd home and opens
only held no-follow `.ssh/*.pub` files, treats same-stem private objects as
metadata-only, and separates ignored sealed raw/private evidence from a schema-bound
sanitized match report. Its two-phase driver stages evidence before sealing the
terminal request ledger, then requires a separate append-only finalization disposition
after atomic archive publication and post-copy verification. The request ledger alone
and every partial or failed disposition remain ineligible. A unique match remains
`unique-match-awaiting-user-approval`; no result selects or uses a key.

The fresh run root and 49,152-byte ledger are exclusive and nonreplayable. Evidence
uses finite byte/event/process/wall/file caps and the existing held-descriptor,
external-UUID, no-internal-fallback, one-way copy, source/destination hash, fsync, and
atomic-finalization contract. Gate L1A is unauthorized and unexecuted; Gate L2 remains
`inventory-evidence-insufficient`. No account/model request, real-secret access,
cloud mutation, paid compute, SSH, private-key read, runtime, browser, SiRA, or
scientific execution occurred.

## Authorization and mutation boundary

Current project state keeps paid compute, prototype execution, benchmark execution,
training, and cloud mutation false. T07 cannot begin a live action until a later user
turn names every readiness authorization field. T09 requires a fresh pilot
authorization. T12 and T14 separately require their exact cloud mutation, hardware,
data, cost/time, artifact-transfer, and termination authority. Read-only inspection or
preflight never supplies mutation authority.

T07 Gate L1 is a separately authorizable read-only account inspection and does not
require cloud-mutation or paid-compute permission. Its authority, if later granted,
cannot imply L2. L2, L3, and L4 each require new exact authorization and state changes
appropriate to their own operation.

A future manual Gate L2M host qualification is itself a paid cloud-mutation boundary:
it may authorize only the exact user-console firewall/ruleset lifecycle, one manual
qualification-host launch/termination, USD 2.00, and 3,600 seconds. It is distinct
from the later Gate L4 scientific-host launch. Both permissions are false now, and a
completed L2M authorization must be closed and reset rather than reused by L3 or L4.

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
- 2026-08-09: Gate L0 selected the D-019 Linux-host alternative as a design-only
  x86_64 Lambda On-Demand Cloud topology. It source-bound Lambda OpenAPI 1.10.0 and a
  minimal immutable amd64 BusyBox qualification image, implemented strict redacted
  inventory/selection/no-filesystem/termination contracts, and separated L1 through
  L4 authority. No Lambda account API, secret, cloud mutation, payload, SSH, runtime,
  browser, model, or SiRA action occurred.
- 2026-08-09: Gate L1.1 repaired the V1 request-evidence defect with a bounded,
  durable request ledger and a fresh immutable V2/0002 plan. Both V1 attempts and
  run 0001 remain blocked historical evidence. Local fake-transport tests covered
  success, reviewed transport and validation failures, ledger I/O failure,
  outcome-unknown recovery, archive eligibility, run reuse, and secret-canary
  exclusion. The new plan remains unauthorized; no account request or real-secret
  access occurred.
- 2026-08-10: Gate L1.2 preserved and adjudicated stopped V2 run 0002 without a
  retained raw body, removed unnecessary audit-history/account-LRN retrieval, and
  created a fresh unauthorized seven-GET V3/0003 plan. Endpoint-specific schemas,
  compatible-extension reporting, strict sensitive-field redaction, commit ancestry,
  and Gate-L2 evidence cross-binding passed local fake-transport and independent
  privacy/spec review. No account request or real-secret access occurred in L1.2.
- 2026-08-10: Authorized Gate L1 V4 completed the seven-GET V3 inventory and sealed
  its ledger/inventory to the approved external archive. Gate L1.3 then repaired the
  regional image-identity verifier offline, derived six unselected candidates, and
  designed strict firewall/host-key decisions. Because account public-key material
  was intentionally not retained, SSH fingerprint matching remains evidence-
  insufficient and no Gate L2 plan or authorization exists.
- 2026-08-10: Gate L1.4 created a fresh unauthorized one-GET Gate L1A plan for the
  missing account SSH public-key evidence. New in-process format/fingerprint parsing,
  no-follow local `.pub` matching, a fresh durable ledger, and private/public evidence
  schemas passed local fake-only design tests. The request and fresh run remain
  unexecuted; no key is selected and Gate L2 stays blocked.
- 2026-08-10: Gate L1A completed with a unique sealed local/account match for
  `fractal-lambda-codex`. Gate L2.0 then validated the user's private candidate,
  firewall, `/32`, agent, no-filesystem, and Jupyter-host-key choices; resolved raw
  provider values only into nonce-protected ignored parameters; copied the sealed
  bundle one-way to the approved external archive; and entered
  `blocked-human-or-source-decision`. Independent review found no source-backed safe
  identification/termination of an accepted launch after an unknown response and no
  authoritative end-to-end supervisor/evidence path. No executable plan or
  authorization block exists. No account/model request, secret, cloud mutation,
  paid compute, SSH, container, browser, SiRA, or scientific execution occurred.
- 2026-08-10: Gate L2.1 pinned Lambda OpenAPI 1.10.0, designed a private random
  ownership conjunction, and fake-tested transaction, watchdog, cap, privacy, and
  descriptor-held archive primitives. Independent review found no authoritative live
  composition: effecting mutations and cleanup are not phase-exact, supervisor and
  watchdog do not share enforced cross-process budgets/lease, the watchdog has no
  concrete independently supervised cleanup entrypoint, and success/terminal evidence
  remains assertion-capable. The automated path therefore ended at
  `manual-console-launch-required`; no V2 plan or authorization block was created.
  No account/model request, secret access, cloud mutation, paid compute, SSH,
  container, browser, SiRA, or scientific execution occurred.
- 2026-08-10: Gate L2.2 pinned the manual console, Lambda Stack/GPU Base, Cloud IDE,
  firewall, termination, billing, read-only API, and BusyBox metadata contracts. The
  sealed inventory contains four x86-64 Lambda Stack 22.04 regional candidates;
  `img-0032` / `22.4.5-2141` ranks first. Static sources do not prove type-specific
  launch-wizard offeredness, so a future transaction must fail closed before Launch
  if the approved alias is not offered. The existing private selection remains GPU Base, which
  has no documented JupyterLab guarantee, so the terminal state is
  `blocked-human-image-selection`. Offline checkpoint/observer schemas and a
  deterministic Jupyter qualification bundle were added, but no executable plan or
  authorization block exists and no account, mutation, paid-compute, SSH, Jupyter,
  container, browser, model, SiRA, or scientific action occurred.
- 2026-08-11: Gate L2.3 validated the new private image/manual-action decision,
  resolved private image/key/firewall/IP and ownership bindings only into ignored
  sealed evidence, verified a one-way APFS archive copy, and rendered plan
  `PLAN-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V3` / run
  `RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0003`. The 21,641-byte plan has
  SHA-256 `1931fcacda4194063c0116ff9630d82f3b8f4ec07ff9b0310342335db629f654`,
  23 ordered actor steps, 13 user checkpoint templates, zero automated mutations and
  an expiry-before-credential guard. It remains unauthorized; no account/model
  request, secret access, cloud mutation, paid compute, SSH, Jupyter, pull, container,
  browser, SiRA or scientific action occurred.

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
- 2026-08-09: Under D-020, select a short-lived x86_64 Lambda On-Demand Cloud host as
  T07's planned substrate. Keep L1 GET-only inventory, L2 host qualification, L3 B2b
  qualification, and L4 live execution as four separate authorization boundaries;
  attach no Lambda persistent filesystem and terminate by exact provider instance ID.
- 2026-08-09: Under D-021, preserve both V1 Gate L1 attempts, retire run 0001, and
  require the fresh V2/0002 path to seal a complete durable request ledger before its
  inventory can bind Gate L2. The V1 observability gap establishes no provider,
  secret, endpoint, network, or transport fault.
- 2026-08-10: Under D-022, preserve run 0002 and its original schema-drift ledger,
  classify its exact mismatch as unadjudicated because the raw body is absent, and
  replace its future execution path with a fresh seven-GET V3 plan that omits broad
  audit history and requires no account LRN.
- 2026-08-10: Under D-023, preserve successful sealed run 0003, repair image identity
  as one alias per official image ID plus regional availability, and stop Gate L2 at
  `inventory-evidence-insufficient` until matchable account SSH public-key evidence
  and the required firewall/host-key human decisions exist.
- 2026-08-10: Under D-024, minimize the next evidence read to one separately
  authorized `GET /api/v1/ssh-keys`, with a fresh run/ledger and ignored raw evidence;
  do not repeat inventory, expose key material publicly, select a key, or imply Gate
  L2 authority.
- 2026-08-10: Under D-025, accept the user's sealed Gate L2 choices and unique Gate
  L1A key match, bind the current same-version-drifted OpenAPI bytes, but stop at
  `blocked-human-or-source-decision`. The source contract cannot guarantee discovery
  and exact-ID termination after an unknown launch response, and independent review
  found the draft controls do not form one enforceable supervisor/evidence path. No
  executable plan or authorization block is issued.
- 2026-08-10: Under D-026, remove local SSH fingerprints and paths from the current
  public run-0003 adjudication while preserving the original Git object and leaving
  sealed evidence untouched.
- 2026-08-10: Under D-027, terminate the automated Lambda API-launch design at
  `manual-console-launch-required`. Retain the Gate L2.1 marker/journal/watchdog/cap
  code as non-authoritative offline evidence, reject the unmaterialized V2 identities,
  and require any future Gate L2 proposal to use a newly reviewed human-operated
  console launch/observation/cleanup topology with fresh authority.
- 2026-08-10: Under D-028, retain D-027 and stop the manual-console/Jupyter design at
  `blocked-human-image-selection`. Recommend but do not select `img-0032` /
  Lambda Stack 22.04 / `22.4.5-2141`; create no executable plan until the user makes
  a new private image and manual-action decision.
- 2026-08-11: Under D-029, accept the separately supplied private Gate L2M decision,
  publish only aliases/hashes, and render one exact executable-but-unauthorized
  manual-console transaction. Keep user console mutations separate from the GET-only
  observer, restrict incident termination to ruleset-bound private IDs, require exact
  restoration/sealing, and expire the plan rather than using stale public metadata.
- 2026-08-11: Under D-030, preserve V3/run 0003 as a safe pre-mutation failure. Its
  observation projected all current firewall fields but did not retain raw bytes or
  unknown key structure, so it is not lossless restoration authority. Supersede the
  V3 manual packet, require the fresh one-GET baseline-capture plan, and prohibit a
  V4 manual plan until that response is completely retained, validated and sealed.

## Blockers and user actions

T07 has no selected local runtime and no executable local B2a plan. Docker Desktop and
Colima/Lima remain terminal rejected provenance. The Lambda inventory and L1A key
evidence are complete, sealed, and nonreplayable. Gate L2.1 rejected automated API
launch. Gate L2M V3/run 0003 then stopped safely after six GETs and before mutation.
It is burned, its manual packet is superseded, and no manual qualification plan is
active. Plan `PLAN-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1` proposes exactly one
read-only global-firewall GET under run
`RUN-T07-L2M-FIREWALL-BASELINE-CAPTURE-0001`; it remains unauthorized. L3/L4 remain
unauthorized.

## Next permitted work

There is no further local B1.x or automated Gate L2 design loop. The next permissible
live input is a fresh exact user authorization of the final clean commit and the
one-GET firewall-baseline capture plan/hash, ledger, complete private retention and
APFS archive contract. That read-only result may support later offline design; it
cannot authorize a manual console action. Gate L2M qualification, Gate L3 B2b, Gate
L4, both SiRA conditions, and the smoke remain blocked.
