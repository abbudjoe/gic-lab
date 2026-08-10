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
- `gate-l1-readonly-inventory-plan-v3.json` is the byte-preserved seven-GET
  contract executed successfully under the now-consumed V4 authorization: plan
  `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V3`, run
  `RUN-T07-L1-LAMBDA-INVENTORY-0003`, SHA-256
  `b5ec82aaa84882a7c3269ebdb695a6c694f891d66d367c05f82eaf9797515331`.
  It removes audit-history and account-LRN retrieval, binds a separate response schema
  for every retained endpoint, accepts only compatible additive keys while retaining
  no unknown values, treats every non-null continuation as a stop, and requires the
  V3 ledger/archive contracts before Gate L2 eligibility. Run 0003 completed all seven
  GETs with HTTP 200/schema-valid outcomes and was sealed to the approved external
  archive. The plan/run are historical and must not be replayed.
- `endpoint-schemas-v3/` contains the seven pinned response contracts. Import and
  fake-transport tests in `lambda_*_v3.py` perform no account request and use no real
  credential.
- `public-source-observations.json` binds the public API and qualification-image
  metadata inspected during Gate L0. No account API or payload was fetched.
- `public-security-observation-l1-3.json` binds the unauthenticated OpenAPI/firewall
  documentation used for the offline image-identity and firewall adjudication.
- `adversarial-containment.sh` is a future Gate L2 fixture source. It was not run in
  Gate L0 and is not a standalone containment boundary.

No executable Gate L2 launch plan may be added yet. Gate L1.3 repaired the image
identity projection and derived six policy-qualifying type/region/image-alias tuples,
with an authoritative consumer that binds each alias to the ignored no-follow sealed
provider-ID map and revalidates the immutable ledger, extension report, archive, and
public adjudication. The global rules remain non-strict and no regional ruleset
exists; any future design must preserve both strict global rules and the separately
governed same-region additive ruleset, plus instance termination before restoration.
In addition, the sealed inventory intentionally contains account SSH-key names
without their public-key material. The required local/account fingerprint match is therefore
`evidence_unavailable`. Gate L2 remains blocked by the exact decisions and evidence
gap in `docs/harness/T07_GATE_L2_RESOURCE_AND_SECURITY_DECISION_PACKET.md`. The
official launch contract does not require an account LRN; the project records it as
unavailable rather than querying broad account history.
