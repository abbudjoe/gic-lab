# T07 Gate L1 V3 authorization packet

Status: **ready for a separate user decision; unauthorized; do not execute from this
packet alone**

This packet grants no authority. It replaces the V1 execution path with a new V2
plan/run identity whose observable request ledger is mandatory. A future
authorization can cover only the eight listed Lambda account GETs and the bounded
local/external evidence actions. It cannot authorize Gate L2, an instance launch,
paid compute, SSH, a model call, browser use, SiRA, or scientific execution.

## Exact immutable identity

| Field | Exact value |
|---|---|
| Provider | Lambda On-Demand Cloud |
| API base | `https://cloud.lambda.ai` |
| Public API lock | OpenAPI `1.10.0`; SHA-256 `365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded` |
| Plan ID | `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V2` |
| Run ID / attempt | `RUN-T07-L1-LAMBDA-INVENTORY-0002` / `2` |
| Plan path | `containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v2.json` |
| Plan SHA-256 / bytes | `02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e` / `8,856` |
| Reviewed implementation commit | `0b900213801315f4312105297774b8ea5a6d9f04` |
| Required execution commit | Exact final clean packet commit from the Gate L1.1 handoff; direct descendant of the reviewed implementation commit with every bound implementation hash unchanged. |
| Transport identity | `giclab.harness.lambda_inventory_v2.LambdaHttpsInventoryTransportV2` |
| Transport source hash | `src/giclab/harness/lambda_inventory_v2.py`; SHA-256 `14b0288f4a6e215077d40f6bb7053dac5f9d6ad87ed07d97383e4cd5a5abef90` |
| Request-ledger schema | `schemas/t07-lambda-request-ledger.schema.json`; SHA-256 `e62dc6d333e581350f128b777c59bf5f9ffe5527a79909f69d1ef75195d2ea73`; 9,746 B |
| Inventory schema | `schemas/t07-lambda-inventory-v2.schema.json`; SHA-256 `bbbe2516956658afa3d972c46a7a306eb769c4b17b95ec0171c85d29df161be6`; 14,597 B |
| Local run root | `artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0002` |
| External bundle | `/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts/RUN-T07-L1-LAMBDA-INVENTORY-0002` |
| Future actor | Codex operator configured to GPT-5.6 Sol/max |

The plan binds SHA-256 values for all runtime modules, `pyproject.toml`, `uv.lock`,
and both schemas. Before the credential source is invoked, the supervisor verifies
those files in process, proves the exact clean branch/commit, and verifies the plan
hash. The committed plan contains `authorized: false`; its pending authorization
placeholder is invalid as a live run binding.

The historical V1 plan at SHA-256
`c7151737bd029e3ebad45d59dc2d9fcd58f401dc7d8658021f1d384129555c69`, V1
packet, and `RUN-T07-L1-LAMBDA-INVENTORY-0001` are blocked provenance. The public V1
executor rejects use. Neither historical authorization may be replayed.

## Exact request allowlist and order

The future transport constructs one in-memory Authorization header and follows no
redirect. Request starts are at least one monotonic second apart. Every response is
validated before the next intent.

| # | Request ID | Exact operation | Response cap |
|---:|---|---|---:|
| 1 | `account-workspace-identity` | `GET https://cloud.lambda.ai/api/v1/audit-events?resource_type=cloud.api_key` | 262,144 B |
| 2 | `instance-types` | `GET https://cloud.lambda.ai/api/v1/instance-types` | 262,144 B |
| 3 | `images` | `GET https://cloud.lambda.ai/api/v1/images` | 262,144 B |
| 4 | `regions` | `GET https://cloud.lambda.ai/api/v1/regions` | 262,144 B |
| 5 | `ssh-keys` | `GET https://cloud.lambda.ai/api/v1/ssh-keys` | 262,144 B |
| 6 | `firewall-rulesets` | `GET https://cloud.lambda.ai/api/v1/firewall-rulesets` | 262,144 B |
| 7 | `global-firewall-ruleset` | `GET https://cloud.lambda.ai/api/v1/firewall-rulesets/global` | 262,144 B |
| 8 | `running-instances` | `GET https://cloud.lambda.ai/api/v1/instances` | 262,144 B |

The only account network endpoint is `cloud.lambda.ai:443` over HTTPS. No curl,
wget, shell, HTTP subprocess, alternate host, retry, pagination request, redirect
follow, or ninth request is authorized.

## Exact request-ledger contract

The ledger is exclusively created and every event is appended and fsynced before
state advances. The maximum success path is 80 events; the hard cap is 96. No request
may use more than nine events.

Required global/request event types are:

```text
run_preflight_started
run_preflight_passed
run_preflight_failed
secret_presence_check_passed
secret_presence_check_failed
request_intent_committed
request_send_started
response_headers_received
response_body_progress
response_body_completed
response_validation_passed
request_failed
request_outcome_unknown_after_send
run_stopped
inventory_validation_started
inventory_validation_passed
inventory_validation_failed
archive_started
archive_passed
archive_failed
```

| Ledger resource | Exact cap |
|---|---:|
| Ledger bytes | 262,144 B |
| Total events | 96 |
| Events per request | 9 |
| Encoded event | 2,048 B |
| Response progress events | 4 per request at fixed 64-KiB thresholds |
| Separate preflight disposition | one fixed file, 16,384 B |
| Retry count | exactly 0 |
| Pagination request flag | exactly false |

The run root is durably and exclusively created before the ledger schema is read.
The one fixed disposition path is
`artifacts/t07/lambda/gate-l1/preflight-dispositions/RUN-T07-L1-LAMBDA-INVENTORY-0002.json`.
Any partial run root or disposition burns the identity. A prefix ending after
send-started without a terminal request event is outcome-unknown and cannot be
replayed.

## Exact aggregate caps

| Resource | Aggregate cap | Per-operation cap or composition |
|---|---:|---|
| Account HTTP calls | 8 GET; 0 mutation | once per exact listed endpoint |
| Raw response bytes | 2,097,152 B | 262,144 B per response; memory-only |
| Provider wall | 60 s | one shared absolute deadline; no retry |
| Archive wall | 60 s | separate hard watchdog |
| Total wall | 180 s | hard watchdog covers preflight through final checks |
| Ledger | 262,144 B | 96 events; 2,048 B/event; 9/request |
| Local inventory | 524,288 B | one exclusive retained file |
| Local terminal ledger | 262,144 B | one exclusive retained file |
| Local copy record | 65,536 B | one exclusive retained file |
| Optional preflight disposition | 16,384 B | one fixed exclusive file; failure path only |
| External sealed bundle | 1,048,576 B | inventory, terminal ledger, `COPY_RECORD.json`, `SEAL.json` |
| Aggregate retained | 1,916,928 B | 851,968 B local success evidence + 1,048,576 B external + conservative 16,384 B disposition allowance |
| Local preallocation | 262,144 B transient | full ledger-cap capacity file, removed with parent fsync at terminal seal |
| Local process calls | 14 | 2 watchdogs + 3 Git reads + 9 read-only `diskutil` calls |
| Local process output/control | 37,814,274 B | 65,536 B Git aggregate + 9 x 4,194,304 B diskutil + 2 readiness bytes |
| Local file creates | 4 | success maximum includes ledger, capacity file, inventory, local record |
| External file creates | 4 | exact sealed-bundle files |
| External directory creates | at most 4 | fixed approved hierarchy plus one staging/final identity |
| Mac mini prewrite free floor | 8,591,048,704 B | 8 GiB + 1,114,112 B conservative peak |
| Mac mini retained free floor | 8,589,934,592 B | exact 8 GiB operational floor |
| External retained-free floor | `max(161,061,273,600, ceil(current_capacity_bytes / 5))` | pre-copy adds 1,048,576 B |
| Provider/API/compute cost | USD 0.00 | no instance or paid compute |
| Model calls/tokens | 0 / 0 | no model provider |
| Browser actions | 0 | no browser |
| SSH operations | 0 | no SSH |
| SiRA/condition executions | 0 | no experiment |

The Mac mini 1,114,112-byte conservative peak is:

```text
262,144 ledger capacity reservation
+ 262,144 terminal ledger maximum
+ 524,288 inventory maximum
+  65,536 local verification maximum
= 1,114,112 bytes
```

## Exact shell-free invocation and local arrays

After a fresh user authorization, replace the two marked authorization values and
the final handoff commit in this shell-free argument array:

```json
[
  ".venv/bin/python",
  "-m",
  "giclab.harness.lambda_inventory_v2",
  "--repository-root",
  "/Users/joseph/.codex/worktrees/84b1/gic-lab",
  "--plan",
  "/Users/joseph/.codex/worktrees/84b1/gic-lab/containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v2.json",
  "--plan-sha256",
  "02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e",
  "--expected-commit",
  "<EXACT_FINAL_GATE_L1_1_PACKET_COMMIT>",
  "--authorization-reference",
  "AUTH-T07-GATE-L1-LAMBDA-INPROCESS-V3-2026-08-09",
  "--authorization-sha256",
  "<SHA256_OF_THE_FRESH_USER_AUTHORIZATION_TEXT>"
]
```

The repository guard may invoke only:

```json
["/usr/bin/git", "branch", "--show-current"]
["/usr/bin/git", "rev-parse", "HEAD"]
["/usr/bin/git", "status", "--porcelain=v1", "--untracked-files=normal"]
```

Each of three storage observations may invoke only:

```json
["/usr/sbin/diskutil", "info", "-plist", "/Volumes/Macintosh HD - Data"]
["/usr/sbin/diskutil", "info", "-plist", "/System/Volumes/Data"]
["/usr/sbin/diskutil", "apfs", "list", "-plist"]
```

The two watchdogs use the already reviewed helper in
`giclab.harness.lambda_inventory` for exact deadlines 180 and 60. Every local child
gets only the newly constructed secret-free environment documented by the V1 packet;
no child inherits a provider or SiRA key.

## Secret and failure contract

The only secret variable is `LAMBDA_API_KEY`. It is supplied outside Git through the
supervisor secret channel and read lazily only after the durable ledger, full ledger
capacity, exact implementation hashes, repository state, storage identity/floors,
and wall checks pass. It is never printed, hashed, persisted, returned, placed in
argv/URL/path/label/log/evidence, or inherited by a child. `SIRA_API_KEY` and
`OPENAI_API_KEY` are forbidden fallbacks.

Failure output uses only a closed stage/class and stable code. Raw exception text,
cause/context, credential-bearing frames, headers, cookies, and raw bodies are not
retained. A failure after observed headers/progress carries the normalized status,
content type, elapsed time, and byte progress in its terminal ledger event.

## Archive and cleanup contract

The external mount must freshly verify writable/unlocked APFS Data UUID
`8478609D-FA37-4ED5-875D-47AE912B9151`, physical-store UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`, external Thunderbolt/UTDM classification,
held no-follow descriptors, distinct source/destination filesystems, and all free
floors. There is no internal fallback.

The source inventory is staged first. After a terminal successful ledger exists, the
finalizer adds the ledger and exact copy/seal records, fsyncs, atomically renames,
rereads, hashes, and performs the third storage observation. The local inventory and
ledger remain. The local verification record is written last. Partial external
staging is preserved for bounded manual evidence review; nothing broadly prunes,
overwrites, or reuses it.

Only the exact complete local/external bundle can be eligible for Gate L2. A missing
file, partial ledger, unknown-after-send prefix, wrong implementation/plan/run/auth/
volume binding, hash mismatch, blocked instance selection, or finalizer failure is
ineligible.

## Stop conditions and remaining blockers

Stop with no further request on any branch, commit, clean-tree, plan hash, bound-file
hash, run identity, ledger creation/write/fsync/cap, secret presence, endpoint,
method, pacing, deadline, status, redirect, content type, response size, JSON/schema,
pagination, storage identity/path/device/floor, archive, hash, fsync, or retained-floor
failure.

Remaining blockers are:

1. A fresh current-turn user authorization must name the exact final clean packet
   commit, V2 plan/run/path/hash, fresh authorization reference, endpoint set, caps,
   secret channel, storage contract, and prohibitions.
2. The future preflight must establish only the presence of `LAMBDA_API_KEY` through
   the approved channel; Gate L1.1 did not access it.
3. The external volume identity and both free-space floors must be freshly observed.
4. Gate L1 must succeed and yield an eligible, complete sealed inventory before an
   account-bound Gate L2 plan can be reviewed or authorized.

These are authorization/live-state blockers, not permission to modify the plan or
retry V1.

## Fresh Gate L1 authorization block

Because a Git commit cannot contain its own SHA, the repository packet carries one
`<EXACT_FINAL_GATE_L1_1_PACKET_COMMIT>` marker. The final Gate L1.1 response resolves
that marker and supplies the fully ready-to-copy block.

```text
I authorize T07 Gate L1 read-only Lambda inventory only on exact clean commit
<EXACT_FINAL_GATE_L1_1_PACKET_COMMIT> of phase-1/sira-smoke-lambda, a direct
descendant of reviewed implementation commit
0b900213801315f4312105297774b8ea5a6d9f04 with every plan-bound implementation
hash unchanged, using run RUN-T07-L1-LAMBDA-INVENTORY-0002 and plan
PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V2 at
containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v2.json, SHA-256
02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e.

The authorization reference is
AUTH-T07-GATE-L1-LAMBDA-INPROCESS-V3-2026-08-09. The operator may access only
LAMBDA_API_KEY through the documented nonlogging, in-process secret channel and may
issue exactly the eight listed GET requests to https://cloud.lambda.ai, once each in
order, with starts at least one second apart, no redirect follow, no pagination and
no retry. The request ledger at
artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0002/request-ledger.jsonl
is mandatory and is bound to schema SHA-256
e62dc6d333e581350f128b777c59bf5f9ffe5527a79909f69d1ef75195d2ea73.

Caps are: 8 GETs; 60 seconds provider wall; 60 seconds archive wall; 180 seconds
total wall; 2,097,152 raw response bytes; 262,144 ledger bytes; 96 ledger events;
9 events per request; 2,048 bytes per event; 524,288 local inventory bytes; 65,536
local verification bytes; 16,384 preflight-disposition bytes; 1,048,576 external
bundle bytes; and 1,916,928 aggregate retained bytes. Automatic retries,
pagination requests, mutation calls, paid compute, model calls/tokens, browser
actions, SSH operations, and SiRA executions are all exactly zero.

I authorize the exact read-only Git/diskutil checks and fixed local/external creates
documented in the V3 packet. The copy must bind APFS UUID
8478609D-FA37-4ED5-875D-47AE912B9151 and physical-store UUID
7904A6F1-F483-4ED7-9E34-BFECAB31C63E through held no-follow descriptors, enforce
the 8,591,048,704-byte Mac mini prewrite floor, 8,589,934,592-byte retained floor,
and dynamic external floor plus 1,048,576 bytes, verify every source/destination
SHA-256, fsync, atomically finalize, retain the source, and prohibit internal
fallback.

This authorization permits no Lambda/cloud mutation, instance launch or
termination, paid compute, SSH, model/provider-model call or token, browser action,
SiRA or scientific execution, scientific-field change, pilot work, or Gate L2. It
forbids access to SIRA_API_KEY and OPENAI_API_KEY. Stop on any contract failure,
preserve the ledger prefix, never replay this run identity, and do not begin Gate L2.
```

Gate L1.1 itself made no account request and accessed no real secret.
