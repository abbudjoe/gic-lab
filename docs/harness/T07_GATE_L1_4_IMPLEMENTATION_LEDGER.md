# T07 Gate L1.4 implementation ledger

Status: **in-progress**

Branch: `phase-1/sira-smoke-lambda`

Required starting commit:
`ae0ec40cb2da067a66f1a8d3d0e5aca857fd9491`

This ledger maps the offline Gate L1.4 design contract to implementation and
evidence. Gate L1A remains unauthorized; no account request, real-secret access,
SSH operation, cloud mutation, or paid compute is permitted by this work.

| ID | Definition-of-done item | Status | Planned evidence |
|---|---|---|---|
| L14-01 | Reverify the exact branch, clean baseline, sealed run-0003 evidence, ignored alias map, three sanitized SSH-key candidates, and five scientific hashes before editing. | met | Read-only Git, SHA-256, ignore, external-seal, and structural checks recorded in the design closeout. |
| L14-02 | Pin the current first-party `GET /api/v1/ssh-keys` contract, including its URL, version, bytes, retrieval time, digest, required fields, types, and extension behavior. | met | Bounded in-process public-documentation read and source record. |
| L14-03 | Implement strict in-process OpenSSH, RFC4716, PKCS8/SPKI public-key, and PEM RSA public-key parsing with standard OpenSSH SHA-256 fingerprints. | in-progress | Focused parser fixtures and independent vectors. |
| L14-04 | Reject private, malformed, unsupported, ambiguous, multi-key, duplicate-name-conflict, and incompatible response evidence; collapse only exact repeated account rows. | not-started | Negative fixtures and typed response projection tests. |
| L14-05 | Create inventory-local opaque account aliases without persisting raw API IDs or public-key bodies in public output. | not-started | Schema validation, deterministic alias tests, and privacy scans. |
| L14-06 | Implement held-no-follow `~/.ssh/*.pub` discovery, same-stem metadata-only inspection, and standard-fingerprint comparison without opening private-key bytes. | not-started | File-race, symlink, nonregular, open-spy, and match-state tests. |
| L14-07 | Define private evidence and sanitized public match-report schemas with unique/no/ambiguous/invalid outcomes and an explicit user-approval boundary. | not-started | Draft 2020-12 schema checks and positive/negative fixtures. |
| L14-08 | Create a fresh one-GET, no-query, no-pagination, no-redirect, no-retry, in-process HTTPS plan with finite request, ledger, evidence, archive, process, file, output, and wall caps. | not-started | Typed plan loader, exact-shape assertions, fresh run identity, and prior-run nonreplay tests. |
| L14-09 | Bind a fresh request-ledger, run root, private evidence manifest, sanitized report, storage guards, and one-way external archive contract. | not-started | Plan/schema/source hashes and fake-only evidence-flow tests. |
| L14-10 | Update the Gate L1.4 design, authorization packet, Lambda README, Phase 1 plan, decision log, readiness record, Gate L2 decision packet, and sanitized notebook note. | not-started | Repository diffs and closeout assertions. |
| L14-11 | Preserve every prior run/plan/evidence byte and all locked scientific fields. | not-started | Hash regressions and baseline-diff checks. |
| L14-12 | Pass focused tests, all Lambda regressions, schema/repository/privacy gates, Ruff, strict mypy, and the accepted portable-Quarto full check. | not-started | Command results recorded after execution. |
| L14-13 | Obtain a clean independent spec-conformance, privacy, and SSH-safety review; repair findings and rerun the full post-review gate. | not-started | Reviewer verdict, repairs, and final gate results. |
| L14-14 | Commit a clean Gate L1.4 design while leaving Gate L1A unauthorized and Gate L2 blocked. | not-started | Final branch, commit, and empty `git status --short`. |

## Terminal contract

The only acceptable closeout state is:

```text
Gate L1.4 design complete
one-request Gate L1A unauthorized
cloud mutation false
paid compute false
prototype execution false
Gate L2 blocked
no account request made
no real secret accessed
```
