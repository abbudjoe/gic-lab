# T07 Gate L2M firewall-baseline capture authorization packet

Status: **authorization consumed; run burned; high-assurance track frozen**

Date: 2026-08-11

This packet is preserved as historical provenance for the one consumed read-only
capture. Run `RUN-T07-L2M-FIREWALL-BASELINE-CAPTURE-0001` may not be replayed, this
text may not be reused as authorization, and the frozen track has no successor plan.
It cannot authorize any request, firewall mutation, or manual qualification.

## Exact identities

| Item | Identity |
|---|---|
| Branch | `phase-1/sira-smoke-lambda` |
| Consumed clean execution commit | `34f26a78272329421f2691be2dcd46ecc842b28f` |
| Reviewed implementation commit | `7e199dc634cee955b00fc587728a14c46cdf232a` |
| Plan ID | `PLAN-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1` |
| Run ID | `RUN-T07-L2M-FIREWALL-BASELINE-CAPTURE-0001` |
| Plan path | `containers/sira-smoke/lambda/manual-console/gate-l2m-firewall-baseline-capture-plan-v1.json` |
| Plan bytes | 6,311 |
| Plan SHA-256 | `bd61aed7ed1da74ad39ed24c56145d9e816e7ab9b2063f2c962e1cfb79d8a63b` |
| Ledger schema SHA-256 | `3b0456ef742d8a02f5465dc04f176fe189b2f8538d2d4895a4098ea17c987ee0` |
| Private baseline schema SHA-256 | `19db331e5b9437187305b7131dd585d6fc99548ad241e9a8d294ef6b8b379e43` |
| Canonical report schema SHA-256 | `7cca0d07b4c24a454a959ff579553743f0136c81fe4695ea25026ddf137756a1` |
| Restoration payload schema SHA-256 | `b1dca29f4912cd24338b3475c667421eb10bae1ef64da67ce058a5299ce8261c` |
| Public contract record SHA-256 | `c1ead1802013f611e1c9d533a8495f12cbb18f9213889ff1c7299502690036f8` |
| Consumed authorization | `AUTH-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1-2026-08-11-34F26A7` |

## Exact operation and transport

The sole provider operation is:

```text
GET https://cloud.lambda.ai/api/v1/firewall-rulesets/global
```

It runs once through the in-process
`giclab.harness.lambda_l2m_observer.LambdaHttpsL2MObserverTransport`. Curl, wget,
shell HTTP, HTTP subprocesses, redirects, pagination, and retries are zero. The only
secret name is `LAMBDA_API_KEY`; it is read in process after nonsecret preflight and
ledger reservation, and never printed, hashed, persisted, returned, or passed to a
child. `SIRA_API_KEY` and `OPENAI_API_KEY` remain forbidden.

The exact shell-free invocation is the plan's `capture_invocation` array with these
four placeholders replaced only by the fresh authorization:

```text
<EXACT-PLAN-SHA256-FROM-FRESH-AUTHORIZATION>
<EXACT-FINAL-CLEAN-L2M-1-HANDOFF-COMMIT>
<FRESH-AUTHORIZATION-REFERENCE>
<FRESH-AUTHORIZATION-SHA256>
```

## Exact caps

| Category | Cap |
|---|---:|
| Account GETs | 1 |
| Raw response | 262,144 bytes |
| Ledger | 65,536 bytes |
| Ledger events | 24 |
| Per event | 4,096 bytes |
| Local artifact aggregate | 1,048,576 bytes |
| External archive | 2,097,152 bytes |
| Provider wall | 60 seconds |
| Archive wall | 60 seconds |
| Total wall | 180 seconds |
| Retry / pagination / redirect | 0 / 0 / 0 |
| Cloud mutation / paid compute | 0 / USD 0.00 |
| SSH / Jupyter / browser / container | 0 / 0 / 0 / 0 |
| Model calls / tokens / SiRA executions | 0 / 0 / 0 |

Local prewrite free space is at least 8,725,200,896 bytes and retained free space at
least 8,589,934,592 bytes. The external target is the approved
`/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts`, bound to APFS Data UUID
`8478609D-FA37-4ED5-875D-47AE912B9151` and physical-store UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`. The dynamic retained floor plus the archive
cap must pass. Held no-follow descriptors, atomic finalization, one-way copy,
source/destination SHA-256 verification, local-source retention, and no internal
fallback are mandatory.

## Stop conditions

Stop before the secret on any branch, commit, cleanliness, plan/hash, implementation,
run freshness, archive freshness, mount identity, topology, symlink, ownership, or
free-space failure. A hard total deadline is armed, and absolute deadlines are checked
again before secret access, request send, and archive entry; the archive also has its
own hard 60-second wall. Stop after the sole GET on transport uncertainty, non-200 status,
unexpected content type, byte cap, malformed JSON, envelope/ruleset/rule schema drift,
unknown material rule fields, ledger failure, seal failure, or archive failure. Never
replay the run identity. No outcome authorizes a PATCH or Gate L2M.

## Historical authorization text — consumed; do not copy

The following text is retained only to explain the historical boundary. Its run and
authorization identities are consumed and nonreplayable. It must not be completed,
copied as fresh authority, or used to access the provider.

```text
Continue T07 with the read-only global-firewall baseline capture only.

I authorize exact clean commit <EXACT-FINAL-CLEAN-L2M-1-HANDOFF-COMMIT> on branch
phase-1/sira-smoke-lambda, a descendant of reviewed implementation commit
7e199dc634cee955b00fc587728a14c46cdf232a, to execute plan
PLAN-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1, run
RUN-T07-L2M-FIREWALL-BASELINE-CAPTURE-0001, at
containers/sira-smoke/lambda/manual-console/gate-l2m-firewall-baseline-capture-plan-v1.json,
6,311 bytes, SHA-256
bd61aed7ed1da74ad39ed24c56145d9e816e7ab9b2063f2c962e1cfb79d8a63b.
Use fresh authorization reference
AUTH-T07-GATE-L2M-FIREWALL-BASELINE-CAPTURE-V1-<CURRENT-DATE-OR-NONCE>.

The operator may access only LAMBDA_API_KEY through the documented nonlogging
in-process channel and issue exactly one GET to
https://cloud.lambda.ai/api/v1/firewall-rulesets/global with no redirect, pagination,
or retry. Enforce the exact plan caps, mandatory fsync-backed ledger, complete private
raw-response retention, description-aware validation, exact private restoration
payload, held-descriptor APFS/UTDM archive contract, source/destination hash
verification, source retention, and no internal fallback.

This permits zero cloud mutation, paid compute, SSH, Jupyter, browser/container/model/
SiRA/scientific execution, and forbids SIRA_API_KEY and OPENAI_API_KEY. Stop after the
capture disposition. Do not begin Gate L2M, Gate L3, Gate L4, or the experiment.
```
