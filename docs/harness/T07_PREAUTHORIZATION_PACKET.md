# T07 preauthorization packet

Status: **live authorization blocked; Gate B2a design remains non-executable**

Prepared: 2026-08-08

## Exact authorization target

- Clean Gate B1 implementation commit: `4be81e4a13fd06b77e36db21c4ad57165f7c115f`.
- Branch: `phase-1/sira-smoke`.
- Gate B1 baseline/previous clean packet commit:
  `38e27ef20637471325ec15be216b4274bed5be49`.
- Profile plan ID: `PLAN-EXP0001-SMOKE`.
- Profile path:
  `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml`.
- Profile SHA-256:
  `ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425`.
- Reactive plan ID: `RUN-EXP0001-SMOKE-REACTIVE`.
- Reactive path:
  `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-reactive.yaml`.
- Reactive SHA-256:
  `7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018`.
- Simulative plan ID: `RUN-EXP0001-SMOKE-SIMULATIVE`.
- Simulative path:
  `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-simulative.yaml`.
- Simulative SHA-256:
  `68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436`.
- Pinned SiRA commit:
  `93fb8d72de71f9a4a13419670adeb34d93cf7acd`.
- Protocol SHA-256:
  `5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c`.
- Scientific configuration SHA-256:
  `f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d`.
- Reactive resolved adapter configuration SHA-256:
  `75ae4bacf985a1f29c14c6b60da7ba05d76215a05023fe87965a5af4c0aa50e3`.
- Simulative resolved adapter configuration SHA-256:
  `9b8ef39965d757f861efc893605a44af6b63dfb486471451ec99dfc1f8d72dcf`.
- Condition-diff path: `docs/harness/sira/T07_GATE_A_CONDITION_DIFF.yaml`.
- Condition-diff SHA-256:
  `9ebb446550b5abae6a05e8b200e41a90f18ea2a17ea7e5fe19c6f044078980a3`.
- Immutable routing SHA-256:
  `8a0e6e2934c98ba3faefab51c6408da2476df428bd43688e41d8aea8280c9619`.
- Gate A runtime adaptation path: `src/giclab/harness/sira_gate_a_runtime.py`.
- Gate A runtime adaptation SHA-256:
  `894783a47c19efc5e141a90a4dd63920b9440e1ef231aad5b2738b1f524bbbcd`.
- Containerfile SHA-256:
  `b46f680c40aea0c65191896fc1674a6b4e00eca73b61f9b48ecbfdde13fb16b1`.
- Immutable-routing source patch SHA-256:
  `4d7e2a25f4313fc754db0fa17aeda51cc5cd75a5653adaf13b01ce87a71cb8ed`.
- Repository-owned staged build-assets SHA-256:
  `d364c2356a4e73bc847f7aabdb272908e006eca0753bd1f74b3984ea1719b79a`.
- Historical, superseded Gate B2 materialization plan ID:
  `PLAN-T07-GATE-B2-MATERIALIZATION`.
- Materialization plan path: `containers/sira-smoke/materialization-plan.json`.
- Materialization plan SHA-256:
  `10fd0350c5e14c4c6d4e32bf40f1f9f696735eae81815a00cd8032e652beaa25`.
- Blocked Gate B2a design plan ID:
  `PLAN-T07-GATE-B2A-DOCKER-STORAGE-QUALIFICATION-V1`.
- Blocked Gate B2a design plan path:
  `containers/sira-smoke/gate-b2a-install-storage-binding-plan.json`.
- Blocked Gate B2a design plan SHA-256:
  `7ccd43e413ec8c4a21a4af043bef2477ede14b5bd40885c979cdeb7e48081eb1`.
- Bound Gate B1.6 implementation commit:
  `321136b2a23158a7618e1489a4d2005d7f7ba1cd`.
- Staged-context evidence SHA-256:
  `747575a0c4c1dc9c0e52a839dc28eea1807e898495ee2c58c7b25ae8ab4ba77b`.

Gate B1.6 evaluates the user-selected Mac mini plus MacBook Target Disk Mode topology
under new dedicated root `/Volumes/Macintosh HD - Data/GIC-Lab`. Sealed immutable
retention is approved beneath its `t07/sealed-artifacts` child; live attempts remain
on the Mac mini. Docker VM/image storage remains a qualification candidate, not an
approved runtime location. The new Gate B2a plan is deliberately
`blocked-design-only`, has `authorized=false`, and contains null system-floor/cap
fields. The historical combined plan remains provenance only.

The profile, protocol, scientific configuration, and both condition plans are
byte-identical to the previous clean packet. Their execution/authorization fields and
all project execution permissions remain false. The previous host-process containment
proposal is superseded; it is not a valid live authorization basis.

## Provider, API, model, availability, and price

| Field | Exact value |
|---|---|
| Provider | `OpenAI` |
| API base URL | `https://api.openai.com/v1/` |
| Immutable revision | `gpt-4o-2024-11-20` |
| Service tier | standard |
| Input price | USD 2.50 per million tokens |
| Cached-input price | USD 1.25 per million tokens |
| Output price | USD 10.00 per million tokens |

Official documentation was reverified read-only on 2026-08-08. The GPT-4o model page
lists `gpt-4o-2024-11-20` under snapshots and lists Chat Completions and Responses as
supported endpoints. The pricing page lists standard GPT-4o rates of USD 2.50 input,
USD 1.25 cached input, and USD 10.00 output per million tokens. Applying the GPT-4o
family row to the dated 2024-11-20 snapshot remains an explicit inference because that
snapshot has no separate row. The floating `gpt-4o` alias currently points to
`gpt-4o-2024-08-06`, so the runtime sends the dated snapshot directly.

- <https://developers.openai.com/api/docs/models/gpt-4o>
- <https://developers.openai.com/api/docs/pricing>

No Models API, model-availability API, completion, Responses, Chat Completions, or any
other provider API request was made. A later unsupported-model or changed-price
response stops; it cannot cause alias/provider fallback or a cap increase.

## Aggregate and per-condition hard limits

Cached input is a subset of input; total tokens equal input plus output. All ceilings
are independently enforced by the Gate A provider boundary when a live runner is
eventually eligible.

| Resource | Aggregate profile | Reactive | Simulative |
|---|---:|---:|---:|
| API cost | USD 4.00 | USD 2.00 | USD 2.00 |
| Input tokens | 400,000 | 200,000 | 200,000 |
| Cached-input tokens | 400,000 | 200,000 | 200,000 |
| Output tokens | 400,000 | 200,000 | 200,000 |
| Total model tokens | 400,000 | 200,000 | 200,000 |
| Wall time | 240 seconds | 120 seconds | 120 seconds |
| Model/API call attempts | 77 | 16 | 61 |
| Browser steps/actions | 2 | 1 | 1 |
| Generic plan `max_tool_calls` | 2 derived | 1 | 1 |
| Retained output bytes | 209,715,200 | 104,857,600 | 104,857,600 |

Every provider choice has a 4,096-output-token ceiling. Multi-sample requests reserve
`n × 4,096` before sending. Failed sends, provider retries, parser retries, and
concurrent reservations share the same durable boundary. Exactly attempt 1 for each
condition is in this future surface; replacements require new authorization accounting
for prior use.

The proposed per-condition container envelope, still ineligible for live use, is 2.000
CPU, 4,294,967,296 bytes memory/swap, 512 PIDs, 1,073,741,824-byte private shm,
134,217,728-byte tmpfs mounts, the condition's 120-second wall limit, and the same
104,857,600-byte retained-output limit. Conditions run sequentially. These values are
not live-enforced until the isolated-egress condition runner is implemented and
materialized.

## Containment status

Gate B1 implements a Docker/OCI attempt abstraction, exact shell-free lifecycle arrays,
security/resource/mount policy, fresh attempt/container identities, image/platform/
lifecycle provenance schemas, adversarial/browser/dummy-secret fixtures, output/wall
monitoring, capture-before-removal, stop→kill escalation, terminal proof, residual
resource proof, and failure cleanup. Runtime read-only input files require an exact
external allowlist; arbitrary host directories are rejected. The container ID is the
authoritative ownership handle.

Control-plane mock/fake tests do not prove namespaces, cgroups, or kernel cleanup. Gate
B2 must run the no-network adversarial fixture in a supported Linux runtime. Host
process groups remain rejected as a fallback.

Chosen build target and base:

```text
platform: linux/arm64
base: mcr.microsoft.com/playwright/python:v1.39.0-jammy@sha256:96955ff5cc37e13f5f1b21f5171afb9fed7e028025aa9d81c690501cd7fa0c6c
arm64 manifest: sha256:f8fca31a4730afa691e73ed99b4a6ebf28b2a9bd65a7038bb6da4bd223bb237b
```

Full decision: `docs/harness/T07_GATE_B1_CONTAINMENT_DECISION.md`.
Exact install/probe packet:
`docs/harness/T07_GATE_B1_INSTALL_AUTHORIZATION_PACKET.md`.

## Immutable routing status

Immutable `gpt-4o-2024-11-20` routing is implemented and fake-tested for `default`,
`encoder`, `memory`, `policy`, `world_model`, `critic`, `actor`, and `fallback`.
The runtime rejects other command models, mixed roles, aliases, provider fallback,
implicit provider transport retry, and `OPENAI_API_KEY` fallback.

The clean upstream checkout is never edited. The container build uses a separately
hashed repository patch that reduces the pinned upstream runner's allowlist/default to
the dated snapshot and removes its `OPENAI_API_KEY` fallback. The Gate A adaptation
then installs the complete role-aware budgeted routing surface. The patch was checked
read-only against the exact pinned upstream source.

The external-volume parser, exact-role paths, bounded guard/state primitives, and
sealed-copy fixtures are implemented and mock-tested. A replacement executable Gate
B2a plan is still required because current official Docker behavior, a numeric system
floor, supported pre-first-start binding/update control, persisted location/default
paths, held-descriptor mount identity, machine stop/reconnect/placement semantics,
typed rollback, and the authorized writer-probe/seal driver are unresolved. Additional
work remains before a live request: empirical
Gate B2a/B2b must pass; a non-host
isolated-egress network policy for the API and browser must be implemented/reviewed;
final runtime/image/package/browser provenance must be observed; and exact
containerized condition commands/canonical child hashes must be materialized under
new authorization. Scientific fields need not and must not be changed.

## Installation actions awaiting authorization

Nothing has been installed, pulled, built, or launched. The blocked Gate B2a design
contains 66 automatable arrays and 9 user-only actions (75 total), zero retries, a
7,200-second aggregate wall cap, 16,777,216-byte output cap, and 577,786,748-byte
metadata-plus-DMG download cap. It stops before every image pull, build,
dependency/browser install, or container action.

The external retained-free floor is exactly 200,048,192,717 bytes and pre-action
floor is 212,933,094,605 bytes. The Mac mini floor remains an exact equation with six
unknown terms; the numeric floor and internal incremental cap are intentionally null.
That is an authorization blocker, not an unbounded allowance. The current B2a packet
is `docs/harness/T07_GATE_B2A_INSTALL_AUTHORIZATION_PACKET.md`.

## Secret contract

The only live secret variable name is:

```text
SIRA_API_KEY
```

The user supplies its file outside the repository. It is mounted read-only only at
`/run/secrets/sira_api_key`; no value appears in image layers, argv, labels, paths,
logs, retained configuration environment, or authorization records. The entrypoint
reads it without echo and exports it only to the SiRA child. `OPENAI_API_KEY` is
removed/rejected. Gate B2 uses only the public dummy canary
`T07_GATE_B2_DUMMY_CANARY_PUBLIC_NOT_A_CREDENTIAL` and scans all retained surfaces.
No real secret name was resolved to a value, and no real value was read or printed.

## Cleanup contract

For every future container attempt:

1. allocate a fresh harness-owned root and immutable UUID before create;
2. capture exact container ID and validate name, labels, image ID, platform, policy,
   mounts, resource limits, and absence of secret configuration environment fields;
3. capture the process table before termination;
4. enforce wall/output bounds, issue bounded container stop, and issue container KILL
   when stop fails or terminal state is absent;
5. capture logs and final inspect and fsync pre-removal evidence;
6. remove only the terminal label-validated container ID;
7. prove no matching running/stopped container and no owned network/volume remain;
8. seal cleanup even for failed probes; any failed proof is infrastructure-invalid;
9. retain raw evidence within caps and never reuse/overwrite an attempt root; and
10. perform no host PID fallback, cloud mutation, provider cleanup, or evidence
    deletion.

The local Docker image/build provenance is retained after Gate B2. The public dummy
file is deleted only after the canary scan. Docker is not uninstalled automatically.

## Reactive versus simulative resolution

The complete machine-readable comparison remains
`docs/harness/sira/T07_GATE_A_CONDITION_DIFF.yaml`. The container layer adds only
condition-owned container name/UUID, condition label, attempt root/output mount, and
mode/job command values. Image ID, platform, security options, resource envelope,
source/patch/model/provider identities, secret-file target, instrumentation, task,
seed, timeout, browser limits, and evidence policy must match.

The only scientific/runtime treatment-owned differences remain:

- reactive uses `web_reactive`/policy, temperature 0.0, top-p 0.5, and at most 16
  model attempts;
- simulative uses `web_simulative`/world-model search, five candidate actions, depth
  one, 20 policy samples, 20 critic samples, temperature/top-p 1.0/0.95, and at most
  61 model attempts; its one-cluster branch skips world-model/critic evaluation; and
- condition/job identity, mode, and condition-owned attempt/output paths differ.

All other resolved fields are equal. Final container image ID and command hashes are
observations deferred until authorized build/materialization; they are explicitly
unknown, not guessed.

## Readiness ledger

| Obligation | Status |
|---|---|
| Named clean baseline and locked scientific files | met |
| Immutable all-role routing and alias/fallback rejection | met and fake-tested |
| Provider budget/retry/concurrency enforcement | met and fake-tested |
| Browser action/output limits | met and fake-tested; empirical browser probe pending |
| Fresh attempt/container identity | met and fake-tested |
| Private PID/IPC, cgroup lifecycle policy | implemented; empirical Gate B2 proof pending |
| Unsafe flag/mount/restart/image rejection | met and fake-tested |
| Evidence-before-removal and stop→kill | met and fake-tested |
| Zero container/network/volume leftovers | met in fake state machine; empirical proof pending |
| Source-clean build context and hashed patch | met; authorized staging/build pending |
| Image/runtime/browser provenance | assembler binds raw/pre-removal/sealed evidence to exact attempt/image; observed values pending Gate B2 |
| Gate B2a wall/output/download/call caps | hashed 75-step blocked design; system disk cap unresolved; unauthorized and not run |
| Secret-file channel and canary scanning | met and fake-tested; real secret untouched |
| Historical no-network Gate B2 commands | superseded and non-authorizing; B2b remains requirements-only and undesigned |
| Exact live isolated-egress policy/commands | blocked; not Gate B1 scope |
| Project/profile/condition authorization | false |
| Live smoke/pilot | not run and unauthorized |

## Validation and review

Pre-edit focused Gate A/B1 tests passed 84 tests and repository validation passed. The
first independent B1.6 review failed and identified authority, archive, guard,
reconnect, rollback, binding, and documentation defects. The implementation was
repaired with regressions or the unsatisfied obligation was converted into an explicit
blocking requirement. Final command and rereview evidence is recorded in
`docs/harness/T07_GATE_B1_6_IMPLEMENTATION_LEDGER.md`; no Quarto success is claimed
unless the local renderer is actually available.

No model/API request, model-availability API request, runtime/dependency/browser
installation, image pull/build, container/browser launch, SiRA condition, evaluator,
pilot, cloud job, or paid compute occurred.

## Blockers and authorization decision

Authorization-stopping blockers:

1. current official Docker artifact/behavior metadata is not freshly verified;
2. six Mac mini floor terms, its numeric floor, and internal incremental cap are
   unresolved;
3. pre-first-start external binding or an exact transient internal VM allocation is
   unproven;
4. version-specific update suppression, persisted location key/source, default
   internal path, clean-stop method, placement commands, and first-party endpoints are
   not sourced;
5. diskutil identity is not bound to a held mount descriptor and freshly re-observed
   when a guard is consumed;
6. machine stop/open-file, placement, default-internal inactivity, reconnect semantics,
   typed rollback, and the authorized writer-probe/seal driver remain unwired;
7. no supported runtime is installed or running;
8. kernel containment and browser shutdown are not empirically proven; and
9. final runtime/image/package/Chromium identity, isolated egress, and condition
   materialization remain unknown/unimplemented.

Public trace release remains blocked by licensing/privacy review but does not block
private access-controlled future smoke retention. Pilot, benchmarks, training,
scientific interpretation, and cloud mutation remain prohibited.

There is no ready-to-copy installation or live-smoke authorization block. The previous
combined Gate B2 block is withdrawn. The B2a packet contains only a ready-to-copy
non-authorization/blocker-resolution block. B2b has requirements only.
