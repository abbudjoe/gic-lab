# T07 bounded-smoke V2 implementation ledger

Status: **complete; ready for bounded-smoke V2 authorization; unauthorized**

Starting commit: `36cfda4ea19ea4d4735d1caeba7f7e4797a769ae`

Reviewed implementation commit: `a7ca7475177aee60126e39c631d61e3d9453ca85`

Plan: `PLAN-T07-BOUNDED-SIRA-SMOKE-V2`, 43,198 bytes, SHA-256
`f0d635783d719d1c5cb5df5351eaf8f6f54e9049da1f2565e4227e66f48ef511`.

## Assembly definition-of-done map

| ID | Contract obligation | Evidence | Status |
|---|---|---|---|
| V2-01 | Verify the exact branch, clean starting commit, V1 plan bytes/hash, reviewed ancestor, 34 V1 bindings, absent V1 roots, and locked scientific hashes before editing. | Recorded starting checks and immutable-hash regression. | met |
| V2-02 | Privately locate and preserve the retained input without exposing values. | Regular/no-follow/ignored historical input retained byte-for-byte; no V1 binding existed because V1 stopped before its write. | met |
| V2-03 | Assign one closed ruleset-name classification and one closed restoration classification. | `stale_high_assurance_name`; `materializer_baseline_bug`. | met |
| V2-04 | Determine stale-input versus implementation cause. | Overall cause `both`; direct V1 abort isolated to canonicalizer parity failure. | met |
| V2-05 | Repair only the defective naming/baseline materialization boundary. | Domain-separated fresh marker generation, independent private locator, exact upstream decision/baseline seal hashes, authoritative canonical form, typed baseline/seal separation, and exact pre-sealed-binding consumption. | met |
| V2-06 | Generate one new private binding from the current protected decision and frozen closeout identities. | Public-safe alias/SHA and V2 schema; protected value-aware validation. | met |
| V2-07 | Enforce fresh path, regular/no-follow/mode 0600, outside-Git retention. | A separately generated locator that is not derivable from the public alias/hash, exact local-root checks, local file/seal guards, focused tests, and live local verification. | met |
| V2-08 | Seal and copy the binding one-way to the approved external archive. | Held descriptors, volume/floor checks, staged verification before claims, fsync, atomic finalization, destination reread/hash equality, local success seal, source retention, exact owned-state failure cleanup, and no fallback. | met |
| V2-09 | Preserve V1 plan/run identities while issuing unique V2 plan/host/condition/authorization identities and roots. | Exact V1 hash test and V2 identity/root validators. | met |
| V2-10 | Keep the new plan executable but unauthorized and bind exact implementation/schema hashes. | V2 plan schema, `authorized: false`, zero current execution permissions, exact reviewed ancestor `a7ca7475177aee60126e39c631d61e3d9453ca85`, and exact artifact table. | met |
| V2-11 | Preserve every scientific field, model route, budget, condition order, spend cap, evidence rule, cleanup rule, and residual limitation. | Byte hashes plus V1-to-V2 science/limit equality tests. | met |
| V2-12 | Cover all 17 required stale/fresh/hash/version/privacy/materialization/regression cases with local fakes only. | Focused V2 and bounded-supervisor regression suite, including exact upstream-seal tamper rejection, direct builder/sealer, pre/post-rename cleanup, exact local/external preseal, nonderivable paths, reviewed-ancestor, and active-governance tests. | met |
| V2-13 | Keep protected values out of source, docs, notebook, plan, stdout, and Git. | Value-aware scan of all changed/public files: zero hits; generic credential scans. | met |
| V2-14 | Run schema/repository validation, Ruff, strict mypy, and the full portable-Quarto gate. | Validation record below. | met |
| V2-15 | Obtain independent scientific-scope, privacy, spend, lifecycle, and cleanup review; repair and rereview. | Independent review record below. | met |
| V2-16 | Commit on `phase-1/sira-smoke-bounded`, leave a clean tree, and stop before authorization/execution. | Final Git identity and status checks at handoff. | met |

## Validation record

- Focused V2 plan/private-binding/supervisor/active-authority suite: 131 passed.
- The regenerated V2 plan binds 34 artifacts with zero byte/hash mismatches; its
  scientific lock, full limit map, and per-condition budgets equal V1 exactly.
- The final private binding and its complete local/external seal were reverified
  in-process against the current implementation, APFS/UTDM identities, permissions,
  byte equality, hashes, floors, and no-internal-fallback contract.
- V1 plan preservation: 55,789 bytes and SHA-256
  `0128e632e0a3a01f7ee0b9014396fed5782c8afa98459fe9ad4db5cc7db3148f`.
- Repository contract validation: passed.
- Candidate protected-value scan: zero hits across 15 private value/identity classes;
  no private locator, path, or local-seal identity was emitted.
- Ruff and strict mypy: passed.
- Offline full `make check` with the accepted portable Quarto 1.9.38 path: 1,185
  tests, repository validation, 16-page notebook render, and site validation passed.
  Quarto emitted only the repository's known non-fatal external-output-path warning.

## Independent review

Final independent rereview: **CLEAN; no remaining P0/P1/P2 findings**. The review
covered the source contract line by line, the `both` adjudication, exact upstream
decision/baseline seal identities, private-value handling, V1 immutability, V2
freshness, unchanged science/budgets/spend, materializer failure behavior, archive
durability, cleanup authority, and absence of execution. It independently rehashed
V1, V2, the supervisor, and all 34 plan-bound artifacts; reran the 131-test focused
suite and full 1,185-test portable-Quarto gate; and confirmed zero private-value hits
and all current authority fields false.

## Execution boundary

No real secret or account endpoint was accessed. No Lambda/OpenAI/public-IP request,
cloud mutation, paid compute, SSH, Jupyter, container, browser, SiRA condition, or
scientific execution occurred. The V2 plan is unauthorized and Gate execution remains
blocked on a fresh user authorization naming the final clean commit.
