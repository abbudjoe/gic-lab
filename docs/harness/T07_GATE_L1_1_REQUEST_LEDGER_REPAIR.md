# T07 Gate L1.1 request-ledger observability repair

Status: **implementation complete; replacement Gate L1 plan unauthorized; no account
request made**

Date: 2026-08-09

This gate repairs an evidence defect in the blocked Gate L1 control plane. It does
not diagnose the Lambda service, credential, endpoint, network, or TLS stack. It
does not supply authority to retry either historical identity.

## Frozen starting state

The repair began only after all starting checks passed:

| Check | Exact observation |
|---|---|
| Branch | `phase-1/sira-smoke-lambda` |
| Clean baseline | `f9a80332da409789fefc435583aa0f1a10d3eb11` |
| Historical V1 plan | `containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan.json` |
| Historical V1 plan SHA-256 | `c7151737bd029e3ebad45d59dc2d9fcd58f401dc7d8658021f1d384129555c69` |
| Local V1 inventory | absent |
| External V1 sealed bundle | absent |
| Implementation freeze | `0b900213801315f4312105297774b8ea5a6d9f04` |

The locked scientific hashes remained:

| Scientific input | SHA-256 |
|---|---|
| EXP-0001 protocol | `5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c` |
| EXP-0001 configuration | `f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d` |
| Smoke profile | `ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425` |
| Reactive condition plan | `7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018` |
| Simulative condition plan | `68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436` |

No scientific file was edited.

## Blocked historical attempts

Both historical attempts used V1 plan/run identity. That identity is permanently
ineligible for another request.

| Attempt | Authorization evidence | Evidence-grounded disposition |
|---|---|---|
| First V1 attempt | The prior Gate L1 user authorization in the task record; no stable authorization reference was specified. | Stopped before the first account request because local curl instructions conflicted with the reviewed in-process transport. Exactly zero account requests were reported; no inventory or sealed bundle exists. |
| Second V1 attempt | `AUTH-T07-GATE-L1-LAMBDA-INPROCESS-V2-2026-08-09`; source file `/Users/joseph/Downloads/T07_GATE_L1_V2_INPROCESS_AUTHORIZATION.md`, SHA-256 `91766bdba10d5aa8a516c0f455ed4ad34d5ae970c4b61f5db5ee09083c51e1c4`. | The supervisor exited through the generic secret-safe failure path. It emitted no request ledger, so whether a request was sent, which phase failed, and what response occurred are unknown. No validated inventory or sealed bundle exists. |

The second disposition must not be upgraded into a claim about the API key, Lambda
availability, endpoint, DNS, TCP, TLS, HTTP status, or provider behavior. The missing
observability is the defect.

The V1 plan and `RUN-T07-L1-LAMBDA-INVENTORY-0001` remain immutable historical
provenance. The public V1 executor now rejects every invocation; its old behavior is
reachable only through a private dummy-canary/fake-boundary regression fixture. The
V1 plan and both prior authorizations are superseded for future execution, not
deleted or rewritten.

## Replacement identities

| Field | Exact value |
|---|---|
| Plan ID | `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V2` |
| Run ID | `RUN-T07-L1-LAMBDA-INVENTORY-0002` |
| Attempt | `2` |
| Pending authorization placeholder | `AUTH-T07-GATE-L1-LAMBDA-INPROCESS-V3-PENDING` |
| Plan path | `containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v2.json` |
| Plan SHA-256 | `02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e` |
| Plan bytes | `8,856` |
| Request-ledger schema | `schemas/t07-lambda-request-ledger.schema.json` |
| Request-ledger schema SHA-256 | `e62dc6d333e581350f128b777c59bf5f9ffe5527a79909f69d1ef75195d2ea73` |

The pending placeholder is deliberately rejected by `InventoryRunBindingV2`. A
future execution needs a fresh user authorization reference and its SHA-256.

## Durable identity and ledger primitive

The future supervisor creates the fresh run identity before reading the ledger
schema or accessing a credential. It traverses or creates every ancestor with
directory-relative, no-follow operations; fsyncs each parent immediately after a new
child is linked; creates the run root exclusively; fsyncs its parent; and holds the
run descriptor while exclusively creating `request-ledger.jsonl` with append and
no-follow flags.

The run root itself is the durable identity tombstone. A schema/hash failure after
the root exists cannot be retried. When the ledger is unavailable before any request,
the supervisor attempts one fixed, exclusive, bounded disposition:

```text
artifacts/t07/lambda/gate-l1/preflight-dispositions/
  RUN-T07-L1-LAMBDA-INVENTORY-0002.json
```

The fixed name prevents UUID-based multiplication. Any object already occupying that
name burns the identity. Reuse, overwrite, truncation, sequence gaps, reordering,
duplicate JSON keys, and a second disposition all fail closed.

Before the secret source is invoked, the writer preallocates and fsyncs a
262,144-byte capacity file, fsyncs the run directory, and proves the numeric Mac mini
prewrite floor. Every event is schema checked, state checked, completely appended,
flushed, and fsynced before in-memory state advances. Terminal sealing fsyncs and
sets the ledger read-only; capacity-reservation removal and its parent fsync are part
of successful sealing.

## Request-state evidence

The supervisor commits and fsyncs, in order:

```text
request_intent_committed
request_send_started
```

before entering the transport. The evidence meanings are intentionally limited:

| Durable prefix | Allowed conclusion |
|---|---|
| No intent | The request was definitely not attempted. |
| Intent without send-started | The request was prepared but not sent. |
| Send-started without a durable terminal event | Network outcome unknown; never replay this run/request identity. |

This is not an exactly-once network claim.

The observer records normalized status/content type, bounded byte progress at no more
than four fixed 64-KiB thresholds, body completion, and response validation before
the next request intent. Status/content continuity, nondecreasing elapsed time and
bytes, exact ordinal/path/query-key identity, per-response byte limits, and complete
failure triples are checked both online and when reading a ledger offline.

Raw headers, authorization values, cookies, arbitrary exception text, query values,
environment dumps, and raw response bodies are forbidden ledger fields. Query 1 is
recorded as path `/api/v1/audit-events` plus query-key name `resource_type`; its value
is not retained.

The closed failure-stage enum is:

```text
secret_source, dns, tcp_connect, tls_handshake, request_write,
response_headers, response_body, http_status, redirect, rate_limit,
content_type, response_size, json_decode, schema_validation, pagination,
ledger_io, archive_io, unknown
```

A generic crash after send-started records
`request_outcome_unknown_after_send` when the ledger remains writable. If the ledger
itself becomes unwriteable, all existing bytes are preserved without truncation or
repair and the identity remains burned.

## Secret-safe failure boundary

The secret source is lazy and is invoked only after ledger creation, capacity,
implementation, repository, storage, and wall-budget checks pass. Only
`LAMBDA_API_KEY` is declared. `SIRA_API_KEY` and `OPENAI_API_KEY` remain rejected
fallbacks.

The public supervisor does not rethrow a transport or ledger exception. It reduces
the exception to the closed category/status/byte fields, completes ledger recovery,
clears the credential and raw response references, exits the catch/finally boundary,
and only then raises a new closed exception. Thus the new exception has no raw cause,
context, or credential-bearing transport traceback. Dummy-canary tests scan messages,
reprs, nested exception chains, every traceback frame's primitive locals, ledgers,
dispositions, artifacts, stdout/stderr, and archive evidence.

## Incremental validation and sealing

Every response is strict-JSON parsed, schema checked, pagination checked, and
normalized before the next intent. Raw bodies remain bounded and memory-only, are
overwritten by a later completed fetch, and are cleared at the supervisor boundary.
A continuation marker, malformed JSON, schema drift, status error, redirect,
content-type error, byte cap, or deadline stops without a further request.

Archive finalization has two phases to avoid a self-attesting ledger:

1. `archive_started` is fsynced.
2. The validated inventory is copied to a fresh external partial directory and
   verified under held storage descriptors.
3. `archive_passed` records that non-ledger staging passed.
4. `run_stopped` is appended; the complete ledger is sealed and validated.
5. The finalizer copies that terminal ledger, creates exact `COPY_RECORD.json` and
   `SEAL.json`, fsyncs, atomically renames, rereads, and verifies the bundle.
6. A separate local verification record binds every destination hash and storage
   identity.

Gate L2 eligibility requires the complete local/external evidence set, eight response
validation events, no unknown outcome, exact inventory/plan/run/authorization/ledger/
implementation bindings, exact approved volume UUIDs, and an eligible selection. A
partial finalization or missing local verification record is ineligible even when the
terminal ledger truthfully says staging passed.

## Scope boundary

All tests used fake in-process transports, synthetic JSON, synthetic storage
observations, and a public dummy token. They validate the control plane, not live
network behavior, the real credential, provider availability, or kernel/filesystem
durability under power loss.

During Gate L1.1 there was no Lambda/account/model API call, real-secret access,
cloud mutation, paid resource, SSH, Docker/container action, browser action, SiRA
execution, experimental condition, or scientific interpretation.
