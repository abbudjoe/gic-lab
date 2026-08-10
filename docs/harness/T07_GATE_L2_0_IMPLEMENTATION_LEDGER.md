# T07 Gate L2.0 implementation ledger

Status: **blocked-human-or-source-decision**

Date: 2026-08-10

This assembly ledger maps the Gate L2.0 contract to observed evidence. `met` means
the offline obligation is complete; `partial` means a tested draft primitive exists
but no authoritative end-to-end control exists; `blocked` means the item prevents an
executable plan. Draft code and schemas are non-authoritative and non-executable.

## Definition-of-done ledger

| ID | Contract item | Status | Evidence / disposition |
|---|---|---|---|
| L20-01 | Exact branch, starting commit, clean tree, prior hashes, and locked scientific files | met | Starting checks passed at `314270ecd27115d801ea6348ac7653d30d56a884`; scientific hashes remained locked. |
| L20-02 | Validate private decision by owner, mode, no-follow, schema, nonce, public IPv4 `/32`, attestation, cost, and wall | met | Corrected 1,047-byte decision hash `0b109b0150eec8739e30e86e5f1318b60c818cc3974354c67dc35a4e2dffd4ea`; no private field printed. |
| L20-03 | Resolve selected candidate/key and raw IDs privately | met | Public alias `l2-decision-6cb543526ab1`; raw bindings remain in ignored evidence. |
| L20-04 | Seal private decision/parameters and copy one-way to approved external archive | met | V2 local/external seals and copy record are bound in the decision document; source retained. |
| L20-05 | Verify newest compatible selected image and key match | met | `img-0111` / `22.4.5-2141`; `fractal-lambda-codex` unique sealed match. |
| L20-06 | Pin current first-party Lambda contract | met | OpenAPI 1.10.0, 240,288 bytes, SHA-256 `320f4877924984f060b179e86595ed58918a1d0696b60b99cae548ec164934f4`. |
| L20-07 | Deterministic preloaded-agent access with no private-key read | partial | Argument and matching primitives are locally tested; there is no bounded process executor or held agent/key-path supervisor. |
| L20-08 | Exact strict SSH and run-owned `known_hosts` lifecycle | partial | Renderer/checkpoint helpers exist; no exclusive writer plus bounded SSH/keyscan lifecycle is implemented. |
| L20-09 | Global firewall snapshot/mutate/verify/restore transaction | partial | Typed bodies/state-machine helpers exist; no authoritative supervisor couples them to response validation, operation order, and evidence. |
| L20-10 | Same-region ruleset create/get/delete transaction | partial | Draft typed helpers and fake tests exist; same end-to-end enforcement gap remains. |
| L20-11 | Exact one-launch/no-filesystem body | partial | Private template and renderer are locally validated; repeated rendering is not prevented by one irreversible supervisor. |
| L20-12 | Unknown launch outcome safely resolves without replay | blocked | First-party schema makes ownership name/tags optional and supplies no strong-consistency, idempotency, or bounded-quiescence guarantee. Zero list results cannot prove no delayed launch. |
| L20-13 | Finite active/error/timeout polling | partial | State-machine unit tests exist; no provider-response semantic supervisor enforces them live. |
| L20-14 | Jupyter checkpoint freshness/challenge/instance binding | partial | Private schema and validators exist; future human step remains unexecuted and is not coupled to a bounded supervisor. |
| L20-15 | ED25519 scan equality before SSH | partial | Deterministic parsing/rendering is tested; no bounded keyscan executor or exclusive `known_hosts` writer exists. |
| L20-16 | Host observation allowlist and no host mutation | partial | Static command allowlist exists; process output/call/deadline enforcement and sensitive projection are incomplete. |
| L20-17 | Pin minimal x86_64 OCI image without pulling | met | BusyBox index/config/layer identities and compressed bytes are source-bound. |
| L20-18 | Exact no-network containment create/lifecycle arrays | partial | Invalid `--pid private` was removed; draft arrays remain unexecuted and kernel behavior unproven. |
| L20-19 | Whole-container TERM-to-KILL cleanup and zero residue | partial | Local state-machine tests exist; no runtime evidence has been collected and no authoritative lifecycle supervisor exists. |
| L20-20 | Provider termination before firewall restoration | partial | Draft state logic models the order; unknown accepted launch can lack an exact termination ID. |
| L20-21 | Provider terminal/nonbillable proof | blocked | Exact-ID terminal proof cannot be guaranteed when the launch result is unknown and the instance is not source-guaranteed discoverable. |
| L20-22 | Evidence transfer, complete eligibility, seal, and external archive | partial | Writer/archive primitives exist, but sealing does not require a complete ledger/success-or-incident set and the archive reopens paths after initial guarding. |
| L20-23 | Sensitive provider/process projection | blocked | No mandatory allowlisted projection prevents Jupyter fields, unrelated account data, or unrelated command lines entering evidence. |
| L20-24 | Exact enforceable aggregate calls, spacing, bytes, wall, cost, output, and storage | blocked | Numeric draft values exist, but no single supervisor enforces their aggregate contract; no executable caps are issued. |
| L20-25 | No raw ID/IP/fingerprint/private path in Git/output | met | Current public adjudication has local key records removed; its new hash is bound, while historical Git provenance remains. |
| L20-26 | Preserve prior sealed evidence and scientific fields | met | Ignored/external evidence and all locked EXP-0001 fields remain unchanged. |
| L20-27 | Required local fake/mocked tests | met | Focused and Lambda suites cover the draft primitives; they make no live-provider or kernel claim. |
| L20-28 | Independent spec/privacy/cloud/SSH/incident review | met | Review rejected readiness and identified the material source and control-plane blockers recorded here. |
| L20-29 | Create executable plan only if every source/privacy/control term is exact | met | No executable plan file exists; proposed V1/run-0001 identities are rejected and non-reusable. |
| L20-30 | End in exactly one permitted terminal state | met | `blocked-human-or-source-decision`; no authorization block and no additional design loop. |

## Draft implementation inventory

The following are retained only as offline, non-authoritative draft controls:

- `src/giclab/harness/lambda_l20_plan.py`;
- `src/giclab/harness/lambda_l2_execution.py`;
- `src/giclab/harness/lambda_l2_evidence.py`;
- `schemas/t07-lambda-l2-*.schema.json`;
- `tests/test_lambda_l20_plan.py`;
- `tests/test_lambda_l2_execution.py`;
- `tests/test_lambda_l2_evidence.py`.

The blocked draft schema encodes `executable_after_exact_authorization: false` and
`blocked-human-or-source-decision`. The repository contains no
`containers/sira-smoke/lambda/gate-l2-host-qualification-plan.json`.

## Review findings requiring a new plan

1. Source-backed discovery/termination after an unknown launch outcome.
2. One irreversible end-to-end supervisor for authorization, identities, order,
   cardinality, response semantics, aggregate quotas, cleanup, and no replay.
3. A bounded SSH/keyscan executor with held identities and exclusive known-hosts.
4. Mandatory allowlisted provider/process evidence projection.
5. Complete success/incident evidence eligibility and descriptor-held archive copy.
6. Empirical provider, SSH, Docker/kernel, billing, and storage evidence under a later
   separately authorized plan.

## Validation record

- Pre-review focused Gate L2 tests: passed.
- Pre-review complete Lambda regressions: passed.
- Pre-review full portable-Quarto `make check`: passed (767 tests).
- Independent review: completed; readiness rejected; blocked disposition required.
- Privacy repair: completed; current adjudication SHA-256
  `23ae723811cb15b2cbc1229592d507624c9107851fc883d9ce023464301631d0`.
- Post-repair focused suite: passed (128 tests).
- Private-scalar scan: 9 private values compared with 301 tracked/intended-add files;
  zero hits.
- Independent blocked-disposition rereview: clean; its local review included 74
  focused plan/execution/evidence tests, two policy/public-surface tests, Ruff, JSON
  parsing, and privacy checks without ignored-evidence or network access.
- Final post-review portable-Quarto `make check`: passed (768 tests), including lock,
  frozen sync, Ruff, strict mypy, repository validation, generated public views,
  16-page Quarto render, and site validation.

No Lambda/account/model request, secret access, cloud mutation, paid compute, SSH,
private-key read, Docker/container/browser, SiRA, or scientific execution occurred.
