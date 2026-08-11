# T07 Gate L2.2 manual-console and Jupyter-only design

Status: **blocked-human-image-selection; offline design only; unauthorized**

Date: 2026-08-10

## Decision

Gate L2.2 ends at exactly:

```text
blocked-human-image-selection
```

The sealed inventory contains four x86-64 `lambda-stack-22-04` regional candidates in
`us-east-1`, but the current private human decision still binds `img-0111`, family
`gpu-base-22-04`. Current first-party documentation lists Docker for GPU Base but does
not list JupyterLab. It lists Docker, JupyterLab, x86-64, and Python 3.10 for Lambda
Stack 22.04. The existing choice therefore cannot support the Jupyter-only contract
without a new human decision. This gate does not silently replace it.

No executable manual plan, plan ID, run ID, authorization block, account request,
console mutation, paid compute, SSH, Jupyter session, container, browser, model call,
SiRA action, or scientific execution exists.

## Verified starting state

The work began on clean branch `phase-1/sira-smoke-lambda` at required commit
`e21ac54df3f51bc7ff76c3078521bf6ffae1bc34`.

Preserved evidence was rehashed before editing:

| Evidence | Bytes | SHA-256 |
|---|---:|---|
| Gate L1 inventory | 59,653 | `022835438165e7e6e70dc992d6904f4e8b9448dc933d1d4c3e39ebdcc8914933` |
| Gate L1 request ledger | 32,287 | `1f94068bdb1d1d2af0075d50c1a0c06eb1c077d4128f90bdc16fd571fa6af707` |
| Gate L1 external seal | — | `3347b8d03d0f937111de92ef79286c7fbcb02027f652f35ba42ac337cf8f7bd5` |
| Gate L1 external copy record | — | `76d8511282962cb6fdc4f72a63eaf41e7e63239acb9fa38e030f51057cb8a0e7` |
| L1.3 private alias map | 9,476 | `9f37b9412110cc7433d5339cf4d8b1eadc92743eaa32db6bf8e4c59024a79d5f` |
| L1.3 alias-map seal | 340 | `ed3fb1ef3323f2b37150204ef060250e4f9510bbeb976d18d2fd1b8d9894c0b5` |
| Gate L1A request ledger | 9,579 | `41dd54aa76e8cad871f8d4064b44fb8b013a83dea96eb4494a9575df21e30e13` |
| Gate L1A private evidence | 5,512 | `835b5692d67fa1286a84f2b6fc0a41318693a7e28171852d01f0d6db0a7293bb` |
| Gate L1A sanitized report | 1,308 | `28e66e39bb569327cc3d53abcc4efc07aad59e5aeb51ff0e0959f00c22c2e855` |
| Gate L1A external seal | — | `6da847cadd75edaacb0d6c8ba69fcac375919dda85a3b4db2dad44cc6a1662f0` |
| L2.0 private decision | 1,047 | `0b109b0150eec8739e30e86e5f1318b60c818cc3974354c67dc35a4e2dffd4ea` |
| L2.0 V2 private parameters | 4,528 | `89028846f059c305d10a741c14681c537556666ac04f290dff9be8985bfe913b` |
| L2.0 V2 parameter seal | 413 | `4a6c6c3cfbf3a142b645fa361018bf6f6e6a8da99ec5ce01160d789b61b28dea` |
| L2.0 V2 bundle seal | 754 | `7382a8b4b4262060b2cc01f686d18444c56af918e8bb552e9bee6e470b45e555` |
| L2.0 V2 external seal | 1,505 | `bb3aeca6cbcf750680a19f0f2da01e56bc099372ea7b873890fda064b430791c` |
| L2.0 V2 copy record | 1,877 | `20240e23b7ad291ad728191a4b3d6133e693515999cfaf72d9eaa30608ad91d5` |

The external archive was mounted, unlocked, writable APFS at
`/Volumes/Macintosh HD - Data`, volume UUID
`8478609D-FA37-4ED5-875D-47AE912B9151`, physical-store UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`, over Thunderbolt, with no internal
fallback. The latest sealed inventory contained zero running instances. The local
Docker/Colima route remains terminally rejected by Gate B1.7.

The locked scientific hashes remain:

| Input | Exact repository path | SHA-256 |
|---|---|---|
| Protocol | `experiments/EXP-0001-sira-simulative-vs-reactive/protocol.yaml` | `5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c` |
| Config | `experiments/EXP-0001-sira-simulative-vs-reactive/config.yaml` | `f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d` |
| Smoke profile | `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/smoke.yaml` | `ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425` |
| Reactive | `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-reactive.yaml` | `7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018` |
| Simulative | `experiments/EXP-0001-sira-simulative-vs-reactive/run-plans/conditions/smoke-simulative.yaml` | `68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436` |

## Governing repository inputs

The exact paths read were `AGENTS.md`, `docs/PLANS.md`, `docs/PROJECT_STATE.yaml`,
`docs/STORAGE_POLICY.md`, `docs/REPRODUCIBILITY.md`, `docs/COMPUTE_POLICY.md`,
`docs/exec-plans/active/PHASE_1_ARTIFACT_EXECUTION.md`,
`docs/readiness/PHASE_1_SMOKE_READINESS.md`, the Gate L0, L1, L1A, L1.3, L1.4,
L2.0, and L2.1 records under `docs/harness/`,
`docs/harness/T07_GATE_L3_B2B_REQUIREMENTS.md`, the five locked experiment paths
above, and ignored/sealed evidence under `artifacts/t07/lambda/` and the approved
external archive. No private scalar was copied to Git or output.

## Current first-party source lock

The machine-readable record is
`containers/sira-smoke/lambda/manual-console/public-source-observations-l2-2.json`,
6,815 bytes, SHA-256
`56a1ba759d4fc5ac6eba2ee85c5bff2a08d0d71f538793f3de5732bb80d0b1a5`.
It records a bounded revalidation at `2026-08-11T06:15:19.646016Z`.

| Source | Bytes | SHA-256 |
|---|---:|---|
| Lambda OpenAPI 3.1.0 / API 1.10.0, `https://docs-api.lambda.ai/api/cloud/spec.json` | 240,288 | `320f4877924984f060b179e86595ed58918a1d0696b60b99cae548ec164934f4` |
| On-Demand overview | 94,148 | `a8c52603d2a0dc6b91aea2d25ea08396fb87e3907822213d02240a148b1401a8` |
| Cloud console | 89,564 | `4f176d3bc6fab4705fd196fb33273b1c54c5b6b7bd32c5416fe8913e3e790052` |
| Connecting / Cloud IDE | 94,987 | `c7c9abe16fb8da1bd1cc0e77f4ab360ca63d0650271b1d12372ed321d438a929` |
| System environment / Docker | 94,340 | `33067d94ff1fd5eb3836e54d121feb1361f8acc3657060616738dbfcceeb7abc` |
| Firewalls | 88,233 | `37fb67fc30565608ca0b2882e023e0e1574c3ebfbc9dadb23e51b89025114623` |
| Billing | 77,250 | `4dc7d91bc45d65d325f3e7a323d7aeec31135ff78aca2c51a839a1a350e61b21` |
| Instance management | 84,693 | `6ddecdd2fa7279a8def8f61cbd0c8f89e069feafa627c491b9e0908c6868fbf4` |

The exact `GET /api/v1/instance-types` OpenAPI operation extract is 1,417 canonical
bytes, operation ID `listInstanceTypes`, SHA-256
`4f9d75684598bdbfb18775970db3848dd37c07e5e7a2e195ebb83de381bd7d08`.

The public BusyBox manifest and its small config metadata blob were re-read by digest
without fetching a layer. The 610-byte manifest has digest/SHA-256
`7a3ebe5bfd1a4a19797d20b0c0bb39d44393e9a03fd852c0865b0f540d868df0`,
config descriptor `db287cb6…30e4`, and one 2,211,507-byte compressed layer
`436a1b1f…2ab`. The separately pinned 459-byte config blob has SHA-256
`db287cb6be81219cd18c1d82b70908f5d33eb028568b456f78eedff2ff2930e4`
and explicitly records `os=linux`, `architecture=amd64`; platform is no longer
inferred from the manifest. The record accounts for one anonymous public-registry
bearer-token request and two metadata reads totaling 1,069 bytes, with zero account,
authenticated-account, installation-payload, or image-layer downloads.

The docs establish the console launch selections, Jupyter launch from the Instances
page, global/per-instance firewall lifecycle, launch-time ruleset attachment, the
manual termination confirmation phrase `erase data on instance`, and billing from
successful health check until provider termination. They do not establish that Cloud
IDE bypasses or is independent of inbound firewall rules. A future authorized run may
only test Cloud IDE under the already-strict firewall and must terminate on failure;
opening another port is prohibited.

## Image adjudication

The sealed inventory projection retained no raw image ID in this record:

| Rank | Opaque alias | Family | Version | Disposition |
|---:|---|---|---|---|
| 1 | `img-0032` | `lambda-stack-22-04` | `22.4.5-2141` | recommended, awaiting human approval |
| 2 | `img-0106` | `lambda-stack-22-04` | `22.4.5-1722` | alternate |
| 3 | `img-0037` | `lambda-stack-22-04` | `22.4.5-1459` | alternate |
| 4 | `img-0012` | `lambda-stack-22-04` | `22.4.5-1026` | alternate |
| — | `img-0111` | `gpu-base-22-04` | `22.4.5-2141` | current choice; no documented JupyterLab guarantee |

Each listed Lambda Stack candidate is x86-64 and available in `us-east-1`; sealed
capacity records separately place `gpu_1x_a10` in that region at the observed 129
cents/hour. Neither the pinned API schema nor the recorded first-party documentation
provides a static type-to-image compatibility matrix. These are therefore ranked
family/architecture/region candidates, not proof that the launch wizard will offer
them for `gpu_1x_a10`. A future user must first select the exact type and region in the
wizard, confirm the approved alias/version is actually offered, and attest that fact
in the single-use launch checkpoint. If it is not offered, the gate stops before
Launch with no substitution and no inference.
The official image schema and sealed inventory expose version but no update timestamp;
update time is recorded unavailable rather than inferred, so ties after numeric version
use the opaque alias.

## Private decision and ownership contract

The future private file is
`~/.config/gic-lab/t07/l2-manual-console-decisions.json`. This gate did not create or
edit it. Its schema is
`schemas/t07-lambda-l2m-human-decision.schema.json`, 3,183 bytes, SHA-256
`7054b83d9aa56683b24ba3c1057ca6f9aeb9ae1ee38fc3d2f37179514d4f1d79`.
The deliberately invalid template is
`containers/sira-smoke/lambda/manual-console/T07_L2M_HUMAN_DECISION_TEMPLATE.json`,
1,479 bytes, SHA-256
`a728ed2365c07ce2de97ddff97555770123379485d071df8c123b42181e5e795`.

The private decision must explicitly approve the image change and every console
mutation/cleanup step, bind the unique matched SSH key for launch only, require
Jupyter-only/no-SSH access, attest workspace-wide global-firewall safety, an exclusive
Lambda-account instance-mutation window, and continuous human presence, acknowledge
outage billing exposure, and carry a public IPv4 `/32`,
32 random bytes, USD 2.00, 3,600 seconds, and 300 seconds per user checkpoint.

A future materializer derives a private 40-hex ruleset marker from at least 160 random
bits. The observer first requires zero name matches, then binds exactly one
`us-east-1` ruleset whose only rule is private-source TCP/22. The ruleset ID—not an
instance name or IP—is the primary ownership join. No provider-enforced name
uniqueness is claimed. The explicit exclusive instance-mutation attestation makes the
zero-instance preflight an account-wide ownership boundary for the short launch
window: zero postlaunch rows stops and cleans up, while any additional or unattached
row is a human identity ambiguity requiring termination review before any workload.
Without that attestation no plan may be materialized.

## Observer and checkpoints

`src/giclab/harness/lambda_l2m_observer.py` is inert on import and implements one
explicitly constructed, in-process, exact-host HTTPS transport for GET observations
of images, instances, one private instance detail, rulesets, one private ruleset
detail, and the global firewall. The engine durably records intent and send-start,
enforces status/content/size/pagination/request-spacing/phase/aggregate limits, and
retains no credential or raw response value in its public-safe journal. It has no
POST/PATCH/DELETE, shell HTTP, SSH, Jupyter, browser, or cloud-mutation boundary and
does not read an environment or secret file; a future separately authorized
supervisor must inject the approved credential channel.

Raw provider response bytes exist only in process memory long enough to be bounded,
hashed, and validated against the endpoint schema. Durable private observation files
contain an exact operation-specific allowlist projection plus the raw byte count and
SHA-256 binding. They omit Jupyter tokens and URLs, action links, unknown additive
scalar values, and all other fields not needed for resource identity or cleanup. The
final receipt cross-check independently verifies both the raw-response identity and
the projection-file identity; incomplete journal prefixes may be sealed for incident
provenance only and force both receipt integrity and evidence eligibility false.

The 12 checkpoint types are schema-bound, single-use, fresh, current-user-owned,
mode `0600`, regular, single-link, and opened no-follow through
`src/giclab/harness/lambda_l2m_checkpoints.py`. A launch-click checkpoint proves only
one user attestation; it never proves a provider launch without the exact ruleset/API
conjunction. Consumption is durably appended and fsynced to a private mode-`0600`,
262,144-byte ledger under an exclusive process lock. A reader restarted before any
live launch reloads that ledger and rejects reused types, nonces, or bytes; a live
postlaunch observer process is never resumed after process loss. An append/fsync
uncertainty burns the checkpoint, marks scientific evidence incomplete, and may
advance only an already validated cleanup transition; exact retained prefix bytes are
sealed as incomplete evidence when final held-file integrity can be proven. Challenge
windows wider than 300 seconds fail. Each action type has required details, which the reader retains in
immutable verified state. Only the observer engine can issue a transition proof: it
derives that proof from checkpoint details plus the matching provider observation or
validated qualification archive. Caller-fabricated `verified=true` objects fail.
Every post-intent checkpoint stage carries typed recovery state. An asynchronous
interrupt during preparation preserves an unconsumed cleanup checkpoint; once the
private consumption record is committed, the verified checkpoint crosses back via a
callback/outcome-unknown capability so advance/apply/receipt interruptions cannot
burn the user's only cleanup authority. Such recovery always makes scientific
evidence incomplete and appends only a sanitized outcome.
Explicit cleanup branches are reachable after every postlaunch phase. An outage
incident freezes the same phase and strict firewall until cleanup is explicitly
resumed. After stop, the engine journal, consumption ledger, terminal summary, and
optional qualification archive can be locally sealed and copied only through the
approved identity/floor-checked UTDM archive boundary. Schema identities are:

| Schema | Bytes | SHA-256 |
|---|---:|---|
| Checkpoint | 12,213 | `8365a8bdac2dc67aeb7cdc0078651429fdbb692541a04685acbbf832d9d05f47` |
| Observer journal | 6,503 | `5486ff6403c72a9402029560135833c920d719e03e6a74ba6ab095e5006ee6d3` |
| Host evidence | 10,562 | `8311ff4dcc82df5bf8272f549119c13fa37baf9ef46e41cea5c3629b11253ef3` |

Each exact schema path derives one canonical repository root at construction time.
The checkpoint reader, observer journal, private human-decision capability, endpoint
schemas, and host-evidence validator must all bind that same root; module installation
location is not an authority source. Every schema still requires its exact
repository-relative path and SHA-256.

The append-only observer journal is exclusive-created and fsynced per schema-valid,
public-safe event. It omits raw IDs, IPs, URLs, headers, credentials, tokens, response
values, and private paths. Before any send, the engine reserves the phase/call/response
and terminal-journal capacity, commits intent and send-start events, and derives the
remaining end-to-end deadline. A prelaunch response or transport failure permanently
stops that run identity; after launch, the same uninterrupted observer retains only
the bounded cleanup path and never resumes workload progression. `preflight_passed`
is written only after the exact five ordered responses prove the private selected raw
image identity and metadata, selected instance type/price/capacity, zero instances, marker
freshness, and the sealed global-firewall semantics. Observation and qualification
capabilities are per-engine and run/authorization bound; they are single-use for the
matching transition. The exact validated qualification file identity and hash are
retained by the engine and reverified during sealing.

Both success and typed failure ZIP validation require the consumed
`qualification_command_completed` checkpoint. The 300-second download-plus-validation
window is anchored to that checkpoint, intersected with normal provider headroom, and
enforced from the bounded archive read through ZIP/schema validation, capability
construction, the fsynced `evidence_validated` receipt, and final monotonic checks by
an active process alarm. Deadline expiry or any `BaseException` writes a sanitized
failure event when possible, marks evidence incomplete, preserves the interrupt, and
enters cleanup-only state. A terminal line declaring `evidence_archive=unavailable`
skips archive validation entirely and requires immediate provider termination; it can
never be converted into a download attestation.

The one-way archive copier reads from and writes to held directory descriptors. It
checks each current source member against the already sealed record, manifest, and
local-seal hashes before copying, revalidates the held UTDM hierarchy before and after
the copy (including failure exit), verifies every destination member and both control
records while still in staging, fsyncs, and only then atomically finalizes. Post-final
verification is defense in depth. A path swap cannot redirect writes to an unheld fallback.

## Qualification bundle

The deterministic bundle root is
`containers/sira-smoke/lambda/manual-console/`. Its 1,510-byte manifest SHA-256 is
`dc9824649f97fab6cfd105b5fc0d0c6c1c5ff513fa25f70e0d517afa623cc261`.
The complete file identities appear in the runbook and host-qualification packet.

The future driver verifies itself and every upload member through held descriptors.
The manifest includes the exact 6,815-byte public-source observation, and the driver
requires its SHA-256, strict structure, exact BusyBox manifest/config/layer identity,
zero account/authenticated/payload requests, and age no greater than 86,400 seconds
before constructing a Docker budget or making any Docker call. Evidence distinguishes
the prior public-registry revalidation timestamp from the in-qualification validation
of its repository binding and truthfully records that the qualification itself makes
no separate registry-metadata request. An expired observation is a hard pre-Docker
stop; a later materializer must refresh it and regenerate/review the driver, schema,
and manifest identities before authorization.

The driver then records bounded host/runtime facts, requires zero pre-existing
containers, pulls exactly the pinned BusyBox digest once, creates one
no-network container, verifies private/default PID plus private cgroup/IPC namespaces,
drops all capabilities, sets no-new-privileges, uses a read-only root and bounded
tmpfs/shm/CPU/memory/PIDs/logs, captures pre-stop process evidence, sends TERM, proves
the adversarial fixture survives, escalates to KILL, proves terminal state, removes by
immutable container ID, and verifies zero labeled container/network/volume residue.
It never runs apt, reconfigures Docker, uses SSH, opens a browser, calls a model, or
runs SiRA. These are fake/static control-plane claims until a later authorized run
produces kernel/runtime evidence.

The private host-evidence document binds the exact future authorization reference,
authorization SHA-256, bundle-manifest SHA-256, decision/marker aliases, and private
instance-binding hash. The driver requires the expected bundle-manifest SHA-256 before
its first Docker call and reserves ten Docker calls from ordinary work for bounded
emergency cleanup. It enforces 270 seconds for ordinary Docker work, 300 seconds
including cleanup, and the
actual—not clamped—containment-fixture duration at no more than 30 seconds.

The public-metadata prerequisite is validated once before any Docker operation. Host OS,
architecture, Python, cgroup, and storage floors are validated before pull. Docker
client/server, containerd, and runc versions must each be present, unique, nonempty,
and bounded; only buildx/BuildKit metadata remains nullable.
Subprocess output is charged while it is read, including timeout and error paths; an
overflow or unexpected pipe/selector error kills and waits for the Docker client. Of
the 8,388,608-byte aggregate, 1,048,576 bytes are unavailable to ordinary work and
reserved for emergency cleanup, so ordinary exhaustion cannot suppress the ten
reserved calls. On success, the Mac validator cross-checks three immutable-ID inspect states
(`created`, TERM-survived, KILL-terminal) and a seven-event lifecycle log against the
typed host evidence. Empty or assertion-only inspect/log files are ineligible. On any
driver failure, ten cleanup calls are reserved from ordinary work. A create with an
unknown response is earlier than the normal 22-call path, so the 32-call aggregate
also has enough unused headroom for five one-second identity polls, one immutable-ID
inspect, kill/remove, three one-second stable-absence polls, and three final resource
residue observations. No match after the five observations remains explicitly
unresolved and can never claim complete cleanup. A deterministic failure archive
records either proven cleanup or an explicit cleanup incident requiring immediate
console termination. Success and
failure source sets are each capped at 16,777,216 bytes; each ZIP is capped at
16,777,216 bytes; the worst late-failure state is capped at 34,603,008 source bytes,
33,554,432 archive bytes, and 68,157,440 aggregate retained bytes.

## Exact budgets and deadlines

| Surface | Exact cap |
|---|---:|
| Manual launch clicks / instances / persistent filesystems | 1 / 1 / 0 |
| Automated Lambda/cloud-account mutations / retries / pagination | 0 / 0 / 0 |
| Read-only Lambda GETs | 44 aggregate; minimum 1-second starts |
| Response bytes | 1,048,576 per GET; 16,777,216 aggregate |
| Observer total wall / events / event / journal | 6,300 s / 512 / 4,096 B / 2,097,152 B |
| Observer wall partition | 1,200 s prelaunch + 3,600 s provider + 1,200 s post-provider cleanup + 300 s archive |
| Private checkpoint / consumption ledger | 16,384 B each / 262,144 B aggregate |
| User wait per checkpoint | 300 s |
| Launch-to-active / Cloud IDE | 600 s / 600 s |
| Jupyter qualification / download+validation | 300 s / 300 s |
| Normal termination-click deadline from launch | 1,800 s |
| Termination verification / firewall cleanup | 600 s / 300 s |
| Incident headroom / provider hard wall | 900 s / 3,600 s |
| Docker calls / ordinary-work ceiling / cleanup reserve / container / fixture wall | 32 / 22 / 10 / 1 / 30 s |
| Docker output | 1,048,576 B/call; 8,388,608 B aggregate |
| Local observer process calls/output | 16 / 4,194,304 B |
| Qualification ZIP / unpacked / files | 16,777,216 B / 33,554,432 B / 16 |
| Remote source / archive per evidence set | 16,777,216 / 16,777,216 B |
| Remote retained source / archives / aggregate | 34,603,008 / 33,554,432 / 68,157,440 B |
| Mac active source+sealed / external archive | 83,886,080 / 41,943,040 B |
| Cost ceiling / observed rate | USD 2.00 / USD 1.29 per hour |
| Modeled list cost at 1,800 / 2,400 / 3,600 s | USD 0.65 / 0.86 / 1.29, before tax |
| SSH / browser automation / model calls+tokens / SiRA / science | 0 / 0 / 0+0 / 0 / 0 |

The 44-GET aggregate is partitioned and enforced; no phase may borrow from another:

| Observer phase | GET cap | Exact allowed observations |
|---|---:|---|
| Preflight | 5 | images, instance types, instances, rulesets, global firewall; one each |
| Strict-global verification | 1 | global firewall |
| Regional-ruleset bind | 1 | exact ruleset list |
| Instance bind/active | 10 | at most ten intentional list observations |
| Cloud IDE checkpoint | 0 | private local checkpoint only |
| Qualification/download | 0 | private local checkpoint/archive only |
| Termination verification | 10 | at most ten intentional list observations |
| Ruleset absence | 2 | ruleset list only |
| Global restoration | 1 | global firewall |
| Incident reserve | 14 | instance/ruleset/global read-only observations only |

Polling rounds are planned observations, not automatic retries; redirects, pagination,
mutation methods, and replay after an ambiguous request remain forbidden. Incident
reads consume the same 44-call aggregate and do not increase it.

The user must click Terminate by 1,800 seconds in the normal path. Provider termination
is the only billing stop; host shutdown is prohibited. One-minute rounding is included
in the modeled list cost. Taxes and an account/control-plane outage are not hard-
bounded by the local supervisor; during an outage a billable instance may exceed both
the normal time and cost ceilings until the user can terminate it in the console.

## Cleanup and incident order

Every success or failure after launch follows this immutable order: user console
termination; read-only terminal/absence verification; user deletion of the exact
run-owned regional ruleset; read-only absence verification; user restoration of the
sealed original global rules; read-only exact semantic verification. Restoration is
forbidden before terminal proof. If the console or API is unavailable, keep the strict
TCP/22-only firewall, launch nothing else, retain all evidence, and raise a high-
severity manual incident until cleanup can resume.

## Scientific boundary

`EXP-0001`, `PLAN-EXP0001-SMOKE`, `SIRA-REACTIVE` first,
`SIRA-SIMULATIVE` second, `PAIR-EXP0001-SMOKE-0000`,
`gpt-4o-2024-11-20`, directional reproduction,
`interpretation_allowed: false`, pilot unauthorized, and training false remain
unchanged. Gate L2M is host qualification only. Gate L3 and Gate L4 remain blocked.
