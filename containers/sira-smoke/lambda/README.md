# T07 Lambda host controls

This directory contains the design-only Gate L0 source locks and unauthorized plans.

- `gate-l1-readonly-inventory-plan.json` is the byte-preserved historical V1 GET-only
  contract. Both V1 authorizations are blocked evidence; run
  `RUN-T07-L1-LAMBDA-INVENTORY-0001` is permanently retired, and the public V1
  execution entry point is disabled.
- `gate-l1-readonly-inventory-plan-v2.json` is the fresh, unauthorized V2 contract:
  plan `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V2`, run
  `RUN-T07-L1-LAMBDA-INVENTORY-0002`, SHA-256
  `02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e`.
  A future exact authorization would use the in-process supervisor in
  `src/giclab/harness/lambda_inventory_v2.py`, the durable request ledger in
  `src/giclab/harness/lambda_request_ledger.py`, and the four-file seal contract in
  `src/giclab/harness/lambda_archive_v2.py`. Import and local fake-transport tests
  perform no account request.
- `public-source-observations.json` binds the public API and qualification-image
  metadata inspected during Gate L0. No account API or payload was fetched.
- `adversarial-containment.sh` is a future Gate L2 fixture source. It was not run in
  Gate L0 and is not a standalone containment boundary.

No executable Gate L2 launch plan may be added until an authorized L1 inventory has
produced the exact account, workspace, instance type, region, provider image, SSH-key,
firewall-ruleset, price, and pre-existing-instance bindings and
`src/giclab/harness/lambda_archive_v2.py` has copied the redacted evidence and complete
validated request ledger to the approved external archive with verified hashes and a
retained local copy record.
