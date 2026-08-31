# T09 V15 command-manifest hash consistency repair ledger

Status: **in-progress**. Category 1 implementation/package-consistency repair only.

```text
operator_attested_model: gpt-5.6-sol
operator_attested_effort: max
runtime_model_introspection_required: false
implementation_delegated: false
```

Implementation, review, testing, repository writes, Git operations, and scientific
decisions are performed directly. No subagent, model, thread, or task is delegated.
ChatGPT exact-head review remains external and required.

## Source and target contract

The governing source is the operator's T09 V15 command-manifest consistency repair
contract submitted on 2026-08-30. The immutable destination base is merge
`bce89afa79a120f7f5acb22fb20512ec9581f7a5`, tree
`0b663b7b35608d8481e4381dcd530c0966adb288`, with ordered parents
`2db290530c36c92562fe6b25f7a4f6aafd77b548` and
`21385c10ec16d30fb73dd6ae6abf0df20fdc6a09`.

Target: one explicit UTF-8 JSON argv hash contract; immutable final argv construction
before hashing; deterministic generator output; independent stored/fresh self-hash and
full-document validation; an exact offline preflight regression; preserved V11-V14
bytes; unchanged V15 science and `AUTONOMOUS-0008` identities; and one unmerged draft
PR for independent exact-head review.

In scope: renderer, argv hash helper, generator, preflight validation, repository
validation, offline fixtures/regressions, deterministic V15 package regeneration,
package bindings, the sanitized stopped disposition, and handoff documentation.

Out of scope: V16, live dotenv or secret access, authenticated metadata/model requests,
Lambda or other cloud requests/mutations, Docker, browser, SiRA/FanOutQA condition or
scientific execution, authorization overlays, run roots, frozen manifests, task
attempts, empirical interpretation, merge, and auto-merge.

## Exact-base evidence

- Original checkout: clean at the operator-specified repository checkout.
- Repair worktree: the requested isolated T09 V15 repair worktree.
- Starting branch: `codex/t09-v15-command-manifest-hash-consistency`.
- Starting commit/tree: `bce89afa79a120f7f5acb22fb20512ec9581f7a5` /
  `0b663b7b35608d8481e4381dcd530c0966adb288`.
- Raw full pytest: 1,805 passed, 24 failed, five skipped across 1,834 nodes. Failures
  are inherited baseline/environmental nodes, including ignored historical evidence.
- Exact base-to-base parity: passed; base 1,802 passed / 27 failed and workspace head
  1,806 passed / 23 failed across 1,829 compared nodes, five private nodes symmetrically
  deselected, zero newly failing, zero missing, and zero invalid transitions.

## Root cause and causal sequence

Classification: **F = A + D + E**. B and C are false.

1. Commit `19c768f318f7e57f5a9a33beca5311f0534dc1b9` generated V15 through
   `t09_freeze_commands.render()` -> `render_command_manifest()` ->
   `canonical_sha256(final argv list)`. All four stored hashes exactly matched their
   stored argv arrays.
2. Commit `b35b6f34b4915007b6ebab44994f97e41ff3c495` rebound the package by
   replacing the execution-contract SHA-256 embedded after
   `--gate-pilot-contract-sha256` in all four already-generated argv arrays. It retained
   the four hashes from `19c768f3…`; this is the first inconsistent commit.
3. Commits `e434948d94f04e26d7efed94607860b1ec335bb6`,
   `ee1aa742298194fe8db05399f1b59eb911b75ae0`, and
   `84666d5b821fc102182c8ff946b0715ce6ce25d4` performed further package/ancestor,
   condition, environment, Task-B, and execution-contract rebindings. They updated the
   stored argv contract digest when required but continued to preserve the four original
   `argv_sha256` values.
4. The merged arrays therefore equal a fresh render, and equality surfaces/selectors
   and pair diffs remain valid, but the stored hashes describe the pre-rebind argv.
5. The renderer is not pre-final hashing: it constructs the complete argv and hashes
   that list immediately before returning it. The generator uses that renderer and the
   same canonical JSON hashing function. No tracked rebind generator exists; the
   inconsistent descendant edits bypassed regeneration.
6. Versioned V15 tests checked schemas, byte bindings, selectors, pair-diff validity,
   and false authorization flags, but did not recompute each stored argv hash or compare
   the source-controlled V15 manifests to a fresh render. Other runtime tests propagated
   the stored hash as fixture authority. Only `t09_preflight.py` performed the complete
   stored/fresh manifest comparison, so the offline Category 3 preflight correctly
   failed closed.
7. V11-V14 all use the intended canonical list hash and all sixteen historical stored
   hashes are valid. Their source-controlled files must remain byte-identical.

## Definition of done

| ID | Required outcome | Planned evidence | Status |
| --- | --- | --- | --- |
| HASH-DOD-01 | Preserve the stopped prelive transaction as a sanitized public record with exact zero-live facts and public evidence identities. | JSON schema/shape, bytes/SHA, privacy scan. | not-started |
| HASH-DOD-02 | Establish one canonical argv-only SHA-256 helper that rejects empty, non-string, and NUL-bearing argv. | Helper unit tests and independently computed vectors. | not-started |
| HASH-DOD-03 | Freeze the complete final argv before hashing and prohibit post-hash mutation. | Renderer source review and mutation regressions. | not-started |
| HASH-DOD-04 | Keep generator and renderer on one construction path and generate byte-identically twice. | Direct render/generator equality and byte comparison. | not-started |
| HASH-DOD-05 | Independently validate stored and fresh self-hashes, argv equality, hash equality, and full manifest equality with typed failure classes. | Preflight unit/mutation tests. | not-started |
| HASH-DOD-06 | Make repository/package validation reject argv/hash inconsistency. | `validate_t09_v15_plan` mutation regression and `make validate`. | not-started |
| HASH-DOD-07 | Preserve the exact merged defect and prove arrays equal, four hashes differ, and exact preflight rejects it. | Historical structural fixture/record and regression. | not-started |
| HASH-DOD-08 | Regenerate the source-controlled V15 package only from the canonical generator and rebind every affected descendant. | Generator output comparison and exact file bindings. | not-started |
| HASH-DOD-09 | Preserve V11-V14 bytes and version-bound validation. | Base/head Git blob hashes and historical validators. | not-started |
| HASH-DOD-10 | Preserve V15 science, pair diffs, provider selectors, flags, and `AUTONOMOUS-0008` identities. | Semantic projection, selector/pair tests, false-state/filesystem assertions. | not-started |
| HASH-DOD-11 | Execute the exact privacy-safe offline V15 preflight with zero provider/model requests, browser actions, and secret reads. | Full `t09_preflight.run` fixture regression. | not-started |
| HASH-DOD-12 | Pass focused, static, repository, full, parity, site, diff, and privacy gates with no new failures/skips/xfails. | Exact commands and result counts. | not-started |
| HASH-DOD-13 | Complete direct Sol/max spec-conformance self-review without delegation. | Recorded checklist and findings disposition. | not-started |
| HASH-DOD-14 | Commit core and package descendants separately, push normally, and open/monitor one draft PR without merge or auto-merge. | Commit/tree/remote/PR/Actions identities. | not-started |

## Implementation mapping

- Canonical helper and atomic renderer: HASH-DOD-02, HASH-DOD-03.
- Generator encoding/check surface: HASH-DOD-04, HASH-DOD-08.
- Preflight and repository validators: HASH-DOD-05, HASH-DOD-06, HASH-DOD-11.
- Historical and mutation regressions: HASH-DOD-07, HASH-DOD-09, HASH-DOD-10.
- Stopped disposition and package/docs rebind: HASH-DOD-01, HASH-DOD-08,
  HASH-DOD-10.
- Validation, self-review, commits, draft PR, and Actions: HASH-DOD-12 through
  HASH-DOD-14.

## Progress and decisions

- 2026-08-30: exact repository, base, tree, ordered parents, PR #9 merge/head, branch
  absence, worktree absence, non-materialization, and destination stability checks pass.
- 2026-08-30: exact-base full and parity evidence captured before repository edits.
- 2026-08-30: source/history archaeology identifies the first inconsistent commit and
  rules out renderer pre-final hashing and divergent generator canonicalization.
- 2026-08-30: assembly item enters implementation with HASH-DOD-02 through
  HASH-DOD-07 as the first correctness workstream.
- 2026-08-30: direct core self-review replaces the initial record-derived historical
  oracle with an exact render from the merged-base execution and source Git blobs.
  The canonical helper, immutable renderer, generator guard, typed preflight boundary,
  repository validator, historical reproduction, mutation matrix, and V11-V14 checks
  pass 27 network-free tests; Ruff, strict mypy, and diff checks pass. The stale V15
  package intentionally remains rejected until it is regenerated after the core commit.

## Next permitted phase

Implement the canonical helper and validation boundary, run the smallest correctness
smoke, perform direct self-review, then bind and regenerate V15 against the immutable
core commit. No package descendant or PR step may claim success until every DoD item
is met.
