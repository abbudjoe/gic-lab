# T07 Gate L0 Lambda host decision

Status: **lambda-host-selected-design-only; Gate L1/L2/L4 unauthorized; Gate L3
requirements only**

Prepared: 2026-08-09

Baseline: clean parent `phase-1/sira-smoke` commit
`0ce094778f979e303794bbfe01acc93829a7ff1d`; design branch
`phase-1/sira-smoke-lambda`.

## Decision

T07 selects a separately approved, short-lived **Lambda On-Demand Cloud x86_64 Linux
host** as its planned execution substrate. This is a design and authorization-boundary
decision only. No account inventory, instance launch, provider mutation, SSH, Docker,
container, browser, model request, SiRA condition, or scientific execution occurred.

The planned topology is:

```yaml
provider: Lambda On-Demand Cloud
architecture: x86_64
persistent_filesystem: none
lifecycle: launch -> qualify/run -> copy evidence -> provider terminate -> confirm nonbillable
ssh: exactly one pre-existing user-approved key
inbound_exposure: effective existing rules must permit TCP/22 only
provider_image: exact regional gpu-base-22-04 image ID selected after inventory
docker: provider-preinstalled and empirically qualified before workload use
scientific_model: external OpenAI gpt-4o-2024-11-20
gpu_required_by_t07: false
```

This closes the topology-choice trigger in D-019. Docker Desktop and Colima/Lima are
terminal rejected alternatives and historical negative infrastructure evidence, not
active blockers to the Lambda design. Their records remain unchanged. A directly
attached SSD was not selected because it would address only part of the local storage
conflict; it would not independently close the audited runtime-provenance and
first-start-network gaps. The containment/scientific governance contract was not
relaxed.

## Scientific contract

The substrate amendment does not modify any scientific field. The following locked
files remain byte-stable:

| Input | Exact path | SHA-256 |
|---|---|---|
| Protocol | `experiments/EXP-0001-sira-simulative-vs-reactive/protocol.yaml` | `5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c` |
| Configuration | `experiments/EXP-0001-sira-simulative-vs-reactive/config.yaml` | `f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d` |
| Smoke profile | `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml` | `ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425` |
| Reactive child | `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-reactive.yaml` | `7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018` |
| Simulative child | `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-simulative.yaml` | `68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436` |

The immutable contract remains `EXP-0001`, `PLAN-EXP0001-SMOKE`, reactive first,
simulative second, pair `PAIR-EXP0001-SMOKE-0000`, model
`gpt-4o-2024-11-20`, directional reproduction, `interpretation_allowed: false`,
pilot unauthorized, and training false.

## Authoritative inputs at exact repository paths

| Role | Exact path |
|---|---|
| Repository doctrine | `AGENTS.md` |
| Significant-work doctrine | `docs/PLANS.md` |
| Project state | `docs/PROJECT_STATE.yaml` |
| Storage policy | `docs/STORAGE_POLICY.md` |
| Reproducibility policy | `docs/REPRODUCIBILITY.md` |
| Compute policy | `docs/COMPUTE_POLICY.md` |
| Decision log | `docs/DECISIONS.md` |
| Active Phase 1 plan | `docs/exec-plans/active/PHASE_1_ARTIFACT_EXECUTION.md` |
| Phase 1 readiness | `docs/readiness/PHASE_1_SMOKE_READINESS.md` |
| Gate A ledger | `docs/harness/T07_GATE_A_IMPLEMENTATION_LEDGER.md` |
| Gate A condition diff/packet | `docs/harness/sira/T07_GATE_A_CONDITION_DIFF.yaml`; `docs/harness/T07_PREAUTHORIZATION_PACKET.md` |
| Gate B1 decision/ledger/packet | `docs/harness/T07_GATE_B1_CONTAINMENT_DECISION.md`; `docs/harness/T07_GATE_B1_IMPLEMENTATION_LEDGER.md`; `docs/harness/T07_GATE_B1_INSTALL_AUTHORIZATION_PACKET.md` |
| Gate B1.5 decision | `docs/harness/T07_GATE_B1_5_STORAGE_TOPOLOGY_DECISION.md` |
| Gate B1.6 decision/ledger | `docs/harness/T07_GATE_B1_6_DOCKER_STORAGE_QUALIFICATION.md`; `docs/harness/T07_GATE_B1_6_IMPLEMENTATION_LEDGER.md` |
| Gate B1.7 decision/ledger | `docs/harness/T07_GATE_B1_7_RUNTIME_DECISION.md`; `docs/harness/T07_GATE_B1_7_IMPLEMENTATION_LEDGER.md` |
| Rejected Colima B2a packet | `docs/harness/T07_GATE_B2A_COLIMA_AUTHORIZATION_PACKET.md` |
| Historical B2b requirements | `docs/harness/T07_GATE_B2B_REQUIREMENTS.md` |
| SiRA audit/command | `docs/audits/sira/UPSTREAM_AUDIT.md`; `docs/audits/sira/COMMAND_CONTRACT.yaml` |
| SiRA adapter/routing patch | `src/giclab/harness/adapters/sira.py`; `containers/sira-smoke/sira-immutable-model-routing.patch` |
| Gate A runtime/tests | `src/giclab/harness/sira_gate_a.py`; `src/giclab/harness/sira_gate_a_runtime.py`; `tests/test_sira_gate_a.py`; `tests/test_sira_adapter.py` |
| Existing generic cloud schema | `schemas/cloud-run.schema.json` |
| Existing Lambda operations guidance | `docs/audits/sr2am/LAMBDA_COMPATIBILITY.yaml`; `docs/audits/sr2am/SERVICE_TOPOLOGY.md`; `docs/audits/sr2am/UPSTREAM_AUDIT.md` |
| Evidence retention | `experiments/EXP-0001-sira-simulative-vs-reactive/EVIDENCE_RETENTION_APPENDIX.yaml` |

## Source-grounded provider decision

Gate L0 inspected only official public documentation and small public source/registry
metadata. The compact source record is
`containers/sira-smoke/lambda/public-source-observations.json`, 5,351 bytes,
SHA-256 `462cf84e08020a89707c55deb6e2a048c53b51241df4ffebf86dec95ae246e82`.
No Lambda account endpoint or installation/image layer payload was fetched.

The official Lambda OpenAPI document is version 1.10.0, 239,644 bytes, SHA-256
`365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded`,
with production base `https://cloud.lambda.ai`. It exposes typed `x86_64`/`arm64`
architecture fields on instance types and images, so selection needs no GPU-name
heuristic. Its account inventory endpoints are GET; launch and termination are POST.
The service documents a general one-request-per-second limit and a stricter launch
limit.

Current public pricing observed 2026-08-09 lists one-GPU A10 at USD 1.29/hour,
one-GPU A6000 at USD 1.09/hour, and one-GPU Quadro RTX 6000 at USD 0.69/hour, plus
applicable sales tax. All three public resource rows meet the numeric minimums, but
none is selected: exact API names, current account capacity, region, price, and the
available regional image/ruleset identities require L1. Lambda documents one-minute
billing, billing through provider termination, and continuing billing after host
shutdown; provider-API termination and terminal/nonbillable confirmation are therefore
inviolable.

The candidate provider image family is `gpu-base-22-04`: official documentation says
it is x86-64, includes Docker, and provides Python 3.10. L1 must bind a current exact
regional image ID; a family name is not sufficient for launch authority.

Primary public sources:

- <https://docs.lambda.ai/api/cloud/spec.json>
- <https://docs.lambda.ai/public-cloud/cloud-api/>
- <https://docs.lambda.ai/public-cloud/on-demand/>
- <https://docs.lambda.ai/public-cloud/billing/>
- <https://docs.lambda.ai/public-cloud/on-demand/creating-managing-instances/>
- <https://docs.lambda.ai/public-cloud/on-demand/managing-system-environment/>
- <https://lambda.ai/instances>

## Deterministic instance policy

L1 must select the minimum tuple ordered by:

```text
(price_cents_per_hour, instance_type_name, region_name, exact_image_id)
```

after filtering for exact x86_64 architecture, current capacity, at least 8 vCPU,
16 GiB RAM, 100 GiB root, price at most 150 cents/hour, an exact x86_64
`gpu-base-22-04` image in the same region, a strictly TCP/22-only effective global
ruleset, and at least one strictly TCP/22-only regional ruleset. An existing instance
with exact reserved name `giclab-t07-l2-qualification` or exact T07 ownership tags
blocks selection. If no tuple qualifies, L1 stops; it cannot escalate to a more
expensive type, GH200, H100, multi-GPU, or another provider.

SSH key and regional firewall approval are separate human bindings after inventory.
No key or ruleset is silently chosen from multiple account resources. Public-key
material is validated in memory and discarded; only key ID/name survive redaction.
Raw audit events, actor/email/IP/user-agent fields, Jupyter credentials, instance IPs,
and raw API responses are never retained. Account/workspace LRNs are retained only as
domain-separated SHA-256 bindings; `LAMBDA_API_KEY` is never printed, hashed,
persisted, or returned.

## Gate boundaries

### Gate L1 — separately authorizable inventory

The exact GET-only plan is
`containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan.json`, plan ID
`PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V1`, SHA-256
`c7151737bd029e3ebad45d59dc2d9fcd58f401dc7d8658021f1d384129555c69`.
It is committed with `authorized: false`; its exact caps and ready-to-copy scope are in
`docs/harness/T07_GATE_L1_READONLY_INVENTORY_AUTHORIZATION_PACKET.md`.
The future supervisor succeeds only after the redacted artifact is copied through a
fresh held-descriptor APFS/UTDM guard to the approved MacBook archive, its destination
hash is verified, and the Mac mini retains the source and local verification record.
Independent hard watchdog processes enforce the 180-second aggregate and 60-second
archive deadlines even if a filesystem operation stalls.

### Gate L2 — host qualification, not executable

Gate L2 is an unauthorized requirements packet, not an account-bound plan. It cannot
receive a plan ID, launch body, account/workspace/type/region/image/key/ruleset
binding, plan hash, or authorization until L1 is separately authorized, run, redacted,
validated, selected, externally archived, and reviewed. L2 also remains blocked on an
authenticated first-contact SSH server-host-key bootstrap; the reviewed provider API
does not attest an ephemeral host key, and `ssh-keyscan` alone is insufficient. L2 may
then launch exactly one instance,
qualify provider Docker with the pinned no-network fixture, copy evidence, and
terminate through the provider API. It may not pull Playwright, install packages,
open a browser, access a real secret, call a model, or run SiRA.

### Gate L3 — requirements only

L3 may be materialized only after L2 succeeds. It preserves the exact x86_64
Playwright 1.39.0 platform manifest, pinned SiRA source/routing patch/frozen lock,
adversarial/dummy-secret/local-page probes, full image provenance, and zero
provider/model calls. It is not executable here.

### Gate L4 — live pair requires fresh authorization

Only a fresh exact authorization after L2 and L3 may launch a qualified host, build or
pull the approved SiRA image, inject `SIRA_API_KEY` through the approved secret
channel, run reactive then simulative, preserve and seal evidence, and terminate the
provider instance. That authorization must bind the clean repository commit, both
child-plan hashes, source/image/environment hashes, provider and OpenAI cost caps,
immutable model, wall/call/token/browser/output caps, and cleanup/termination plan.

## Current terminal state and blockers

```text
decision_state: lambda-host-selected-design-only
Gate L1 inventory: unauthorized
Gate L2 host qualification: unauthorized and non-account-bound
Gate L3: requirements only
Gate L4 live smoke: unauthorized
paid_compute_allowed: false
prototype_execution_allowed: false
benchmark_execution_allowed: false
training_allowed: false
cloud_mutation_allowed: false
```

The design has no unresolved public-source blocker to asking for L1 authorization.
The account-specific facts are deliberately unresolved and are L1 outputs, not
invented blockers: account/workspace binding; current types, prices, capacity and
regions; exact provider image ID; existing key choices; effective global/regional
firewall rules; and existing instances. Gate L2 remains blocked until those facts are
sealed/archived, the user approves one exact key/ruleset and inventory-selected tuple,
and an authenticated server-host-key fingerprint/bootstrap is source-verified or
separately authorized. L2 also needs a fresh account-bound plan and user authorization;
none exists in Gate L0.
