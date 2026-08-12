# T07 bounded-smoke OpenAI secret-source repair

Status: **complete offline repair; V3 unauthorized and unexecuted**

Date: 2026-08-12

## Starting disposition

The repair began on clean branch `phase-1/sira-smoke-bounded` at
`cac0ff114973a293426c7278fc7a4f6089953c65`. V2 remains exactly 43,198 bytes at
SHA-256 `f0d635783d719d1c5cb5df5351eaf8f6f54e9049da1f2565e4227e66f48ef511`.
Its preflight stopped before creating a local, upload, remote, or external run root;
reading a secret; issuing a Lambda/OpenAI/public-IP request; reaching a user
checkpoint; mutating cloud state; or creating billable work. V2 and every `0002` run
identity are blocked, immutable, and nonreusable.

The previously inspected source is a repository-external, user-owned dotenv file at
the exact approved private location under the user's Documents tree. Metadata and
assignment-name-only inspection established a regular no-follow single-link file,
mode 0644, no group/world write bit, outside this worktree's tracking, and ignored in
the source checkout. It contains exactly one `OPENAI_API_KEY` and one separate
`LAMBDA_API_KEY`, each using the reviewed plain, unquoted, single-line assignment
syntax. No value was read, printed, decoded, hashed, or persisted during this repair.

## Repaired source and channel contract

V3 uses `OPENAI_API_KEY` in that exact privately supplied `.env` as the only OpenAI
credential source. The source path is bound by a domain-separated SHA-256 of the path,
not of any value. `LAMBDA_API_KEY` remains isolated in the local Lambda observer and
cannot enter the remote host, OpenAI metadata child, Docker, or SiRA. The strict
parser:

- opens the absolute source path component by component through held `O_NOFOLLOW`
  descriptors;
- requires a current-user-owned regular single-link file of at most 65,536 bytes that
  is not group/world writable;
- parses ASCII `NAME=value` records in process without shell evaluation,
  interpolation, escaping, quoting, export syntax, multiline values, NUL, or carriage
  returns;
- selects exactly one nonempty `OPENAI_API_KEY` value into a mutable lease and never
  returns an unrelated value;
- rejects missing, duplicate, empty, malformed, or changed-while-held input using a
  closed secret-safe code; and
- zeroes the mutable lease after its single write and never hashes the credential.

The separately plan-bound source schema is
`schemas/t07-bounded-openai-secret-source.schema.json`, 4,411 bytes, SHA-256
`38cf99ee79532dbc91c85aa8b97868c26351d12c9acc606f315f77257e8d66d4`.
The V3 plan binds 34 tracked implementation artifacts and that local-only schema
identity separately. It retains the V2 36-member tracked upload-archive cap because
the source schema is not needed by the remote runtime. The plan explicitly records no
provider fallback, no complete `.env` upload, and no user-created `SIRA_API_KEY` file.

## One-run delivery and release ordering

The safe order is fixed and fail-closed:

1. bind the one exact instance and open Cloud IDE/Jupyter;
2. create and qualify `/home/ubuntu/.config/giclab` as an exact current-user-owned
   mode-0700 canonical path, with no symlinked hierarchy and with the final secret-file
   target both nonexistent and non-symlink;
3. automatically materialize one fresh local mode-0600 filtered file from the
   selected in-memory `OPENAI_API_KEY` value;
4. upload only that file plus the non-release runtime inputs;
5. qualify the remote file as a regular, non-symlink, current-user-owned exact
   mode-0600 file;
6. durably commit the upload outcome and destroy the exact local device/inode; then
7. and only then issue, upload, and attest the single-use bootstrap release.

The local temporary file is fixed at
`artifacts/t07/bounded-upload/RUN-T07-BOUNDED-HOST-0003/t07-bounded-openai-provider-key`.
It is untracked and excluded from both the 36-member repository archive and every
evidence archive. Its identity receipt binds the execution commit, plan,
authorization, private binding, source attempt, and exact device/inode without
retaining a credential derivative.

Cleanup overwrites, fsyncs, unlinks, fsyncs the parent, and verifies absence. The
hash-first cleanup capability remains available after authorization expiry or
unrelated repository drift. A definite upload failure uses the typed
`definitely-not-uploaded` abort cleanup. An ambiguous upload or failed remote
permission qualification uses the conservative `unknown-or-permissions-unqualified`
abort cleanup and requires credential rotation. Neither abort path permits bootstrap
release. Receipt-write failure, path replacement, or unverified destruction remains a
typed security incident rather than being rewritten as `not_materialized`.

After the release, the remote bootstrap revalidates the exact held file descriptor,
including current-user ownership, exact mode 0600, and the same closed single-value
byte alphabet as the local parser. The container entrypoint independently enforces the
same contract after Docker resolves the bind mount, closing the path-swap boundary. A
complete or multi-line `.env` is rejected before any provider child. The OpenAI metadata child
receives the provider credential under native name `OPENAI_API_KEY`; the two condition
children receive an ephemeral `SIRA_API_KEY` alias because the pinned SiRA adapter
requires that name. No process receives both names, and `LAMBDA_API_KEY` is rejected
from every remote/container child environment. Remote destruction is attempted on
every success/failure path and must be proven by exact cleanup-receipt validation or
exact terminal/absent proof for the bound instance. Before termination, identity
replacement or an unavailable receipt remains an incident requiring conservative
cleanup. Exact termination may prove remote destruction and clear rotation caused only
by the absent receipt; detected exposure, local cleanup failure, or destruction still
unproven after termination requires manual cleanup and rotation. Missing workload or
accounting evidence remains unresolved regardless.

Every untrusted runtime output is scanned for direct, hex, standard-base64, and
URL-safe-base64 representations before it can be hashed or retained. Semantic
credential-shaped JSON is also rejected. No secret value, secret hash, or derivative
is retained in command receipts, logs, evidence, ZIPs, manifests, or external
archives.

## Preserved contracts

The V2 private security binding is reused because schema `0.3.0` contains no secret
path, filename, assignment, value, or derivative. Both protected upstream seal files
and the restoration payload are verified by exact SHA-256 before parsing. Firewall
and resource contents, external seal, and public alias/hash remain unchanged.

The five locked scientific hashes remain:

| Input | SHA-256 |
|---|---|
| protocol | `5bdf3fdcf2c486883ad74044bd373c1804362c7d9ad8e990f5e10fa1c0f99b4c` |
| config | `f05767de862f3f519f429f5b73baa67043ed96209f3d47db9fd2d084847ec16d` |
| smoke profile | `ab276b9e49256d49f143e252eddf6fe5c447d6f9c11300745b450fb7f1d0e425` |
| reactive condition | `7ca19470e550e48978090c9b7014e047c56d80962e40275b846f589b08bfb018` |
| simulative condition | `68f5f4a4a123620bab039ba7bc6844243cad229ed992df6562bf0d8562874436` |

V3's `scientific_lock` and complete `limits` objects equal V2 exactly. The order
remains reactive then simulative, every role uses `gpt-4o-2024-11-20`, condition
attempts remain one each with zero retry, and interpretation, pilot, and training
remain false.

## Authority boundary

The V3 plan is executable by design but `authorized: false`; all current Lambda,
OpenAI, mutation, paid-compute, Jupyter, container, browser, SiRA, and scientific
permissions are zero/false. This repair performed only local metadata/name
inspection, source edits, dummy-fixture tests, hash calculation, and offline
validation. It did not access a real secret or external endpoint and does not itself
authorize V3.
