# T07 Gate L1.4 implementation ledger

Status: **complete**

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
| L14-03 | Implement strict in-process OpenSSH, RFC4716, PKCS8/SPKI public-key, and PEM RSA public-key parsing with standard OpenSSH SHA-256 fingerprints. | met | Fixed-vector and format fixtures passed; fingerprints bind canonical SSH wire bytes. |
| L14-04 | Reject private, malformed, unsupported, ambiguous, multi-key, duplicate-name-conflict, and incompatible response evidence; collapse only exact repeated account rows. | met | Negative response/key fixtures and exact-repeat multiplicity tests passed. |
| L14-05 | Create inventory-local opaque account aliases without persisting raw API IDs or public-key bodies in public output. | met | Three deterministic aliases, schemas, repository hygiene, and 135-value added-surface scan with zero hits. |
| L14-06 | Implement held-no-follow `~/.ssh/*.pub` discovery, same-stem metadata-only inspection, and standard-fingerprint comparison without opening private-key bytes. | met | Production resolves the passwd-bound current-user home; fixture seams remain confined to `.ssh`; unique/no/ambiguous, symlink, nonregular, path-swap, and private-open-spy tests passed. |
| L14-07 | Define private evidence and sanitized public match-report schemas with unique/no/ambiguous/invalid outcomes and an explicit user-approval boundary. | met | Four Draft 2020-12 schemas plus relational recommendation semantics passed, including the false-recommendation regression. |
| L14-08 | Create a fresh one-GET, no-query, no-pagination, no-redirect, no-retry, in-process HTTPS plan with finite request, ledger, evidence, archive, process, file, output, and wall caps. | met | 12,448-byte plan SHA-256 `23b29823b8daf94cfb463b275149ed562656c735955a4f449b8703334de531bc`; typed loader, exact source-loading wrapper, and rendered-command test passed. |
| L14-09 | Bind a fresh request-ledger, run root, private evidence manifest, sanitized report, storage guards, and one-way external archive contract. | met | Plan-bound supervisor/archive composition; typed observed-failure and unknown-outcome separation; authoritative append-only post-ledger finalization disposition; fake end-to-end success/failure; concrete archive-driver tests; prewrite cap regression; ledger nonreuse; exclusive writers; and APFS/UTDM two-phase archive contract. |
| L14-10 | Update the Gate L1.4 design, authorization packet, Lambda README, Phase 1 plan, decision log, readiness record, Gate L2 decision packet, and sanitized notebook note. | met | Required files and public-surface closeout assertions present. |
| L14-11 | Preserve every prior run/plan/evidence byte and all locked scientific fields. | met | Historical plan verifier and authoritative run-0003 consumer passed; five scientific hashes and baseline diff remained exact. |
| L14-12 | Pass focused tests, all Lambda regressions, schema/repository/privacy gates, Ruff, strict mypy, and the accepted portable-Quarto full check. | met | Final focused suite 55 passed; all Lambda tests 241 passed; repository validation, formatting, Ruff, strict mypy, scientific-hash diff, and added public-surface privacy scan passed; post-review `make check` passed 694 tests and rendered/validated 16 pages with the accepted portable Quarto 1.9.38 binary. |
| L14-13 | Obtain a clean independent spec-conformance, privacy, and SSH-safety review; repair findings and rerun the full post-review gate. | met | Independent rereview at implementation anchor `2a0bea7e34e7a6838e62bb1ac5c94686335ff23a` approved all DoD items with no remaining spec, privacy, SSH-safety, evidence-integrity, or control-plane findings. |
| L14-14 | Commit a clean Gate L1.4 design while leaving Gate L1A unauthorized and Gate L2 blocked. | met | Final closeout commit and post-commit branch/clean-tree proof are returned to the user; the plan remains `authorized: false`, run 0001 is absent, and Gate L2 remains blocked. |

## Independent-review repair loop

The first independent review returned five findings and no approval. The repaired
control plane now:

1. binds a dedicated shell-free supervisor and compatible two-phase archive driver;
2. resolves production discovery from the current UID's passwd home instead of an
   arbitrary caller-supplied directory;
3. validates recommendation semantics relationally, not only structurally;
4. validates, encodes, sizes, hashes, and reserves every evidence component before
   the first evidence write; and
5. renders the exact command contract while reserving the mathematically
   non-self-referential clean execution commit for the final returned authorization
   block.

The second rereview identified three remaining control-plane defects. The follow-up
repair binds a repository-owned source-loading wrapper instead of relying on a stale
installed package; preserves typed DNS/TLS/HTTP/body failures as exact
`request_failed` events while reserving unknown outcome for an untyped post-send
crash; and makes an exclusive, append-only, fsync-backed post-ledger finalization
disposition the sole authority for complete archive evidence. Concrete temporary
volume tests now cover the durable archive driver as well as its post-copy-floor
failure.

The final reviewer found one additional evidence-accuracy issue: a typed response-body
failure carried exact sub-threshold bytes and timing, but terminal recovery used only
the coarser progress-ledger state. The final repair consistency-validates and retains
the typed bytes, status, content type, and elapsed time; a 123-byte failure and a
completed-response schema failure now prove the exact terminal metadata. Untyped
post-send crashes remain outcome-unknown.

The repaired implementation anchor is
`2a0bea7e34e7a6838e62bb1ac5c94686335ff23a`. The regenerated 12,448-byte plan has
SHA-256 `23b29823b8daf94cfb463b275149ed562656c735955a4f449b8703334de531bc`.
Independent rereview approved the result with no findings. The post-review full gate
passed 694 tests, repository/site validation, and a 16-page Quarto render.

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
