# T07 Gate L1A SSH-key fingerprint authorization packet

Status: **unauthorized; ready for a fresh one-request authorization**

Date: 2026-08-10

This packet authorizes nothing by itself. It is the reviewed contract for one future
read-only account request whose only purpose is to match the three already-known
Lambda account key names to local public-key files. It cannot authorize Gate L2,
resource mutation, SSH, or paid compute.

## Immutable identities

- Reviewed implementation commit:
  `2a0bea7e34e7a6838e62bb1ac5c94686335ff23a`
- Plan ID: `PLAN-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1`
- Run ID: `RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001`
- Plan path:
  `containers/sira-smoke/lambda/gate-l1a-ssh-key-fingerprint-plan-v1.json`
- Plan bytes: 12,448
- Plan SHA-256:
  `23b29823b8daf94cfb463b275149ed562656c735955a4f449b8703334de531bc`
- API base URL: `https://cloud.lambda.ai`
- Exact operation: `GET /api/v1/ssh-keys`, no query
- Transport:
  `giclab.harness.lambda_inventory_v3.LambdaHttpsInventoryTransportV3`, in-process
  HTTPS only
- Supervisor:
  `giclab.harness.lambda_ssh_key_executor.execute_authorized_ssh_key_fingerprint`
- Archive driver:
  `giclab.harness.lambda_ssh_key_archive.DurableSSHKeyArchiver`
- Shell-free entrypoint wrapper:
  `/Users/joseph/.codex/worktrees/84b1/gic-lab/containers/sira-smoke/lambda/run_gate_l1a.py`
- Pending reference:
  `AUTH-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1-PENDING`

The future execution commit must be a clean direct descendant of the reviewed
implementation commit, and every plan-bound artifact hash must remain exact. A fresh
authorization must name the exact clean execution commit and a non-pending
authorization reference.

The future operator must invoke the committed source-loading wrapper with the exact argument
array below; the two values supplied by the fresh authorization are shown as typed
placeholders because no authorization exists in this packet:

```text
[
  "/Users/joseph/.codex/worktrees/84b1/gic-lab/.venv/bin/python",
  "/Users/joseph/.codex/worktrees/84b1/gic-lab/containers/sira-smoke/lambda/run_gate_l1a.py",
  "--repository-root",
  "/Users/joseph/.codex/worktrees/84b1/gic-lab",
  "--plan",
  "/Users/joseph/.codex/worktrees/84b1/gic-lab/containers/sira-smoke/lambda/gate-l1a-ssh-key-fingerprint-plan-v1.json",
  "--plan-sha256",
  "23b29823b8daf94cfb463b275149ed562656c735955a4f449b8703334de531bc",
  "--expected-commit",
  "<exact-clean-execution-commit-named-by-the-user>",
  "--implementation-commit",
  "2a0bea7e34e7a6838e62bb1ac5c94686335ff23a",
  "--authorization-reference",
  "AUTH-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1-2026-08-10",
  "--authorization-sha256",
  "<sha256-of-the-exact-user-authorization-record>"
]
```

The credential is never an argument. The entrypoint reads only `LAMBDA_API_KEY` from
the approved in-process environment channel after ledger, repository, storage, and
archive preflight pass.

## Source and schema locks

- OpenAPI 3.1.0 / Lambda API 1.10.0, 239,644 bytes, SHA-256
  `365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded`;
- response schema SHA-256
  `3cceae5b7fdea392cd16197533c32fb9a240dcdd6bff734f25db31c0baae615c`;
- private fingerprint-evidence schema SHA-256
  `a7a940a12f4a77895661b9e11883495c7f1efc89a4e65609e842777d8c8864a7`;
- sanitized match-report schema SHA-256
  `666ef981556b3f90759d45b7a48b6627951dd7f10518f9de748f4c1e5ac09925`;
- request-ledger schema SHA-256
  `4f2916e96a4453370f9621b7c78e4e53f7bb67a296e379bff4a79b5fe71d8557`.

## Exact caps

| Surface | Hard cap |
|---|---:|
| Account requests | 1 GET |
| Raw response | 131,072 bytes |
| Request ledger | 49,152 bytes; 24 events; 9 request events; 2,048 bytes/event |
| Preflight disposition | 16,384 bytes |
| Local raw/private evidence | 196,608 bytes |
| Sanitized match report | 16,384 bytes |
| Local verification | 65,536 bytes |
| External sealed bundle | 524,288 bytes |
| Aggregate retained | 1,048,576 bytes; component maxima sum to 999,424 bytes |
| Provider wall | 30 seconds |
| Archive wall | 60 seconds |
| Total wall | 150 seconds |
| Local processes | 15 calls; 37,879,810 output bytes |
| Local creates | 7 files |
| External creates | 7 files; 4 directories |
| Automatic retries, pagination, redirects followed | 0 each |
| Mutation, provider cost, model calls/tokens, browser, SSH, private-key reads, SiRA | 0 each |

The Mac mini prewrite floor is 8,590,868,480 bytes and retained floor is
8,589,934,592 bytes. The external volume must meet its dynamic retained floor plus
524,288 bytes.

## Execution and stop contract

Before secret access, the operator must verify the exact branch/commit/clean tree,
implementation ancestry and hashes, plan and schema hashes, fresh run identity,
missing local/external run roots, ledger capacity, current UTDM/APFS/physical-store
identity, no-follow path hierarchy, free-space floors, and no internal fallback.

Only `LAMBDA_API_KEY` may be accessed through the nonlogging in-process secret
channel. The ledger must durably record `request_intent_committed` and
`request_send_started` before the transport. The request runs once, with no query,
redirect, retry, or pagination. Any unknown post-send outcome burns the run and stops.

Stop on HTTP/auth/rate-limit/content-type/size/JSON/schema/candidate-name drift,
private or unsupported key material, multiple-key input, duplicate-name conflict,
ledger failure, storage drift, archive failure, or a requirement for another request.
Never infer a missing match.

On success, the plan-bound supervisor resolves the current UID through the passwd
database and inspects only that exact held no-follow `~/.ssh/*.pub` scope and
same-stem metadata;
open no private-key file and use no agent or SSH process. Seal the raw/private and
sanitized evidence locally, copy it one way to the approved external archive, verify
all hashes, fsync and atomically finalize, then require a passed post-ledger
`archive-finalization.jsonl` disposition. The request ledger proves staging only and
can never make an incomplete archive eligible. Retain the source and stop before Gate
L2.

## Ready-to-copy authorization block

```text
Continue T07 with Gate L1A SSH-key fingerprint recovery only.

I authorize exactly one read-only Lambda account request under plan
PLAN-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1, run
RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001, at
containers/sira-smoke/lambda/gate-l1a-ssh-key-fingerprint-plan-v1.json,
12,448 bytes, SHA-256
23b29823b8daf94cfb463b275149ed562656c735955a4f449b8703334de531bc.

The execution must use branch phase-1/sira-smoke-lambda on the exact clean commit I
name in this authorization. Reviewed implementation commit
2a0bea7e34e7a6838e62bb1ac5c94686335ff23a must be an ancestor and every plan-bound
artifact hash must remain unchanged. Use authorization reference
AUTH-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1-2026-08-10.

The operator may access only LAMBDA_API_KEY through the documented nonlogging
in-process secret channel and issue exactly one GET to
https://cloud.lambda.ai/api/v1/ssh-keys with no query, once, with no redirect follow,
pagination, or retry. The fresh fsync-backed ledger and run root are mandatory.

Caps are: 1 GET; 131,072 response bytes; 49,152 ledger bytes; 24 ledger events;
9 request events; 2,048 bytes/event; 16,384 preflight-disposition bytes; 196,608
private-evidence bytes; 16,384 sanitized-report bytes; 65,536 verification bytes;
524,288 external-bundle bytes; 1,048,576 aggregate retained bytes; 30 seconds provider
wall; 60 seconds archive wall; 150 seconds total wall; 15 local process calls;
37,879,810 local process-output bytes; 7 local and 7 external file creates; and
4 external directory creates. All retry, pagination, redirect-follow, mutation,
provider-cost, model-call/token, browser, SSH, private-key-read, and SiRA caps are zero.

Revalidate APFS UUID 8478609D-FA37-4ED5-875D-47AE912B9151 and physical-store UUID
7904A6F1-F483-4ED7-9E34-BFECAB31C63E through held no-follow descriptors; enforce the
8,590,868,480-byte Mac mini prewrite floor, 8,589,934,592-byte retained floor, and
dynamic external floor plus 524,288 bytes; prohibit internal fallback; verify every
source/destination SHA-256; fsync and atomically finalize; and retain the local source.

Inspect only ~/.ssh/*.pub contents and same-stem private-file metadata. Do not open a
private key, invoke an SSH agent or SSH process, print/commit a public-key body, raw
provider key ID, exact fingerprint, or exact home path, or select/use an account key.
Stop after the sealed sanitized match disposition. Gate L2 remains unauthorized.

This authorization permits no cloud mutation, key/firewall change, instance launch
or termination, paid compute, SSH, model/provider-model call, browser, container,
SiRA, scientific execution, or scientific-field change. It forbids SIRA_API_KEY and
OPENAI_API_KEY. Stop on any contract failure; never replay the run identity and never
begin Gate L2.
```

The copied block still requires the user to insert/name the exact clean execution
commit in the same current-turn authorization. No authorization exists until then.
