# T07 Lambda host controls

This directory contains the design-only Gate L0 source locks and unauthorized plans.

- `gate-l1-readonly-inventory-plan.json` is the exact, unauthorized, GET-only L1
  inventory contract. The separately authorized future supervisor is
  `src/giclab/harness/lambda_inventory.py`; import and Gate L0 tests perform no request.
- `public-source-observations.json` binds the public API and qualification-image
  metadata inspected during Gate L0. No account API or payload was fetched.
- `adversarial-containment.sh` is a future Gate L2 fixture source. It was not run in
  Gate L0 and is not a standalone containment boundary.

No executable Gate L2 launch plan may be added until an authorized L1 inventory has
produced the exact account, workspace, instance type, region, provider image, SSH-key,
firewall-ruleset, price, and pre-existing-instance bindings and
`src/giclab/harness/lambda_archive.py` has copied the redacted evidence to the approved
external archive with verified hashes and a retained local copy record.
