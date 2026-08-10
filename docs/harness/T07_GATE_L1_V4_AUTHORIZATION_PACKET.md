# T07 Gate L1 V4 authorization packet

Status: **ready for a separate user decision; unauthorized; do not execute from this
packet alone**

This packet grants no authority. It supersedes the V1 and V2 inventory execution paths
for future use while preserving their plans, authorizations, run roots, and ledgers as
blocked historical evidence. A fresh user authorization may cover only the exact seven
Lambda account GETs and bounded local/external sealing actions below. It cannot
authorize Gate L2, an instance launch, paid compute, SSH, a model call, browser use,
SiRA, or scientific execution.

## Exact immutable identity

| Field | Exact value |
|---|---|
| Provider | Lambda On-Demand Cloud |
| API base | `https://cloud.lambda.ai` |
| Public API contract | OpenAPI `1.10.0`; 239,644 B; SHA-256 `365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded` |
| Public spec URL | `https://docs.lambda.ai/api/cloud/spec.json` |
| Public docs URL | `https://docs-api.lambda.ai/api/cloud` |
| Plan ID | `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V3` |
| Run ID / attempt | `RUN-T07-L1-LAMBDA-INVENTORY-0003` / `3` |
| Plan path | `containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v3.json` |
| Plan bytes / SHA-256 | 12,500 / `b5ec82aaa84882a7c3269ebdb695a6c694f891d66d367c05f82eaf9797515331` |
| Reviewed implementation commit | `718c75c694b3033fa7ef2ed5e7c4696fd8c389f3` |
| Required execution commit | Exact final clean Gate L1.2 handoff commit, a descendant of the reviewed implementation commit with every plan-bound implementation hash unchanged |
| Branch | `phase-1/sira-smoke-lambda` |
| Transport | `giclab.harness.lambda_inventory_v3.LambdaHttpsInventoryTransportV3` (`in-process-https`) |
| Authorization placeholder | `AUTH-T07-GATE-L1-LAMBDA-INPROCESS-V4-PENDING` (invalid for execution) |
| Local run root | `artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0003` |
| Failure-only disposition | `artifacts/t07/lambda/gate-l1/preflight-dispositions/RUN-T07-L1-LAMBDA-INVENTORY-0003.json` |
| External final bundle | `/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts/RUN-T07-L1-LAMBDA-INVENTORY-0003` |
| Future actor | Codex operator configured to GPT-5.6 Sol/max |

A Git commit cannot encode its own SHA. The copy-ready block below therefore uses
`<EXACT_FINAL_GATE_L1_2_PACKET_COMMIT>`; the clean committed handoff resolves it to the
exact final SHA. The supervisor requires the execution commit to be clean, exact, and a
descendant of the reviewed implementation commit before it can access the credential.

## Exact schema identities

| Contract | Bytes | SHA-256 |
|---|---:|---|
| `schemas/t07-lambda-request-ledger-v3.schema.json` | 9,683 | `aa3208546cfa3ba171bd6c7b5af67124260e25cb3d32c8989b34d0ad6ce89a0d` |
| `schemas/t07-lambda-inventory-v3.schema.json` | 21,486 | `53db8500f6ef98f440cde80022442aa55dae26d4de5e703c014b744aa88b4c3b` |
| `schemas/t07-lambda-schema-extension-report.schema.json` | 2,444 | `74ac1e1d2c5f7bb761335206543648a3ddcfb94149a5268e61c669d14777ed64` |
| `schemas/t07-lambda-audit-structural-report.schema.json` | 2,634 | `8ac8097b79e4e211ebf3cb1e9d39fcaad72f504f7bb9edc442f2cdb1440d1e08` |

| Endpoint response schema | SHA-256 |
|---|---|
| `endpoint-schemas-v3/instance-types.schema.json` | `cfa9782f27021640ef0739c9c3896ad391eca76e6e89b02b3375487bfbf6bcf2` |
| `endpoint-schemas-v3/images.schema.json` | `ba3b0ba8e6ecf1c97f94a54a3872056b44527ff81e4538fc35c40b911e896cba` |
| `endpoint-schemas-v3/regions.schema.json` | `acb882c12a74063157c9d6e41c372e57443536d237a7e5a43fb843d848ec1d62` |
| `endpoint-schemas-v3/ssh-keys.schema.json` | `bd5062e1f55e79535a3eb624826339482338600d272b3140b21a4f2096fd84cc` |
| `endpoint-schemas-v3/firewall-rulesets.schema.json` | `66b49463fca2e10db56b70127546691b5cefea5c20babcfafb6098f1844e09d3` |
| `endpoint-schemas-v3/global-firewall-ruleset.schema.json` | `9328a3cbd4cc97b40c695eb756ba2d339f15936dbf3d931c4f9915090661812f` |
| `endpoint-schemas-v3/instances.schema.json` | `37de7898716eb42c8452cd76755b3218602214f4983755c44714038ff26e480c` |

The plan cross-binds every schema hash to its implementation manifest. Before the
credential source is invoked, the supervisor loads the exact plan, validates every
schema against Draft 2020-12, verifies every runtime artifact hash in process, proves
the exact clean branch/commit, proves reviewed-implementation ancestry, creates and
reserves the fresh ledger, and validates storage identity/floors. The committed plan
contains `authorized: false`; authority exists only in a separately hashed user block.

## Exact request allowlist and order

Each request is a GET with no body or query. Every response cap is 262,144 B.

| # | Request ID | Exact operation | Response schema SHA-256 |
|---:|---|---|---|
| 1 | `instance-types` | `GET https://cloud.lambda.ai/api/v1/instance-types` | `cfa9782f27021640ef0739c9c3896ad391eca76e6e89b02b3375487bfbf6bcf2` |
| 2 | `images` | `GET https://cloud.lambda.ai/api/v1/images` | `ba3b0ba8e6ecf1c97f94a54a3872056b44527ff81e4538fc35c40b911e896cba` |
| 3 | `regions` | `GET https://cloud.lambda.ai/api/v1/regions` | `acb882c12a74063157c9d6e41c372e57443536d237a7e5a43fb843d848ec1d62` |
| 4 | `ssh-keys` | `GET https://cloud.lambda.ai/api/v1/ssh-keys` | `bd5062e1f55e79535a3eb624826339482338600d272b3140b21a4f2096fd84cc` |
| 5 | `firewall-rulesets` | `GET https://cloud.lambda.ai/api/v1/firewall-rulesets` | `66b49463fca2e10db56b70127546691b5cefea5c20babcfafb6098f1844e09d3` |
| 6 | `global-firewall-ruleset` | `GET https://cloud.lambda.ai/api/v1/firewall-rulesets/global` | `9328a3cbd4cc97b40c695eb756ba2d339f15936dbf3d931c4f9915090661812f` |
| 7 | `running-instances` | `GET https://cloud.lambda.ai/api/v1/instances` | `37de7898716eb42c8452cd76755b3218602214f4983755c44714038ff26e480c` |

Request starts are at least one monotonic second apart. Each response is validated and
redacted before the next intent. The only account network endpoint is
`cloud.lambda.ai:443`. No audit/history request, account-LRN request, curl, wget,
shell/HTTP subprocess, alternate host, redirect follow, retry, pagination request, or
eighth request is permitted.

## Exact compatibility and privacy contract

Each endpoint requires its documented success envelope, required fields, types, and
nullability. Missing/type-incompatible required data stops the run. Additive object
keys are accepted only where the bound endpoint schema leaves them open. The retained
extension report may contain only unknown key names, JSON types, structural locations,
and structural hashes; no unknown scalar value is retained or promoted.

Every non-null continuation token and every `has_more` value other than false/null is
`pagination_present` and stops the run without a follow-up request. Compatible
additions are marked `compatible_extension_observed`. Raw responses remain memory-only.
The redacted inventory omits authorization headers, API keys, cookies, SSH public keys,
instance IPs, Jupyter credentials, audit history, and unrelated tag values.

## Exact request-ledger contract

The mandatory ledger is:

`artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0003/request-ledger.jsonl`

It is exclusively created under a fresh run root. The writer owns contiguous sequence
numbers; validates the closed allowlist and lifecycle; appends completely; flushes and
fsyncs before state advances; and rejects reuse, truncation, gaps, reordering, mixed
identity, and events after terminal state. Before entering the transport for every
request, `request_intent_committed` and then `request_send_started` must be durably
committed.

| Ledger resource | Exact cap |
|---|---:|
| Ledger bytes | 172,032 B |
| Total events | 84 |
| Events per request | 9 |
| Encoded event | 2,048 B |
| Separate preflight disposition | 16,384 B |
| Retry count | 0 |
| Pagination request flag | false |

A prefix ending at send-started without durable terminal request evidence is outcome
unknown and nonreplayable. Any ledger I/O/cap/state failure stops all later requests.
Gate L2 requires a complete success ledger and a separately verified local/external
seal; structural validity alone is insufficient.

## Exact aggregate caps

| Resource | Aggregate cap | Per-operation/composition |
|---|---:|---|
| Account HTTP calls | 7 GET; 0 mutation | once per exact listed endpoint |
| Raw response bytes | 1,835,008 B | 262,144 B per response; memory-only |
| Provider wall | 60 s | one shared deadline; no retry |
| Archive wall | 60 s | separate hard watchdog |
| Total wall | 180 s | preflight through terminal checks |
| Request ledger | 172,032 B | 84 events; 2,048 B/event; 9/request |
| Schema-extension report | 65,536 B | embedded in the redacted inventory |
| Local redacted inventory | 524,288 B | one exclusive retained file |
| Local copy record | 65,536 B | one exclusive retained file |
| Optional preflight disposition | 16,384 B | failure path only |
| External sealed bundle | 1,048,576 B | inventory, terminal ledger, `COPY_RECORD.json`, `SEAL.json` |
| Aggregate retained | 1,826,816 B | 761,856 B local success + 1,048,576 B external + 16,384 B conservative disposition |
| Local process calls | 15 | 2 watchdogs + 4 Git reads + 9 read-only `diskutil` calls |
| Local process output/control | 37,879,810 B | 131,072 B Git aggregate + 9 x 4,194,304 B diskutil + 2 readiness bytes |
| Local file creates | 4 | ledger, capacity file, inventory, local record |
| External file creates | 4 | exact sealed-bundle files |
| External directory creates | at most 4 | approved hierarchy plus one staging/final identity |
| Mac mini prewrite floor | 8,590,868,480 B | 8 GiB + 933,888 B conservative peak |
| Mac mini retained floor | 8,589,934,592 B | exact 8 GiB operational floor |
| External free floor | `max(161,061,273,600, ceil(current_capacity_bytes / 5)) + 1,048,576 B` before copy | no internal fallback |
| Provider/API/compute cost | USD 0.00 | no instance or paid compute |
| Model calls/tokens | 0 / 0 | no model provider |
| Browser actions | 0 | no browser |
| SSH operations | 0 | no SSH |
| SiRA/condition executions | 0 | no experiment |

The Mac mini conservative peak is:

```text
172,032 ledger capacity reservation
+ 172,032 terminal ledger maximum
+ 524,288 inventory maximum
+  65,536 local verification maximum
= 933,888 bytes
```

## Exact shell-free invocation and local arrays

Only after a fresh V4 user authorization, replace the two authorization markers and
the final clean commit in this argument array:

```json
[
  ".venv/bin/python",
  "-m",
  "giclab.harness.lambda_inventory_v3",
  "--repository-root",
  "/Users/joseph/.codex/worktrees/84b1/gic-lab",
  "--plan",
  "/Users/joseph/.codex/worktrees/84b1/gic-lab/containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v3.json",
  "--plan-sha256",
  "b5ec82aaa84882a7c3269ebdb695a6c694f891d66d367c05f82eaf9797515331",
  "--expected-commit",
  "<EXACT_FINAL_GATE_L1_2_PACKET_COMMIT>",
  "--implementation-commit",
  "718c75c694b3033fa7ef2ed5e7c4696fd8c389f3",
  "--authorization-reference",
  "AUTH-T07-GATE-L1-LAMBDA-INPROCESS-V4-2026-08-10",
  "--authorization-sha256",
  "<SHA256_OF_THE_FRESH_USER_AUTHORIZATION_TEXT>"
]
```

The only Git arrays are:

```json
["/usr/bin/git", "branch", "--show-current"]
["/usr/bin/git", "rev-parse", "HEAD"]
["/usr/bin/git", "status", "--porcelain=v1", "--untracked-files=normal"]
["/usr/bin/git", "merge-base", "--is-ancestor", "718c75c694b3033fa7ef2ed5e7c4696fd8c389f3", "<EXACT_FINAL_GATE_L1_2_PACKET_COMMIT>"]
```

Each of three storage observations may invoke only:

```json
["/usr/sbin/diskutil", "info", "-plist", "/Volumes/Macintosh HD - Data"]
["/usr/sbin/diskutil", "info", "-plist", "/System/Volumes/Data"]
["/usr/sbin/diskutil", "apfs", "list", "-plist"]
```

Every child process gets a newly constructed secret-free environment. Neither the
provider credential nor either forbidden model credential is inherited by a child.

## Secret, archive, and cleanup contract

The only secret variable is `LAMBDA_API_KEY`. A future authorization may permit the
supervisor to test its presence and read it lazily, in process, only after ledger,
plan/implementation, clean-commit/ancestry, storage, and cap preflight succeeds. The
value may never be printed, hashed, persisted, returned, placed in argv/URL/path/log/
ledger/archive, or passed to a child. `SIRA_API_KEY` and `OPENAI_API_KEY` remain
forbidden fallbacks.

The external archive must freshly bind writable/unlocked APFS Data UUID
`8478609D-FA37-4ED5-875D-47AE912B9151`, physical-store UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`, exact mount
`/Volumes/Macintosh HD - Data`, external Thunderbolt/UTDM classification, held
no-follow descriptors, distinct source/destination devices, and all floors. There is
no internal fallback.

The only external hierarchy components that may be created if absent are, in order,
`/Volumes/Macintosh HD - Data/GIC-Lab`, its `t07` child, and its
`sealed-artifacts` child, followed by exactly one fresh run-0003 staging directory and
its atomic final name. The only local creates are the fresh run root and its bounded
ledger/capacity/inventory/copy-record files, or the one exclusive failure disposition
when the run root cannot be safely completed. Existing objects are never overwritten
or reused.

Only after seven complete valid outcomes may the supervisor create the redacted
inventory, validate it, stage it externally, seal the complete ledger, write bounded
copy/seal records, fsync, atomically finalize, reread, verify every SHA-256, and create
the local verification record. The local inventory and ledger remain. A partial
external directory is preserved for bounded review and is never promoted. Nothing
prunes unrelated data or overwrites/reuses a run identity.

## Stop conditions and remaining blockers

Stop before the credential or first request on branch, commit, clean-tree, ancestry,
plan/hash, implementation/hash, schema, run freshness, ledger reservation, storage
identity/floor, or cap drift. Stop without another request on endpoint/order/method,
pacing, deadline, status, redirect, content type, response size, JSON/schema,
pagination, extension-report, ledger, archive, fsync, or hash failure. Never replay run
0003 after a possible send.

Remaining blockers are:

1. This V3 plan is unauthorized. A fresh user must approve the exact final clean
   commit, plan/hash, implementation commit, run, endpoints, caps, secret channel, and
   archive contract.
2. The real credential must be present only through that authorized secret channel;
   it was not accessed in Gate L1.2.
3. The external volume identities, held paths, and free floors must pass fresh
   preflight; no current observation is carried forward as trusted execution state.
4. Run 0003 local and external identities must still be absent.
5. Gate L2 remains blocked after L1 authorization until all seven responses validate,
   the evidence is sealed/verified, and the user reviews and selects an eligible
   instance tuple, existing SSH key, and firewall ruleset. Authenticated first-contact
   SSH host-key trust remains a separate Gate L2 blocker.

## Ready-to-copy V4 authorization block

The final clean-commit handoff must replace the marked commit before the user signs
this text.

```text
Continue T07 with Gate L1 V4 only.

I authorize T07 Gate L1 read-only Lambda inventory only on exact clean commit
<EXACT_FINAL_GATE_L1_2_PACKET_COMMIT> of phase-1/sira-smoke-lambda, a descendant of
reviewed implementation commit 718c75c694b3033fa7ef2ed5e7c4696fd8c389f3 with every
plan-bound implementation hash unchanged, using run
RUN-T07-L1-LAMBDA-INVENTORY-0003 and plan
PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V3 at
containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v3.json, 12,500 bytes,
SHA-256 b5ec82aaa84882a7c3269ebdb695a6c694f891d66d367c05f82eaf9797515331.

The authorization reference is AUTH-T07-GATE-L1-LAMBDA-INPROCESS-V4-2026-08-10. The
operator may access only LAMBDA_API_KEY through the documented nonlogging in-process
secret channel and issue exactly seven GET requests to https://cloud.lambda.ai, once
each in this order: /api/v1/instance-types, /api/v1/images, /api/v1/regions,
/api/v1/ssh-keys, /api/v1/firewall-rulesets,
/api/v1/firewall-rulesets/global, /api/v1/instances. Starts must be at least one
second apart, with no redirect follow, pagination request, retry, audit/history request,
or HTTP subprocess. The mandatory ledger is
artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0003/request-ledger.jsonl,
bound to schema SHA-256 aa3208546cfa3ba171bd6c7b5af67124260e25cb3d32c8989b34d0ad6ce89a0d.

Caps are: 7 GETs; 60 seconds provider wall; 60 seconds archive wall; 180 seconds total
wall; 1,835,008 raw response bytes; 172,032 ledger bytes; 84 ledger events; 9 events
per request; 2,048 bytes per event; 524,288 local inventory bytes; 65,536 extension-
report bytes within that inventory; 65,536 local verification bytes; 16,384 preflight-
disposition bytes; 1,048,576 external sealed-bundle bytes; 1,826,816 aggregate retained
bytes; 15 local process calls; and 37,879,810 local process output/control bytes.
Automatic retries, pagination requests, mutation calls, paid compute, model calls/
tokens, browser actions, SSH operations, and SiRA executions are all exactly zero.

I authorize only the exact read-only Git/diskutil checks and fixed local/external
creates documented in the V4 packet. The copy must bind APFS UUID
8478609D-FA37-4ED5-875D-47AE912B9151 and physical-store UUID
7904A6F1-F483-4ED7-9E34-BFECAB31C63E through held no-follow descriptors, enforce the
8,590,868,480-byte Mac mini prewrite floor, 8,589,934,592-byte retained floor, and
dynamic external floor plus 1,048,576 bytes, verify every source/destination SHA-256,
fsync, atomically finalize, retain the source, and prohibit internal fallback.

This authorization permits no Lambda/cloud mutation, instance launch or termination,
paid compute, SSH, model/provider-model call or token, browser action, SiRA or
scientific execution, scientific-field change, pilot work, or Gate L2. It forbids
access to SIRA_API_KEY and OPENAI_API_KEY. Stop on any contract failure, preserve the
ledger prefix, never replay this run identity after a possible send, and do not begin
Gate L2.
```

Gate L1.2 made no account request and accessed no real secret.
