# T09 V15 provider-entry normalization implementation ledger

Status: **implementation-complete-local-validation-complete-pr-review-required**.
Category 1 only.

```text
operator_attested_model: gpt-5.6-sol
operator_attested_effort: max
runtime_model_introspection_required: false
implementation_delegated: false
```

Implementation, review, tests, repository writes, Git operations, and scientific
decisions were not delegated. ChatGPT exact-head review remains external and required.

## Immutable implementation record

- Core repair commit: `f5750d1d8e3fe5f03450210fe95f652d2e8f4288`.
- Explicit V15 contract registration commit:
  `8e2f55beb617fdb05d2e01a72f91f7cf6958a9f5`.
- Fresh V15 package commit: `19c768f318f7e57f5a9a33beca5311f0534dc1b9`.
- Active V15 clean-package compatibility commit:
  `276ee1753a5efe5033a86451124fb805a256616d`.
- Historical V14 parity-node compatibility commit:
  `bfe65c75afe080bec3affcf03b63d0f20500d48c`.
- V14 stopped disposition: 3,390 bytes, SHA-256
  `71d7a78dac976d131f5e45cb8a2ff1aabe657c2423535322a4a570a9f792947e`.
- V15 plan: 19,927 bytes, SHA-256
  `b597b610a65dcaa733eb02e184a4ae5af5846ff5d22b0e09d04a30044d86c921`.
- V15 runtime profile: 15,624 bytes, SHA-256
  `db25a49105d1075c42fe58114a0c35dd099e7b6a67b33ff1f979220168154676`.

## Definition-of-done ledger

| ID | Contract | Status | Evidence |
| --- | --- | --- | --- |
| V15-DOD-01 | Preserve V14 evidence and terminal cleanup | met | Sanitized hash-bound record; prior closeout remains authoritative |
| V15-DOD-02 | Unify provider-entry authority validation | met | One direct/retained resolver and one semantic reconstruction |
| V15-DOD-03 | Normalize a complete collision-free authority closure | met | Held exact copy, typed manifest, immediate retained validation |
| V15-DOD-04 | Bind three exact replacement hashes | met | Eligibility, source-evidence, and normalized-manifest reconstruction |
| V15-DOD-05 | Keep normalization before live authority | met | Ordering regression records normalization before credentials, GETs, POST, and capability use |
| V15-DOD-06 | Support repeated bounded slots | met | Offline slot 1 to 2 and slot 2 to 3 flows |
| V15-DOD-07 | Fail closed on unsafe or contradictory evidence | met | Tamper, type, mode, ownership, link, cap, plan, host, slot, and closeout cases |
| V15-DOD-08 | Preserve cleanup priority | met | Normalization failure does not duplicate or regress provider/security cleanup |
| V15-DOD-09 | Preserve V14 cleanup/idempotence controls | met | Historical lifecycle and resume regressions retained |
| V15-DOD-10 | Create fresh V15 identities with unchanged science | met | V15 package, equal pair selectors, semantic science equality |
| V15-DOD-11 | Keep flags false and create no run root | met | Schema and filesystem assertions |
| V15-DOD-12 | Pass focused/full/static/parity/site/privacy gates | met | 226 focused tests pass; raw full and exact parity are classified below; static, privacy, diff, and 16-page site gates pass |
| V15-DOD-13 | Perform Sol/max self-review without delegation | met | Direct/retained, ordering, cleanup, identity, and science review |
| V15-DOD-14 | Open and monitor one draft PR | partial | Local exact-head handoff is complete; independent review remains required |

## Exact-head validation record

- Focused replacement-normalization, cleanup-lifecycle, provider-contract,
  accounting, metadata, cidfile, and finalizer selection: 226 passed with zero
  skips or xfails.
- The complete selected T09 suite has one inherited failure because the ignored
  historical T07 launch fixture is absent from a fresh worktree. Its five
  historical private-evidence nodes remain opt-in skips; no V15 test is skipped
  or xfailed.
- Raw full pytest: 1,792 passed, 23 inherited/environmental failures, and five
  inherited private-evidence skips.
- Exact base/head parity, with the five private nodes symmetrically deselected:
  base 1,755 passed / 27 failed across 1,782 nodes; head 1,792 passed / 23
  failed across 1,815 nodes. All 33 head-only nodes pass, four inherited
  failures become passing, and there are zero newly failing nodes, zero missing
  base nodes, and zero invalid transitions. `parity_passed` is true.
- Ruff formatting and lint, strict mypy over 65 source files, lock integrity,
  repository validation, `git diff --check`, and exact-head `make ci-check`
  pass.
- Portable Quarto 1.9.38 renders and validates all 16 notebook pages.
- Added-line privacy scans find zero high-risk token or private-key matches. The
  only literal credential assignments are three explicit fake test fixtures;
  no binary changed file is present.
- Both V15 machine pair diffs are valid with equal explicit V15 selectors, the
  V14/V15 scientific projections are equal, every V15 authorization/execution
  flag is false, and no V15 run root exists.

No live secret, metadata, provider, cloud, Docker, browser, SiRA, evaluator, or
scientific execution occurred. Category 3 remains unauthorized.
