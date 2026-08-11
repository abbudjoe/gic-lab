# T07 high-assurance infrastructure closeout

Status: **candidate closeout; private materialization pending**

Date: 2026-08-11

## Decision

The T07 high-assurance infrastructure track is being frozen, not deleted. Its purpose
was to seek production-grade containment, launch recovery, credential isolation,
resource cleanup, and reconstruction evidence before the one-pair research smoke. It
found real control-plane defects and preserved reusable controls, but the accumulated
production-orchestration requirements are not all prerequisites for a bounded research
smoke.

The final track state is `high-assurance-infrastructure-frozen`. The next planned work
is a separately reviewed child branch, `phase-1/sira-smoke-bounded`. This closeout does
not create or authorize that branch's execution plan, and T07 remains unexecuted.

## Firewall capture adjudication

Burned capture `RUN-T07-L2M-FIREWALL-BASELINE-CAPTURE-0001` retains one complete
HTTP-200 response and a ten-event request ledger. The original terminal disposition
remains `schema_drift`. Offline adjudication classifies the response as
`compatible_additive_top_level_extension`: the documented envelope and required
global-ruleset fields are present, all four rules pass the strict description-aware
canonicalizer, and the sole additive data-level field is response metadata whose name
and JSON type may be reported while its value remains private.

The pinned first-party OpenAPI 3.1.0/API 1.10.0 document is 240,288 bytes, SHA-256
`320f4877924984f060b179e86595ed58918a1d0696b60b99cae548ec164934f4`. It does not
explicitly forbid additive properties on the global-ruleset data object. The PATCH
request contains only `rules`; response metadata is excluded.

Public-safe records:

- `docs/harness/evidence/T07_FIREWALL_CAPTURE_0001_OFFLINE_ADJUDICATION.json`,
  SHA-256 `894d609ff45aa3e3d1d9ea73da175c32198fc336cebe629e7124ae2841304cd5`;
- `docs/harness/evidence/T07_FIREWALL_CAPTURE_0001_STRUCTURAL_REPORT.json`,
  SHA-256 `3d1082138711560b809276d46912c22e8b6dedec8323f1323729356aebbc4887`.

No private firewall scalar, workspace identity, provider resource value, or source
network is present in either record.

## Authoritative private baseline

| Item | Identity |
|---|---|
| Canonicalization version | `t07-firewall-canonical-v1` |
| Response parser version | `t07-firewall-response-v2` |
| Baseline alias | `l2m-firewall-baseline-b0ef71115811` |
| Canonical semantic SHA-256 | `b0ef711158113cdbdbb1707cb43f21a635271bb2e93bfc0e898ce7118589f764` |
| Restoration payload alias | `l2m-firewall-restoration-50ca7febe9f1` |
| Restoration payload SHA-256 | `50ca7febe9f160ada862371376485ea2ece11b373d25179ccd578d9c7acd42b8` |
| Local baseline-seal SHA-256 | `<PENDING_PRIVATE_MATERIALIZATION>` |
| External copy-record SHA-256 | `<PENDING_PRIVATE_MATERIALIZATION>` |
| External seal SHA-256 | `<PENDING_PRIVATE_MATERIALIZATION>` |

The private baseline retains the exact provider response and every rule value. Its
restoration payload contains only protocol, port range when applicable, source
network, and exact description. Rule order is non-authoritative; duplicate
multiplicity and every description/protocol/port/source semantic are authoritative.
Missing and empty descriptions are distinct. Unknown rule-level fields fail closed.

The local source is retained. The final bundle must be copied one way through held
no-follow APFS descriptors, fsynced, atomically finalized, hash-verified, and sealed
on the approved external archive with no internal fallback.

## Completed controls and terminal negative results

Reusable completed controls include immutable GPT-4o snapshot routing, exact
reactive/simulative command comparison, aggregate and per-condition budgets, isolated
secret handling, fresh attempt roots, raw log/session retention, durable request
ledgers, read-only Lambda inventory, evidence hashing, provider termination checks,
and the repaired firewall baseline.

The terminal negative results remain evidence:

1. macOS process-group enumeration cannot prove descendant containment;
2. the Docker Desktop path remained blocked by first-start, storage, rollback, and
   vendor-state gaps;
3. the reviewed Colima/Lima runtime candidate was rejected;
4. automated Lambda launch was rejected because exactly-once recovery and a complete
   effecting supervisor could not be proven;
5. manual-console qualification was designed but never executed; and
6. request-ledger, schema, identity, and firewall-baseline evidence defects were found
   and repaired without executing SiRA.

No SiRA trajectory, browser task, model request, or scientific condition ran. The
scientific protocol, treatment/control assignment, reactive-first order, immutable
`gpt-4o-2024-11-20`, directional-reproduction label, and interpretation boundary are
unchanged.

## Occam admission rule

> A control is a bounded-smoke hard blocker only when its failure could make the
> comparison misleading, expose a credential/private value, materially exceed approved
> spending, leave a billable resource running, or prevent reconstruction of what
> happened.

Controls beyond that boundary remain valuable production hardening, but are deferred
and do not automatically block a separately governed bounded research smoke.

## Freeze boundary

Every execution permission remains false. The burned capture and manual-console plans
remain historical, immutable and nonreplayable. The typed project state and both
high-assurance preflight entry points reject the frozen track before credential access.
No fresh executable high-assurance plan or authorization block exists.

After the final clean closeout commit is known, the recommended local annotation is:

```bash
git tag -a t07-high-assurance-infrastructure-v1 <FINAL-CLEAN-CLOSEOUT-COMMIT> -m 'T07 high-assurance infrastructure v1'
```

This closeout does not create or push that tag.
