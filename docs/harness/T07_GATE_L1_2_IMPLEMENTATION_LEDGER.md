# T07 Gate L1.2 implementation ledger

Status: **implementation and packet assembled; new plan unauthorized**

Branch: `phase-1/sira-smoke-lambda`

Baseline: `258ccc3c524e96e0fadc3afc23a43fa40f6a7d7a`

Frozen implementation commit: `718c75c694b3033fa7ef2ed5e7c4696fd8c389f3`

Source contract: the user's 2026-08-10 “T07 Gate L1.2 — Audit-schema
adjudication and minimal inventory-plan repair” instruction.

## Definition-of-done ledger

| ID | Obligation | Status | Evidence |
|---|---|---|---|
| L12-01 | Prove exact branch, baseline, clean starting tree, V2 plan/schema/ledger hashes, missing V2 inventory/bundle, locked scientific hashes, and no secret need before editing. | met | Starting checks recorded in the adjudication document; immutable-hash regressions. |
| L12-02 | Locate the retained 18,058-byte body without exposing account data. | met | Run 0002 contains only its 6,652-byte request ledger; raw body state is `absent`. |
| L12-03 | Preserve the original run and ledger; create a separate machine-readable adjudication. | met | `docs/harness/evidence/T07_RUN_0002_HISTORICAL_SCHEMA_ADJUDICATION.json`; V1/V2/run-0002 hash tests. |
| L12-04 | When the body is absent, do not invent a fixture or exact mismatch. | met | Classification is `unadjudicated_raw_body_absent`; no structural report or raw-value copy exists. |
| L12-05 | Pin and analyze the first-party public OpenAPI contract. | met | OpenAPI 1.10.0 observation, 239,644 B, SHA-256 `365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded`; endpoint schemas. |
| L12-06 | Minimize the inventory to the seven Gate-L2-required GETs and remove audit history/account-LRN retrieval. | met | `lambda_cloud_v3.py`; V3 plan; endpoint-order/no-audit/no-account-LRN tests. |
| L12-07 | Apply a conservative endpoint-specific external-schema policy. | met | Seven response schemas; strict required/type checks; additive-name/type-only reporting; pagination hard stops. |
| L12-08 | Retain no unknown scalar, audit value, public key, instance IP, Jupyter credential, or unrelated tag value. | met | Typed redaction plus positive-source/negative-retained privacy fixtures and canary scans. |
| L12-09 | Create fresh immutable V3/0003 identities without modifying prior plans/runs. | met | `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V3`; `RUN-T07-L1-LAMBDA-INVENTORY-0003`; plan V3 at SHA-256 `b5ec82aaa84882a7c3269ebdb695a6c694f891d66d367c05f82eaf9797515331`. |
| L12-10 | Recalculate finite caps for seven requests. | met | V3 plan and schemas; exact cap assertions; aggregate retained 1,826,816 B. |
| L12-11 | Bind implementation/schema hashes and prove the final execution commit descends from the reviewed implementation. | met | Frozen implementation manifest; exact clean-commit guard; `git merge-base --is-ancestor`; pre-secret equality/ancestry tests; Gate-L2 cross-binding tests. |
| L12-12 | Create typed structural, extension, and inventory schemas. | met | Four V3 core schemas plus seven endpoint schemas; meta-schema and repository tests. |
| L12-13 | Make a non-null continuation token a pagination stop with no follow-up request. | met | Parser and fake-supervisor tests cover ordinary, empty-string, zero, empty-array, and empty-object tokens. |
| L12-14 | Keep complete raw responses memory-only and make incomplete evidence Gate-L2-ineligible. | met | V3 parser/supervisor/archive; raw persistence false; terminal-ledger and evidence revalidation tests. |
| L12-15 | Cross-bind endpoint outcomes, schema/extension hashes, selection, ledger response bytes, plan, authorization, commits, and archive hashes. | met | `lambda_archive_v3.py`; adversarial Gate-L2 tamper matrix. |
| L12-16 | Preserve local/external held-descriptor, floor, fsync, hash, atomic-finalize, and source-retention contracts. | met | Versioned V3 archive driver; concrete local fake-volume lifecycle and drift tests. |
| L12-17 | Exercise every required local deterministic test class with no external transport. | met | V3 schema/adjudication/parser/supervisor/archive suites plus full Lambda regression. |
| L12-18 | Update decision, plan, readiness, project state, Lambda README, L2 requirements, and public notebook with sanitized infrastructure-only state. | met | Files listed below; no scientific result or protocol change. |
| L12-19 | Produce an unauthorized V4 packet and stop before authorization. | met | `docs/harness/T07_GATE_L1_V4_AUTHORIZATION_PACKET.md`; pending authorization placeholder remains invalid. |
| L12-20 | Independent spec-conformance and privacy review, repairs, rereview, and post-review full gate. | met | Reviewer found ancestry/evidence/privacy gaps; repairs added; final implementation review clean. Final full-gate record below. |

## Assembly mapping

- Adjudication and privacy: L12-02 through L12-08.
- Parser, schema, and plan: L12-05 through L12-14.
- Evidence retention and Gate L2 eligibility: L12-11, L12-14 through L12-16.
- Governance and handoff: L12-01, L12-09, L12-17 through L12-20.

No requirement is partial. Gate L1 execution itself is intentionally blocked because
the new plan is unauthorized; Gate L2 is blocked until a separately authorized V3 run
produces a complete validated and externally sealed inventory.

## Created files

- `containers/sira-smoke/lambda/gate-l1-readonly-inventory-plan-v3.json`
- `containers/sira-smoke/lambda/public-openapi-observation-v3.json`
- `containers/sira-smoke/lambda/endpoint-schemas-v3/*.schema.json`
- `schemas/t07-lambda-audit-structural-report.schema.json`
- `schemas/t07-lambda-schema-extension-report.schema.json`
- `schemas/t07-lambda-inventory-v3.schema.json`
- `schemas/t07-lambda-request-ledger-v3.schema.json`
- `src/giclab/harness/lambda_cloud_v3.py`
- `src/giclab/harness/lambda_inventory_plan_v3.py`
- `src/giclab/harness/lambda_request_ledger_v3.py`
- `src/giclab/harness/lambda_inventory_v3.py`
- `src/giclab/harness/lambda_archive_v3.py`
- `tests/test_lambda_inventory_v3.py`
- `tests/test_lambda_archive_v3.py`
- `docs/harness/evidence/T07_RUN_0002_HISTORICAL_SCHEMA_ADJUDICATION.json`
- `docs/harness/T07_GATE_L1_2_AUDIT_SCHEMA_ADJUDICATION.md`
- `docs/harness/T07_GATE_L1_2_IMPLEMENTATION_LEDGER.md`
- `docs/harness/T07_GATE_L1_V4_AUTHORIZATION_PACKET.md`

## Updated files

- `tests/test_harness_schemas.py`
- `tests/test_phase1_closeout.py`
- `containers/sira-smoke/lambda/README.md`
- `docs/exec-plans/active/PHASE_1_ARTIFACT_EXECUTION.md`
- `docs/DECISIONS.md`
- `docs/STORAGE_POLICY.md`
- `docs/readiness/PHASE_1_SMOKE_READINESS.md`
- `docs/PROJECT_STATE.yaml`
- `docs/harness/T07_GATE_L2_HOST_QUALIFICATION_AUTHORIZATION_PACKET.md`
- `docs/harness/T07_GATE_L3_B2B_REQUIREMENTS.md`
- `notebook/weekly/2026-08-08-phase-1.qmd`

## Validation and review record

All commands were run with `LAMBDA_API_KEY`, `SIRA_API_KEY`, and `OPENAI_API_KEY`
removed from the child environment. Fake in-process transports and public dummy
canaries were the only credential/request fixtures.

| Gate | Result |
|---|---|
| Focused V3 inventory/archive/schema suite | passed |
| Full Lambda inventory and request-ledger regression | passed |
| V1/V2 plan and run-0002 immutable-hash checks | passed |
| Plan loading, implementation-hash verification, schema meta-validation | passed |
| Repository validation and `git diff --check` | passed |
| Ruff format/check and strict mypy | passed |
| Sensitive-value and secret-canary negative scans | passed |
| Independent implementation spec/privacy rereview | clean; no findings remain |
| Portable-Quarto `make check` | passed; 604 tests plus render/site validation |
| Post-document independent spec/privacy review | clean; no findings remain |

## Terminal state

```text
Gate L1.2 complete
historical run 0002 preserved and adjudicated
new V3 plan unauthorized
new run 0003 unexecuted
cloud mutation false
paid compute false
prototype execution false
Gate L2 blocked
no account request made
no real secret accessed
```
