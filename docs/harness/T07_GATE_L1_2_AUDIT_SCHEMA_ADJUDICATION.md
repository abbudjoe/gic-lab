# T07 Gate L1.2 audit-schema adjudication

Status: **complete offline; historical run 0002 preserved; V3 plan unauthorized**

Date: 2026-08-10

This gate adjudicates the evidence from the stopped V2 plan/run 0002 and
repairs only the future read-only inventory contract. It made no authenticated
account request and did not access a real secret.

## Starting identities

| Item | Exact identity |
|---|---|
| Branch | `phase-1/sira-smoke-lambda` |
| Baseline | `258ccc3c524e96e0fadc3afc23a43fa40f6a7d7a` |
| Historical plan | `PLAN-T07-GATE-L1-LAMBDA-READONLY-INVENTORY-V2` |
| Historical plan SHA-256 | `02d83cb6e303242dec9261146488adfa2b2b026605edc48a95e1fe9ec3b9229e` |
| Historical run | `RUN-T07-L1-LAMBDA-INVENTORY-0002` (burned; no replay) |
| Historical ledger | `artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0002/request-ledger.jsonl` |
| Historical ledger bytes / SHA-256 | 6,652 / `a1cb81ce286881c33d879ce73787e755eed8ecd1f64ca2b9eaca7d39824a2c94` |
| V2 ledger schema SHA-256 | `e62dc6d333e581350f128b777c59bf5f9ffe5527a79909f69d1ef75195d2ea73` |

The V1 and V2 plans and the run-0002 ledger remain byte-identical. The ledger is a
read-only regular file. The locked EXP-0001 protocol, configuration, smoke profile,
reactive plan, and simulative plan remain at their recorded hashes; no scientific
field was changed.

## Retained-response disposition

The complete 18,058-byte response body does **not** exist under the immutable run-0002
root. The ledger is the only retained regular file. Therefore no raw structural
analyzer was run and no structural report was fabricated. Exact live-response
adjudication is impossible from retained evidence.

The original ledger remains unchanged and continues to record:

```text
GET /api/v1/audit-events?resource_type=cloud.api_key
HTTP 200
18,058 response bytes
542 ms elapsed
request_failed(schema_drift)
outcome unknown after send: false
```

The additive adjudication record is
`docs/harness/evidence/T07_RUN_0002_HISTORICAL_SCHEMA_ADJUDICATION.json`. It binds the
historical plan and ledger hashes, records the missing raw-body state, and classifies
the mismatch as `unadjudicated_raw_body_absent`. It does not alter or rehabilitate the
historical ledger. Run 0002 is incomplete, Gate-L2-ineligible, and permanently
nonreplayable.

## Official public contract

The first-party public contract identity used for future parsing is:

| Field | Exact value |
|---|---|
| Documentation | `https://docs-api.lambda.ai/api/cloud` |
| Machine-readable specification | `https://docs.lambda.ai/api/cloud/spec.json` |
| Declared version | OpenAPI `1.10.0` |
| Bytes | 239,644 |
| SHA-256 | `365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded` |
| Byte/hash retrieval | `2026-08-09T20:36:01Z` |
| Public-doc revalidation | `2026-08-10T11:35:38Z` |

The current rendered first-party page still advertises OpenAPI 1.10.0. The byte count
and SHA-256 are the prior exact public-spec retrieval, not an inferred hash of the
rendered page. `containers/sira-smoke/lambda/public-openapi-observation-v3.json`
preserves this distinction.

For audit events, the documented success envelope requires `data` and `page_token`;
`data` is an array and `page_token` is a required string-or-null value. The documented
event contract requires the eleven fields listed in the Gate L1.2 source contract and
permits the documented nullable LRN fields. Additive properties are not explicitly
forbidden by the observed public schema.

## Sanitized mismatch analysis

No claim is made about the missing live body. Independently, source inspection proved
that the historical V2 parser was narrower than the official public contract: it
required an exact eighteen-field event object, including seven fields not required by
the public contract, and attempted to derive a workspace/account binding that the
launch contract does not require. This is a documented parser-contract incompatibility,
but it cannot establish which structural difference occurred in the missing live body.

The historical adjudication category therefore remains exactly
`unadjudicated_raw_body_absent`, not `implementation_schema_bug`, provider failure, key
failure, or API failure.

## Endpoint minimization decision

Audit history is not needed to design Gate L2. It is potentially sensitive, paginated
account history and supplies no required launch field. The fresh plan therefore removes
it and makes no replacement identity or account-history request.

The exact V3 endpoint order is:

1. `GET /api/v1/instance-types`
2. `GET /api/v1/images`
3. `GET /api/v1/regions`
4. `GET /api/v1/ssh-keys`
5. `GET /api/v1/firewall-rulesets`
6. `GET /api/v1/firewall-rulesets/global`
7. `GET /api/v1/instances`

An account LRN is recorded as `unavailable_not_required`. Gate L2 must bind the exact
V3 authorization, plan, implementation/execution commits, seven endpoint outcomes,
sealed inventory hash, ledger hash, and the resource IDs later approved by the user.

## External-schema compatibility policy

Each endpoint has its own schema. The future parser requires the documented envelope,
required fields, types, and nullability. Missing or type-incompatible required data is
a hard stop. Additive object keys are accepted only where the official schema does not
forbid them; only their names, JSON value types, locations, and structural hashes may
enter the extension report. Unknown scalar values never enter retained output or
authoritative project fields.

Any non-null continuation value, including an empty string or empty container, is
`pagination_present`. Any `has_more` value other than exactly false or null is also a
stop. The plan authorizes zero follow-up pagination requests. A compatible additive
extension is recorded as `compatible_extension_observed`; it does not broaden the
redacted inventory.

Known sensitive fields—including SSH public-key material, instance public/private IPs,
Jupyter credentials, and unrelated tag values—are schema-validated in memory and
dropped from retained inventory. Raw responses are never persisted.

## Terminal boundary

Gate L1.2 performed only public-document inspection, local source/evidence inspection,
hashing, fake-transport tests, and repository validation. It made zero Lambda/account/
model API requests, accessed zero real secrets, and performed zero cloud mutation,
paid compute, SSH, browser, container, SiRA, or scientific execution. The fresh V3
plan and run 0003 remain unauthorized and unexecuted; Gate L2 remains blocked.
