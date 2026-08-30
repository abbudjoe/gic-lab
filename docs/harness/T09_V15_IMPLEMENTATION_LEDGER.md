# T09 V15 provider-entry normalization implementation ledger

Status: **repeated-slot-closeout-repair-complete-exact-head-validation-in-progress**.
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
- Repeated-slot host-preflight closeout repair commit:
  `9b1ea06da0530128add702575e72212016d5cc47`.
- Fresh V15 package commit: `19c768f318f7e57f5a9a33beca5311f0534dc1b9`.
- Active V15 clean-package compatibility commit:
  `276ee1753a5efe5033a86451124fb805a256616d`.
- Historical V14 parity-node compatibility commit:
  `bfe65c75afe080bec3affcf03b63d0f20500d48c`.
- V14 stopped disposition: 3,390 bytes, SHA-256
  `71d7a78dac976d131f5e45cb8a2ff1aabe657c2423535322a4a570a9f792947e`.
- V15 plan: 20,292 bytes, SHA-256
  `b7bd2832623789f968b9830ae10f074eb18c71dcd45575918ab134c42473b8b3`.
- V15 runtime profile: 15,974 bytes, SHA-256
  `64075a67989522495145bf02c32544bd3a07f30c38d46daa4e9f5c16c65faa1d`.

## Definition-of-done ledger

| ID | Contract | Status | Evidence |
| --- | --- | --- | --- |
| V15-DOD-01 | Preserve V14 evidence and terminal cleanup | met | Sanitized hash-bound record; prior closeout remains authoritative |
| V15-DOD-02 | Unify provider-entry authority validation | met | One direct/retained resolver and one semantic reconstruction |
| V15-DOD-03 | Normalize a complete collision-free authority closure | met | Held exact copy, typed manifest, immediate retained validation |
| V15-DOD-04 | Bind three exact replacement hashes | met | Eligibility, source-evidence, and normalized-manifest reconstruction |
| V15-DOD-05 | Keep normalization before live authority | met | Ordering regression records normalization before credentials, GETs, POST, and capability use |
| V15-DOD-06 | Support repeated bounded slots | met | Provider-entry and host-preflight slot 1 to 2 to 3 production paths |
| V15-DOD-07 | Fail closed on unsafe or contradictory evidence | met | Tamper, type, mode, ownership, link, cap, plan, host, slot, and closeout cases |
| V15-DOD-08 | Preserve cleanup priority | met | Normalization failure does not duplicate or regress provider/security cleanup |
| V15-DOD-09 | Preserve V14 cleanup/idempotence controls | met | Historical lifecycle and resume regressions retained |
| V15-DOD-10 | Create fresh V15 identities with unchanged science | met | V15 package, equal pair selectors, semantic science equality |
| V15-DOD-11 | Keep flags false and create no run root | met | Schema and filesystem assertions |
| V15-DOD-12 | Pass focused/full/static/parity/site/privacy gates | met | 226 focused tests pass; raw full and exact parity are classified below; static, privacy, diff, and 16-page site gates pass |
| V15-DOD-13 | Perform Sol/max self-review without delegation | met | Direct/retained, ordering, cleanup, identity, and science review |
| V15-DOD-14 | Open and monitor one draft PR | partial | Local exact-head handoff is complete; independent review remains required |
| V15-DOD-15 | Preserve immutable eligibility history | met | Shared publisher retains the predecessor and publishes exact slot-suffixed current receipts |
| V15-DOD-16 | Resume terminal host closeout idempotently | met | Byte-identical source, receipt, journal, and eligibility snapshots; zero live mutations on retry |

## Exact-head validation record

The prior exact-head record applied to reviewed head
`3edd3aae130a92a43209cbe8307783f196bd27a2` and is superseded by the repeated-slot
repair. Focused production-path, negative-history, V15 package, Ruff, and targeted
strict-mypy gates pass. Full, parity, privacy, and portable-site results will be
recorded in a descendant validation commit after this rebound package is immutable.

No live secret, metadata, provider, cloud, Docker, browser, SiRA, evaluator, or
scientific execution occurred. Category 3 remains unauthorized.
