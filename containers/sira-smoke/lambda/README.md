# T07 Lambda host controls

This directory contains the design-only Gate L0 source locks and unauthorized plans.

- `gate-l1-readonly-inventory-plan.json` is the byte-preserved historical V1 GET-only
  contract. Both V1 authorizations are blocked evidence; run
  `RUN-T07-L1-LAMBDA-INVENTORY-0001` is permanently retired, and the public V1
  execution entry point is disabled.
- `gate-l1-readonly-inventory-plan-v2.json` is the byte-preserved historical V2
  contract:
  plan `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V2`, run
  `RUN-T07-L1-LAMBDA-INVENTORY-0002`, SHA-256
  `02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e`.
  Its authorization and run are blocked historical provenance. The run
  durably observed one HTTP-200 audit response but stopped at `schema_drift`; its raw
  body was not retained, so the additive adjudication is
  `unadjudicated_raw_body_absent`. The run identity is permanently retired.
- `gate-l1-readonly-inventory-plan-v3.json` is the fresh, unauthorized seven-GET
  contract: plan `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V3`, run
  `RUN-T07-L1-LAMBDA-INVENTORY-0003`, SHA-256
  `b5ec82aaa84882a7c3269ebdb695a6c694f891d66d367c05f82eaf9797515331`.
  It removes audit-history and account-LRN retrieval, binds a separate response schema
  for every retained endpoint, accepts only compatible additive keys while retaining
  no unknown values, treats every non-null continuation as a stop, and requires the
  V3 ledger/archive contracts before Gate L2 eligibility. It remains unauthorized and
  unexecuted.
- `endpoint-schemas-v3/` contains the seven pinned response contracts. Import and
  fake-transport tests in `lambda_*_v3.py` perform no account request and use no real
  credential.
- `public-source-observations.json` binds the public API and qualification-image
  metadata inspected during Gate L0. No account API or payload was fetched.
- `adversarial-containment.sh` is a future Gate L2 fixture source. It was not run in
  Gate L0 and is not a standalone containment boundary.

No executable Gate L2 launch plan may be added until a separately authorized V3 L1
inventory has produced the exact instance type, region, provider image, SSH-key,
firewall-ruleset, price, and pre-existing-instance bindings and
`src/giclab/harness/lambda_archive_v3.py` has copied the redacted evidence and complete
validated request ledger to the approved external archive with verified hashes and a
retained local copy record. The official launch contract does not require an account
LRN; the project records it as unavailable rather than querying broad account history.
