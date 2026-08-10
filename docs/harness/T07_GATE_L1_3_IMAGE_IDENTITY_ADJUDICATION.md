# T07 Gate L1.3 image-identity adjudication

Status: **complete offline; run 0003 preserved; Gate L2 unauthorized**

Date: 2026-08-10

This adjudication supplements the immutable Gate L1 run. It does not rewrite the
request ledger, inventory, extension report, external seal, or copy record. No
authenticated request or real-secret access was needed.

## Bound evidence

| Item | Exact identity |
|---|---|
| Run | `RUN-T07-L1-LAMBDA-INVENTORY-0003` |
| Inventory | `artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0003/inventory-redacted.json`, 59,653 B, SHA-256 `022835438165e7e6e70dc992d6904f4e8b9448dc933d1d4c3e39ebdcc8914933` |
| Request ledger | `artifacts/t07/lambda/gate-l1/RUN-T07-L1-LAMBDA-INVENTORY-0003/request-ledger.jsonl`, 32,287 B, 44 events, SHA-256 `1f94068bdb1d1d2af0075d50c1a0c06eb1c077d4128f90bdc16fd571fa6af707` |
| Canonical extension report | 1,863 B, SHA-256 `20f035039e633e5ef81c544f439b8fac6dc08ee4dafce1eacd2646df0e3a9263` |
| External seal | SHA-256 `3347b8d03d0f937111de92ef79286c7fbcb02027f652f35ba42ac337cf8f7bd5` |
| External copy record | SHA-256 `76d8511282962cb6fdc4f72a63eaf41e7e63239acb9fa38e030f51057cb8a0e7` |

The original `/api/v1/images` response body was not retained. The sealed redacted
inventory does retain the schema-validated image rows, including provider IDs, and was
therefore sufficient for private identity adjudication. Provider IDs were never
printed or committed.

## Exact classification

The defect is `verifier_key_bug`.

The official OpenAPI `Image` schema describes `Image.id` as the unique image
identifier and `region` as availability. The historical verifier treated every
per-region availability row as though it required a globally unique row identity.
The observed structure is:

| Structural fact | Count |
|---|---:|
| Image rows | 259 |
| Unique official image IDs | 124 |
| Opaque public aliases | 124 |
| IDs appearing once | 109 |
| IDs appearing in ten regions | 15 |
| Repeated-ID availability groups | 15 |
| Exact same-ID/same-region duplicate groups | 0 |
| Exact duplicate extra rows | 0 |
| Conflicting intrinsic-metadata groups | 0 |
| Family/name groups containing distinct IDs | 7 |

Thus, the response did not contain conflicting identities and did not require a
weaker schema. The correct representation is one image identity per official
`Image.id`, with a set of regional availability records. Identical family/name values
do not merge distinct IDs.

## Privacy-preserving repair

`src/giclab/harness/lambda_l13_security.py` assigns one inventory-local alias in the
form `img-NNNN` to each ID. Assignment uses sorted raw-ID order so the frozen Gate L0
final tie-break remains deterministic without publishing an ID or ID-derived token.
The public projection contains aliases and approved image metadata only. A repeated ID
with different name, family, version, or architecture fails closed; a same-region
exact duplicate may collapse only with explicit multiplicity and source indices.

The reversible mapping is local, ignored, exclusive-create, fsync-backed, read-only
evidence:

| Item | Exact identity |
|---|---|
| Map | `artifacts/t07/lambda/gate-l1-3/RUN-T07-L1-LAMBDA-INVENTORY-0003/image-id-alias-map.json`, 9,476 B, SHA-256 `9f37b9412110cc7433d5339cf4d8b1eadc92743eaa32db6bf8e4c59024a79d5f` |
| Seal | `artifacts/t07/lambda/gate-l1-3/RUN-T07-L1-LAMBDA-INVENTORY-0003/IMAGE_ALIAS_MAP_SEAL.json`, 340 B, SHA-256 `ed3fb1ef3323f2b37150204ef060250e4f9510bbeb976d18d2fd1b8d9894c0b5` |

Both paths are excluded by the repository's `artifacts/` ignore rule. Creation walks
the exact repository-contained run path through held no-follow directory descriptors,
uses exclusive dirfd-relative writes, fsyncs file and directory state, and rejects
path escape or symlink ancestors. The authoritative consumer opens both files through
the same no-follow hierarchy, verifies the public byte/hash record and seal, and
requires every private raw-ID/alias pair to equal the independently recomputed
projection. The committed adjudication contains the map hash required by the contract
but no raw ID, individual raw-ID hash, or reversible token.

## Source identity

The first-party OpenAPI observation is version 1.10.0 at
`https://docs.lambda.ai/api/cloud/spec.json`, retrieved
2026-08-10T14:18:11.958474Z, 239,644 B, SHA-256
`365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded`.
`containers/sira-smoke/lambda/public-security-observation-l1-3.json` records the
source facts and retrieval contract.

## Resulting boundary

The versioned Gate L1.3 consumer revalidates the full immutable request ledger,
inventory schema and provenance, canonical extension-report identity, local and
external archive records, seal, storage floors, private alias map, public adjudication
schemas, repaired alias/availability projection, and fixed candidate matrix. It does
not change the historical V3 plan, parser, schema, run, or scientific protocol. Mock
and offline tests validate this control-plane representation; they make no claim about
provider execution or kernel containment.
