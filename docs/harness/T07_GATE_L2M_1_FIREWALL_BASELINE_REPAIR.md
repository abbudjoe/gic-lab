# T07 Gate L2M.1 firewall-baseline repair

Status: **fresh-readonly-firewall-baseline-required; capture plan unauthorized**

Date: 2026-08-11

## Decision

The retained run-0003 observation is an `incomplete_or_transformed_baseline`. It is
not safe restoration authority. The observer retained a schema-validated projection
with every currently expected rule field, but it did not retain the 660-byte provider
response or unknown raw-key structure. The official rule schema does not explicitly
forbid additive properties. The repository therefore cannot prove that the projection
is a byte-preserved or lossless representation of every restoration-relevant field.

No description or other value was inferred. No baseline alias, restoration payload,
manual V4 plan, or run-0004 identity was created. The only next executable proposal is
one fresh, separately authorized read-only GET of the global firewall.

## Historical evidence adjudication

| Item | Exact identity |
|---|---|
| Historical plan | `PLAN-T07-GATE-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-V3` |
| Historical run | `RUN-T07-L2M-MANUAL-CONSOLE-HOST-QUALIFICATION-0003` |
| Plan SHA-256 | `1931fcacda4194063c0116ff9630d82f3b8f4ec07ff9b0310342335db629f654` |
| Observer journal bytes / SHA-256 | 22,869 / `732ca7f649292ca9d87924d722ccd9d563320529b97c05686c2754d1a2718e4a` |
| Observation 0006 bytes / SHA-256 | 782 / `7168f04f6ad961db10fde3431daa59052f3fc4539128b1bbc2c510e66d37ca25` |
| Request outcome | GET, HTTP 200, 660 response bytes, endpoint schema passed |
| Original disposition | `schema_failure` |
| Adjudicated disposition | `incomplete_or_transformed_baseline` |
| Replay | prohibited |
| Cloud mutation before stop | none |

The sanitized structural report records four projected rules; every projection has
`protocol`, explicit `port_range`, `source_network`, and a string `description`.
There are four nonempty and zero empty projected descriptions, and only the public
protocol classes `tcp` and `udp` are recorded. No description, CIDR, ID, name, or
other private scalar is committed.

The adjudication and structural report are:

- `docs/harness/evidence/T07_RUN_0003_FIREWALL_BASELINE_ADJUDICATION.json`
- `docs/harness/evidence/T07_RUN_0003_FIREWALL_STRUCTURAL_REPORT.json`

## Official provider contract

The first-party public OpenAPI document was retrieved without authentication from
`https://docs-api.lambda.ai/api/cloud/spec.json` at
`2026-08-11T17:42:05.506294Z`.

| Field | Value |
|---|---|
| OpenAPI version | `3.1.0` |
| API version | `1.10.0` |
| Bytes | 240,288 |
| SHA-256 | `320f4877924984f060b179e86595ed58918a1d0696b60b99cae548ec164934f4` |
| GET | `/api/v1/firewall-rulesets/global` |
| PATCH | `/api/v1/firewall-rulesets/global` |

`FirewallRule` requires non-null string `protocol`, `source_network`, and
`description`. Description length is 0 through 128. `port_range` is an exact pair of
integers 1 through 65,535, required for TCP/UDP/all and forbidden for ICMP. The
response includes stable `id`, `name`, and `rules`; only `rules` belongs in the PATCH
body. The pinned public extraction is
`containers/sira-smoke/lambda/manual-console/public-firewall-contract-l2m-1.json`.

## Repaired semantic and restoration contract

Canonicalization version `t07-firewall-canonical-v1` represents each rule as:

```text
protocol
port_range = exact pair or explicit absent state
source_network = canonical IPv4 network semantics; bare hosts become /32, while
                 explicitly prefixed values with host bits are rejected
description = exact decoded Unicode string, including empty string
```

The ruleset is a sorted multiset. Ordering is ignored, duplicate multiplicity is
preserved, and any description, source-network, port, protocol, count, ruleset ID, or
ruleset-name drift fails. Missing description never becomes empty description.
Unknown additive rule fields block until their restoration relevance is reviewed.

The exact restoration payload contains only `rules` and preserves each observed
description/source/protocol/port-presence value. Response-only ID/name are excluded.
Private baseline and restoration schemas exist now, but no private baseline artifact
or restoration payload is materialized until a complete fresh response is captured.

The manual observer delegates to this versioned canonicalizer. That implementation
hash change makes historical V3 fail its immutable implementation binding before
credential access; V3 remains byte-identical historical evidence and cannot be
re-rendered or replayed.

## Run-0003 incident seal

The additive incident bundle retains the original plan, journal, observation,
adjudication, structural report, manifest, and seal. The original three hashes were
reverified after sealing. The local source remains under the ignored run root; the
copy was fsynced, atomically finalized, and hash-verified on the approved APFS/UTDM
archive with no internal fallback.

| Item | Identity |
|---|---|
| Incident alias | `l2m-incident-81cff71b09e0` |
| Local incident-seal SHA-256 | `552f5d57dbb232c09cdffceb9bb2c337f6995994a0dec564be7f90022e2ba15c` |
| External copy-record SHA-256 | `ac867c4fac4bb51beb66e5247863cb9c00326e7b6186e5718e5f51957f4a5a77` |
| External seal SHA-256 | `283b992203ccbe85491a3ef853b2741a3e183b70d19a8db729db7db5492f98b1` |
| Destination hashes verified | true |
| Source retained | true |
| Run replay allowed | false |
| No mutation occurred | true |

## Fresh capture plan

| Item | Exact identity |
|---|---|
| Plan | `PLAN-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1` |
| Run | `RUN-T07-L2M-FIREWALL-BASELINE-CAPTURE-0001` |
| Path | `containers/sira-smoke/lambda/manual-console/gate-l2m-firewall-baseline-capture-plan-v1.json` |
| Bytes | 6,311 |
| SHA-256 | `bd61aed7ed1da74ad39ed24c56145d9e816e7ab9b2063f2c962e1cfb79d8a63b` |
| Reviewed implementation commit | `7e199dc634cee955b00fc587728a14c46cdf232a` |
| Pending reference | `AUTH-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1-PENDING` |
| Authority | false |

The plan permits one GET, zero retry, zero pagination, zero redirects, and no other
provider operation. Before the secret read it verifies the exact clean branch/commit,
plan and implementation hashes, fresh local/external identities, APFS/physical-store
UUIDs, no-follow hierarchy, and free-space floors. It creates and fsyncs a bounded
ledger before request intent/send, retains the complete raw response privately,
validates the official envelope and complete rule semantics, creates a private exact
restoration payload plus a public-safe canonical report, then performs a one-way
held-descriptor archive copy with source/destination hash verification. Failure burns
the run and never authorizes the historical manual plan.

## Scientific and execution boundary

EXP-0001, `PLAN-EXP0001-SMOKE`, `SIRA-REACTIVE` then `SIRA-SIMULATIVE`, pair
`PAIR-EXP0001-SMOKE-0000`, model `gpt-4o-2024-11-20`, directional reproduction,
`interpretation_allowed: false`, pilot unauthorized, and training false remain
unchanged. This repair made no authenticated account/model request, read no real
secret, and performed no cloud mutation, paid compute, SSH, Jupyter, browser,
container, SiRA, or scientific execution.

## Remaining blocker

A fresh current-turn authorization must bind the final clean handoff commit, exact
capture plan/hash, reviewed implementation commit, nonlogging `LAMBDA_API_KEY`
channel, one GET, ledger/cap/storage contract, and fresh run/archive identities. Only
a completed and sealed baseline capture can support a new offline manual-plan repair.
Gate L2M manual qualification, Gate L3, Gate L4, and the experiment remain blocked.
