# T07 Gate L1.4 SSH-key fingerprint design

Status: **design complete; one-request Gate L1A unauthorized; Gate L2 blocked**

Date: 2026-08-10

## Scope and preserved evidence

This offline gate designs the minimum account read needed to close the remaining
SSH-key identity gap. It made no account request and did not access a real secret.
Runs 0001, 0002, and 0003 remain immutable and nonreplayable.

The required starting state was verified before editing:

- branch `phase-1/sira-smoke-lambda`, clean baseline
  `ae0ec40cb2da067a66f1a8d3d0e5aca857fd9491`;
- run-0003 inventory SHA-256
  `022835438165e7e6e70dc992d6904f4e8b9448dc933d1d4c3e39ebdcc8914933`;
- run-0003 request-ledger SHA-256
  `1f94068bdb1d1d2af0075d50c1a0c06eb1c077d4128f90bdc16fd571fa6af707`;
- external `SEAL.json` SHA-256
  `3347b8d03d0f937111de92ef79286c7fbcb02027f652f35ba42ac337cf8f7bd5`;
- external `COPY_RECORD.json` SHA-256
  `76d8511282962cb6fdc4f72a63eaf41e7e63239acb9fa38e030f51057cb8a0e7`;
- historical post-run adjudication SHA-256 at the L1.4 baseline
  `95b08f6e9345aa09ba4b81dcb6b70484ca0a4d2a964cc553f2a3ae4fe96ee782`;
- current privacy-minimized public adjudication SHA-256
  `23ae723811cb15b2cbc1229592d507624c9107851fc883d9ce023464301631d0`;
  the historical Git object and sealed evidence remain preserved;
- ignored alias map, 9,476 bytes, SHA-256
  `9f37b9412110cc7433d5339cf4d8b1eadc92743eaa32db6bf8e4c59024a79d5f`;
- ignored alias seal, 340 bytes, SHA-256
  `ed3fb1ef3323f2b37150204ef060250e4f9510bbeb976d18d2fd1b8d9894c0b5`.

The only sanitized account SSH-key candidates remain `aic-codex-lambda`,
`codex-fawx-20260527`, and `fractal-lambda-codex`. Their state remains
`evidence_unavailable`; this design does not select one.

The five scientific hashes remain:

- protocol: `5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c`;
- config: `f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d`;
- smoke profile: `ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425`;
- reactive condition: `7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018`;
- simulative condition: `68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436`.

## Official response contract

The first-party machine-readable contract was retrieved in process from
`https://docs.lambda.ai/api/cloud/spec.json` at
`2026-08-10T15:59:37.767582Z`:

| Field | Pinned value |
|---|---|
| OpenAPI | `3.1.0` |
| Lambda Cloud API version | `1.10.0` |
| Bytes | 239,644 |
| SHA-256 | `365488015cf79fda38e1268f44a9e2d4af4fe2794ad3c6878c78a7e1f98caded` |
| Operation | `listSSHKeys` |
| Method/path | `GET /api/v1/ssh-keys` |
| Query parameters | none |

The HTTP-200 envelope is exactly an object with required array `data`; the envelope
explicitly forbids additive fields. Every `SSHKey` requires string `id`, `name`, and
`public_key`; `name` is 1–64 characters and `public_key` is 1–4,096 characters. The
item schema does not explicitly forbid additive properties. Therefore the Gate L1A
parser rejects envelope additions and missing/type-incompatible authoritative fields,
but accepts item additions while retaining only their key names. It never retains
unknown scalar values outside the ignored raw response.

Any redirect, retry requirement, pagination/continuation field, query, second request,
candidate-name drift, or incompatible schema burns/stops the fresh run without a
follow-up request.

## Fingerprint and match contract

`src/giclab/harness/lambda_ssh_key_fingerprint.py` implements strict in-process
parsers for:

- OpenSSH Ed25519 and RSA public keys;
- RFC4716 SSH2 public-key blocks;
- PKCS8-style `PUBLIC KEY` SubjectPublicKeyInfo for RSA and Ed25519;
- PKCS#1 `RSA PUBLIC KEY` PEM.

The standard fingerprint is `SHA256:` plus unpadded Base64 of SHA-256 over the
canonical SSH public-key wire blob. Text-body hashes are never substituted. The
parser rejects private-key labels, malformed/canonicality violations, unsupported
algorithms, multiple keys, trailing data, and ambiguous evidence. Exact account rows
collapse only when `id`, `name`, and `public_key` are identical; multiplicity remains
private. A repeated name with different material and a raw ID with conflicting
metadata hard-fail. Raw IDs receive only inventory-local aliases.

`src/giclab/harness/lambda_ssh_key_match.py` resolves the production home from the
passwd database for the current UID, holds its exact `.ssh` child, and opens only
single-link current-user regular files ending in `.pub`, with no-follow open and
pre-open identity revalidation. Its injected home argument is fixture-only and still
selects only that fixture home's `.ssh` child. A same-stem non-`.pub` object is never
opened; only existence, owner, mode, and regular-file metadata are recorded privately.
Exact paths and fingerprints remain ignored/private. Public results use only opaque
local aliases or basenames and the four closed states `unique_match`, `no_match`,
`ambiguous_match`, or `invalid_evidence`.

A recommendation is emitted only when exactly one account record has a one-to-one
local fingerprint match and its same-stem private counterpart is a current-user
regular file by metadata. Even then the state is
`unique-match-awaiting-user-approval`; no key use or Gate L2 authority follows.

## Fresh plan and evidence boundary

- Plan: `PLAN-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1`
- Run: `RUN-T07-L1A-LAMBDA-SSH-KEY-FINGERPRINT-0001`
- Future authorization placeholder:
  `AUTH-T07-GATE-L1A-LAMBDA-SSH-KEY-FINGERPRINT-V1-PENDING`
- Plan path:
  `containers/sira-smoke/lambda/gate-l1a-ssh-key-fingerprint-plan-v1.json`
- Plan bytes: 12,448
- Plan SHA-256:
  `23b29823b8daf94cfb463b275149ed562656c735955a4f449b8703334de531bc`
- Reviewed implementation commit:
  `2a0bea7e34e7a6838e62bb1ac5c94686335ff23a`

The new append-only ledger is created before secret access under the fresh run root,
reserves all 49,152 bytes before send, fsyncs intent and send-started events, permits
one request ordinal, and cannot be reused. The private raw response, private evidence
manifest, sanitized match report, and private seal use exclusive no-follow writes,
file/directory fsync, readback, and mode `0400`.

`src/giclab/harness/lambda_ssh_key_executor.py` is the plan-bound, shell-free
supervisor. The exact repository-owned wrapper loads the hash-bound `src/` tree even
when the reviewed virtual environment contains an older installed package. The
supervisor composes the exact V3 in-process transport, new ledger, parser, matcher,
evidence writer, a secret-free 150-second hard watchdog, and
`src/giclab/harness/lambda_ssh_key_archive.py`. The archive driver is prepared before
secret access, stages the four sealed evidence sources through held UTDM descriptors,
then accepts only a validated terminal ledger before adding the ledger, copy record,
and seal and atomically publishing seven files. The request ledger's `archive_passed`
event attests only staging. A separate exclusive, append-only, fsync-backed
`archive-finalization.jsonl` is created before finalization and is the sole authority
for complete archive evidence. It records an exact passed or failed state after final
source/destination reread, SHA-256 equality, retained-floor validation, and atomic
publication; a ledger alone is never eligible. Fake end-to-end tests prove the
composed success, typed-failure, unknown-after-send, and finalization-failure paths,
while concrete temporary-volume tests exercise the actual archive driver. They make
no live request and inspect no real home.

Every raw/private/report/seal component and the complete aggregate are encoded,
schema/semantic validated, sized, and hashed before the first evidence file is
created. The sanitized validator independently rejects a recommendation unless the
same report contains exactly one corresponding `unique_match`, a present same-stem
counterpart, and the explicit awaiting-user-approval state.

Private ignored/sealed evidence may contain the raw response, raw provider key IDs,
account public-key bodies, exact fingerprints, exact local `.pub` paths, and the raw
matching map. Repository/public output may contain only the three already-public key
names, opaque aliases, match states, same-stem-presence booleans, the false
private-read flag, and a unique recommendation awaiting approval.

The approved archive remains
`/Volumes/Macintosh HD - Data/GIC-Lab/t07/sealed-artifacts`, bound to APFS UUID
`8478609D-FA37-4ED5-875D-47AE912B9151` and physical-store UUID
`7904A6F1-F483-4ED7-9E34-BFECAB31C63E`. Future execution must repeat the held
no-follow UTDM identity checks, prohibit internal fallback, copy one way, verify every
source/destination SHA-256, fsync, atomically finalize, and retain the local source.

## Decision and blockers

Gate L1.4 ends at **design complete; Gate L1A unauthorized**. Gate L2 remains
`inventory-evidence-insufficient` until a separately authorized Gate L1A completes
with valid sealed evidence.

After Gate L1A, Gate L2 still requires:

1. exactly one user-approved existing account key after a unique match, or a separate
   user choice if the result is no-match/ambiguous/invalid;
2. exact type, region, and image-alias selection after fresh price/capacity/image and
   zero-running-instance revalidation;
3. the global-firewall option, exact workspace-dependency attestation, and exact
   current public IPv4 `/32` unless a separately approved no-inbound design is used;
4. a separately authorized same-region TCP/22 ruleset lifecycle or reviewed
   supersession of D-020;
5. independent host-key trust;
6. exact launch, containment, incident, evidence, cleanup, provider-terminal, and
   firewall-restore contracts under a new clean-commit-bound Gate L2 plan and
   current-turn authorization.

No Lambda/account/model API, real-secret access, cloud mutation, paid compute, SSH,
private-key read, browser, container, SiRA, or scientific execution occurred.
